"""Artifact — a contract-backed execution consequence (design doc §13, §24.1).

    Artifact {
        id
        payload
        provenance
    }

An Artifact records that *this execution occurrence produced this semantic
consequence*. It does not assert universal truth (§13.4) and it is not a
control decision (§13.5 / Law E-Artifact-Control-Separation).

Artifact identity must not depend on a filesystem path, conversation ID, prompt
position or physical storage layout.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Mapping, TYPE_CHECKING

from .ids import ArtifactId

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .provenance import Provenance


@dataclass(frozen=True)
class ArtifactPayload:
    """Nominal extension slot for domain-defined Artifact content.

    ``ArtifactPayload``, ``StateDomainPayload`` and ``ProvenanceDetail`` share an
    underlying shape but are deliberately distinct nominal types (§15.2), so an
    extension author cannot accidentally pass one where another was expected.
    """

    data: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.data[key]


@dataclass(frozen=True)
class Artifact:
    """A durable, domain-defined semantic consequence produced at a boundary."""

    id: ArtifactId
    payload: ArtifactPayload = field(default_factory=ArtifactPayload)
    provenance: "Provenance | None" = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", ArtifactId.of(self.id))

    def with_provenance(self, provenance: "Provenance") -> "Artifact":
        """Return a copy carrying occurrence provenance (Law E5)."""
        return replace(self, provenance=provenance)

    @classmethod
    def create(
        cls,
        artifact_id: "str | ArtifactId",
        data: "Mapping[str, Any] | None" = None,
        provenance: "Provenance | None" = None,
    ) -> "Artifact":
        return cls(
            id=ArtifactId.of(artifact_id),
            payload=ArtifactPayload(data=dict(data or {})),
            provenance=provenance,
        )


__all__ = ["Artifact", "ArtifactPayload"]
