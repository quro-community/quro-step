"""Position validation for the mount boundary (§5, §10.4)."""

from __future__ import annotations

from ..model.failure import MountFailure, MountFailureKind
from ..model.position import PathSegment, SemanticPosition


def validate_position(position: SemanticPosition) -> "MountFailure | None":
    """Return a ``MountFailure`` if the Position is malformed, else ``None``.

    Validation is purely structural: it never resolves the Position against a
    plan and never selects a substitute (Law M2).
    """
    if not isinstance(position, SemanticPosition):
        return MountFailure(
            kind=MountFailureKind.INVALID_POSITION,
            position=None,
            detail=f"expected SemanticPosition, got {type(position).__name__}",
        )
    if not position.branch.name:
        return MountFailure(
            kind=MountFailureKind.INVALID_POSITION,
            position=position,
            detail="branch identity must not be empty",
        )
    for index, segment in enumerate(position.path):
        if not isinstance(segment, PathSegment):
            return MountFailure(
                kind=MountFailureKind.INVALID_POSITION,
                position=position,
                detail=f"path segment {index} is not a PathSegment",
            )
        if not segment.unit.name:
            return MountFailure(
                kind=MountFailureKind.INVALID_POSITION,
                position=position,
                detail=f"path segment {index} has an empty UnitId",
            )
    return None


__all__ = ["validate_position"]
