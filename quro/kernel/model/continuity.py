"""ExecutionContinuity — durable semantic reconstruction source (design doc §7).

    ExecutionContinuity
        |
        | interpreted at P
        v
    ExecutionState(P)

not::

    ExecutionContinuity  <->  stored authoritative ExecutionState

The Kernel treats Continuity as an abstraction. This module provides the
reference in-memory implementation; a real deployment may back the same
capability surface (``resolveUnitAt`` / ``isRecoverable`` / ``project`` /
``update``, §7.3) with filesystem or database storage.

Section 8 / Patch 3: Continuity holds the plan applicable to each branch, so
``mount`` never receives an ``ExecutionPlan`` directly and replanning stays
outside the Kernel.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Mapping

from .artifact import Artifact
from .history import History, SemanticRecord
from .ids import DEFAULT_BRANCH, BranchId, InstanceId, UnitId
from .plan import ExecutionPlan
from .position import SemanticPosition
from .provenance import Provenance
from .state import StateDomainPayload

#: ``(branch, unit, instance)`` — a declared occurrence of a unit in a lineage.
OccurrenceKey = "tuple[BranchId, UnitId, InstanceId]"


@dataclass(frozen=True)
class ExecutionContinuity:
    """Reference ExecutionContinuity: an immutable semantic reconstruction source.

    Being immutable is what makes ``mount`` referentially transparent for free:
    ``mount`` cannot mutate ``C`` because it has no mutation API (Law M5).
    """

    plans: Mapping[BranchId, ExecutionPlan] = field(default_factory=dict)
    branch_parents: Mapping[BranchId, "BranchId | None"] = field(default_factory=dict)
    occurrences: "frozenset[tuple[BranchId, UnitId, InstanceId]]" = frozenset()
    positions: "frozenset[SemanticPosition]" = frozenset()
    recoverable: "frozenset[SemanticPosition]" = frozenset()
    history: History = field(default_factory=History)
    artifacts: "tuple[Artifact, ...]" = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "plans", MappingProxyType({BranchId.of(k): v for k, v in self.plans.items()})
        )
        object.__setattr__(
            self,
            "branch_parents",
            MappingProxyType(
                {
                    BranchId.of(k): (BranchId.of(v) if v is not None else None)
                    for k, v in self.branch_parents.items()
                }
            ),
        )
        object.__setattr__(
            self,
            "occurrences",
            frozenset(
                (BranchId.of(b), UnitId.of(u), InstanceId.of(i)) for (b, u, i) in self.occurrences
            ),
        )
        object.__setattr__(self, "positions", frozenset(self.positions))
        object.__setattr__(self, "recoverable", frozenset(self.recoverable))
        object.__setattr__(self, "artifacts", tuple(self.artifacts))

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    @classmethod
    def create(
        cls, plan: "ExecutionPlan | None" = None, branch: BranchId = DEFAULT_BRANCH
    ) -> "ExecutionContinuity":
        """A fresh continuity, optionally already referencing a branch plan."""
        continuity = cls()
        if plan is not None:
            continuity = continuity.with_plan(branch, plan)
        return continuity

    def with_plan(
        self,
        branch: "str | BranchId",
        plan: ExecutionPlan,
        parent: "str | BranchId | None" = None,
    ) -> "ExecutionContinuity":
        """Attach/replace the plan applicable to a branch.

        A replan simply replaces the plan a *new* branch references; ``mount``
        never needs to know a replan occurred (§8).
        """
        branch_id = BranchId.of(branch)
        plans = dict(self.plans)
        plans[branch_id] = plan
        parents = dict(self.branch_parents)
        parents.setdefault(branch_id, BranchId.of(parent) if parent is not None else None)
        return replace(self, plans=plans, branch_parents=parents)

    def with_branch(
        self, branch: "str | BranchId", parent: "str | BranchId | None"
    ) -> "ExecutionContinuity":
        """Declare a lineage (Fork/Backtrack allocate branches upstream)."""
        branch_id = BranchId.of(branch)
        parents = dict(self.branch_parents)
        parents[branch_id] = BranchId.of(parent) if parent is not None else None
        return replace(self, branch_parents=parents)

    def established(self, position: SemanticPosition) -> "ExecutionContinuity":
        """Record that an occurrence/Position now exists in this continuity."""
        added = frozenset(
            (position.branch, seg.unit, seg.instance) for seg in position.path
        )
        return replace(
            self,
            occurrences=self.occurrences | added,
            positions=self.positions | {position},
        )

    def established_many(self, *positions: SemanticPosition) -> "ExecutionContinuity":
        continuity = self
        for position in positions:
            continuity = continuity.established(position)
        return continuity

    def marked_recoverable(self, position: SemanticPosition) -> "ExecutionContinuity":
        """Promote a Position to *declared recoverable* (a Checkpoint)."""
        base = self.established(position)
        return replace(base, recoverable=base.recoverable | {position})

    def marked_recoverable_many(self, *positions: SemanticPosition) -> "ExecutionContinuity":
        continuity = self
        for position in positions:
            continuity = continuity.marked_recoverable(position)
        return continuity

    def record(self, record) -> "ExecutionContinuity":
        """Append one runtime record (History append law, §6.1)."""
        return replace(self, history=self.history.append(record))

    def record_evidence(
        self, payload: "Mapping[str, Any]", position: "SemanticPosition | None" = None
    ) -> "ExecutionContinuity":
        """Append continuity-relevant semantic evidence."""
        return self.record(SemanticRecord(payload=dict(payload), position=position))

    def append_semantic_artifact(
        self, artifact: Artifact, provenance: Provenance
    ) -> "ExecutionContinuity":
        """Occurrence registration / semantic append (§16.2).

        This is deliberately *not* universal semantic merge: it appends the
        Artifact and a continuity-relevant record, and nothing else.
        """
        stored = artifact.with_provenance(provenance)
        record = SemanticRecord(
            payload={
                "artifact": stored.id.name,
                "relation": provenance.relation.kind.value,
            },
            position=provenance.position,
        )
        return replace(
            self,
            artifacts=self.artifacts + (stored,),
            history=self.history.append(record),
        )

    # ------------------------------------------------------------------
    # Continuity capabilities (§7.3)
    # ------------------------------------------------------------------
    def plan_for(self, branch: "str | BranchId") -> "ExecutionPlan | None":
        return self.plans.get(BranchId.of(branch))

    def occurrence_known(
        self,
        branch: "str | BranchId",
        unit: "str | UnitId",
        instance: "int | InstanceId",
    ) -> bool:
        key = (BranchId.of(branch), UnitId.of(unit), InstanceId.of(instance))
        return key in self.occurrences

    def position_known(self, position: SemanticPosition) -> bool:
        if not position.path:
            return self.plan_for(position.branch) is not None
        return all(
            self.occurrence_known(position.branch, seg.unit, seg.instance)
            for seg in position.path
        )

    def is_recoverable(self, position: SemanticPosition) -> bool:
        """Whether ``position`` was explicitly marked externally recoverable."""
        return position in self.recoverable

    def all_positions(self) -> "frozenset[SemanticPosition]":
        return frozenset(self.positions)

    def all_recoverable(self) -> "frozenset[SemanticPosition]":
        return frozenset(self.recoverable)

    def resolve_unit_at(self, position: SemanticPosition):
        """Structural resolution delegate (see :mod:`quro.kernel.mount.resolver`)."""
        from ..mount.resolver import resolve_unit_at

        return resolve_unit_at(position, self)

    def artifact(self, artifact_id: "str | None" = None) -> "Artifact | None":
        for stored in self.artifacts:
            if artifact_id is None or stored.id.name == artifact_id:
                return stored
        return None

    def project(self, position: SemanticPosition) -> StateDomainPayload:
        """Interpret Continuity at a Position into a domain payload.

        The Kernel fixes *that* a projection exists, not what it contains: the
        shape below is the reference toy-domain projection.
        """
        evidence = tuple(dict(record.payload) for record in self.history.semantic_records())
        return StateDomainPayload(
            data={
                "position": str(position),
                "branch": position.branch.name,
                "ancestry": tuple(str(seg) for seg in position.path),
                "artifacts": tuple(a.id.name for a in self.artifacts),
                "evidence": evidence,
                "recoverable": position in self.recoverable,
            }
        )


__all__ = ["ExecutionContinuity", "OccurrenceKey"]
