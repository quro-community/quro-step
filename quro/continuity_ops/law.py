"""The preservation obligations, one per record type, stated as checkable functions.

Each operation owes a **D3** obligation — a preservation promise with *both* halves,
the declaration that the operation happened and the content it promised. Baseline
v1.0's `AR-2` names why both: they fail independently, and M4 discovered that the hard
way when its first formulation of Law E16 checked only the content half and passed a
fold that recorded nothing at all.

The obligations are stated over the **observation vocabulary** rather than over
objects, so the same check runs against a mounted state, a domain projection, a
declared on-demand resource, or a fresh interpreter — exactly as the four milestones
ran theirs. Nothing here decides *which* route a fact takes; the caller supplies the
delivered set, and that is what keeps this module free of access-surface policy.

An obligation is not a Kernel law. The Kernel does not read these records and cannot
enforce anything here; the framework states the obligation and a conformance check
discharges it, which is what Baseline v1.0 calls Tier 2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .records import BacktrackRecord, BranchAllocation, FoldRecord

#: The two halves, named as values so a report can say which one failed. This is the
#: distinction `AR-2` exists for: a per-half verdict is the difference between "the
#: fold kept nothing" and "the fold promised nothing readable".
HALF_DECLARATION = "declaration"
HALF_CONTENT = "content"


@dataclass(frozen=True)
class ObligationResult:
    """One obligation's verdict, with the facts behind it rather than a boolean."""

    obligation: str
    subject: str
    declared: "tuple[str, ...]"
    delivered: "tuple[str, ...]"
    missing: "tuple[str, ...]"
    detail: str = ""

    @property
    def satisfied(self) -> bool:
        return not self.missing

    @property
    def missing_declaration(self) -> "tuple[str, ...]":
        return tuple(item for item in self.missing if not item.startswith("retained:"))

    @property
    def missing_content(self) -> "tuple[str, ...]":
        return tuple(item for item in self.missing if item.startswith("retained:"))

    def as_dict(self) -> dict:
        return {
            "obligation": self.obligation,
            "subject": self.subject,
            "declared": list(self.declared),
            "delivered": list(self.delivered),
            "missing": list(self.missing),
            "missing_declaration": list(self.missing_declaration),
            "missing_content": list(self.missing_content),
            "satisfied": self.satisfied,
            "detail": self.detail,
        }


def _check(
    obligation: str, subject: str, declared: "Iterable[str]", delivered: "Iterable[str]", detail: str = ""
) -> ObligationResult:
    declared_items = tuple(sorted(set(declared)))
    delivered_items = tuple(sorted(set(delivered)))
    have = set(delivered_items)
    return ObligationResult(
        obligation=obligation,
        subject=subject,
        declared=declared_items,
        delivered=delivered_items,
        missing=tuple(item for item in declared_items if item not in have),
        detail=detail,
    )


# ---------------------------------------------------------------------------
# The obligations
# ---------------------------------------------------------------------------


def check_preservation(
    record: "BranchAllocation | BacktrackRecord", *, delivered: "Iterable[str]"
) -> ObligationResult:
    """The declaration half, for the two record types whose promise is structural.

    A branch allocation promises that the parent's recoverable Positions survived into
    the child. A return promises that the target Position is where execution now is.
    Neither promises *content*, so both are single-halved by construction — and saying
    so explicitly is the point: the two-halved requirement is a property of
    information-reducing operations, and applying it to one that reduces nothing would
    be inventing an obligation.
    """
    if isinstance(record, BranchAllocation):
        return _check(
            "branch-allocation-preservation",
            record.as_item(),
            record.observations(),
            delivered,
            detail="the parent's recoverable Positions remain recoverable in the child, "
            "and every declared binding survives the allocation",
        )
    if isinstance(record, BacktrackRecord):
        return _check(
            "return-preservation",
            record.as_item(),
            record.observations(),
            delivered,
            detail="the return is a forward step: the target Position is where "
            "execution now is, and nothing prior was mutated",
        )
    raise TypeError(f"no preservation obligation is defined for {type(record).__name__}")


def fold_declares_its_sources(
    record: FoldRecord, *, available: "Iterable[str]"
) -> ObligationResult:
    """**D4** — a fold may only retain what it declared it folded.

    The check that stops a fold satisfying its promise by pointing at content it never
    claimed to compress. It is not hypothetical: the experiment tree's own control for
    this shape had to be built twice, because the first version carried the ledger
    durably *as well as* caching it and therefore measured nothing.
    """
    present = set(available)
    named = {
        artifact
        for artifact in (
            FoldRecord.artifact_of_retained(entry) for entry in record.retains
        )
        if artifact is not None
    }
    undeclared = tuple(sorted(artifact for artifact in named if artifact not in set(record.folded_from)))
    missing_sources = tuple(sorted(artifact for artifact in record.folded_from if artifact not in present))
    return ObligationResult(
        obligation="fold-declares-its-sources",
        subject=record.as_item(),
        declared=tuple(sorted(named)),
        delivered=tuple(sorted(set(record.folded_from))),
        missing=undeclared + missing_sources,
        detail="a retained fact must name an artifact the fold declared it folded, and "
        "that artifact must be present",
    )


