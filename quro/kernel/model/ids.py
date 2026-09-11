"""Stable semantic identities (design doc §4.4, §5.1).

The identity model deliberately separates::

    UnitId     = which unit
    InstanceId = which occurrence
    BranchId   = which lineage

None of these may depend on a filesystem path, conversation ID, LLM session,
prompt position or physical storage layout (§5.1).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class UnitId:
    """Stable identity of a child within its parent composite."""

    name: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name

    @classmethod
    def of(cls, name: "str | UnitId") -> "UnitId":
        return name if isinstance(name, UnitId) else cls(str(name))


@dataclass(frozen=True, order=True)
class InstanceId:
    """Identity of one concrete execution occurrence of a :class:`UnitId`.

    ``InstanceId`` disambiguates repeated visits to the same ``UnitId``
    (loop iteration, retry attempt, Nth Steering cycle). It is an identity
    model, not a retry policy.
    """

    index: int

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("InstanceId.index must be non-negative")

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"#{self.index}"

    @classmethod
    def of(cls, value: "int | InstanceId") -> "InstanceId":
        return value if isinstance(value, InstanceId) else cls(int(value))


@dataclass(frozen=True, order=True)
class BranchId:
    """Identity of the lineage a Position belongs to (§5.3).

    Fork creation is outside Kernel scope, but the field must exist in the core
    Position type so downstream consumers never need a breaking schema change.
    """

    name: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name

    @classmethod
    def of(cls, name: "str | BranchId") -> "BranchId":
        return name if isinstance(name, BranchId) else cls(str(name))


@dataclass(frozen=True, order=True)
class ArtifactId:
    """Stable, storage-independent logical identity of an Artifact (§13.3)."""

    name: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name

    @classmethod
    def of(cls, name: "str | ArtifactId") -> "ArtifactId":
        return name if isinstance(name, ArtifactId) else cls(str(name))


@dataclass(frozen=True)
class StepOccurrence:
    """One concrete execution occurrence of a Step (§4.4)."""

    unit: UnitId
    instance: InstanceId

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.unit}{self.instance}"


DEFAULT_BRANCH = BranchId("main")

__all__ = [
    "ArtifactId",
    "BranchId",
    "DEFAULT_BRANCH",
    "InstanceId",
    "StepOccurrence",
    "UnitId",
]
