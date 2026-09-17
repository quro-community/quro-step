"""The three declared records — plain frozen dataclasses, no Kernel types inside.

Each is what an upper-layer operation *declares it did*. The Kernel never sees one:
it is carried in a payload, and every reader in :mod:`.channels` reads it back by
content.

**Every field is load-bearing**, in the sense that exactly one case family fails if it
is absent — `docs/design/Q4-Kernel-Upper-Layer-Decisions.md` `UD-4` carries the table.
A field with no case that fails without it would be a field added on speculation, and
the design's own minimal-model discipline (v0.2's "no field added to any existing
object because it might be useful") is why none is here.

The `(channel, projection)` pair every record carries is F18's mandatory declaration,
not machinery invented for these operations: a durable fact that does not say how it
becomes reachable is measurably unreachable from a state-only continuation. Measured
three times — M2's R2 family, M3's B2 family, M4's AF2 family — and the asymmetry
between the three channels is why `UD-3` picks `semantic-record` as the default.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

# -- the three realization channels ------------------------------------------
#
# The same three Kernel extension slots Milestone 2 declared and every later
# milestone reused. Named here identically so a record written by one layer is
# readable by another; the *readers* are this package's, because a production
# module should not depend on a disposable experiment's decoder.

#: ``ExecutionContinuity.record_evidence`` → ``History``. The only channel the
#: Kernel's own reference projection publishes, so a fact declared here reaches a
#: state-only continuation without domain code.
CH_RECORD = "semantic-record"
#: The ``Provenance`` a registration carries. Subject-centred: it attaches to the
#: Artifact being registered.
CH_PROVENANCE = "provenance-relation"
#: ``Artifact.payload.data`` — what an artifact declares about itself.
CH_ARTIFACT = "artifact-payload"

CHANNELS = (CH_RECORD, CH_PROVENANCE, CH_ARTIFACT)

#: The payload key a record occupies. One key with a `kind` discriminator, rather
#: than one key per record type: the reader is then a single function, and *which
#: operation this is* is stated by the record instead of implied by where it sits.
RECORD_KEY = "continuity-op"

#: Projection policies a record may declare. `domain` means the domain publishes it
#: through its own projection; `none` means it relies on the Kernel's reference
#: projection (which publishes `semantic-record` and nothing else); `on-demand` means
#: it is materialised through a resource the domain declares reachable.
PROJ_NONE = "none"
PROJ_DOMAIN = "domain"
PROJ_ON_DEMAND = "on-demand"
PROJECTIONS = (PROJ_NONE, PROJ_DOMAIN, PROJ_ON_DEMAND)


def _strings(values: "Any") -> "tuple[str, ...]":
    return tuple(str(value) for value in (values or ()))


def _pairs(values: "Any") -> "tuple[tuple[str, str], ...]":
    return tuple((str(key), str(value)) for key, value in (values or ()))


class ContinuityRecord:
    """Common surface: a kind token and the declared ``(channel, projection)`` pair.

    A plain mixin, not a dataclass: the three records are frozen dataclasses in their
    own right, and inheriting from a dataclass base would couple their ``__init__``
    shapes. It exists so ``isinstance`` works and so ``channel``/``projection`` have
    one implementation rather than three.

    The first version of this module declared the protocol in the docstring and had
    the records simply *resemble* it — so ``record.channel`` raised ``AttributeError``
    on the first call that used it. A protocol stated in prose is not a protocol.
    """

    kind: str = ""

    def as_dict(self) -> dict:  # pragma: no cover - overridden
        raise NotImplementedError

    def as_item(self) -> str:  # pragma: no cover - overridden
        raise NotImplementedError

    def observations(self) -> "tuple[str, ...]":
        """**Every** observation name this record declares. One definition, two users.

        The preservation checks require a delivered set that contains these names; a
        projection publishing a record's facts needs to produce exactly them. Both
        sides call this method, so a check and its subject cannot drift.

        They could, before. `FoldRecord` carried `as_item` / `summary_item` /
        `coverage_item` and the fold check *called* them, while the two other checks
        built `lineage:` / `inherited:` / `governed-by:` / `returned-to:` as f-strings
        **inside the check function**. A consumer writing the projection the check
        demanded had to copy those f-strings out of the check — and composition is
        where that was found, because composition is the first thing that has to make
        the two ends agree rather than exercising them one at a time.
        """
        return (self.as_item(),)

    @property
    def channel(self) -> str:
        """Which of the three realization channels carries this record."""
        return getattr(self, "realization_channel", CH_RECORD)

    @property
    def projection(self) -> str:
        """Which projection the domain declares for it."""
        return getattr(self, "projection_policy", PROJ_NONE)


@dataclass(frozen=True)
class BranchAllocation(ContinuityRecord):
    """A declared branch allocation — Fork's *fact*, never Fork's *resolution*.

    Nothing here is a Kernel type. ``inherited_positions`` is an opaque list of
    position labels: the Kernel does not read it, and the domain reads it only to
    compare against what the continuity actually carries.
    """

    child_branch: str
    parent_branch: str
    inherited_positions: "tuple[str, ...]" = ()
    #: ``(branch, identity)`` pairs the domain declares govern each branch.
    #: Branch-scoped by `UD-2`: the binding is a property of the branch.
    bindings: "tuple[tuple[str, str], ...]" = ()
    declared_by: str = ""
    realization_channel: str = CH_RECORD
    projection_policy: str = PROJ_DOMAIN

    kind = "allocate"

    def __post_init__(self) -> None:
        for name in ("child_branch", "parent_branch", "declared_by"):
            object.__setattr__(self, name, str(getattr(self, name)))
        object.__setattr__(self, "inherited_positions", _strings(self.inherited_positions))
        object.__setattr__(self, "bindings", _pairs(self.bindings))

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "childBranch": self.child_branch,
            "parentBranch": self.parent_branch,
            "inheritedPositions": list(self.inherited_positions),
            "bindings": [list(pair) for pair in self.bindings],
            "declaredBy": self.declared_by,
            "realizationChannel": self.realization_channel,
            "projectionPolicy": self.projection_policy,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BranchAllocation":
        return cls(
            child_branch=data["childBranch"],
            parent_branch=data["parentBranch"],
            inherited_positions=_strings(data.get("inheritedPositions", ())),
            bindings=_pairs(data.get("bindings", ())),
            declared_by=data.get("declaredBy", ""),
            realization_channel=data.get("realizationChannel", CH_RECORD),
            projection_policy=data.get("projectionPolicy", PROJ_DOMAIN),
        )

    def as_item(self) -> str:
        """The observation name — content, never identity, never a fingerprint."""
        return f"allocated:{self.child_branch}<-{self.parent_branch}@{self.declared_by}"

    def observations(self) -> "tuple[str, ...]":
        return (
            self.as_item(),
            f"lineage:{self.child_branch}<-{self.parent_branch}",
            *(
                f"inherited:{self.child_branch}:{position}"
                for position in self.inherited_positions
            ),
            *(f"governed-by:{branch}={identity}" for branch, identity in self.bindings),
        )

    def binding_of(self, branch: str) -> "str | None":
        for name, identity in self.bindings:
            if name == branch:
                return identity
        return None

    def with_channel(self, channel: str, projection: str = PROJ_DOMAIN) -> "BranchAllocation":
        return replace(self, realization_channel=channel, projection_policy=projection)


@dataclass(frozen=True)
class BacktrackRecord(ContinuityRecord):
    """A declared return to a prior recoverable Position.

    ``kind`` is a domain-defined opaque token — nothing in this package interprets
    it, which is what makes "the Kernel must not resolve a return target" checkable
    rather than aspirational.
    """

    kind_token: str
    from_position: str
    to_position: str
    declared_by: str = ""
    realization_channel: str = CH_RECORD
    projection_policy: str = PROJ_DOMAIN

    kind = "backtrack"

    def __post_init__(self) -> None:
        for name in ("kind_token", "from_position", "to_position", "declared_by"):
            object.__setattr__(self, name, str(getattr(self, name)))

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "returnKind": self.kind_token,
            "fromPosition": self.from_position,
            "toPosition": self.to_position,
            "declaredBy": self.declared_by,
            "realizationChannel": self.realization_channel,
            "projectionPolicy": self.projection_policy,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BacktrackRecord":
        return cls(
            kind_token=data.get("returnKind", ""),
            from_position=data["fromPosition"],
            to_position=data["toPosition"],
            declared_by=data.get("declaredBy", ""),
            realization_channel=data.get("realizationChannel", CH_RECORD),
            projection_policy=data.get("projectionPolicy", PROJ_DOMAIN),
        )

    def as_item(self) -> str:
        return (
            f"backtrack:{self.kind_token}:{self.from_position}->{self.to_position}"
            f"@{self.declared_by}"
        )

    def observations(self) -> "tuple[str, ...]":
        return (self.as_item(), f"returned-to:{self.to_position}")

    def with_channel(self, channel: str, projection: str = PROJ_DOMAIN) -> "BacktrackRecord":
        return replace(self, realization_channel=channel, projection_policy=projection)


@dataclass(frozen=True)
class FoldRecord(ContinuityRecord):
    """A declared compression of pre-fold content — Fold's *fact*.

    The obligation this record states is **two-halved** (Baseline v1.0 `AR-2`): the
    declaration that the fold happened and what it covered, *and* the content it
    promised to carry. They fail independently, and M4's own first formulation of the
    law checked only the second — which passed a fold that recorded nothing at all
    until Audit A caught it.
    """

    fold_id: str
    #: D4 — what the fold took from. A fold that omits a source cannot retain its
    #: content: it would be promising something it never claimed to compress.
    folded_from: "tuple[str, ...]" = ()
    #: The opaque declared dependency set. Same status as a fingerprint's declared
    #: coverage: the Kernel never computes it and never defines it.
    coverage: "tuple[str, ...]" = ()
    summary: "tuple[tuple[str, str], ...]" = ()
    #: The facts this fold promises remain derivable. Checked by `law.py`.
    retains: "tuple[str, ...]" = ()
    declared_by: str = ""
    realization_channel: str = CH_RECORD
    projection_policy: str = PROJ_DOMAIN

    kind = "fold"

    #: The **content-half** vocabulary: how a carried fact is named. The declaration half
    #: is `observations()`; this is the other half, and it was the third instance of a
    #: vocabulary minted inside a check rather than on the record — found by the same
    #: reverse injection that found the first two, after the first fix looked complete.
    RETAINED_PREFIX = "retained:"

    @staticmethod
    def retained_name(artifact_id: str, key: str, value: str) -> str:
        """The observation name of one carried fact."""
        return f"{FoldRecord.RETAINED_PREFIX}{artifact_id}:{key}={value}"

    @classmethod
    def retained_names(cls, carried: "Mapping[str, Mapping[str, str]]") -> "tuple[str, ...]":
        """Every observation name a carried ledger materializes.

        The inverse of what a fold writes: a consumer holding a ledger asks the record
        what names it produces, rather than reproducing the format from a check.
        """
        return tuple(
            cls.retained_name(artifact_id, key, value)
            for artifact_id, facts in carried.items()
            for key, value in facts.items()
        )

    @staticmethod
    def artifact_of_retained(entry: str) -> "str | None":
        """The Artifact a retained-fact name points at, or ``None`` if it is not one."""
        if not entry.startswith(FoldRecord.RETAINED_PREFIX):
            return None
        remainder = entry[len(FoldRecord.RETAINED_PREFIX):]
        artifact_id = remainder.split(":", 1)[0]
        return artifact_id or None

    def __post_init__(self) -> None:
        for name in ("fold_id", "declared_by"):
            object.__setattr__(self, name, str(getattr(self, name)))
        object.__setattr__(self, "folded_from", _strings(self.folded_from))
        object.__setattr__(self, "coverage", _strings(self.coverage))
        object.__setattr__(self, "summary", _pairs(self.summary))
        object.__setattr__(self, "retains", _strings(self.retains))

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "foldId": self.fold_id,
            "foldedFrom": list(self.folded_from),
            "coverage": list(self.coverage),
            "summary": [list(pair) for pair in self.summary],
            "retains": list(self.retains),
            "declaredBy": self.declared_by,
            "realizationChannel": self.realization_channel,
            "projectionPolicy": self.projection_policy,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FoldRecord":
        return cls(
            fold_id=data["foldId"],
            folded_from=_strings(data.get("foldedFrom", ())),
            coverage=_strings(data.get("coverage", ())),
            summary=_pairs(data.get("summary", ())),
            retains=_strings(data.get("retains", ())),
            declared_by=data.get("declaredBy", ""),
            realization_channel=data.get("realizationChannel", CH_RECORD),
            projection_policy=data.get("projectionPolicy", PROJ_DOMAIN),
        )

    def as_item(self) -> str:
        return f"fold:{self.fold_id}@{self.declared_by}"

    def summary_item(self) -> str:
        rendered = ";".join(f"{key}={value}" for key, value in self.summary)
        return f"summary:{self.fold_id}:{rendered}"

    def coverage_item(self) -> str:
        return f"coverage:{self.fold_id}:{','.join(sorted(self.coverage))}"

    def observations(self) -> "tuple[str, ...]":
        """Both halves, named: the declaration and the facts it promised to carry."""
        return (
            self.as_item(),
            self.summary_item(),
            self.coverage_item(),
            *self.retains,
        )

    def declares(self, entry: str) -> bool:
        return entry in self.retains

    def with_channel(self, channel: str, projection: str = PROJ_DOMAIN) -> "FoldRecord":
        return replace(self, realization_channel=channel, projection_policy=projection)

    def with_retains(self, entries: "tuple[str, ...]") -> "FoldRecord":
        return replace(self, retains=_strings(entries))


#: Every record type this package can carry, so a reader can iterate or dispatch.
RECORD_TYPES = (BranchAllocation, BacktrackRecord, FoldRecord)

_KINDS = {record_type.kind: record_type for record_type in RECORD_TYPES}


def record_from_dict(data: Mapping[str, Any]) -> "ContinuityRecord | None":
    """Decode whichever record ``data`` carries, or ``None`` for a foreign payload.

    Returning ``None`` rather than raising is deliberate: a payload that carries
    something else is *not this package's record*, and a reader that crashed on one
    would make a foreign payload look like a corrupt one.
    """
    record_type = _KINDS.get(str(data.get("kind", "")))
    if record_type is None:
        return None
    return record_type.from_dict(data)


def record_from_payload(payload: "Mapping[str, Any] | None") -> "ContinuityRecord | None":
    """Decode a record out of a payload that carries one under :data:`RECORD_KEY`."""
    if not isinstance(payload, Mapping):
        return None
    inner = payload.get(RECORD_KEY)
    if not isinstance(inner, Mapping):
        return None
    return record_from_dict(inner)


__all__ = [
    "BranchAllocation",
    "BacktrackRecord",
    "CH_ARTIFACT",
    "CH_PROVENANCE",
    "CH_RECORD",
    "CHANNELS",
    "ContinuityRecord",
    "FoldRecord",
    "PROJECTIONS",
    "PROJ_DOMAIN",
    "PROJ_NONE",
    "PROJ_ON_DEMAND",
    "RECORD_KEY",
    "RECORD_TYPES",
    "record_from_dict",
    "record_from_payload",
]
