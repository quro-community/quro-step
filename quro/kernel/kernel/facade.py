"""Canonical public Kernel API (design doc §18).

Deliberately small::

    interface Kernel {
        mount(position, continuity) -> Result[ExecutionState, MountFailure]
        execute(state, unit)        -> Result[Artifact, Failure]
        update(continuity, artifact, provenance) -> Result[ExecutionContinuity, UpdateFailure]
    }

There is intentionally no ``next``, ``steer``, ``retry``, ``backtrack``,
``replan``, ``compact``, ``fork`` or ``fold`` on the facade. The Kernel
executes; the enclosing Control layer selects continuation (§19).
"""

from __future__ import annotations

from typing import Any

from ..continuity.updater import ContinuityUpdater
from ..execution.executor import Executor
from ..model.artifact import Artifact
from ..model.failure import Failure, MountFailure, UpdateFailure
from ..model.unit import ExecUnit
from ..model.position import SemanticPosition
from ..model.provenance import Provenance
from ..model.result import Result
from ..model.state import ExecutionState
from ..mount.mounter import Mounter


class Kernel:
    """The minimal unified execution substrate."""

    def __init__(
        self,
        executor: Executor,
        mounter: "Mounter | None" = None,
        updater: "ContinuityUpdater | None" = None,
    ) -> None:
        self._executor = executor
        self._mounter = mounter or Mounter()
        self._updater = updater or ContinuityUpdater()

    # -- boundary 1: mount ------------------------------------------------
    def mount(
        self, position: SemanticPosition, continuity: Any
    ) -> "Result[ExecutionState, MountFailure]":
        """Materialize an ExecutionState from a declared Position and Continuity."""
        return self._mounter.mount(position, continuity)

    # -- boundary 2: execute ----------------------------------------------
    def execute(
        self, state: ExecutionState, unit: ExecUnit
    ) -> "Result[Artifact, Failure]":
        """Bounded execution: ExecutionState + ExecUnit -> Artifact | Failure."""
        return self._executor.execute(state, unit)

    # -- boundary 3: update -----------------------------------------------
    def update(
        self, continuity: Any, artifact: Artifact, provenance: Provenance
    ) -> "Result[Any, UpdateFailure]":
        """Register an Artifact occurrence into Continuity (non-destructively)."""
        return self._updater.update(continuity, artifact, provenance)


__all__ = ["Kernel"]
