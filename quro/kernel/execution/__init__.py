"""Execution boundary: bounded execution producing Artifact | Failure (§13)."""

from .executor import CallableExecutor, Executor, execute_into
from .result import ExecutionResult, execution_result

__all__ = [
    "CallableExecutor",
    "ExecutionResult",
    "Executor",
    "execute_into",
    "execution_result",
]
