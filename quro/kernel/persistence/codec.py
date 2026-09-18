"""The durable Kernel model ⇄ plain JSON.

Backlog item `B-10`: *no codec exists anywhere in ``src/``.* The records round-trip
(``quro.continuity_ops``' ``as_dict``/``from_dict``) while the continuity carrying them
does not, so crossing a process boundary — the evidence form every milestone uses —
required a codec each domain wrote for itself.

**This is a representation, not a store.** v0.2 §36 delegates persistence to stores and
defines no URI system or storage topology; nothing here writes a byte. What it fixes is
what the bytes *mean*, which is the half a store cannot supply.

## The defect it exists to make impossible

Milestone 3's codec encoded ``default_interpretation`` and never decoded it. Its own
record says what that cost: *"a continuity-scoped binding lives in exactly this field,
so a codec that did not restore it manufactured a failure and would have blamed the
owner for it."* That is not "a codec had a bug" — it is **a lossy codec reads as the
model being wrong**, and nothing detected it. The next domain re-runs the same risk on
a different field.

So the obligation is stated once, where both ends can read it:

    every field of a covered type is carried, in both directions,
    and adding a field cannot make the codec silently lossy.

The field set is not copied into this module. It is read from ``dataclasses.fields`` of
the type itself (see :data:`COVERED_TYPES`), and ``tests/kernel/test_persistence_codec.py``
asserts the encodings agree with it. A field the model grows and the codec does not
carry fails a test; it does not quietly disappear.

## What it refuses

A continuity whose *type* declares fields this codec does not know is **refused by
name**, never encoded with those fields missing. ``dataclasses.fields` is the test, so
a domain subclass — the fold milestone's ``FoldProjection`` is one — is caught at the
call rather than at the consumer that reads a field that is no longer there. A domain
declares how to carry its own fields, or it is told it has not.

## What is not carried, and why

```text
interpretation_resolver  a live domain capability, not data. A codec that carried it
                         would be carrying a domain object graph. Supplied at decode,
                         the way every milestone's `decode_model` supplies it.
declared policy          how to read, not what is true — a projection, a channel set,
                         a retention ledger's scope. Supplied at decode (M4's landing
                         found this split the hard way); the codec must never hand a
                         fresh interpreter the answer it is entitled to derive.
ExecutionState           carried, but as *transport*. v0.2 §7.2 forbids a stored state
                         as a second answer to "what is true at P"; the reconstruction
                         path stays Position + Continuity → mount → State.
```

## Determinism

Sets and mappings are emitted in a stable order (sorted by their string rendering), so
two equal continuities encode to equal payloads. That is what lets a caller put the
result under a content address without a canonicalization pass of its own.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any, Callable, Mapping

from ..model import (
    Artifact,
    ArtifactId,
    ArtifactPayload,
    BranchId,
    CausalRelation,
    Checkpoint,
    ConversationRecord,
    ExecutionContinuity,
    ExecutionPlan,
    ExecutionState,
    ExecUnit,
    Failure,
    FailureReason,
    Fingerprint,
    History,
    InstanceId,
    InterpretationIdentity,
    MountFailure,
    MountFailureKind,
    PathSegment,
    Provenance,
    ProvenanceDetail,
    RelationKind,
    SemanticPosition,
    SemanticRecord,
    StabilityContract,
    StateDomainPayload,
    Step,
    ToolTraceRecord,
    UnitId,
    UnitKind,
    UpdateFailure,
    UpdateFailureKind,
)


class CodecError(ValueError):
    """The model cannot be represented — named rather than produced lossily."""


# ---------------------------------------------------------------------------
# What is covered, stated once
# ---------------------------------------------------------------------------

#: Every type this codec claims to carry. The claim is checked, not asserted:
#: ``tests/kernel/test_persistence_codec.py`` walks a maximally-populated continuity,
#: collects every model object it reaches, and fails if one is not named here — so a
#: new nested type cannot slip past the coverage discipline by being new.
COVERED_TYPES: "tuple[type, ...]" = (
    SemanticPosition,
    PathSegment,
    ExecutionPlan,
    ExecUnit,
    Step,
    ExecutionContinuity,
    History,
    SemanticRecord,
    ConversationRecord,
    ToolTraceRecord,
    Checkpoint,
    Artifact,
    ArtifactPayload,
    Provenance,
    ProvenanceDetail,
    CausalRelation,
    InterpretationIdentity,
    Fingerprint,
    ExecutionState,
    StateDomainPayload,
    MountFailure,
    Failure,
    FailureReason,
    UpdateFailure,
)

#: Fields that are part of the model and are NOT durable data. A closed list, never a
#: pattern: a field added to a covered type is either carried or named here, and the
#: default is "carried" — an omission is a test failure, not a silent exclusion.
NON_DURABLE_FIELDS: "Mapping[type, frozenset[str]]" = {
    ExecutionContinuity: frozenset({"interpretation_resolver"}),
}

#: Model types carried as a *scalar* rather than as a field table — an id becomes its
#: name, an occurrence becomes its index. They are named here so that the coverage
#: check can be exact in both directions: every model object a graph reaches is either
#: covered or a leaf, and a leaf that stops being reached is a stale claim (LL6).
#:
#: ``StepOccurrence`` is deliberately absent. It is a model type nothing in the durable
#: graph contains, so claiming it as a carried leaf would be a claim with no subject —
#: and the check that every leaf is still reached is what would say so.
LEAF_TYPES: "tuple[type, ...]" = (
    UnitId,
    BranchId,
    InstanceId,
    ArtifactId,
)

#: Types whose encoding carries one key that is not a dataclass field, because the
#: payload has to say which member of a polymorphic family it is. Closed, per type, so
#: an extra key anywhere else is a failure rather than an allowance.
DISCRIMINATOR_KEYS: "Mapping[type, str]" = {
    SemanticRecord: "kind",
    ConversationRecord: "kind",
    ToolTraceRecord: "kind",
    MountFailure: "boundary",
    Failure: "boundary",
    UpdateFailure: "boundary",
}


def covered_field_names(kind: type) -> "frozenset[str]":
    """The field names of ``kind`` that a faithful encoding must carry."""
    carried = {field.name for field in dataclasses.fields(kind)}
    return frozenset(carried - NON_DURABLE_FIELDS.get(kind, frozenset()))


def expected_keys(kind: type) -> "frozenset[str]":
    """The keys a faithful encoding of ``kind`` must have — fields plus discriminator."""
    keys = set(covered_field_names(kind))
    discriminator = DISCRIMINATOR_KEYS.get(kind)
    if discriminator is not None:
        keys.add(discriminator)
    return frozenset(keys)


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------


def encode_position(position: SemanticPosition) -> dict:
    return {
        "path": [encode_segment(segment) for segment in position.path],
        "branch": position.branch.name,
    }


def encode_segment(segment: PathSegment) -> dict:
    return {"unit": segment.unit.name, "instance": segment.instance.index}


def encode_plan(plan: ExecutionPlan) -> dict:
    return {
        "root": plan.root.name,
        "units": [encode_unit(unit) for unit in plan.all_units()],
        "name": plan.name,
    }


def encode_unit(unit: ExecUnit) -> dict:
    return {
        "id": unit.id.name,
        "kind": unit.kind.value,
        "definition": None if unit.definition is None else encode_step(unit.definition),
        "children": [child.name for child in unit.children],
    }


def encode_step(step: Step) -> dict:
    return {
        "id": step.id.name,
        "objective": step.objective,
        "executor": step.executor,
        "params": dict(step.params),
    }


def encode_artifact(artifact: Artifact) -> dict:
    return {
        "id": artifact.id.name,
        "payload": encode_artifact_payload(artifact.payload),
        "provenance": (
            None if artifact.provenance is None else encode_provenance(artifact.provenance)
        ),
    }


def encode_artifact_payload(payload: ArtifactPayload) -> dict:
    return {"data": dict(payload.data)}


def encode_provenance(provenance: Provenance) -> dict:
    return {
        "position": encode_position(provenance.position),
        "occurrence": provenance.occurrence.index,
        "relation": encode_relation(provenance.relation),
        "detail": encode_provenance_detail(provenance.detail),
    }


def encode_provenance_detail(detail: ProvenanceDetail) -> dict:
    return {"data": dict(detail.data)}


def encode_identity(identity: InterpretationIdentity) -> dict:
    return {"name": identity.name, "version": identity.version}


def encode_fingerprint(fingerprint: Fingerprint) -> dict:
    return {"value": fingerprint.value}


def encode_state_payload(payload: StateDomainPayload) -> dict:
    return {"data": dict(payload.data)}


def encode_relation(relation: CausalRelation) -> dict:
    return {
        "kind": relation.kind.value,
        "prior": None if relation.prior is None else relation.prior.name,
        "label": relation.label,
    }


def encode_record(record: Any) -> dict:
    if isinstance(record, SemanticRecord):
        return {
            "kind": record.kind,
            "payload": dict(record.payload),
            "position": None if record.position is None else encode_position(record.position),
        }
    if isinstance(record, ConversationRecord):
        return {"kind": record.kind, "text": record.text, "role": record.role}
    if isinstance(record, ToolTraceRecord):
        return {"kind": record.kind, "tool": record.tool, "detail": dict(record.detail)}
    raise CodecError(f"no encoding for record type {type(record).__name__}")


def encode_history(history: History) -> dict:
    return {"records": [encode_record(record) for record in history.records]}


def encode_checkpoint(checkpoint: Checkpoint) -> dict:
    return {
        "position": encode_position(checkpoint.position),
        "default_interpretation": (
            None
            if checkpoint.default_interpretation is None
            else str(checkpoint.default_interpretation)
        ),
        "stability_contract": checkpoint.stability_contract.value,
        "pinned_fingerprint": (
            None
            if checkpoint.pinned_fingerprint is None
            else str(checkpoint.pinned_fingerprint)
        ),
    }


def _encode_plans(continuity: ExecutionContinuity) -> dict:
    return {
        branch.name: encode_plan(plan)
        for branch, plan in sorted(continuity.plans.items(), key=lambda item: item[0].name)
    }


def _encode_branch_parents(continuity: ExecutionContinuity) -> dict:
    return {
        branch.name: (None if parent is None else parent.name)
        for branch, parent in sorted(continuity.branch_parents.items(), key=lambda i: i[0].name)
    }


def _encode_positions(positions: "frozenset[SemanticPosition]") -> list:
    return [encode_position(position) for position in sorted(positions, key=str)]


def _encode_occurrences(continuity: ExecutionContinuity) -> list:
    return [
        [branch.name, unit.name, instance.index]
        for branch, unit, instance in sorted(
            continuity.occurrences, key=lambda item: (item[0].name, item[1].name, item[2].index)
        )
    ]


def _encode_checkpoints(continuity: ExecutionContinuity) -> list:
    return [
        encode_checkpoint(declaration)
        for _, declaration in sorted(continuity.checkpoints.items(), key=lambda item: str(item[0]))
    ]


def _uncovered_fields(instance: Any, base: type) -> "frozenset[str]":
    """Fields ``type(instance)`` declares that ``base`` does not — the drop surface."""
    declared = {field.name for field in dataclasses.fields(base)}
    actual = {field.name for field in dataclasses.fields(type(instance))}
    return frozenset(actual - declared)


def encode_continuity(
    continuity: ExecutionContinuity, *, extras: "Mapping[str, Any] | None" = None
) -> dict:
    """Encode ``C`` — plans, lineage, positions, declarations, history, artifacts.

    ``extras`` carries the fields of a domain subclass, and is required exactly when
    the type has such fields: a subclass encoded without them would lose them and
    report success, which is the defect this module exists to make impossible.
    """
    uncovered = _uncovered_fields(continuity, ExecutionContinuity)
    if uncovered and extras is None:
        raise CodecError(
            f"{type(continuity).__name__} declares fields this codec does not carry: "
            f"{sorted(uncovered)}. Pass extras={{...}} to say how they travel, or the "
            "fields would be dropped without a word."
        )
    if extras is not None and frozenset(extras) != uncovered:
        raise CodecError(
            f"extras must cover exactly the fields beyond ExecutionContinuity: "
            f"{sorted(uncovered)}, got {sorted(extras)}"
        )
    encoded = {
        "plans": _encode_plans(continuity),
        "branch_parents": _encode_branch_parents(continuity),
        "occurrences": _encode_occurrences(continuity),
        "positions": _encode_positions(continuity.positions),
        "recoverable": _encode_positions(continuity.recoverable),
        "checkpoints": _encode_checkpoints(continuity),
        "default_interpretation": (
            None
            if continuity.default_interpretation is None
            else str(continuity.default_interpretation)
        ),
        "domain": continuity.domain,
        "interpretation_requirement": continuity.interpretation_requirement,
        "history": encode_history(continuity.history),
        "artifacts": [encode_artifact(artifact) for artifact in continuity.artifacts],
    }
    if uncovered:
        encoded["extras"] = dict(extras)
    return _jsonable(encoded, where="continuity")


def encode_state(state: ExecutionState) -> dict:
    return {
        "position": encode_position(state.position),
        "unit": encode_unit(state.unit),
        "interpretation": (
            None if state.interpretation is None else str(state.interpretation)
        ),
        "domain_payload": encode_state_payload(state.domain_payload),
    }


def encode_failure(failure: Any) -> dict:
    """Encode whichever of the three failure boundaries is handed in.

    The ``boundary`` discriminator is what makes a failure decodable *as itself*: v0.2
    §37 gives the three different owners, and a payload that could not tell them apart
    would let a mount failure be read as an execution failure.
    """
    if isinstance(failure, MountFailure):
        return _jsonable(
            {
                "boundary": "mount",
                "kind": failure.kind.value,
                "position": (
                    None if failure.position is None else encode_position(failure.position)
                ),
                "detail": failure.detail,
                "expected": None if failure.expected is None else str(failure.expected),
                "actual": None if failure.actual is None else str(failure.actual),
            },
            where="mount-failure",
        )
    if isinstance(failure, UpdateFailure):
        return _jsonable(
            {
                "boundary": "update",
                "kind": failure.kind.value,
                "position": (
                    None if failure.position is None else encode_position(failure.position)
                ),
                "reason": None if failure.reason is None else encode_reason(failure.reason),
            },
            where="update-failure",
        )
    if isinstance(failure, Failure):
        return _jsonable(
            {
                "boundary": "execute",
                "position": encode_position(failure.position),
                "reason": encode_reason(failure.reason),
            },
            where="failure",
        )
    raise CodecError(f"no encoding for failure type {type(failure).__name__}")


def encode_reason(reason: FailureReason) -> dict:
    return {"code": reason.code, "detail": dict(reason.detail)}


#: The single place a covered type is bound to its encoder. Declared rather than
#: inferred so that a *reader* — a store, or the coverage check — can ask what this
#: codec does with a type it was handed, instead of restating the mapping and letting
#: the two drift.
ENCODERS: "Mapping[type, Callable[[Any], dict]]" = {
    SemanticPosition: encode_position,
    PathSegment: encode_segment,
    ExecutionPlan: encode_plan,
    ExecUnit: encode_unit,
    Step: encode_step,
    ExecutionContinuity: encode_continuity,
    History: encode_history,
    SemanticRecord: encode_record,
    ConversationRecord: encode_record,
    ToolTraceRecord: encode_record,
    Checkpoint: encode_checkpoint,
    Artifact: encode_artifact,
    ArtifactPayload: encode_artifact_payload,
    Provenance: encode_provenance,
    ProvenanceDetail: encode_provenance_detail,
    CausalRelation: encode_relation,
    InterpretationIdentity: encode_identity,
    Fingerprint: encode_fingerprint,
    ExecutionState: encode_state,
    StateDomainPayload: encode_state_payload,
    MountFailure: encode_failure,
    Failure: encode_failure,
    FailureReason: encode_reason,
    UpdateFailure: encode_failure,
}


def _jsonable(encoded: Any, *, where: str) -> dict:
    """Refuse a payload a process boundary could not actually carry.

    The model's extension slots are ``Mapping[str, Any]`` and the domain fills them, so
    an unserializable value is the domain's to fix and this is where it is told — at
    encode time, naming the payload, rather than at whatever later writes the file.
    """
    try:
        json.dumps(encoded)
    except (TypeError, ValueError) as exc:
        raise CodecError(f"the {where} payload is not plain JSON: {exc}") from exc
    return encoded


# ---------------------------------------------------------------------------
# Decoding
# ---------------------------------------------------------------------------


def decode_position(data: Mapping[str, Any]) -> SemanticPosition:
    position = SemanticPosition.root(data.get("branch"))
    for segment in data.get("path", ()):
        position = position.child(segment["unit"], segment["instance"])
    return position


def decode_segment(data: Mapping[str, Any]) -> PathSegment:
    return PathSegment.of(data["unit"], data["instance"])


def decode_plan(data: Mapping[str, Any]) -> ExecutionPlan:
    units = {}
    for encoded in data.get("units", ()):
        unit = decode_unit(encoded)
        units[unit.id] = unit
    return ExecutionPlan(
        root=UnitId.of(data["root"]), units=units, name=data.get("name", "plan")
    )


def decode_unit(data: Mapping[str, Any]) -> ExecUnit:
    definition = data.get("definition")
    return ExecUnit(
        id=UnitId.of(data["id"]),
        kind=UnitKind(data["kind"]),
        definition=None if definition is None else decode_step(definition),
        children=tuple(UnitId.of(child) for child in data.get("children", ())),
    )


def decode_step(data: Mapping[str, Any]) -> Step:
    return Step(
        id=UnitId.of(data["id"]),
        objective=data.get("objective", ""),
        executor=data.get("executor", "default"),
        params=dict(data.get("params", {}) or {}),
    )


def decode_artifact(data: Mapping[str, Any]) -> Artifact:
    provenance = data.get("provenance")
    return Artifact(
        id=data["id"],
        payload=ArtifactPayload(data=dict(data.get("payload", {}).get("data", {}) or {})),
        provenance=None if provenance is None else decode_provenance(provenance),
    )


def decode_provenance(data: Mapping[str, Any]) -> Provenance:
    return Provenance(
        position=decode_position(data["position"]),
        occurrence=InstanceId.of(data.get("occurrence", 0)),
        relation=decode_relation(data.get("relation", {}) or {}),
        detail=ProvenanceDetail(data=dict(data.get("detail", {}).get("data", {}) or {})),
    )


def decode_relation(data: Mapping[str, Any]) -> CausalRelation:
    return CausalRelation(
        kind=RelationKind(data.get("kind", RelationKind.INITIAL.value)),
        prior=data.get("prior"),
        label=data.get("label"),
    )


def decode_record(data: Mapping[str, Any]) -> Any:
    kind = data.get("kind")
    if kind == "semantic":
        position = data.get("position")
        return SemanticRecord(
            payload=dict(data.get("payload", {}) or {}),
            position=None if position is None else decode_position(position),
        )
    if kind == "conversation":
        return ConversationRecord(text=data.get("text", ""), role=data.get("role", "agent"))
    if kind == "tool-trace":
        return ToolTraceRecord(tool=data.get("tool", ""), detail=dict(data.get("detail", {}) or {}))
    raise CodecError(f"unknown record kind {kind!r}")


def decode_history(data: Mapping[str, Any]) -> History:
    return History(records=tuple(decode_record(item) for item in data.get("records", ())))


def decode_checkpoint(data: Mapping[str, Any]) -> Checkpoint:
    pinned = data.get("pinned_fingerprint")
    declared = data.get("default_interpretation")
    return Checkpoint(
        position=decode_position(data["position"]),
        default_interpretation=None if declared is None else InterpretationIdentity.of(declared),
        stability_contract=StabilityContract(data.get("stability_contract", "nominal")),
        pinned_fingerprint=None if pinned is None else Fingerprint.of(pinned),
    )


def _decode_plans(continuity: ExecutionContinuity, data: Mapping[str, Any]) -> ExecutionContinuity:
    plans = dict(continuity.plans)
    parents = dict(continuity.branch_parents)
    for branch, encoded in data.get("plans", {}).items():
        plans[BranchId.of(branch)] = decode_plan(encoded)
    for branch, parent in data.get("branch_parents", {}).items():
        parents[BranchId.of(branch)] = None if parent is None else BranchId.of(parent)
    return dataclasses.replace(continuity, plans=plans, branch_parents=parents)


def out_of_band_fields(kind: type) -> "frozenset[str]":
    """The fields of ``kind`` a payload cannot carry, and a caller must supply.

    Named so a fresh interpreter can ask what it owes rather than discover it.
    """
    return NON_DURABLE_FIELDS.get(kind, frozenset())


def extras_from(data: Mapping[str, Any]) -> dict:
    """The domain's declared extra fields, as carried in a payload."""
    return dict(data.get("extras", {}) or {})


