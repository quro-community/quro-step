"""Recoverability queries and Law E2' non-destructiveness checks (design doc §16.3).

Law E2' — Update Non-Destructiveness::

    update(C, A, prov) = Ok(C')
        =>
    forall P. isRecoverable(P, C) => isRecoverable(P, C')
"""

from __future__ import annotations

from typing import Any, Iterable

from ..model.position import SemanticPosition


def recoverable_positions(continuity: Any) -> "frozenset[SemanticPosition]":
    """Every Position declared recoverable in ``continuity``."""
    getter = getattr(continuity, "all_recoverable", None)
    if getter is not None:
        return frozenset(getter())
    positions = getattr(continuity, "all_positions", None)
    if positions is None:
        return frozenset()
    return frozenset(p for p in positions() if is_recoverable(continuity, p))


def is_recoverable(continuity: Any, position: SemanticPosition) -> bool:
    checker = getattr(continuity, "is_recoverable", None)
    if checker is None:
        return False
    return bool(checker(position))


def lost_recoverability(
    before: "Iterable[SemanticPosition]", after: "Iterable[SemanticPosition]"
) -> "frozenset[SemanticPosition]":
    """Positions recoverable before an update but not after."""
    return frozenset(before) - frozenset(after)


def preserves_recoverability(
    before: "Iterable[SemanticPosition]", after: "Iterable[SemanticPosition]"
) -> bool:
    return not lost_recoverability(before, after)


def pick_violation(
    candidates: "Iterable[SemanticPosition]",
) -> "SemanticPosition | None":
    """Deterministically choose one violated Position for the error payload."""
    ordered = sorted(candidates, key=str)
    return ordered[0] if ordered else None


__all__ = [
    "is_recoverable",
    "lost_recoverability",
    "pick_violation",
    "preserves_recoverability",
    "recoverable_positions",
]
