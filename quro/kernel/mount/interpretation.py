"""Interpretation resolution and the ``pinned`` verification gate (E6, E8, E9).

This is the *only* place the Kernel touches an interpretation, and it does
exactly three things:

1. **resolution (E6)** — decide *which* declared reference to resolve, then ask
   the domain resolver to resolve it. The Kernel never interprets identity as
   meaning, and never falls back to an ambient default when nothing was
   declared: an unresolved reference is ``MountFailure(InterpretationRequired)``.
   The resolution order is a declared chain, not a per-implementation default
   (**G3**, ``INTERPRETATION_RESOLUTION_CHAIN``).
2. **verification (E9)** — if the addressed Checkpoint declares
   ``stabilityContract = pinned``, ask the domain registry for the fingerprint of
   what it resolved and compare. A mismatch is
   ``MountFailure(InterpretationDrift)``, never a silent pass.
3. nothing else. Under ``nominal`` (the default, E8) no check occurs and none
   may be implied: the claim is *absent*, not accidentally true.

Law E12's boundary is load-bearing here: a fingerprint verifies exactly what it
was computed over, never semantic equivalence. Law E13's boundary is enforced by
absence: there is no equivalence operator to call.

**G1** (Closure 0) names the boundary between E6's *additive* promise and E6a's
*must refuse* requirement. A continuity that declares nothing is either a legacy
single-reading domain (``"legacy-exempt"`` → no identity) or a domain that must
declare (``"must-declare"`` → explicit refusal). The classification is a declared
field on the continuity; ``None`` preserves the pre-G1 heuristic, now demoted to
*the implementation of the default* rather than the contract itself.
"""

from __future__ import annotations

from typing import Any

from ..model.checkpoint import Checkpoint
from ..model.failure import MountFailure, MountFailureKind
from ..model.interpretation import (
    LEGACY_EXEMPT,
    MUST_DECLARE,
    CrossDomainInterpretation,
    Fingerprint,
    InterpretationIdentity,
    UnknownInterpretation,
)
from ..model.position import SemanticPosition
from ..model.result import Err, Ok, Result

#: G3 — the *declared* resolution order for an interpretation. The Kernel
#: consults these sources in order and refuses explicitly when none answers; an
#: interior or root Position resolves through this same chain (falling to the
#: continuity-wide default, then to refusal), never through an undocumented
#: per-implementation default.
INTERPRETATION_RESOLUTION_CHAIN: "tuple[str, ...]" = (
    "mount-argument",
    "declared-checkpoint",
    "continuity-default",
    "refuse",
)


def resolve_interpretation(
    position: SemanticPosition,
    continuity: Any,
    interpretation: "InterpretationIdentity | str | None",
) -> "Result[InterpretationIdentity, MountFailure]":
    """Choose the declared reference to resolve, or refuse explicitly (E6a).

    Resolution order (declared — **G3**, ``INTERPRETATION_RESOLUTION_CHAIN``)::

        1. the identity passed to mount
        2. the identity declared on the Checkpoint at this Position
        3. the continuity-wide declared default
        4. MountFailure(InterpretationRequired) — never an ambient fallback

    **G1** decides what step 4 means for a continuity that declares *nothing*: a
    ``"legacy-exempt"`` continuity resolves to *no* identity (the single-reading
    legacy case — never a fabricated one); a ``"must-declare"`` continuity is
    refused explicitly. An unclassified continuity keeps the pre-G1 heuristic,
    which is exempt exactly when it names no domain and carries no Checkpoint.
    """
    if interpretation is not None:
        return Ok(InterpretationIdentity.of(interpretation))

    declared = _declared_interpretation(position, continuity)
    if declared is not None:
        return Ok(declared)

    requirement = getattr(continuity, "interpretation_requirement", None)
    if requirement == MUST_DECLARE:
        # G1 — the domain has declared that an undeclared reading is a refusal;
        # the heuristic exemption is *not* consulted even where it would exempt.
        return Err(MountFailure.interpretation_required(position))
    if requirement == LEGACY_EXEMPT:
        # G1 — the domain has declared the legacy single-reading case: no
        # identity, never a fabricated one.
        return Ok(None)  # type: ignore[return-value]
    # Default: preserve the pre-G1 behaviour exactly. The heuristic below is now
    # explicitly the *implementation of the default*, not the contract.
    if _is_legacy_exempt(continuity):
        return Ok(None)  # type: ignore[return-value]
    return Err(MountFailure.interpretation_required(position))