def decode_continuity(
    data: Mapping[str, Any],
    *,
    resolver: "Any | None" = None,
    factory: "Callable[[ExecutionContinuity, Mapping[str, Any]], Any] | None" = None,
) -> ExecutionContinuity:
    """Rebuild ``C`` — the Kernel model, plus whatever the caller declares it owes.

    ``resolver`` is the domain's live interpretation environment (E6c), which is not
    data and cannot be carried.

    ``factory`` receives a rebuilt ``ExecutionContinuity`` together with the payload's
    declared extras and returns the domain's own type. When a payload *has* extras and
    no factory claims them, this refuses: an unclaimed extra is a field that would be
    dropped on the read side, which is the same loss as dropping it on the write side.
    """
    extras = extras_from(data)
    if extras and factory is None:
        raise CodecError(
            f"the payload declares extra fields {sorted(extras)} that no factory claims; "
            "decode with factory=... or the fields are dropped on the way back in."
        )

    continuity = ExecutionContinuity.create(
        domain=data.get("domain"),
        default_interpretation=data.get("default_interpretation"),
        interpretation_resolver=resolver,
        interpretation_requirement=data.get("interpretation_requirement"),
    )
    continuity = _decode_plans(continuity, data)

    continuity = dataclasses.replace(
        continuity,
        occurrences=frozenset(
            (BranchId.of(branch), UnitId.of(unit), InstanceId.of(instance))
            for branch, unit, instance in data.get("occurrences", ())
        ),
        positions=frozenset(decode_position(item) for item in data.get("positions", ())),
    )
    # Declared recoverability is rebuilt through the declared door rather than assigned,
    # so a payload cannot assert that a Position is recoverable without also stating the
    # occurrence it belongs to — the door the model uses everywhere else.
    continuity = continuity.marked_recoverable_many(
        *(decode_position(item) for item in data.get("recoverable", ()))
    )
    continuity = continuity.with_checkpoints(
        *(decode_checkpoint(item) for item in data.get("checkpoints", ()))
    )
    continuity = dataclasses.replace(
        continuity,
        history=decode_history(data.get("history", {}) or {}),
        artifacts=tuple(decode_artifact(item) for item in data.get("artifacts", ())),
    )
    if factory is not None:
        return factory(continuity, extras)
    return continuity


