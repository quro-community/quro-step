"""Reading and writing a record through each of the three realization channels.

Every reader takes a real ``ExecutionContinuity`` and reads the durable object. None
caches, and none reaches into a runtime object — a reader that could see runtime
state would report success for an operation that externalized nothing.

The channel asymmetry these readers expose is the measurement `UD-3` rests on, and it
is worth stating where the code lives rather than only in a document:

```text
semantic-record       reaches the mounted payload through the Kernel's OWN reference
                      projection — no domain code needed
provenance-relation   does NOT reach the payload (which carries Artifact NAMES, not
                      their provenance detail); it needs a declared domain projection
artifact-payload      reaches the payload only through a declared projection or a
                      declared reachable on-demand resource
```

So `CH_RECORD` is the default, and a record declared into either other channel is
buying something specific: a provenance-shaped relation genuinely belongs on the
Artifact being registered, and a fold's carried content genuinely belongs in the
summary's own payload. What it is *paying* is that the domain must then declare a
projection, or a state-only continuation cannot reach it.

These readers are this package's own. The experiment trees have their own decoders,
and a production module must not depend on a directory the project is free to delete
(v0.2 §35's reverse-dependency rule, which `tests/test_continuity_ops.py::ReverseDependencyIsForbidden` checks).
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from quro.kernel import CausalRelation, Provenance, ProvenanceDetail

from .records import (
    CH_ARTIFACT,
    CH_PROVENANCE,
    CH_RECORD,
    CHANNELS,
    RECORD_KEY,
    ContinuityRecord,
    FoldRecord,
    record_from_payload,
)

#: ``RelationKind.DOMAIN_DEFINED``'s value — the Kernel already names this kind; this
#: package introduces no relation kind of its own.
DOMAIN_DEFINED = "domain-defined"


# ---------------------------------------------------------------------------
# Write side
# ---------------------------------------------------------------------------


def encode_record(record: ContinuityRecord) -> dict:
    """The payload a record occupies, wherever it is carried."""
    return {RECORD_KEY: record.as_dict()}


def provenance_with_record(record: ContinuityRecord, position: Any, *, occurrence: int = 0) -> Provenance:
    """A ``Provenance`` whose detail slot carries a declared record.

    Subject-centred, because that is the shape the Kernel's slot has: the record
    attaches to *the Artifact being registered*. The relation kind stays the Kernel's
    own ``domain-defined``, and the record travels in ``detail``.
    """
    return Provenance(
        position=position,
        occurrence=occurrence,
        relation=CausalRelation(kind=DOMAIN_DEFINED),
        detail=ProvenanceDetail(
            data={
                "declaredBy": getattr(record, "declared_by", ""),
                RECORD_KEY: record.as_dict(),
            }
        ),
    )


def artifact_data_with_record(record: ContinuityRecord, data: "Mapping[str, Any] | None" = None) -> dict:
    """The payload an Artifact-shaped carrier should be created with.

    Kept as a function rather than a convention so a caller cannot forget the key and
    produce a record that is durable but unreadable — the shape NCF-6 was built to
    catch in the experiment tree.
    """
    payload = dict(data or {})
    payload[RECORD_KEY] = record.as_dict()
    return payload


# ---------------------------------------------------------------------------
# Read side — one reader per channel
# ---------------------------------------------------------------------------


def records_from_records(continuity: Any) -> "tuple[ContinuityRecord, ...]":
    """Records carried as continuity evidence (the ``semantic-record`` channel)."""
    found = []
    for entry in continuity.history.semantic_records():
        decoded = record_from_payload(dict(entry.payload))
        if decoded is not None:
            found.append(decoded)
    return tuple(found)


def records_from_provenance(continuity: Any) -> "tuple[ContinuityRecord, ...]":
    """Records carried by the ``Provenance`` of a registered Artifact."""
    found = []
    for artifact in continuity.artifacts:
        provenance = getattr(artifact, "provenance", None)
        if provenance is None:
            continue
        decoded = record_from_payload(dict(getattr(provenance.detail, "data", {}) or {}))
        if decoded is not None:
            found.append(decoded)
    return tuple(found)


def records_from_artifacts(continuity: Any) -> "tuple[ContinuityRecord, ...]":
    """Records an Artifact declares about itself (the ``artifact-payload`` channel)."""
    found = []
    for artifact in continuity.artifacts:
        payload = dict(getattr(getattr(artifact, "payload", None), "data", {}) or {})
        decoded = record_from_payload(payload)
        if decoded is not None:
            found.append(decoded)
    return tuple(found)


_READERS = {
    CH_RECORD: records_from_records,
    CH_PROVENANCE: records_from_provenance,
    CH_ARTIFACT: records_from_artifacts,
}


def read_records(continuity: Any, channel: str) -> "tuple[ContinuityRecord, ...]":
    """Read one channel. An unknown channel is a caller error, not an empty answer."""
    reader = _READERS.get(channel)
    if reader is None:
        raise ValueError(f"unknown record channel: {channel!r}")
    return reader(continuity)


def read_records_any(
    continuity: Any, channels: "Iterable[str]" = CHANNELS
) -> "tuple[ContinuityRecord, ...]":
    """The union over channels, de-duplicated **by content**.

    By content, never by identity and never by a fingerprint: the same record in two
    channels is one record, and two records differing only in their ``declared_by``
    are two records.

    A bare channel name is one channel, not a sequence of its characters — refused by
    construction here rather than left for a caller to rediscover, because silently
    iterating a string reports "no records" for a reader that asked for exactly one.
    """
    if isinstance(channels, str):
        channels = (channels,)
    seen: "dict[str, ContinuityRecord]" = {}
    for channel in channels:
        for record in read_records(continuity, channel):
            seen.setdefault(_content_key(record), record)
    return tuple(seen.values())


def read_fold_records(
    continuity: Any, channels: "Iterable[str]" = CHANNELS
) -> "tuple[FoldRecord, ...]":
    """Every declared fold the continuity carries, across the given channels."""
    return tuple(
        record
        for record in read_records_any(continuity, channels)
        if isinstance(record, FoldRecord)
    )


def records_reachable_from_state(payload: "Mapping[str, Any] | None") -> "tuple[ContinuityRecord, ...]":
    """Records a *state-only* continuation can see, through the declared routes.

    Two routes, and they are not the same one counted twice:

    ``evidence``       the Kernel's own reference projection publishing semantic
                       records — so a ``semantic-record`` fact reaches a state with no
                       domain code at all
    ``records``        a domain projection's own key — how the other two channels reach
                       a state-only consumer

    Which routes exist per channel is an *observation*, not an assumption, which is why
    they are read separately here even though the caller usually unions them.
    """
    data = dict(payload or {})
    found = []
    for key in ("evidence", "records"):
        for entry in data.get(key, ()) or ():
            decoded = record_from_payload(entry if isinstance(entry, Mapping) else None)
            if decoded is not None:
                found.append(decoded)
    return tuple(found)


def _content_key(record: ContinuityRecord) -> str:
    """A hashable key over the record's *declared content*, never its identity."""
    return repr(sorted((str(key), repr(value)) for key, value in record.as_dict().items()))


__all__ = [
    "CH_ARTIFACT",
    "CH_PROVENANCE",
    "CH_RECORD",
    "CHANNELS",
    "DOMAIN_DEFINED",
    "artifact_data_with_record",
    "encode_record",
    "provenance_with_record",
    "read_fold_records",
    "read_records",
    "read_records_any",
    "records_from_artifacts",
    "records_from_provenance",
    "records_from_records",
    "records_reachable_from_state",
]
