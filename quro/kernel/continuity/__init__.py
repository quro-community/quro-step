"""Continuity capabilities: reader, updater, recoverability (design doc §7.3)."""

from .reader import ContinuityReader, ContinuityWriter
from .recoverability import (
    is_recoverable,
    lost_recoverability,
    pick_violation,
    preserves_recoverability,
    recoverable_positions,
)
from .updater import ContinuityUpdater

__all__ = [
    "ContinuityReader",
    "ContinuityUpdater",
    "ContinuityWriter",
    "is_recoverable",
    "lost_recoverability",
    "pick_violation",
    "preserves_recoverability",
    "recoverable_positions",
]
