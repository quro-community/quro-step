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
        declared = (
            record.as_item(),
            f"lineage:{record.child_branch}<-{record.parent_branch}",
            *(f"inherited:{record.child_branch}:{position}" for position in record.inherited_positions),
            *(f"governed-by:{branch}={identity}" for branch, identity in record.bindings),
        )
        return _check(
            "branch-allocation-preservation",
            record.as_item(),
            declared,
            delivered,
            detail="the parent's recoverable Positions remain recoverable in the child, "
            "and every declared binding survives the allocation",
        )
    if isinstance(record, BacktrackRecord):
        declared = (record.as_item(), f"returned-to:{record.to_position}")
        return _check(
            "return-preservation",
            record.as_item(),
            declared,
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
        entry.split(":", 2)[1]
        for entry in record.retains
        if entry.startswith("retained:") and entry.count(":") >= 2
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
    materializable = {
        f"retained:{artifact_id}:{key}={value}"
        for artifact_id, facts in carried.items()
        for key, value in facts.items()
    }
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
    declared = (
        record.as_item(),
        record.summary_item(),
        record.coverage_item(),
        *record.retains,
    )
    return _check(
        "fold-preservation",
        record.as_item(),
        declared,
        delivered,
        detail="Law E16: the fold's declaration and its declared-retained facts remain "
        "derivable through a declared route",
    )


def check_all(records: "Iterable[Any]", *, delivered: "Iterable[str]") -> "tuple[ObligationResult, ...]":
    """Every obligation the given records owe, against one delivered set.

    The convenience a conformance runner wants; the per-record functions above are what
    a caller uses when it needs to know *which* route supplied an answer.
    """
    results = []
    for record in records:
        if isinstance(record, FoldRecord):
            results.append(check_fold_preservation(record, delivered=delivered))
        elif isinstance(record, (BranchAllocation, BacktrackRecord)):
            results.append(check_preservation(record, delivered=delivered))
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
]
