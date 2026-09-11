"""Conformance helpers shared by the K1–K11 suite (design doc §20, §21).

These helpers make kernel invariants assertable rather than merely documented.
"""

from __future__ import annotations

from typing import Any, Iterable

from ..model.position import SemanticPosition
from ..model.state import ExecutionState

#: Names the Kernel facade must never expose (design doc §18).
CONTROL_METHOD_NAMES = (
    "next",
    "steer",
    "retry",
    "backtrack",
    "replan",
    "compact",
    "fork",
    "fold",
)


def forbidden_control_methods(kernel: Any) -> "tuple[str, ...]":
    """Which forbidden control methods (if any) leak onto the facade."""
    return tuple(name for name in CONTROL_METHOD_NAMES if hasattr(kernel, name))


def facade_is_closed(kernel: Any) -> bool:
    """True when the Kernel facade exposes no control authority (§18, §19)."""
    return not forbidden_control_methods(kernel)


def assert_facade_closed(kernel: Any) -> None:
    leaked = forbidden_control_methods(kernel)
    assert not leaked, f"Kernel facade must not expose control methods: {leaked}"


def assert_position_fidelity(state: ExecutionState, position: SemanticPosition) -> None:
    """Law M1 — positionOf(mount(P, C)) = P."""
    assert state.position == position, (
        f"Position Fidelity violated: mounted {state.position} for requested {position}"
    )


def assert_recoverability_preserved(
    before: "Iterable[SemanticPosition]", after: "Iterable[SemanticPosition]"
) -> None:
    """Law E2 — previously recoverable Positions remain recoverable."""
    before, after = frozenset(before), frozenset(after)
    lost = before - after
    assert not lost, f"recoverability lost for: {sorted(str(p) for p in lost)}"


__all__ = [
    "CONTROL_METHOD_NAMES",
    "assert_facade_closed",
    "assert_position_fidelity",
    "assert_recoverability_preserved",
    "facade_is_closed",
    "forbidden_control_methods",
]
