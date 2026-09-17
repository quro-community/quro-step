"""The three operations — one body shape, because they are one thing.

```text
    declare a record  →  commit it through the Kernel's ordinary update() boundary
    →  declare its route  →  leave everything prior untouched
```

That is not a style choice. It is what four independently-built experiments found,
each running its own case matrix against its own operation: a branch, a return, a
relation and a fold are all `mount(P, C)` with a declared record carried in `C`. None
needed a fourth Kernel method; none needed a field on `ExecutionState`; the append-only
law was never relaxed.

**Refusals are values.** Every operation returns the Kernel's own ``Result`` and
propagates the Kernel's own ``UpdateFailure`` — this layer adds no failure vocabulary,
because a refusal that came from ``update`` is the Kernel's statement and re-wrapping it
would obscure which layer refused. ``OperationError`` is reserved for *caller* mistakes:
an unknown channel, or a record type an operation cannot carry.

**Two constraints worth knowing before you call these**, both discovered by the
milestones rather than designed:

* ``allocate`` refuses the ``provenance-relation`` channel. A fork registers no
  Artifact, and that channel is subject-centred — it attaches to the Artifact being
  registered. A fork record has one natural channel, where a return record has three.
* ``fold`` must be given the ledger it carried. An operation that declares a retention
  promise and carries nothing is the exact shape the experiment tree's highest-weighted
  control injects, and it looks completely successful: ``mount`` works, the record is
  there, no error is raised, and the promise is unkept. ``law.py`` checks it; this
  module will not make it true for you.
"""

from __future__ import annotations

from typing import Any, Mapping

from quro.kernel import Artifact, ExecutionContinuity, ExecutionPlan, Result, SemanticPosition

from .channels import (
    CH_ARTIFACT,
    CH_PROVENANCE,
    CH_RECORD,
    artifact_data_with_record,
    encode_record,
    provenance_with_record,
)
from .records import (
    BranchAllocation,
    BacktrackRecord,
    ContinuityRecord,
    FoldRecord,
    PROJ_DOMAIN,
)

#: The key a fold's carried ledger occupies in the summary's payload. The *content*
#: half of E16; `retains` is the declaring half, and the gap between them opening
#: silently is what the law exists to forbid.
CARRIED_KEY = "retained-content"

#: The key a summary's own content occupies. Excluded from the ledger readers so a
#: continuation cannot satisfy a "retained original" need out of the summary itself —
#: the summary is the fold's *output*, not a pre-fold fact.
SUMMARY_KEY = "summary-content"


class OperationError(RuntimeError):
    """A caller mistake — not a refusal. An unknown channel, or an impossible record.

    Deliberately not used for ``update``'s refusals: those come back as the Kernel's
    own ``Result``, so a caller can always tell which layer declined.
    """


def _occurrence(position: SemanticPosition) -> int:
    """The occurrence index a provenance must carry for ``update`` to accept it.

    ``update`` refuses a provenance whose occurrence does not reconstruct its
    Position's leaf (E5), so this is read off the position rather than passed in.
    """
    return position.path[-1].instance.index if position.path else 0


def _mount_and_execute(kernel: Any, continuity: Any, position: SemanticPosition) -> Result:
    """Run the unit at ``position`` through the Kernel's two execution boundaries."""
    mounted = kernel.mount(position, continuity)
    if mounted.is_err():
        return mounted
    return kernel.execute(mounted.value, mounted.value.unit)


