"""Mounter — the materialization/reconstruction boundary (design doc §10).

``mount`` means::

    declared Position + declared Continuity -> executable state

It does **not** mean choose another Position, replan, steer or fork. Position
establishment belongs to the enclosing Control mechanism.
"""

from __future__ import annotations

from typing import Any

from ..model.failure import MountFailure, MountFailureKind
from ..model.position import SemanticPosition
from ..model.result import Err, Ok, Result
from ..model.state import ExecutionState, StateDomainPayload
from .resolver import resolve_unit_at
from .validation import validate_position


def _project(
    continuity: Any, position: SemanticPosition
) -> "tuple[StateDomainPayload | None, str | None]":
    """Project Continuity at a Position, reporting domain misbehavior.

    A domain ``project`` that raises or returns something unmappable is an
    ordinary boundary failure, not a crash: ``mount`` must stay a total function
    returning ``Result`` (design doc §10.2, §37).
    """
    projector = getattr(continuity, "project", None)
    if projector is None:
        return StateDomainPayload(), None
    try:
        payload = projector(position)
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


class Mounter:
    """Reference ``mount`` implementation (Laws M1–M7)."""

    def mount(
        self, position: SemanticPosition, continuity: Any
    ) -> "Result[ExecutionState, MountFailure]":
        invalid = validate_position(position)
        if invalid is not None:
            return Err(invalid)

        resolved = resolve_unit_at(position, continuity)
        if resolved.is_err():
            return Err(resolved.error)

        unit = resolved.value
        payload, projection_failure = _project(continuity, position)
        if projection_failure is not None:
            return Err(
                MountFailure(
                    kind=MountFailureKind.INVALID_POSITION,
                    position=position,
                    detail=projection_failure,
                )
            )

        state = ExecutionState(
            position=position,
            unit=unit,
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
