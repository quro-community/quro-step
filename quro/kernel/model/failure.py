"""Failure boundary types (design doc §14, §17, §37).

The Kernel *reports* failure. It never decides what happens next::

    MountFailure  != retry
    Failure       != replan
    UpdateFailure != backtrack

Law E3 — Failure Does Not Auto-Advance: on Failure, ``update`` is not implicitly
invoked and next-Position establishment is not implicitly invoked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .position import SemanticPosition


class MountFailureKind(str, Enum):
    """Why a declared Position could not be materialized (§10.4)."""

    UNKNOWN_BRANCH = "unknown-branch"
    UNRESOLVED_UNIT = "unresolved-unit"
    UNKNOWN_OCCURRENCE = "unknown-occurrence"
    INVALID_POSITION = "invalid-position"


@dataclass(frozen=True)
class MountFailure:
    """Explicit failure to materialize a declared Position.

    The implementation must never silently substitute a nearest Position, first
    child, fallback child, another branch or another occurrence (M2 / §10.4).
    """

    kind: MountFailureKind
    position: "SemanticPosition | None" = None
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", MountFailureKind(self.kind))

    def __str__(self) -> str:  # pragma: no cover - trivial
        where = f" at {self.position}" if self.position is not None else ""
        return f"MountFailure({self.kind.value}{where}): {self.detail}"


@dataclass(frozen=True)
class FailureReason:
    """Opaque, domain-defined execution failure reason (§14.1)."""

    code: str
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "detail", MappingProxyType(dict(self.detail)))

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.code


@dataclass(frozen=True)
class Failure:
    """Typed execution failure result of ``execute`` (§14.1)."""

    position: "SemanticPosition"
    reason: FailureReason

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"Failure({self.reason.code}) at {self.position}"


class UpdateFailureKind(str, Enum):
    """Deliberately narrow: infrastructural or law-violation only (§17)."""

    STORAGE_UNAVAILABLE = "storage-unavailable"
    RECOVERABILITY_VIOLATION = "recoverability-violation"
    CONCURRENT_MODIFICATION = "concurrent-modification"
    DOMAIN_REJECTED = "domain-rejected"


@dataclass(frozen=True)
class UpdateFailure:
    """Canonical ``update`` error set (Patch 2).

    ``RecoverabilityViolation`` is the one semantically load-bearing case: it is
    what the reference updater returns instead of *silently* dropping a
    previously recoverable Position (Law E2').
    """

    kind: UpdateFailureKind
    position: "SemanticPosition | None" = None
    reason: "FailureReason | None" = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", UpdateFailureKind(self.kind))

    @classmethod
    def storage_unavailable(cls, reason: "FailureReason | None" = None) -> "UpdateFailure":
        return cls(kind=UpdateFailureKind.STORAGE_UNAVAILABLE, reason=reason)

    @classmethod
    def recoverability_violation(cls, position: "SemanticPosition") -> "UpdateFailure":
        return cls(
            kind=UpdateFailureKind.RECOVERABILITY_VIOLATION, position=position
        )

    @classmethod
    def concurrent_modification(cls) -> "UpdateFailure":
        return cls(kind=UpdateFailureKind.CONCURRENT_MODIFICATION)

    @classmethod
    def domain_rejected(cls, reason: "FailureReason | None" = None) -> "UpdateFailure":
        return cls(kind=UpdateFailureKind.DOMAIN_REJECTED, reason=reason)

    def __str__(self) -> str:  # pragma: no cover - trivial
        target = f" ({self.position})" if self.position is not None else ""
        return f"UpdateFailure({self.kind.value}){target}"


__all__ = [
    "Failure",
    "FailureReason",
    "MountFailure",
    "MountFailureKind",
    "UpdateFailure",
    "UpdateFailureKind",
]
