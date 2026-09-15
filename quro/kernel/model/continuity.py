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
from .checkpoint import Checkpoint
from .history import History, SemanticRecord
from .ids import DEFAULT_BRANCH, BranchId, InstanceId, UnitId
from .interpretation import (
    INTERPRETATION_REQUIREMENTS,
    InterpretationIdentity,
    UnknownInterpretation,
)
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
    checkpoints: Mapping[SemanticPosition, Checkpoint] = field(default_factory=dict)
    default_interpretation: "InterpretationIdentity | None" = None
    domain: "str | None" = None
    #: The domain-owned resolver this continuity resolves its declared
    #: interpretations through (E6c). Opaque to the Kernel beyond
    #: ``resolve(identity)`` and ``fingerprint(reading)``; ``None`` means the
    #: structural-only continuity that declares no interpretation environment.
    #:
    #: A *field*, not an instance attribute, precisely so it survives the
    #: non-destructive transforms (``replace``, fork/backtrack/branch
    #: allocation) the way E6d requires a declared interpretation to survive
    #: ``update``.
    interpretation_resolver: "Any | None" = None
    #: G1 — the declared boundary between "additive" (E6) and "must refuse"
    #: (E6a). ``"legacy-exempt"`` means an undeclared reading is the single-
    #: reading legacy case (no identity, never a fabricated one);
    #: ``"must-declare"`` means an undeclared reading is refused explicitly
    #: (``MountFailure(InterpretationRequired)``).
    #:
    #: ``None`` (the default) preserves the pre-Closure-0 behaviour exactly —
    #: the ``_declares_any`` heuristic — so a continuity that does not opt in is
    #: unchanged. The classification is a *declaration*, not a Kernel judgement:
    #: the Kernel never decides which domains are exempt (Closure 0 §8).
    interpretation_requirement: "str | None" = None
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
        object.__setattr__(
            self,
            "checkpoints",
            MappingProxyType(
                {
                    position: (
                        declaration
                        if isinstance(declaration, Checkpoint)
                        else Checkpoint(
                            position=position,
                            default_interpretation=declaration,
                        )
                    )
                    for position, declaration in self.checkpoints.items()
                }
            ),
        )
        if self.default_interpretation is not None:
            object.__setattr__(
                self,
                "default_interpretation",
                InterpretationIdentity.of(self.default_interpretation),
            )
        if self.domain is not None:
            object.__setattr__(self, "domain", str(self.domain))
        if self.interpretation_requirement is not None:
            requirement = str(self.interpretation_requirement)
            if requirement not in INTERPRETATION_REQUIREMENTS:
                raise ValueError(
                    "interpretation_requirement must be one of "
                    f"{INTERPRETATION_REQUIREMENTS} or None, not {requirement!r}"
                )
            object.__setattr__(self, "interpretation_requirement", requirement)
        object.__setattr__(self, "artifacts", tuple(self.artifacts))

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    @classmethod
    def create(
        cls,
        plan: "ExecutionPlan | None" = None,
        branch: BranchId = DEFAULT_BRANCH,
        *,
        domain: "str | None" = None,
        default_interpretation: "InterpretationIdentity | str | None" = None,
        interpretation_resolver: "Any | None" = None,
        interpretation_requirement: "str | None" = None,
    ) -> "ExecutionContinuity":
        """A fresh continuity, optionally already referencing a branch plan.

        ``domain`` and ``default_interpretation`` are the continuity's declared
        interpretation environment (E6): a domain may name itself so a foreign
        interpretation is refused explicitly (K16), and it may declare the
        reading its recoverable Positions default to.

        ``interpretation_requirement`` is G1's declared classification
        (``"legacy-exempt"`` / ``"must-declare"``). ``None`` keeps the pre-G1
        heuristic default, so an existing caller is unaffected.
        """
        continuity = cls(
            domain=domain,
            default_interpretation=(
                InterpretationIdentity.of(default_interpretation)
                if default_interpretation is not None
                else None
            ),
            interpretation_resolver=interpretation_resolver,
            interpretation_requirement=interpretation_requirement,
        )
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

    def with_interpretation_resolver(self, resolver: "Any | None") -> "ExecutionContinuity":
        """Attach/replace the domain resolver (a non-destructive transform).

        Stated as a named operation for the same reason ``rebind_interpretation``
        is: a declared interpretation environment is part of the continuity's
        semantics, so changing it should read as a change, not as a side effect.
        """
        return replace(self, interpretation_resolver=resolver)

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
        """Promote a Position to *declared recoverable*."""
        base = self.established(position)
        return replace(base, recoverable=base.recoverable | {position})

    def marked_recoverable_many(self, *positions: SemanticPosition) -> "ExecutionContinuity":
        continuity = self
        for position in positions:
            continuity = continuity.marked_recoverable(position)
        return continuity

    # -- Checkpoints (E6/E8/E9 declarations) ------------------------------
    def with_checkpoint(self, checkpoint: Checkpoint) -> "ExecutionContinuity":
        """Declare recoverability together with the re-entry contract it carries.

        The Checkpoint *is* the declaration: marking a Position recoverable and
        stating how it may be re-entered (which interpretation, how strongly
        pinned) is one act, not two that can drift apart.
        """
        base = self.marked_recoverable(checkpoint.position)
        declarations = dict(base.checkpoints)
        declarations[checkpoint.position] = checkpoint
        return replace(base, checkpoints=declarations)

    def with_checkpoints(self, *checkpoints: Checkpoint) -> "ExecutionContinuity":
        continuity = self
        for checkpoint in checkpoints:
            continuity = continuity.with_checkpoint(checkpoint)
        return continuity

    def checkpoint_at(self, position: SemanticPosition) -> "Checkpoint | None":
        """The declared Checkpoint for ``position``, if any (E9's gate)."""
        checkpoint = self.checkpoints.get(position)
        if checkpoint is not None:
            return checkpoint
        if position in self.recoverable and self.default_interpretation is not None:
            return Checkpoint.nominal(position, self.default_interpretation)
        return None

    def declared_interpretation_at(
        self, position: SemanticPosition
    ) -> "InterpretationIdentity | None":
        """The interpretation declared as default for ``position`` (E6)."""
        checkpoint = self.checkpoint_at(position)
        if checkpoint is not None and checkpoint.default_interpretation is not None:
            return checkpoint.default_interpretation
        return self.default_interpretation

    def rebind_interpretation(
        self,
        interpretation: "InterpretationIdentity | str | None",
        *,
        position: "SemanticPosition | None" = None,
        stability: "object | None" = None,
        fingerprint: "object | None" = None,
    ) -> "ExecutionContinuity":
        """Change a declared interpretation by an explicit, named operation (E6d).

        ``update`` never drops or rewrites a declared interpretation silently;
        this is the named operation that is allowed to change one. With
        ``position`` the change is scoped to that Checkpoint, otherwise it
        replaces the continuity-wide default.
        """
        if position is None:
            return replace(
                self,
                default_interpretation=(
                    InterpretationIdentity.of(interpretation)
                    if interpretation is not None
                    else None
                ),
            )

        existing = self.checkpoint_at(position) or Checkpoint(position=position)
        stability_contract = (
            existing.stability_contract if stability is None else stability
        )
        pinned_fingerprint = (
            existing.pinned_fingerprint if fingerprint is None else fingerprint
        )
        rebound = Checkpoint(
            position=position,
            default_interpretation=(
                InterpretationIdentity.of(interpretation)
                if interpretation is not None
                else existing.default_interpretation
            ),
            stability_contract=stability_contract,
            pinned_fingerprint=pinned_fingerprint,
        )
        return self.with_checkpoint(rebound)

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
        """Structural resolution delegate (see :mod:`quro.kernel.mount.structural`)."""
        from ..mount.structural import resolve_unit_at

        return resolve_unit_at(position, self)

    def all_checkpoints(self) -> "frozenset[Checkpoint]":
        """Every declared Checkpoint, including implicit per-position defaults."""
        return frozenset(
            checkpoint
            for checkpoint in (
                self.checkpoint_at(position) for position in self.recoverable
            )
            if checkpoint is not None
        )

    def resolve_interpretation(self, identity):
        """Resolve a declared reference through the domain's resolver (E6c).

        Raises whatever the domain's resolver raises — ``UnknownInterpretation``
        or ``CrossDomainInterpretation`` for the two refusals the Kernel names,
        or any other domain-defined error. A continuity that declares no resolver
        resolves nothing, which is the structural-only case.

        The returned reading is opaque to the Kernel: it travels straight back to
        the domain's own fingerprint capability and is never inspected,
        interpreted or compared here (E12/E13).
        """
        resolver = getattr(self, "interpretation_resolver", None)
        if resolver is None:
            raise UnknownInterpretation(
                f"no interpretation resolver is declared on {self.domain or 'this continuity'}"
            )
        target = InterpretationIdentity.of(identity)
        candidate = getattr(resolver, "resolve", None)
        if callable(candidate):
            return candidate(target)
        if callable(resolver):
            return resolver(target)
        raise UnknownInterpretation(f"resolver {resolver!r} is not callable")

    def resolved_interpretation(self, identity) -> "Any | None":
        """The domain value a declared identity resolves to, if it resolves.

        Advisory convenience over :meth:`resolve_interpretation`; returns ``None``
        instead of raising when nothing resolves. The value itself is opaque to
        the Kernel and is handed straight back to the domain.
        """
        try:
            return self.resolve_interpretation(identity)
        except Exception:  # boundary: an unresolvable identity is simply unavailable
            return None

    def fingerprint_of(self, identity, resolved=None, checkpoint=None):
        """The *domain-computed* fingerprint for a declared identity (E12).

        The Kernel never computes a fingerprint and never defines its coverage:
        it asks the domain, then compares the answer with what a pinned
        Checkpoint declared. A domain whose resolution carries no fingerprint
        returns ``None``, which under a pinned contract is a drift failure, not a
        pass.
        """
        value = resolved
        if value is None:
            value = self.resolved_interpretation(identity)
        if value is None:
            return None
        computed = getattr(value, "content_fingerprint", None)
        if computed is None:
            computed = getattr(value, "fingerprint", None)
        return computed

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