def decode_state(data: Mapping[str, Any]) -> ExecutionState:
    declared = data.get("interpretation")
    return ExecutionState(
        position=decode_position(data["position"]),
        unit=decode_unit(data["unit"]),
        interpretation=None if declared is None else InterpretationIdentity.of(declared),
        domain_payload=StateDomainPayload(data=dict(data.get("domain_payload", {}).get("data", {}) or {})),
    )


def decode_failure(data: Mapping[str, Any]) -> Any:
    boundary = data.get("boundary")
    if boundary == "mount":
        position = data.get("position")
        expected = data.get("expected")
        actual = data.get("actual")
        return MountFailure(
            kind=MountFailureKind(data["kind"]),
            position=None if position is None else decode_position(position),
            detail=data.get("detail", ""),
            expected=None if expected is None else Fingerprint.of(expected),
            actual=None if actual is None else Fingerprint.of(actual),
        )
    if boundary == "update":
        position = data.get("position")
        reason = data.get("reason")
        return UpdateFailure(
            kind=UpdateFailureKind(data["kind"]),
            position=None if position is None else decode_position(position),
            reason=None if reason is None else decode_reason(reason),
        )
    if boundary == "execute":
        return Failure(
            position=decode_position(data["position"]),
            reason=decode_reason(data["reason"]),
        )
    raise CodecError(f"unknown failure boundary {boundary!r}")


