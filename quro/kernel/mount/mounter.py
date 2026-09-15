"""Mounter — the materialization/reconstruction boundary (design doc §10).

``mount`` means::

    declared Position + declared Continuity -> executable state

It does **not** mean choose another Position, replan, steer or fork. Position
establishment belongs to the enclosing Control mechanism.
"""

from __future__ import annotations

from typing import Any

from ..model.failure import MountFailure, MountFailureKind
from ..model.interpretation import (
    CrossDomainInterpretation,
    InterpretationIdentity,
    UnknownInterpretation,
)
from ..model.position import SemanticPosition
from ..model.result import Err, Ok, Result
from ..model.state import ExecutionState, StateDomainPayload
from .interpretation import check_stability, resolve_interpretation
from .structural import resolve_unit_at
from .validation import validate_position

#: G6 — the attribute a domain-owned ``project`` sets to *declare* how it is
#: parameterised. When present it is the contract: the Kernel calls the
#: projection exactly as declared. When absent, the Kernel falls back to
#: signature sniffing — the documented legacy path, never the contract.
DECLARED_PARAMETERS_ATTR = "declared_parameters"

#: G6 — the closed vocabulary of parameters a ``project`` may declare.
DECLARABLE_PARAMETERS = ("position", "interpretation", "resolved")


def _project_payload(
    continuity: Any,
    position: SemanticPosition,
    identity: "InterpretationIdentity | None" = None,
    resolved: Any = None,
) -> "tuple[StateDomainPayload | None, str | None]":
    """Project Continuity at a Position, reporting domain misbehavior.

    A domain ``project`` that raises or returns something unmappable is an
    ordinary boundary failure, not a crash: ``mount`` must stay a total function
    returning ``Result`` (design doc §10.2, §37).

    The declared interpretation is passed when the Continuity's ``project``
    accepts it, so a domain can honour the distinguishing power of the
    interpretation axis — while a Continuity whose ``project`` takes only the
    Position keeps working unchanged (E6 is additive).
    """
    project = getattr(continuity, "project", None)
    if project is None:
        return StateDomainPayload(), None
    try:
        if identity is None:
            payload = project(position)
        else:
            payload = _project_with_declaration(
                project, position, identity, resolved=resolved
            )
    except Exception as exc:  # boundary: report, do not propagate
        return None, f"continuity.project raised: {exc!r}"
    if payload is None:
        return StateDomainPayload(), None
    if isinstance(payload, StateDomainPayload):
        return payload, None
    try:
        return StateDomainPayload(data=dict(payload)), None
    except Exception as exc:  # boundary: report, do not propagate
        return None, f"continuity.project returned an unmappable payload: {exc!r}"


def _project_with_declaration(
    project: Any,
    position: SemanticPosition,
    identity: InterpretationIdentity,
    *,
    resolved: Any = None,
) -> Any:
    """Call a ``project`` that declares how it is parameterised (**G6**).

    A domain-owned projection may *declare* which parameters it accepts by
    setting ``declared_parameters`` on the callable — a tuple (or
    comma-separated string) drawn from ``("position", "interpretation",
    "resolved")``. When a declaration is present it **is** the contract: the
    Kernel calls the projection exactly as declared and never inspects the
    signature.

    When nothing is declared the Kernel falls back to signature sniffing —
    the documented **legacy path**, not the contract. This keeps E6 additive for
    existing single-parameter domains while giving every new domain a way to
    state its intent rather than have it inferred.
    """
    declared = _declared_call_parameters(project)
    if declared is not None:
        provided = {"position": position, "interpretation": identity, "resolved": resolved}
        positional = [provided[name] for name in declared if name == "position"]
        keywords = {name: provided[name] for name in declared if name != "position"}
        return project(*positional, **keywords)
    return _sniff_projected(project, position, identity, resolved)


def _sniff_projected(
    project: Any,
    position: SemanticPosition,
    identity: InterpretationIdentity,
    resolved: Any = None,
) -> Any:
    """Legacy fallback (pre-G6): infer the shape from the signature.

    Retained so an undeclared ``project`` keeps working unchanged. A domain that
    wants a *guaranteed* call shape declares it (see
    ``_declared_call_parameters``); sniffing is never the documented
    contract.
    """
    import inspect

    try:
        signature = inspect.signature(project)
    except (TypeError, ValueError):  # builtins / opaque callables
        return project(position)
    parameters = signature.parameters
    positional = [
        parameter
        for parameter in parameters.values()
        if parameter.kind
        in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
    ]
    if len(positional) >= 3:
        return project(position, identity, resolved)
    if len(positional) == 2:
        return project(position, identity)
    if "resolved" in parameters:
        return project(position, interpretation=identity, resolved=resolved)
    if "interpretation" in parameters:
        return project(position, interpretation=identity)
    return project(position)


