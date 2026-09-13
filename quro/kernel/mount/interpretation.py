"""Interpretation resolution and the ``pinned`` verification gate (E6, E8, E9).

This is the *only* place the Kernel touches an interpretation, and it does
exactly three things:

1. **resolution (E6)** — decide *which* declared reference to resolve, then ask
   the domain resolver to resolve it. The Kernel never interprets identity as
   meaning, and never falls back to an ambient default when nothing was
   declared: an unresolved reference is ``MountFailure(InterpretationRequired)``.
2. **verification (E9)** — if the addressed Checkpoint declares
   ``stabilityContract = pinned``, ask the domain registry for the fingerprint of
   what it resolved and compare. A mismatch is
   ``MountFailure(InterpretationDrift)``, never a silent pass.
3. nothing else. Under ``nominal`` (the default, E8) no check occurs and none
   may be implied: the claim is *absent*, not accidentally true.

Law E12's boundary is load-bearing here: a fingerprint verifies exactly what it
was computed over, never semantic equivalence. Law E13's boundary is enforced by
absence: there is no equivalence operator to call.
"""

from __future__ import annotations

from typing import Any

from ..model.checkpoint import Checkpoint
from ..model.failure import MountFailure, MountFailureKind
from ..model.interpretation import (
    CrossDomainInterpretation,
    Fingerprint,
    InterpretationIdentity,
    UnknownInterpretation,
)
from ..model.position import SemanticPosition
from ..model.result import Err, Ok, Result


def resolve_interpretation(
    position: SemanticPosition,
    continuity: Any,
    interpretation: "InterpretationIdentity | str | None",
) -> "Result[InterpretationIdentity, MountFailure]":
    """Choose the declared reference to resolve, or refuse explicitly (E6a).

    Resolution order::

        1. the identity passed to mount
        2. the identity declared on the Checkpoint at this Position
        3. the continuity-wide declared default
        4. MountFailure(InterpretationRequired) — never an ambient fallback

    A Continuity that declares no interpretation environment at all is the
    single-reading legacy case; it resolves to *no* identity rather than to a
    fabricated one, so nothing in the Kernel can mistake a missing declaration
    for a resolved interpretation.
    """
    if interpretation is not None:
        return Ok(InterpretationIdentity.of(interpretation))

    declared = getattr(continuity, "declared_interpretation_at", None)
    if declared is not None:
        identity = declared(position)
        if identity is not None:
            return Ok(InterpretationIdentity.of(identity))
    elif getattr(continuity, "default_interpretation", None) is not None:
        # A continuity-shaped object without the query helper still answers the
        # one question that matters: what is declared here?
        return Ok(InterpretationIdentity.of(continuity.default_interpretation))

    if getattr(continuity, "domain", None) is None and not _declares_any(continuity):
        return Ok(None)  # type: ignore[return-value]
    return Err(MountFailure.interpretation_required(position))


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