def _commit_record(
    kernel: Any,
    continuity: Any,
    record: ContinuityRecord,
    position: SemanticPosition,
    *,
    artifact: "Artifact | None" = None,
) -> Result:
    """Put a record into its declared channel. One call, three channels.

    The two channels that ride an Artifact registration need one; the one that does not
    cannot use ``provenance-relation`` at all, which is why the guard below exists
    rather than a silent fallback.
    """
    channel = record.channel
    if channel not in (CH_RECORD, CH_PROVENANCE, CH_ARTIFACT):
        raise OperationError(f"unknown realization channel: {channel!r}")

    if channel == CH_RECORD:
        return _ok(continuity.record_evidence(encode_record(record), position=position))

    if channel == CH_PROVENANCE:
        if artifact is None:
            raise OperationError(
                "the provenance-relation channel is subject-centred: it attaches to the "
                "Artifact being registered, and this operation registers none. Declare "
                "semantic-record or artifact-payload instead."
            )
        return kernel.update(
            continuity, artifact, provenance_with_record(record, position, occurrence=_occurrence(position))
        )

    # CH_ARTIFACT
    if artifact is None:
        raise OperationError(
            "the artifact-payload channel carries the record inside an Artifact's own "
            "payload, and this operation registers none."
        )
    carrying = Artifact.create(
        artifact.id.name,
        data=artifact_data_with_record(record, dict(getattr(artifact.payload, "data", {}) or {})),
    )
    return kernel.update(
        continuity, carrying, provenance_with_record(record, position, occurrence=_occurrence(position))
    )


def _ok(value: Any) -> Result:
    from quro.kernel import Ok

    return Ok(value)


# ---------------------------------------------------------------------------
# The three operations
# ---------------------------------------------------------------------------


def backtrack(
    kernel: Any,
    continuity: ExecutionContinuity,
    position: SemanticPosition,
    record: BacktrackRecord,
) -> "Result[ExecutionContinuity, Any]":
    """Re-enter a prior recoverable Position, recording the return.

    A return is a **forward step**: ``mount`` re-enters the target, the unit at it
    executes and registers its Artifact through the ordinary ``update`` boundary, and
    the continuity advances. Nothing before the target is mutated — that is the
    append-only law, and the experiment tree's control that violates it is caught.

    ``position`` is the target. The operation does not choose it: resolving which prior
    Position a return means is a domain judgement, and a Kernel or library that picked
    one would be making exactly the decision Corollary C1 forbids it to make.

    **Not defined:** what happens to continuations established after the target. See
    ``UB-1`` in ``docs/design/Q4-Kernel-Undefined-Behaviour-Register.md`` — a caller must
    not depend on any particular fate for them without a declared policy.
    """
    if not isinstance(record, BacktrackRecord):
        raise OperationError(f"backtrack takes a BacktrackRecord, not {type(record).__name__}")

    executed = _mount_and_execute(kernel, continuity, position)
    if executed.is_err():
        return executed
    artifact = executed.value

    committed = _commit_record(kernel, continuity, record, position, artifact=artifact)
    if committed.is_err():
        return committed

    from quro.kernel import Ok

    return Ok(committed.value.established(position))


def allocate(
    kernel: Any,
    continuity: ExecutionContinuity,
    position: SemanticPosition,
    allocation: BranchAllocation,
    plan: ExecutionPlan,
    *,
    new_occurrences: "tuple[tuple[str, int], ...]" = (),
) -> "Result[ExecutionContinuity, Any]":
    """Establish a child branch and record the allocation.

    The parent's recoverable Positions remain recoverable in the child, **with their
    occurrence indices preserved** — a fork that renumbered would collapse two genuinely
    different occurrences into one, which is the shape the experiment tree's
    occurrence-collapse control injects.

    ``new_occurrences`` lets a child establish Positions of its own beyond the inherited
    ones. ``plan`` is attached to the child branch; ``mount`` resolves it from the
    continuity, so a fork needs no special mode.

    **Not defined:** N-ary, cyclic or merged branch topologies. That is *open* rather
    than undefined — foreseeable and testable, simply untested — and it is deliberately
    not in the UB register. Do not read the binary model as a general one.
    """
    if not isinstance(allocation, BranchAllocation):
        raise OperationError(f"allocate takes a BranchAllocation, not {type(allocation).__name__}")

    child = allocation.child_branch
    inherited = tuple(
        _position_from_label(label, child) for label in allocation.inherited_positions
    )
    fresh = tuple(_position_from_label(f"{leaf}#{index}", child) for leaf, index in new_occurrences)

    updated = continuity.with_plan(child, plan, parent=allocation.parent_branch)
    updated = updated.established_many(*inherited, *fresh)
    for child_position in inherited + fresh:
        updated = updated.marked_recoverable(child_position)

    # The owner's decision, taken per UD-2: a binding is a property of the branch, so it
    # travels in the record. A caller that wants continuity-scoped bindings declares
    # them on the continuity instead — deliberately, and knows what it is giving up.
    committed = _commit_record(kernel, updated, allocation, position)
    if committed.is_err():
        return committed
    return committed


