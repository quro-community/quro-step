"""Executor — the bounded execution boundary (design doc §13).

    ExecutionState + ExecUnit -> execute -> Artifact | Failure

An Artifact is a semantic consequence, not a control decision. Producing one
does not advance outer control, choose a next Position, retry, replan, steer,
backtrack or fork (§13.5 / K6).
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Protocol, runtime_checkable

from ..model.artifact import Artifact
from ..model.failure import Failure
from ..model.unit import ExecUnit, Step
from ..model.result import Err, Ok
from ..model.state import ExecutionState
from .result import ExecutionResult, execution_result, failure_at

#: A domain handler receives the mounted state and the unit to execute.
ExecHandler = Callable[[ExecutionState, ExecUnit], Any]


@runtime_checkable
class Executor(Protocol):
    """Boundary contract for bounded execution."""

    def execute(self, state: ExecutionState, unit: ExecUnit) -> ExecutionResult:
        ...  # pragma: no cover - protocol


class CallableExecutor:
    """Reference executor: dispatches to domain handlers by executor key.

    Handlers may return an ``Artifact``, an ``Ok[Artifact]`` or an
    ``Err[Failure]``. A handler that raises is converted into an ``Err`` — the
    Kernel reports failure rather than propagating a crash across its boundary.
    """

    def __init__(
        self,
        handlers: "Mapping[str, ExecHandler] | None" = None,
        default: "ExecHandler | None" = None,
    ) -> None:
        self._handlers = dict(handlers or {})
        self._default = default

    def register(self, key: str, handler: ExecHandler) -> "CallableExecutor":
        self._handlers[key] = handler
        return self

    def handler_for(self, unit: ExecUnit) -> "ExecHandler | None":
        definition = unit.definition
        key = definition.executor if isinstance(definition, Step) else "default"
        handler = self._handlers.get(key)
        if handler is not None:
            return handler
        wildcard = self._handlers.get("*")
        if wildcard is not None:
            return wildcard
        return self._default

    def execute(self, state: ExecutionState, unit: ExecUnit) -> ExecutionResult:
        handler = self.handler_for(unit)
        if handler is None:
            return Err(
                failure_at(
                    state.position,
                    "no-executor",
                    unit=str(unit.id),
                    executor=_executor_key(unit),
                )
            )
        try:
            outcome = handler(state, unit)
        except Exception as exc:  # boundary: report, do not propagate
            return Err(
                failure_at(
                    state.position,
                    "executor-raised",
                    unit=str(unit.id),
                    error=repr(exc),
                )
            )
        if isinstance(outcome, (Ok, Err)):
            return outcome
        if isinstance(outcome, Artifact):
            return Ok(outcome)
        return Err(
            failure_at(
                state.position,
                "invalid-executor-result",
                unit=str(unit.id),
                result=repr(outcome),
            )
        )


def execute_into(
    executor: Executor, state: ExecutionState, unit: ExecUnit
) -> ExecutionResult:
    """Functional wrapper used by the facade and by conformance helpers."""
    return execution_result(executor.execute(state, unit))


def _executor_key(unit: ExecUnit) -> str:
    definition = unit.definition
    return definition.executor if isinstance(definition, Step) else "default"


__all__ = [
    "CallableExecutor",
    "ExecHandler",
    "Executor",
    "execute_into",
]
