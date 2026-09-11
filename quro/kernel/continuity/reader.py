"""Continuity capability protocols (design doc §7.3).

The Kernel needs access to capabilities *equivalent to*::

    resolveUnitAt(position)
    isRecoverable(position)
    project(position)
    update(...)

The precise storage interface may vary; these protocols are what the mount and
update boundaries depend on.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..model.artifact import Artifact
from ..model.plan import ExecutionPlan
from ..model.position import SemanticPosition
from ..model.provenance import Provenance
from ..model.state import StateDomainPayload


@runtime_checkable
class ContinuityReader(Protocol):
    """Read-side capability surface required by ``mount``."""

    def plan_for(self, branch) -> "ExecutionPlan | None":
        ...  # pragma: no cover - protocol

    def occurrence_known(self, branch, unit, instance) -> bool:
        ...  # pragma: no cover - protocol

    def is_recoverable(self, position: SemanticPosition) -> bool:
        ...  # pragma: no cover - protocol

    def all_positions(self) -> "frozenset[SemanticPosition]":
        ...  # pragma: no cover - protocol

    def project(self, position: SemanticPosition) -> StateDomainPayload:
        ...  # pragma: no cover - protocol


@runtime_checkable
class ContinuityWriter(Protocol):
    """Write-side capability surface required by ``update``."""

    def append_semantic_artifact(
        self, artifact: Artifact, provenance: Provenance
    ) -> "ContinuityReader":
        ...  # pragma: no cover - protocol


__all__ = ["ContinuityReader", "ContinuityWriter"]