def fold(
    kernel: Any,
    continuity: ExecutionContinuity,
    position: SemanticPosition,
    record: FoldRecord,
    *,
    carried: "Mapping[str, Mapping[str, str]]",
    summary_id: str,
    summary_content: "Mapping[str, str] | None" = None,
) -> "Result[ExecutionContinuity, Any]":
    """Compress named pre-fold content into a summary, recording what was retained.

    ``carried`` is the ledger — ``artifact_id -> {key: value}`` — of the facts this fold
    promises to keep. It is a required argument, not something the operation derives,
    because *whether the promise was kept* is the measurement: an operation that
    computed the ledger itself could only ever be as honest as its own computation, and
    the law would have nothing independent to check it against.

    The originals named in ``folded_from`` stay physically present. A fold that removes
    them is not a fold — it is a contract violation, and the experiment tree's control
    for that shape is caught by the append-only check.

    **Not defined:** what a summary means relative to what it superseded. See ``UB-2``
    in the register — a consumer must not infer priority from recency, ordering,
    identity or coverage.
    """
    if not isinstance(record, FoldRecord):
        raise OperationError(f"fold takes a FoldRecord, not {type(record).__name__}")

    payload: "dict[str, Any]" = {SUMMARY_KEY: dict(summary_content or {})}
    payload[CARRIED_KEY] = {artifact: dict(facts) for artifact, facts in carried.items()}
    summary = Artifact.create(summary_id, data=payload)

    committed = _commit_record(kernel, continuity, record, position, artifact=summary)
    if committed.is_err():
        return committed

    from quro.kernel import Ok

    return Ok(committed.value.established(position))


def _position_from_label(label: str, branch: str) -> SemanticPosition:
    """A child-branch Position from an opaque inherited label.

    The label is opaque to the Kernel and readable by the domain that authored it. Its
    shape is ``<segment>/<segment>/...`` where each segment is ``<unit>#<instance>`` —
    the *whole* path, not just the leaf, because a Position is addressed by its full
    ancestry and rebuilding only the last segment would place every inherited Position
    directly under the branch root.

    The occurrence index is **preserved**, never reset: "the parent's recoverable
    Positions remain recoverable in the child" means the child inherits ``apply#0``,
    never a renumbered ``apply#0`` standing in for ``apply#1``.

    A malformed segment is a caller error, which is why this raises rather than
    skipping: a silently-ignored segment would build a Position that is not the one
    declared, and the preservation check would then compare against the wrong thing.
    """
    path = label.split(":", 1)[-1]
    position = SemanticPosition.root(branch)
    for segment in path.split("/"):
        if not segment:
            continue
        unit, separator, index = segment.partition("#")
        if not unit or not separator:
            raise OperationError(
                f"inherited position label segment is not <unit>#<instance>: {segment!r}"
            )
        position = position.child(unit, int(index))
    if not position.path:
        raise OperationError(f"inherited position label has no path: {label!r}")
    return position


__all__ = [
    "CARRIED_KEY",
    "OperationError",
    "SUMMARY_KEY",
    "allocate",
    "backtrack",
    "fold",
]
