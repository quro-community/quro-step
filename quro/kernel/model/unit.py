"""ExecUnit / Step — the compositional execution abstraction (design doc §4.2–§4.3).

Step, Pipeline and composite units all present the same external boundary::

    ExecUnit -> bounded execution -> Artifact | Failure

The Kernel need not understand the internal semantics of a concrete unit beyond
resolving and executing it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from .ids import UnitId


class UnitKind(str, Enum):
    """Whether an ExecUnit is a leaf or a composition of children."""

    ATOMIC = "atomic"
    COMPOSITE = "composite"


@dataclass(frozen=True)
class Step:
    """A stable execution definition (design doc §4.3).

    The exact domain fields are not fixed by the minimal Kernel; ``objective``,
    ``executor`` and ``params`` are the reference shape used by the toy domain.
    """

    id: UnitId
    objective: str = ""
    executor: str = "default"
    params: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", UnitId.of(self.id))
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))

    def param(self, name: str, default: Any = None) -> Any:
        return self.params.get(name, default)


@dataclass(frozen=True)
class ExecUnit:
    """The compositional execution abstraction (design doc §4.2)."""

    id: UnitId
    kind: UnitKind = UnitKind.ATOMIC
    definition: "Step | None" = None
    children: "tuple[UnitId, ...]" = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", UnitId.of(self.id))
        object.__setattr__(self, "kind", UnitKind(self.kind))
        object.__setattr__(self, "children", tuple(UnitId.of(c) for c in self.children))
        if self.kind is UnitKind.COMPOSITE and not self.children:
            raise ValueError(f"composite ExecUnit {self.id} must declare children")

    @property
    def is_atomic(self) -> bool:
        return self.kind is UnitKind.ATOMIC

    @property
    def is_composite(self) -> bool:
        return self.kind is UnitKind.COMPOSITE

    def has_child(self, unit: "str | UnitId") -> bool:
        return UnitId.of(unit) in self.children

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.id.name

    # -- constructors -----------------------------------------------------
    @classmethod
    def atomic(
        cls,
        unit_id: "str | UnitId",
        definition: "Step | None" = None,
        **step_kwargs: Any,
    ) -> "ExecUnit":
        uid = UnitId.of(unit_id)
        if definition is None:
            definition = Step(id=uid, **step_kwargs)
        return cls(id=uid, kind=UnitKind.ATOMIC, definition=definition)

    @classmethod
    def composite(
        cls,
        unit_id: "str | UnitId",
        children: "tuple[str | UnitId, ...]",
        definition: "Step | None" = None,
    ) -> "ExecUnit":
        return cls(
            id=UnitId.of(unit_id),
            kind=UnitKind.COMPOSITE,
            definition=definition,
            children=tuple(UnitId.of(c) for c in children),
        )


__all__ = ["ExecUnit", "Step", "UnitKind"]
