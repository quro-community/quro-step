"""ExecutionPlan — execution structure (design doc §4.1).

::

    ExecutionPlan {
        root: ExecUnitId
    }

The Kernel consumes an already-established plan. Producing a plan is outside
Kernel responsibility::

    Plan != Execution

A replan may create a new plan; the Kernel does not need to know that
replanning occurred.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Mapping

from .ids import UnitId
from .unit import ExecUnit


@dataclass(frozen=True)
class ExecutionPlan:
    """A root ExecUnitId plus the registry of units it references."""

    root: UnitId
    units: Mapping[UnitId, ExecUnit] = field(default_factory=dict)
    name: str = "plan"

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", UnitId.of(self.root))
        object.__setattr__(
            self,
            "units",
            MappingProxyType({UnitId.of(k): v for k, v in self.units.items()}),
        )

    @property
    def root_unit(self) -> "ExecUnit | None":
        return self.units.get(self.root)

    def unit(self, unit: "str | UnitId") -> "ExecUnit | None":
        return self.units.get(UnitId.of(unit))

    def contains(self, unit: "str | UnitId") -> bool:
        return UnitId.of(unit) in self.units

    def all_units(self) -> "tuple[ExecUnit, ...]":
        return tuple(self.units.values())

    def child_of(self, parent: ExecUnit, unit: "str | UnitId") -> "ExecUnit | None":
        """Structural child lookup: only declared children resolve (Law M3)."""
        uid = UnitId.of(unit)
        if parent.is_composite and parent.has_child(uid):
            return self.units.get(uid)
        return None

    def with_unit(self, unit: ExecUnit) -> "ExecutionPlan":
        """Return a plan with one unit replaced/added (replanning is upstream)."""
        units = dict(self.units)
        units[unit.id] = unit
        return replace(self, units=units)


__all__ = ["ExecutionPlan"]