def _declared_interpretation(
    position: SemanticPosition, continuity: Any
) -> "InterpretationIdentity | None":
    """Steps 2–3 of the declared chain, in order, or ``None`` if neither answers."""
    declared = getattr(continuity, "declared_interpretation_at", None)
    if declared is not None:
        identity = declared(position)
        if identity is not None:
            return InterpretationIdentity.of(identity)
        return None
    default = getattr(continuity, "default_interpretation", None)
    if default is not None:
        # A continuity-shaped object without the query helper still answers the
        # one question that matters: what is declared here?
        return InterpretationIdentity.of(default)
    return None


def _is_legacy_exempt(continuity: Any) -> bool:
    """The pre-G1 default: exempt iff the continuity names no domain and no
    Checkpoint (i.e. it declares no interpretation environment at all).

    This is *not* the contract any more — it is the implementation of the
    ``None`` default. A continuity that wants the other reading declares it
    explicitly via ``interpretation_requirement`` (G1).
    """
    return getattr(continuity, "domain", None) is None and not _declares_any(continuity)


def _declares_any(continuity: Any) -> bool:
    getter = getattr(continuity, "all_checkpoints", None)
    if getter is None:
        return False
    try:
        return bool(getter())
    except Exception:  # boundary: an unanswerable Continuity declares nothing
        return False


def check_stability(
    position: SemanticPosition,
    continuity: Any,
    identity: "InterpretationIdentity | None",
    resolved: Any,
) -> "Result[None, MountFailure]":
    """Apply the addressed Checkpoint's stability contract (E9).

    ``nominal`` (or no Checkpoint at all) is always satisfied — this function
    does not even look at the fingerprint, because no claim was made. ``pinned``
    is satisfied iff the domain-computed fingerprint matches the declared one;
    a mismatch, or a registry that cannot produce a fingerprint for a pinned
    contract, is an explicit ``InterpretationDrift``.
    """
    checkpoint_at = getattr(continuity, "checkpoint_at", None)
    if checkpoint_at is None:
        return Ok(None)
    try:
        checkpoint: "Checkpoint | None" = checkpoint_at(position)
    except Exception:  # boundary: report, do not propagate
        return Ok(None)

    if checkpoint is None or not checkpoint.is_pinned:
        # E8 — nominal carries no stability claim, so nothing can be violated.
        return Ok(None)

    expected = checkpoint.pinned_fingerprint
    actual = _fingerprint_of(continuity, checkpoint, identity, resolved)
    if actual is None or actual != expected:
        return Err(
            MountFailure.interpretation_drift(
                position=position,
                expected=expected,
                actual=actual if actual is not None else Fingerprint("<unavailable>"),
            )
        )
    return Ok(None)


def _fingerprint_of(
    continuity: Any,
    checkpoint: Checkpoint,
    identity: "InterpretationIdentity | None",
    resolved: Any,
) -> "Fingerprint | None":
    """Ask the *domain* for the fingerprint of what it resolved.

    The Kernel never computes a fingerprint and never defines its coverage
    (E12): it only compares the value the registry produced against the value
    the Checkpoint declared. A missing ``Fingerprint`` is reported as
    unavailable rather than treated as "no claim" — under ``pinned`` an
    unverifiable contract is a failure, not a pass.
    """
    registry = getattr(continuity, "fingerprint_of", None)
    if registry is None:
        return None
    try:
        value = registry(identity, resolved, checkpoint)
    except Exception:  # boundary: an unanswerable registry cannot verify
        return None
    if value is None:
        return None
    return value if isinstance(value, Fingerprint) else Fingerprint.of(value)


__all__ = ["check_stability", "resolve_interpretation"]
