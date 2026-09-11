"""Error-as-value result boundary (design doc §10.1, §13.1, §16.1).

Every Kernel boundary returns a ``Result`` rather than raising or returning a
bare value:

    mount   -> Result[ExecutionState, MountFailure]
    execute -> Result[Artifact, Failure]
    update  -> Result[ExecutionContinuity, UpdateFailure]

A ``Result`` carries no control authority: it reports, it does not decide
(§37 Error Ownership).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar, Union

T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")


@dataclass(frozen=True)
class Ok(Generic[T]):
    """Success case of a Kernel boundary."""

    value: T

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    @property
    def error(self) -> "E":  # pragma: no cover - guarded access
        raise ValueError("Ok has no error value")

    def unwrap(self) -> T:
        return self.value


@dataclass(frozen=True)
class Err(Generic[E]):
    """Failure case of a Kernel boundary."""

    error: E

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    @property
    def value(self) -> "T":  # pragma: no cover - guarded access
        raise ValueError(f"Err has no value: {self.error!r}")

    def unwrap(self) -> "T":  # pragma: no cover - guarded access
        raise ValueError(f"Err has no value: {self.error!r}")

    def unwrap_err(self) -> E:
        return self.error


Result = Union[Ok[T], Err[E]]


def ok(value: T) -> "Result[T, E]":
    return Ok(value)


def err(error: E) -> "Result[T, E]":
    return Err(error)


def is_ok(result: "Result[T, E]") -> bool:
    return result.is_ok()


def is_err(result: "Result[T, E]") -> bool:
    return result.is_err()


def unwrap(result: "Result[T, E]") -> T:
    return result.unwrap()


def map_result(result: "Result[T, E]", fn: Callable[[T], U]) -> "Result[U, E]":
    if result.is_err():
        return result  # type: ignore[return-value]
    return Ok(fn(result.value))  # type: ignore[attr-defined]


__all__ = [
    "Err",
    "Ok",
    "Result",
    "err",
    "is_err",
    "is_ok",
    "map_result",
    "ok",
    "unwrap",
]
