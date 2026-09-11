"""Result plumbing for the execution boundary (§13.1)."""

from __future__ import annotations

from ..model.artifact import Artifact
from ..model.failure import Failure, FailureReason
from ..model.position import SemanticPosition
from ..model.result import Err, Ok, Result

#: The canonical ``execute`` result boundary: ``Artifact | Failure``.
ExecutionResult = Result[Artifact, Failure]


def execution_result(outcome) -> ExecutionResult:
    """Normalize an executor response into the canonical Result boundary."""
    if isinstance(outcome, (Ok, Err)):
        return outcome
    if isinstance(outcome, Artifact):
        return Ok(outcome)
    raise TypeError(f"executor returned unsupported value: {outcome!r}")


def failure_at(position: SemanticPosition, code: str, **detail) -> Failure:
    return Failure(position=position, reason=FailureReason(code=code, detail=detail))


__all__ = ["ExecutionResult", "execution_result", "failure_at"]
