"""Position resolution against Continuity's branch-associated plan (§8, §10.6).

Resolution is *structural*, not merely data lookup::

    Continuity.resolveUnitAt(P)
        -> plan associated with P.branch
        -> walk P.path
        -> resolve ExecUnit

Semantic requirements enforced here (no more, no less)::

    correct Position
    correct occurrence
    correct branch
    no substitution
    no control selection
"""

from __future__ import annotations

from typing import Any

from ..model.failure import MountFailure, MountFailureKind
from ..model.ids import InstanceId, UnitId
from ..model.unit import ExecUnit
from ..model.position import SemanticPosition
from ..model.result import Err, Ok, Result


def _plan_for(continuity: Any, branch):
    getter = getattr(continuity, "plan_for", None)
    if getter is not None:
        return getter(branch)
    return getattr(continuity, "plan", None)


def _occurrence_known(continuity: Any, branch, unit: UnitId, instance: InstanceId) -> bool:
    """Fail closed: a Continuity that cannot answer occurrence queries cannot
    prove the occurrence exists, and an unprovable occurrence must not be
    silently accepted (Law M2/M4)."""
    checker = getattr(continuity, "occurrence_known", None)
    if checker is None:
        return False
    return bool(checker(branch, unit, instance))


def resolve_unit_at(
    position: SemanticPosition, continuity: Any
) -> "Result[ExecUnit, MountFailure]":
    """Resolve the ExecUnit designated by ``position`` under ``continuity``.

    Never falls back to a nearest/first-child/other-occurrence Position. An
    unresolved Position is an explicit ``MountFailure`` (Law M2 / K4). The
    semantic Position model in the design docs' earlier draft allowed a
    ``currentChildAt(pos) ?? firstChild(unit)`` default; the consolidated v0.2
    architecture forbids that, and this implementation follows v0.2.
    """
    plan = _plan_for(continuity, position.branch)
    if plan is None:
        return Err(
            MountFailure(
                kind=MountFailureKind.UNKNOWN_BRANCH,
                position=position,
                detail=f"no ExecutionPlan is associated with branch {position.branch.name!r}",
            )
        )

    root = plan.root_unit
    if root is None:
        return Err(
            MountFailure(
                kind=MountFailureKind.UNRESOLVED_UNIT,
                position=position,
                detail=f"plan root {str(plan.root)!r} is not defined in the plan",
            )
        )

    current: ExecUnit = root
    for index, segment in enumerate(position.path):
        child = plan.child_of(current, segment.unit) if current.is_composite else None
        if child is None:
            return Err(
                MountFailure(
                    kind=MountFailureKind.UNRESOLVED_UNIT,
                    position=position,
                    detail=(
                        f"path segment {index} ({segment.unit}) is not a declared child "
                        f"of {current.id}"
                    ),
                )
            )
        if not _occurrence_known(
            continuity, position.branch, segment.unit, segment.instance
        ):
            return Err(
                MountFailure(
                    kind=MountFailureKind.UNKNOWN_OCCURRENCE,
                    position=position,
                    detail=(
                        f"occurrence {segment.unit}{segment.instance} is not recorded "
                        f"on branch {position.branch.name!r}"
                    ),
                )
            )
        current = child

    return Ok(current)


__all__ = ["resolve_unit_at"]