def _declared_call_parameters(project: Any) -> "tuple[str, ...] | None":
    """The declared projection parameters, or ``None`` when none is declared.

    A declaration naming anything outside the closed vocabulary is a domain
    error and is reported, never silently ignored or downgraded to inference —
    the contract *is* the declaration (G6).
    """
    declared = getattr(project, DECLARED_PARAMETERS_ATTR, None)
    if declared is None:
        return None
    if callable(declared):
        declared = declared()
    if isinstance(declared, str):
        declared = tuple(part.strip() for part in declared.split(",") if part.strip())
    try:
        names = tuple(str(name) for name in declared)
    except TypeError as exc:
        raise TypeError(
            f"{DECLARED_PARAMETERS_ATTR} must name parameters, not {declared!r}"
        ) from exc
    unknown = [name for name in names if name not in DECLARABLE_PARAMETERS]
    if unknown:
        raise ValueError(
            f"{DECLARED_PARAMETERS_ATTR} names unknown parameters {unknown}; "
            f"expected a subset of {DECLARABLE_PARAMETERS}"
        )
    return names


def _resolve_identity(
    continuity: Any, identity: "InterpretationIdentity | None"
) -> "tuple[Any, MountFailureKind | None]":
    """Resolve the declared reference through the domain's resolver (E6c).

    Returns ``(resolved, None)`` on success — including the structural-only case
    where nothing was declared or no resolver exists. A resolver that refuses
    (unknown or cross-domain) maps to the matching ``MountFailureKind``: the
    Kernel reports *why*, and never substitutes.
    """
    if identity is None:
        return None, None
    resolve = getattr(continuity, "resolve_interpretation", None)
    if resolve is None:
        return None, None
    try:
        return resolve(identity), None
    except UnknownInterpretation:
        return None, MountFailureKind.UNKNOWN_INTERPRETATION
    except CrossDomainInterpretation:
        return None, MountFailureKind.CROSS_DOMAIN_INTERPRETATION
    except Exception:
        return None, MountFailureKind.UNKNOWN_INTERPRETATION


def resolved_interpretation(continuity: Any, identity: "InterpretationIdentity | None") -> Any:
    """The domain value behind a mounted identity, if one is registered.

    Advisory: a convenience for callers that want the resolved value without
    calling ``mount``. The Kernel itself never inspects, interprets or compares
    it (E12/E13) — it only ever travels back to the *domain's* own fingerprint
    capability.
    """
    getter = getattr(continuity, "resolved_interpretation", None)
    if getter is None or identity is None:
        return None
    try:
        return getter(identity)
    except Exception:  # boundary: a value that cannot be fetched is unavailable
        return None


class Mounter:
    """Reference ``mount`` implementation (Laws M1–M7, E6, E8, E9)."""

    def mount(
        self,
        position: SemanticPosition,
        continuity: Any,
        interpretation: "InterpretationIdentity | str | None" = None,
    ) -> "Result[ExecutionState, MountFailure]":
        invalid = validate_position(position)
        if invalid is not None:
            return Err(invalid)

        # E6 — interpretation is a named, explicit third input, never ambient.
        declared = resolve_interpretation(position, continuity, interpretation)
        if declared.is_err():
            return Err(declared.error)
        identity = declared.value

        structural = resolve_unit_at(position, continuity)
        if structural.is_err():
            return Err(structural.error)

        unit = structural.value

        # E6c — *resolve* the declared reference before projecting or verifying.
        # A reference nobody can resolve is a refusal, never a compatible-looking
        # default (the interpretation-axis analogue of Lemma 5). A continuity
        # that declares no resolver resolves nothing, which is the structural-only
        # case that must keep working unchanged.
        resolved, resolution_failure = _resolve_identity(continuity, identity)
        if resolution_failure is not None:
            return Err(
                MountFailure(
                    kind=resolution_failure,
                    position=position,
                    detail=f"interpretation {identity} could not be resolved",
                )
            )

        payload, projection_failure = _project_payload(
            continuity, position, identity=identity, resolved=resolved
        )
        if projection_failure is not None:
            return Err(
                MountFailure(
                    kind=MountFailureKind.INVALID_POSITION,
                    position=position,
                    detail=projection_failure,
                )
            )

        # E9 — a pinned Checkpoint verifies its fingerprint here, at resolution
        # time, and fails explicitly on drift. Nominal claims nothing.
        verification = check_stability(
            position, continuity, identity, resolved=resolved
        )
        if verification.is_err():
            return Err(verification.error)

        state = ExecutionState(
            position=position,
            unit=unit,
            interpretation=identity,
            domain_payload=payload or StateDomainPayload(),
        )

        # Law M1 — Position Fidelity: the mounted state may not silently change
        # the requested Position. This is a structural guard, not a fixup.
        if state.position != position:
            return Err(
                MountFailure(
                    kind=MountFailureKind.INVALID_POSITION,
                    position=position,
                    detail="mount would violate Position Fidelity",
                )
            )
        return Ok(state)


__all__ = ["Mounter"]
