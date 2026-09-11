"""Provenance — occurrence identity + causal relation (design doc §15).

Minimal closed core::

    Provenance = {
        position:   SemanticPosition,
        occurrence: InstanceId,
        relation:   CausalRelation,
        detail:     ProvenanceDetail
    }

Law E5 — Provenance Sufficiency: provenance attached to an Artifact must be
sufficient to reconstruct its occurrence identity ``(Position, InstanceId)``.
Richer domain provenance may be added via ``detail``, but it cannot replace
this closed core.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, TYPE_CHECKING

from .ids import ArtifactId, InstanceId

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .position import SemanticPosition


class RelationKind(str, Enum):
    """Extensible causal-relation taxonomy (§15.1)."""

    INITIAL = "initial"
    RETRY_OF = "retry-of"
    DOMAIN_DEFINED = "domain-defined"


@dataclass(frozen=True)
class CausalRelation:
    """Why this occurrence exists relative to prior occurrences."""

    kind: RelationKind = RelationKind.INITIAL
    prior: "ArtifactId | None" = None
    label: "str | None" = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", RelationKind(self.kind))
        if self.prior is not None:
            object.__setattr__(self, "prior", ArtifactId.of(self.prior))

    @classmethod
    def initial(cls) -> "CausalRelation":
        return cls(kind=RelationKind.INITIAL)

    @classmethod
    def retry_of(cls, prior: "str | ArtifactId") -> "CausalRelation":
        return cls(kind=RelationKind.RETRY_OF, prior=ArtifactId.of(prior))

    @classmethod
    def domain_defined(cls, label: str) -> "CausalRelation":
        return cls(kind=RelationKind.DOMAIN_DEFINED, label=label)


@dataclass(frozen=True)
class ProvenanceDetail:
    """Nominal extension slot for domain-defined provenance detail (§15.2)."""

    data: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


@dataclass(frozen=True)
class Provenance:
    """Occurrence identity and causal relation attached to an Artifact."""

    position: "SemanticPosition"
    occurrence: InstanceId
    relation: CausalRelation = field(default_factory=CausalRelation.initial)
    detail: ProvenanceDetail = field(default_factory=ProvenanceDetail)

    def __post_init__(self) -> None:
        object.__setattr__(self, "occurrence", InstanceId.of(self.occurrence))

    def identity(self) -> "tuple[SemanticPosition, InstanceId]":
        """The closed core: ``(Position, InstanceId)`` (K11).

        Deliberately independent of ``relation`` and ``detail`` content.
        """
        return (self.position, self.occurrence)


__all__ = [
    "CausalRelation",
    "Provenance",
    "ProvenanceDetail",
    "RelationKind",
]
