"""ExecutionState — minimal executable semantic projection (design doc §9).

Canonical minimal shape::

    ExecutionState = {
        position:       SemanticPosition,        // closed Kernel field
        unit:           ExecUnit,                // closed Kernel field
        interpretation: InterpretationIdentity,  // closed Kernel field (E6)
        domainPayload:  StateDomainPayload       // isolated extension slot
    }

Law ::

    ExecutionState(P, C)
        = the minimal executable semantic projection of Continuity C at Position P

It is *derived*, never an independently persisted second source of truth
(§9.4). Law E1 — Domain Payload Non-Interference: ``domainPayload`` must not
encode Position substitution, next-Position choice or outer control decisions.

The ``interpretation`` field is the named, explicit third input to ``mount``,
carried into the mounted state (E6). It is *not* an equivalence verdict: two
states may carry the same identity and mean different things, or different
identities and mean the same thing (E11). Determinism (M3/M5) is defined *per
fixed* interpretation, not across interpretations (E6e).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from .interpretation import InterpretationIdentity
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
    interpretation: "InterpretationIdentity | None" = None
    domain_payload: StateDomainPayload = field(default_factory=StateDomainPayload)

    def __post_init__(self) -> None:
        if self.interpretation is not None:
            object.__setattr__(
                self, "interpretation", InterpretationIdentity.of(self.interpretation)
            )

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
        *,
        interpretation: "InterpretationIdentity | str | None" = None,
    ) -> "ExecutionState":
        if payload is None:
            domain = StateDomainPayload()
        elif isinstance(payload, StateDomainPayload):
            domain = payload
        else:
            domain = StateDomainPayload(data=dict(payload))
        return cls(
            position=position,
            unit=unit,
            interpretation=(
                InterpretationIdentity.of(interpretation)
                if interpretation is not None
                else None
            ),
            domain_payload=domain,
        )


def position_of(state: ExecutionState) -> SemanticPosition:
    """Functional form of ``positionOf(S)`` used by the mount laws."""
    return state.position


__all__ = ["ExecutionState", "StateDomainPayload", "position_of"]
