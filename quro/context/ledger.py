"""The ledger: the small file a fresh process must have, and the bodies it must not.

Backlog item `B-14`. `encode_model` carries `history` **and** every artifact payload, so
one write costs O(everything) and a run writes O(n²) — append-only semantics over a
whole-payload rewrite. It breaks nothing at fifteen rounds, which is why it has not
surfaced; what it breaks is the architecture's own thesis (*continuity is persisted
semantic state*) at the scale the thesis exists for.

The split is the one the read side already names:

```text
THE LEDGER   `(C, P)` without artifact bodies or plan definitions — small, rewritten
             whole, and references to immutable versions a fresh process can resolve
THE BODIES   one file per artifact, addressed by a name the ledger declares, written
             once and never rewritten
THE PLANS    one file per content-addressed plan version, referenced by branch and
             written once and never rewritten
```

## What this module does not do, and the check that keeps it that way

**It never touches an `Artifact.payload`.** Every payload access this pair needs is the
codec's, and this module moves the codec's *own encoding* — a split and a rejoin of a
plain dict. That is not a stylistic preference: `quro.context` ships a closed allow-list,
`CONTENT_READERS`, of the functions permitted to read payload content, checked by an AST
sweep in `checks.content_reader_names`. A ledger that reached into a payload would have
to be added to that list — and **widening an allow-list in the same change that a new
module trips it is structurally indistinguishable from weakening it**. Composing with
the codec rather than duplicating it is what keeps the list the length it is.

## The refusal that is the whole obligation (LL6)

An aggregate check that is handed no subjects evaluates none and reports no failures, so
"nothing failed" and "there was nothing to fail" must not be the same value. A ledger
whose artifact bodies were dropped is *well-formed* — `decode_continuity` reads
`data.get("artifacts", ())` and would rebuild a continuity with no artifacts at all,
reporting success.

So the marker is a dict and never an absent key, and **both** of these refuse by name:

```text
the payload does not declare where its bodies are        not split, or not a ledger
an entry names a body the caller did not supply          a declared body is missing
```

An empty artifact set is representable — it is a ledger whose manifest is an empty list —
and it is a different value from a ledger whose bodies went missing.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Mapping

from quro.kernel.persistence import decode_model, encode_model

from .layout import Layout

#: The key a ledger's artifact slot carries instead of a list. A dict with this key says
#: *the bodies are elsewhere and the manifest says where*; anything else is refused.
LEDGER_BODIES = "bodies"

#: The marker for a plan slot that has been split out of the ledger.
LEDGER_PLAN_VERSION = "version"

#: How much of a digest names a file. Sixteen hex characters is 64 bits — far past the
#: point where a collision inside one session's artifact set is a real possibility, and
#: short enough to read.
DIGEST_CHARS = 16


class LedgerError(ValueError):
    """The ledger cannot be read or written as declared — named, never guessed at."""


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------


def body_name(artifact_id: object) -> str:
    """The file name one artifact's body gets.

    A digest of the id rather than the id. Artifact ids are free-form and this model's
    own carry `:` (`fold::<unit><instance>`), so using one directly as a path component
    would need an escaping rule — and an escaping rule is a *second* place the id→file
    mapping is stated, which is precisely what the manifest exists to avoid. Deriving
    it leaves nothing to keep in sync.
    """
    digest = hashlib.sha256(str(artifact_id).encode("utf-8")).hexdigest()[:DIGEST_CHARS]
    return f"a{digest}.json"


def plan_name(encoded_plan: Mapping[str, Any]) -> str:
    """The immutable version name for one codec-encoded ``ExecutionPlan``."""
    material = json.dumps(encoded_plan, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:DIGEST_CHARS]
    return f"p{digest}.json"


def session_id(seed: Any) -> str:
    """A content address for a run, from whatever seed the caller declares.

    Content-addressed rather than timestamped, and the reason is an instrument rather
    than tidiness: the codec is deterministic — *"two equal continuities encode to equal
    payloads"* — so two runs of the same question over the same workspace with the same
    configuration either collide on one id and resume, or diverge, and the divergence is
    a **fact** rather than an argument. That is the only cheap way `UB-3` (a domain
    hook's determinism) has ever had of being observable.

    It holds only in a mechanical configuration; a model-backed policy or reader makes
    the run non-deterministic by construction, and the id will diverge for that reason
    and no other.
    """
    if isinstance(seed, str):
        material = seed
    else:
        try:
            material = json.dumps(seed, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise LedgerError(
                f"a seed must be a string or plain JSON, and this one is not: {exc}"
            ) from exc
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:DIGEST_CHARS]
    return f"s{digest}"


# ---------------------------------------------------------------------------
# Split and join — pure, over the codec's own encoding
# ---------------------------------------------------------------------------


def declared_bodies(envelope: Mapping[str, Any]) -> "tuple[tuple[str, str], ...]":
    """``(artifact id, body name)`` pairs the ledger declares, in artifact order.

    **The single place the manifest's shape is stated.** Both the writer of a body file
    and the reader that puts it back ask here, so the two ends cannot disagree about the
    format — which is what a duplicated walk would let them do (`LF-5`).

    Refuses rather than returning an empty tuple for a payload that declares nothing:
    an empty tuple is what a ledger with no artifacts legitimately returns, and the two
    must not be the same value.
    """
    inner = envelope.get("continuity")
    if not isinstance(inner, Mapping):
        raise LedgerError("this payload has no 'continuity'; it is not a codec envelope")
    declared = inner.get("artifacts")
    if not isinstance(declared, Mapping) or LEDGER_BODIES not in declared:
        raise LedgerError(
            "this payload does not declare where its artifact bodies are. A ledger "
            f"carries them under `artifacts`: {{{LEDGER_BODIES!r}: [...]}}; a bare list "
            "means the bodies are held inside it, and an absent key means nothing said "
            "— refusing rather than decoding an artifact set that is empty for a reason "
            "nothing stated."
        )
    manifest = declared[LEDGER_BODIES]
    if not isinstance(manifest, list):
        raise LedgerError(
            f"the body manifest is {type(manifest).__name__}, not a list: {manifest!r}"
        )
    pairs = []
    for entry in manifest:
        if not isinstance(entry, Mapping) or "body" not in entry:
            raise LedgerError(f"a manifest entry names no body: {entry!r}")
        pairs.append((str(entry.get("id", "")), str(entry["body"])))
    return tuple(pairs)


def declared_plans(envelope: Mapping[str, Any]) -> "tuple[tuple[str, str], ...]":
    """``(branch, version name)`` pairs the ledger declares, in branch order.

    A bare plan would decode successfully, but accepting one would make a session's
    cost grow with every round again. The ledger therefore carries only stable version
    references and refuses an unsplit plan definition.
    """
    inner = envelope.get("continuity")
    if not isinstance(inner, Mapping):
        raise LedgerError("this payload has no 'continuity'; it is not a codec envelope")
    declared = inner.get("plans")
    if not isinstance(declared, Mapping):
        raise LedgerError("this payload has no plan references; it is not a split ledger")
    pairs = []
    for branch, reference in sorted(declared.items()):
        if not isinstance(reference, Mapping) or set(reference) != {LEDGER_PLAN_VERSION}:
            raise LedgerError(
                f"the plan for branch {branch!r} is not a stable version reference: "
                f"{reference!r}"
            )
        pairs.append((str(branch), str(reference[LEDGER_PLAN_VERSION])))
    return tuple(pairs)


def split(
    continuity: Any, position: Any
) -> "tuple[dict, dict[str, dict], dict[str, dict]]":
    """``(ledger payload, artifact bodies, immutable plan versions)``. Pure.

    The codec's own :func:`encode_model` does the encoding; this separates what it
    produced. It is why nothing here reads a payload.
    """
    envelope = encode_model(continuity, position)
    inner = dict(envelope["continuity"])
    artifacts = inner.pop("artifacts", None)
    if not isinstance(artifacts, list):
        raise LedgerError(
            "the codec's continuity encoding carries no artifact list, so there is "
            "nothing to separate — this envelope has already been split, or the codec's "
            "shape has moved and this module did not."
        )
    bodies: "dict[str, dict]" = {}
    manifest = []
    for encoded in artifacts:
        name = body_name(encoded["id"])
        manifest.append({"id": str(encoded["id"]), "body": name})
        bodies[name] = encoded
    inner["artifacts"] = {LEDGER_BODIES: manifest}
    encoded_plans = inner.get("plans")
    if not isinstance(encoded_plans, Mapping):
        raise LedgerError("the codec's continuity encoding carries no plans mapping")
    plans: "dict[str, dict]" = {}
    references = {}
    for branch, encoded in encoded_plans.items():
        name = plan_name(encoded)
        plans[name] = encoded
        references[str(branch)] = {LEDGER_PLAN_VERSION: name}
    inner["plans"] = references
    return {**envelope, "continuity": inner}, bodies, plans


def join(
    envelope: Mapping[str, Any],
    bodies: Mapping[str, Any],
    plans: Mapping[str, Any],
    *,
    resolver: "Any | None" = None,
    factory: "Callable[..., Any] | None" = None,
) -> "tuple[Any, Any]":
    """``(C, P)``, with every body the ledger declared put back where it was. Pure.

    ``resolver`` and ``factory`` go straight through to :func:`decode_model`: what a
    domain owes at decode is the codec's business and this module does not restate it.
    """
    pairs = declared_bodies(envelope)
    missing = [name for _id, name in pairs if name not in bodies]
    if missing:
        raise LedgerError(
            f"the ledger declares {len(missing)} body/bodies that were not supplied: "
            f"{sorted(missing)}. A declared body is not an optional one — supplying "
            "fewer would decode a continuity whose artifacts are silently absent."
        )
    missing_plans = [name for _branch, name in declared_plans(envelope) if name not in plans]
    if missing_plans:
        raise LedgerError(
            f"the ledger declares {len(missing_plans)} plan version(s) that were not supplied: "
            f"{sorted(missing_plans)}. A plan reference is not optional during resume."
        )
    inner = dict(envelope["continuity"])
    inner["artifacts"] = [bodies[name] for _id, name in pairs]
    inner["plans"] = {
        branch: plans[name] for branch, name in declared_plans(envelope)
    }
    return decode_model({**envelope, "continuity": inner}, resolver=resolver, factory=factory)


# ---------------------------------------------------------------------------
# The disk, which is the only part of this that is not pure
# ---------------------------------------------------------------------------


def write_session(
    layout: Layout,
    session: Any,
    continuity: Any,
    position: Any,
) -> dict:
    """Write the ledger, and each body that is not already there.

    A body whose file exists is **compared, not overwritten**. An artifact id determines
    its body, so an existing file with different content is not a rewrite to be
    performed — it is a collision or a corruption, and performing it would hide both.
    The cost is a read per already-written body per round; it is paid deliberately,
    because the alternative is a silent wrong answer and this repository has no cheaper
    currency for that.
    """
    envelope, bodies, plans = split(continuity, position)
    directory = layout.bodies(session)
    directory.mkdir(parents=True, exist_ok=True)

    written, unchanged = [], []
    for name in sorted(bodies):
        path = layout.body(session, name)
        payload = json.dumps(bodies[name], indent=1, sort_keys=True)
        if path.exists():
            if path.read_text(encoding="utf-8") != payload:
                raise LedgerError(
                    f"body {name!r} already holds different content at {path}. An "
                    "artifact id determines its body, so this is a collision or a "
                    "corruption rather than a rewrite, and overwriting would hide both."
                )
            unchanged.append(name)
            continue
        path.write_text(payload, encoding="utf-8")
        written.append(name)

    plan_directory = layout.plans(session)
    plan_directory.mkdir(parents=True, exist_ok=True)
    plans_written, plans_unchanged = [], []
    for name in sorted(plans):
        path = layout.plan(session, name)
        payload = json.dumps(plans[name], indent=1, sort_keys=True)
        if path.exists():
            if path.read_text(encoding="utf-8") != payload:
                raise LedgerError(
                    f"plan version {name!r} already holds different content at {path}. "
                    "A version is immutable, so overwriting would hide corruption."
                )
            plans_unchanged.append(name)
            continue
        path.write_text(payload, encoding="utf-8")
        plans_written.append(name)

    ledger = layout.ledger(session)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps(envelope, indent=1, sort_keys=True), encoding="utf-8")
    return {
        "session": str(session),
        "ledger": str(ledger),
        "artifacts": len(bodies),
        "bodies_written": tuple(written),
        "bodies_unchanged": tuple(unchanged),
        "plans": len(plans),
        "plans_written": tuple(plans_written),
        "plans_unchanged": tuple(plans_unchanged),
    }


def read_session(
    layout: Layout,
    session: Any,
    *,
    resolver: "Any | None" = None,
    factory: "Callable[..., Any] | None" = None,
) -> "tuple[Any, Any]":
    """``(C, P)`` from disk. Every body the ledger declares is loaded, or it refuses."""
    ledger = layout.ledger(session)
    if not ledger.exists():
        raise LedgerError(f"no ledger at {ledger}")
    envelope = json.loads(ledger.read_text(encoding="utf-8"))

    bodies = {}
    for artifact_id, name in declared_bodies(envelope):
        path = layout.body(session, name)
        if not path.exists():
            raise LedgerError(
                f"the ledger declares artifact {artifact_id!r} in body {name!r} and "
                f"{path} does not exist. The ledger and its bodies are one value; a "
                "ledger that outlived its bodies is not a partial reconstruction."
            )
        bodies[name] = json.loads(path.read_text(encoding="utf-8"))
    plans = {}
    for branch, name in declared_plans(envelope):
        path = layout.plan(session, name)
        if not path.exists():
            raise LedgerError(
                f"the ledger declares branch {branch!r} uses plan version {name!r} and "
                f"{path} does not exist. A session cannot resume against an absent plan."
            )
        encoded = json.loads(path.read_text(encoding="utf-8"))
        if plan_name(encoded) != name:
            raise LedgerError(
                f"plan version {name!r} does not match its content at {path}. A plan "
                "version is content-addressed, so this is corruption rather than a "
                "replacement a resume may accept."
            )
        plans[name] = encoded
    return join(envelope, bodies, plans, resolver=resolver, factory=factory)


__all__ = [
    "DIGEST_CHARS",
    "LEDGER_BODIES",
    "LEDGER_PLAN_VERSION",
    "LedgerError",
    "body_name",
    "declared_bodies",
    "declared_plans",
    "join",
    "plan_name",
    "read_session",
    "session_id",
    "split",
    "write_session",
]
