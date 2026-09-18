"""The on-demand route: what a record declared reachable, and how it is reached.

`continuity_ops` declares three projection policies. Two of them already have readers
in that package: `PROJ_NONE` is the Kernel's own reference projection, and
`PROJ_DOMAIN` is a domain's `project` hook. The third —

```text
PROJ_ON_DEMAND    materialised through a resource the domain declares reachable
```

— has been **a name with no mechanism** since it was written. `law.py` says the
preservation obligations are stated over an observation vocabulary "so the same check
runs against a mounted state, a domain projection, **a declared on-demand resource**,
or a fresh interpreter", and nothing in `src/` has ever produced that fourth thing.

This module is that mechanism's declaration half. It answers one question —

```text
which durable resources did a record declare askable-for?
```

— and answers it **by deriving from the records**, never from an argument. A store
built from a caller-supplied resource list would be a declaration living beside the
records instead of in them, and the route could then be widened without touching a
record. One producer, not two.

**Nothing here is published into `ExecutionState`.** For an on-demand fact, a state
carrying a reference to it would *be* the second declaration this module exists to
avoid: the route's whole content is that the fact is NOT reachable by reading the
state, and is reachable only by asking. The asymmetry is the mechanism.

A refusal is a value, not an exception, for the same reason `operations.py` gives: a
caller must be able to tell which layer declined. `ContextError` is reserved for caller
mistakes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from quro.continuity_ops import (
    CARRIED_KEY,
    PROJECTIONS,
    PROJ_ON_DEMAND,
    ContinuityRecord,
    FoldRecord,
    read_records_any,
)

#: Nothing declared this askable-for. The route does not exist for it.
UNDECLARED = "undeclared"

#: Something declared it, and the durable content is not there.
#:
#: `undeclared` and `unavailable` are **not** the same answer, and collapsing them is
#: the read-side form of the defect M4 found when its first formulation of E16 checked
#: only the content half: "the fold kept nothing" and "nothing could read what it
#: promised" are different facts about different layers.
UNAVAILABLE = "unavailable"

REFUSAL_KINDS = (UNDECLARED, UNAVAILABLE)


class ContextError(RuntimeError):
    """A caller mistake — not a refusal.

    Deliberately not used for a route refusal: those come back as a ``RouteRefusal``
    value, so a caller can always tell a malformed request from a legitimate one that
    the durable state cannot satisfy.
    """


@dataclass(frozen=True)
class RouteRefusal:
    """Why a resource could not be delivered, with the facts rather than a boolean."""

    kind: str
    subject: str
    detail: str = ""

    def __post_init__(self) -> None:
        if self.kind not in REFUSAL_KINDS:
            raise ContextError(
                f"unknown refusal kind: {self.kind!r}; expected one of {REFUSAL_KINDS}"
            )
        object.__setattr__(self, "subject", str(self.subject))

    def as_dict(self) -> dict:
        return {"kind": self.kind, "subject": self.subject, "detail": self.detail}


# ---------------------------------------------------------------------------
# The declaration half — derived from the records, never supplied
# ---------------------------------------------------------------------------


def declared_records(continuity: Any) -> "tuple[ContinuityRecord, ...]":
    """Every record in ``continuity`` that declares the on-demand route.

    Read through ``read_records_any`` — the package's own channel readers — so this
    function cannot see a record that a declared channel does not carry. A reader that
    reached into ``continuity`` some other way would be the second access path this
    package is built to not be.
    """
    return tuple(
        record
        for record in read_records_any(continuity)
        if record.projection == PROJ_ON_DEMAND
    )


def declared_resources(continuity: Any) -> "tuple[str, ...]":
    """The Artifact names a record declared askable-for, sorted and de-duplicated.

    Derived from the record's own retained-fact names — ``FoldRecord.artifact_of_retained``,
    the inverse of the naming function the fold wrote with — **intersected with what
    the record declared it folded** (D4). The intersection is the whole point: a
    resource is askable-for only if the record claimed to compress it, so a fold cannot
    make reachable something it never declared a source.

    An artifact name that appears in a record's ``retains`` but not in its
    ``folded_from`` is a D4 violation and is *not* admitted here. It is reported by
    ``law.fold_declares_its_sources`` instead — one check, one subject.
    """
    names = set()
    for record in declared_records(continuity):
        if not isinstance(record, FoldRecord):
            # A record that declares the route but retains no resources declares no
            # resources. Returning nothing is the correct answer, not a gap: a branch
            # allocation and a return have nothing to materialise.
            continue
        declared_sources = set(record.folded_from)
        for entry in record.retains:
            artifact_id = FoldRecord.artifact_of_retained(entry)
            if artifact_id is not None and artifact_id in declared_sources:
                names.add(artifact_id)
    return tuple(sorted(names))


def declares(continuity: Any, resource: str) -> bool:
    """Whether ``continuity`` declares ``resource`` askable-for."""
    return str(resource) in declared_resources(continuity)


# ---------------------------------------------------------------------------
# The delivery half
# ---------------------------------------------------------------------------


def carried_ledger(continuity: Any) -> "dict[str, dict[str, str]]":
    """The content a fold carried forward, read from the artifacts that carry it.

    Deliberately reads **every** artifact rather than the one the fold registered:
    `FoldRecord` carries no pointer to its summary, and hard-coding an id here would
    make the reader depend on a fixture detail rather than on declared content. This is
    the same decision the fold experiment made and defended; an artifact carrying no
    ``CARRIED_KEY`` simply contributes nothing.

    A missing ledger is not an error and is never smoothed into an empty one silently —
    the caller must be able to tell "the fold carried nothing" from "the fold promised
    nothing readable".
    """
    ledger: "dict[str, dict[str, str]]" = {}
    for artifact in getattr(continuity, "artifacts", ()) or ():
        # Direct attribute access, not ``getattr(artifact, "payload", None)``: an
        # Artifact always has a payload, and spelling it as a string literal would make
        # this read invisible to the source scan that keeps the set of content readers
        # closed. A detector that cannot see a read cannot bound it.
        payload = dict(artifact.payload.data)
        carried = payload.get(CARRIED_KEY)
        if not isinstance(carried, Mapping):
            continue
        for artifact_id, entries in carried.items():
            if not isinstance(entries, Mapping):
                continue
            bucket = ledger.setdefault(str(artifact_id), {})
            for key, value in entries.items():
                bucket[str(key)] = str(value)
    return ledger


def deliver_through(
    store: Any, resources: "Iterable[str] | None" = None
) -> "tuple[str, ...]":
    """The observation names the on-demand route *durably* materialises.

    ``resources`` is what the caller asked for; omitted, the store's own declaration is
    used. Naming them explicitly is how an agent's *choice* is expressed — §26's flow is
    ``summary → HINTS → agent chooses → resource access``, and a function that always
    delivered everything would delete the agent from its own architecture.

    **Read from the carried ledger, never from the record's declaration.** The first
    version of this function rendered the names off ``record.retains`` — which is the
    fold's *promise*, not its *content* — and so reported a route that delivered
    everything a fold claimed, including when nothing had been made durable at all. It
    is the mirror of the defect M4's Audit A caught: a check that reads only the
    declaration passes a fold that carried nothing, and a check that reads only the
    carrying passes a fold that declared nothing. Both halves are read here, and the
    names come from the ledger.

    The rendering is the **record's** own naming function, asked of the record type, so
    nothing in this package mints an observation name. A consumer that rebuilt these
    strings here would be the third instance of the defect that took this repository two
    reverse injections to find.
    """
    wanted = set(
        store.resources() if resources is None else (str(item) for item in resources)
    )
    ledger = {
        artifact_id: dict(entries)
        for artifact_id, entries in carried_ledger(store.continuity).items()
        if artifact_id in wanted
    }
    return tuple(sorted(set(FoldRecord.retained_names(ledger))))


__all__ = [
    "ContextError",
    "REFUSAL_KINDS",
    "RouteRefusal",
    "UNAVAILABLE",
    "UNDECLARED",
    "carried_ledger",
    "declared_records",
    "declared_resources",
    "declares",
    "deliver_through",
]