def decode_reason(data: Mapping[str, Any]) -> FailureReason:
    return FailureReason(code=data["code"], detail=dict(data.get("detail", {}) or {}))


# ---------------------------------------------------------------------------
# The unit that crosses a boundary
# ---------------------------------------------------------------------------


def encode_model(
    continuity: ExecutionContinuity,
    position: SemanticPosition,
    *,
    extras: "Mapping[str, Any] | None" = None,
) -> dict:
    """``(C', P')`` — what a fresh interpreter needs and nothing else.

    A domain's *declared policy* does not belong here. It is how to read, not what is
    true, and a fresh interpreter is entitled to know the policy it should apply and
    never to be handed the answer (M4's landing). A domain that has policy to declare
    wraps this payload in its own envelope; the Kernel will not guess on its behalf.
    """
    return _jsonable(
        {
            "continuity": encode_continuity(continuity, extras=extras),
            "position": encode_position(position),
        },
        where="model",
    )


def decode_model(
    envelope: Mapping[str, Any],
    *,
    resolver: "Any | None" = None,
    factory: "Callable[[ExecutionContinuity, Mapping[str, Any]], Any] | None" = None,
) -> "tuple[ExecutionContinuity, SemanticPosition]":
    """Rebuild ``(C', P')``."""
    return (
        decode_continuity(envelope["continuity"], resolver=resolver, factory=factory),
        decode_position(envelope["position"]),
    )


__all__ = [
    "COVERED_TYPES",
    "DISCRIMINATOR_KEYS",
    "ENCODERS",
    "LEAF_TYPES",
    "NON_DURABLE_FIELDS",
    "CodecError",
    "covered_field_names",
    "decode_artifact",
    "decode_checkpoint",
    "decode_continuity",
    "decode_failure",
    "decode_history",
    "decode_model",
    "decode_plan",
    "decode_position",
    "decode_reason",
    "decode_record",
    "decode_relation",
    "decode_segment",
    "decode_state",
    "decode_step",
    "decode_unit",
    "encode_artifact",
    "encode_artifact_payload",
    "encode_checkpoint",
    "encode_continuity",
    "encode_failure",
    "encode_fingerprint",
    "encode_history",
    "encode_identity",
    "encode_model",
    "encode_plan",
    "encode_position",
    "encode_provenance",
    "encode_provenance_detail",
    "encode_reason",
    "encode_record",
    "encode_relation",
    "encode_segment",
    "encode_state",
    "encode_state_payload",
    "encode_step",
    "encode_unit",
    "expected_keys",
    "extras_from",
    "out_of_band_fields",
]
