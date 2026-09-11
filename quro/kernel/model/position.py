"""SemanticPosition — semantic execution identity (design doc §5).

``SemanticPosition`` answers *where is execution semantically located?* It is
not a runtime pointer, and it must never depend on a filesystem path,
conversation ID, LLM session, prompt position or physical storage layout.

Canonical shape (root → leaf; ``[]`` = root)::

    PathSegment       = { unit: UnitId, instance: InstanceId }
    SemanticPosition  = { path: PathSegment[], branch: BranchId }
"""

from __future__ import annotations

from dataclasses import dataclass

from .ids import DEFAULT_BRANCH, BranchId, InstanceId, UnitId


@dataclass(frozen=True)
class PathSegment:
    """One addressed child occurrence within its parent composite."""

    unit: UnitId
    instance: InstanceId

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.unit}{self.instance}"

    @classmethod
    def of(
        cls,
        unit: "str | UnitId",
        instance: "int | InstanceId | None" = None,
    ) -> "PathSegment":
        return cls(UnitId.of(unit), InstanceId.of(0 if instance is None else instance))


@dataclass(frozen=True)
class SemanticPosition:
    """Semantic execution identity: ``(path, branch)``."""

    path: "tuple[PathSegment, ...]" = ()
    branch: BranchId = DEFAULT_BRANCH

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", tuple(self.path))
        object.__setattr__(self, "branch", BranchId.of(self.branch))

    # -- construction -----------------------------------------------------
    @classmethod
    def root(cls, branch: BranchId = DEFAULT_BRANCH) -> "SemanticPosition":
        return cls(path=(), branch=branch)

    def child(
        self,
        unit: "str | UnitId",
        instance: "int | InstanceId" = 0,
        *,
        segment: "PathSegment | None" = None,
    ) -> "SemanticPosition":
        """Append one segment (root → leaf direction)."""
        seg = segment if segment is not None else PathSegment.of(unit, instance)
        return SemanticPosition(path=self.path + (seg,), branch=self.branch)

    def with_branch(self, branch: "str | BranchId") -> "SemanticPosition":
        return SemanticPosition(path=self.path, branch=BranchId.of(branch))

    # -- inspection -------------------------------------------------------
    @property
    def is_root(self) -> bool:
        return not self.path

    @property
    def depth(self) -> int:
        return len(self.path)

    @property
    def leaf_segment(self) -> "PathSegment | None":
        return self.path[-1] if self.path else None

    @property
    def occurrence(self) -> "InstanceId | None":
        """The occurrence identity of the addressed leaf, if any."""
        return self.path[-1].instance if self.path else None

    def unit_ids(self) -> "tuple[UnitId, ...]":
        return tuple(seg.unit for seg in self.path)

    def parent(self) -> "SemanticPosition | None":
        if not self.path:
            return None
        return SemanticPosition(path=self.path[:-1], branch=self.branch)

    def is_prefix_of(self, other: "SemanticPosition") -> bool:
        """Structural ancestry check; branch identity must match."""
        return (
            self.branch == other.branch
            and len(self.path) <= len(other.path)
            and other.path[: len(self.path)] == self.path
        )

    def ancestors(self) -> "tuple[SemanticPosition, ...]":
        """Root → self, inclusive."""
        return tuple(
            SemanticPosition(path=self.path[: i + 1], branch=self.branch)
            for i in range(len(self.path))
        )

    def __str__(self) -> str:
        rendered = "/".join(str(seg) for seg in self.path) or "<root>"
        return f"{self.branch.name}:{rendered}"


__all__ = ["PathSegment", "SemanticPosition"]
