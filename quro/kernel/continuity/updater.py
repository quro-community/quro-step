"""ContinuityUpdater — the continuity registration/update boundary (§16, §17).

Canonical signature (Patch 2)::

    update(
        continuity: ExecutionContinuity,
        artifact: Artifact,
        provenance: Provenance
    ) -> Result[ExecutionContinuity, UpdateFailure]

The minimal semantic role is occurrence registration / semantic append — *not*
universal semantic merge, deduplication, conflict resolution, branch folding or
summarization. Axiom Folding and friends are explicitly higher-level and must
not be performed here.
"""

from __future__ import annotations

from typing import Any

from ..model.artifact import Artifact
from ..model.failure import FailureReason, UpdateFailure
from ..model.provenance import Provenance
from ..model.result import Err, Ok, Result
from .recoverability import lost_recoverability, pick_violation, recoverable_positions


def _provenance_violation(
    continuity: Any, provenance: "Provenance | None"
) -> "str | None":
    """Enforce Law E5 — Provenance Sufficiency at the update boundary."""
    if provenance is None:
        return "provenance is required to register an Artifact occurrence"
    if not isinstance(provenance, Provenance):
        return f"expected Provenance, got {type(provenance).__name__}"
    position = provenance.position
    if position is not None and position.path:
        leaf = position.path[-1].instance
        if leaf != provenance.occurrence:
            return (
                "provenance occurrence does not reconstruct its Position leaf "
                f"occurrence ({provenance.occurrence} != {leaf})"
            )
    return None


class ContinuityUpdater:
    """Reference ``update`` implementation (Law E2', K8)."""

    def update(
        self,
        continuity: Any,
        artifact: Artifact,
        provenance: Provenance,
    ) -> "Result[Any, UpdateFailure]":
        violation = _provenance_violation(continuity, provenance)
        if violation is not None:
            return Err(
                UpdateFailure.domain_rejected(
                    reason=FailureReason(code="provenance-insufficient", detail={"detail": violation})
                )
            )

        before = recoverable_positions(continuity)

        try:
            updated = continuity.append_semantic_artifact(artifact, provenance)
        except Exception as exc:  # ordinary infrastructural failure, §16.1
            return Err(
                UpdateFailure.storage_unavailable(
                    reason=FailureReason(code="storage-unavailable", detail={"error": repr(exc)})
                )
            )

        if updated is None:
            return Err(
                UpdateFailure.storage_unavailable(
                    reason=FailureReason(code="storage-unavailable", detail={"error": "no continuity"})
                )
            )

        after = recoverable_positions(updated)
        lost = lost_recoverability(before, after)
        if lost:
            violated = pick_violation(lost)
            # Never silently destroy recoverability: report the violation.
            return Err(UpdateFailure.recoverability_violation(violated))

        return Ok(updated)


__all__ = ["ContinuityUpdater"]
