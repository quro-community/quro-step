"""ExecutionState — minimal executable semantic projection (design doc §9).

Canonical minimal shape::

    ExecutionState = {
        position:      SemanticPosition,   // closed Kernel field
        unit:          ExecUnit,           // closed Kernel field
        domainPayload: StateDomainPayload  // isolated extension slot
    }

Law ::

    ExecutionState(P, C)
        = the minimal executable semantic projection of Continuity C at Position P

It is *derived*, never an independently persisted second source of truth
(§9.4). Law E1 — Domain Payload Non-Interference: ``domainPayload`` must not
encode Position substitution, next-Position choice or outer control decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from .unit import ExecUnit
from .position import SemanticPosition


@dataclass(frozen=True)
class StateDomainPayload:
    """Nominal extension slot for domain-defined local execution state (§15.2)."""

    data: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.data[key]


@dataclass(frozen=True)
class ExecutionState:
    """The executable semantic projection of Continuity at a Position."""

    position: SemanticPosition
    unit: ExecUnit
    domain_payload: StateDomainPayload = field(default_factory=StateDomainPayload)

    @property
    def position_of(self) -> SemanticPosition:
        """The mounted Position (Law M1)."""
        return self.position

    @classmethod
    def at(
        cls,
        position: SemanticPosition,
        unit: ExecUnit,
        payload: "StateDomainPayload | Mapping[str, Any] | None" = None,
    ) -> "ExecutionState":
        if payload is None:
            domain = StateDomainPayload()
        elif isinstance(payload, StateDomainPayload):
            domain = payload
        else:
            domain = StateDomainPayload(data=dict(payload))
        return cls(position=position, unit=unit, domain_payload=domain)


def position_of(state: ExecutionState) -> SemanticPosition:
    """Functional form of ``positionOf(S)`` used by the mount laws."""
    return state.position


__all__ = ["ExecutionState", "StateDomainPayload", "position_of"]