def fold_carries_what_it_declared(
    record: FoldRecord, *, carried: "Mapping[str, Mapping[str, str]]"
) -> ObligationResult:
    """The **content** half of Law E16, checked against what was actually carried.

    ``carried`` maps ``artifact_id -> {key: value}`` — the ledger the fold wrote into
    durable content. A declared-retained fact is honoured only if the ledger holds it
    with that value.
    """
    materializable = set(FoldRecord.retained_names(carried))
    return _check(
        "fold-carries-what-it-declared",
        record.as_item(),
        record.retains,
        materializable,
        detail="every fact the fold declared it retained is present in the carried ledger",
    )


def check_fold_preservation(
    record: FoldRecord, *, delivered: "Iterable[str]"
) -> ObligationResult:
    """**Law E16, both halves**, against whatever the caller's route delivered.

    The declared subject is the fold's own declaration *and* every fact its manifest
    promises:

    ```text
    declaration half   fold:<id>@<declaredBy>, summary:<id>:<content>,
                       coverage:<id>:<set>
    content half       every entry in retains
    ```

    Both, because a law that checks one is measurably weaker than it claims — in the
    flattering direction, since a fold that declares nothing at all passes a
    content-only check. `missing_declaration` and `missing_content` on the result say
    which half failed, so a reader can tell "the fold kept nothing" from "nothing could
    read what it promised".
    """
    return _check(
        "fold-preservation",
        record.as_item(),
        record.observations(),
        delivered,
        detail="Law E16: the fold's declaration and its declared-retained facts remain "
        "derivable through a declared route",
    )


def operation_recorded(kind: str) -> ObligationResult:
    """The obligation an operation owes whether or not its record survived.

    This exists because of a **vacuous pass**, found by composing the three operations
    rather than exercising them one at a time.

    ``check_all`` checks the obligations of the records it is given. Give it none and it
    returns none — and a runner whose assertion is *"no obligation failed"* then reports
    PASS for a continuity that performed three operations and recorded nothing at all. M4's
    Audit A closed the neighbouring hole, where a law checking only a manifest's content
    passed a fold that declared nothing; this is the same failure one level down, where
    the subject is absent rather than empty and there is no manifest to check in the
    first place.

    It is the shape the module's own docstring warns about from the other side — *a fold
    that declares a retention promise and carries nothing looks completely successful* —
    and it is why ``expected`` is a parameter of :func:`check_all` rather than an
    assumption: **only the caller knows what it performed.**
    """
    subject = f"<absent:{kind}>"
    return ObligationResult(
        obligation="operation-recorded",
        subject=subject,
        declared=(f"record:{kind}",),
        delivered=(),
        missing=(f"record:{kind}",),
        detail=f"an {kind!r} operation was performed and left no readable record: no "
        f"obligation could be checked, which is not the same as an obligation being met",
    )


def check_all(
    records: "Iterable[Any]",
    *,
    delivered: "Iterable[str]",
    expected: "Iterable[str]" = (),
) -> "tuple[ObligationResult, ...]":
    """Every obligation the given records owe, against one delivered set.

    ``expected`` names the operation kinds the caller knows it performed — ``"allocate"``,
    ``"backtrack"``, ``"fold"``. Every expected kind that left no readable record
    contributes an :func:`operation_recorded` failure instead of contributing silence.

    Leave ``expected`` empty and the check is *records-in, verdicts-out*: it will not
    invent an expectation, and it will pass an empty continuity. That is the right
    default for a caller checking one record, and the wrong one for a conformance
    runner — which is why the vacuity is named here rather than defaulted away.

    The per-record functions above are what a caller uses when it needs to know *which*
    route supplied an answer.
    """
    records = tuple(records)
    results = []
    for record in records:
        if isinstance(record, FoldRecord):
            results.append(check_fold_preservation(record, delivered=delivered))
        elif isinstance(record, (BranchAllocation, BacktrackRecord)):
            results.append(check_preservation(record, delivered=delivered))

    present = {getattr(record, "kind", "") for record in records}
    for kind in sorted(set(expected)):
        if kind not in present:
            results.append(operation_recorded(kind))
    return tuple(results)


__all__ = [
    "HALF_CONTENT",
    "HALF_DECLARATION",
    "ObligationResult",
    "check_all",
    "check_fold_preservation",
    "check_preservation",
    "fold_carries_what_it_declared",
    "fold_declares_its_sources",
    "operation_recorded",
]
