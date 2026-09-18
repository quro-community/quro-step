"""The read side's conformance checks.

`continuity_ops/law.py` is the write side's obligation layer. This is its mirror: the
obligations a *reader* of a declared route owes, stated as checkable functions.

Two families, and they are deliberately different in shape:

```text
value checks    over objects a caller already built — a view, a block set, a store
source checks   pure functions over (path, text) pairs, so a reverse injection can
                feed them a synthetic source and exercise BOTH arms
```

The source checks are pure for a specific reason: a detector that has only ever been
observed to pass is half a check, and re-running one against a synthetic defect is how
this repository proves the other half. A detector written as a loop over `rglob` cannot
be handed a defect; one written as a pure function over text can.
"""

from __future__ import annotations

import ast
import pathlib
import re
from typing import Any, Iterable, Mapping

from quro.continuity_ops import RECORD_TYPES, FoldRecord

from .blocks import BLOCK_CONTENT, BLOCK_KINDS, BLOCK_ORDER, ContextBlocks
from .view import ContextView, contract_members

#: Functions inside ``src/quro/context/`` that are allowed to read Artifact payload
#: content, and the reason each one is. A closed list, because an open one would grow
#: silently — and the growth would be exactly the second access path this package is
#: built to not be.
CONTENT_READERS = {
    "carried_ledger": "reads the fold ledger out of the artifacts that carry it",
    "_loaded_block": "renders a resource the caller explicitly asked for",
}

#: The call that would mean the framework chose a bound. Written as a pattern rather
#: than as a literal constant *and* a pattern, because a literal constant spelling the
#: same characters would be found by the scan it exists to feed.
BOUND_CALL = re.compile(r"Bound\(([^)]*)\)")


# ---------------------------------------------------------------------------
# Value checks
# ---------------------------------------------------------------------------


def missing_members(subject: Any, *, contract: Any = ContextView) -> "tuple[str, ...]":
    """The contract's members that ``subject`` does not provide.

    Derived from the *contract* rather than from a second list of names, so the check
    and the thing it checks cannot drift apart. An `any`-shaped check that inspects
    nothing reports nothing, so the caller is expected to assert
    :func:`contract_members` is non-empty as well.
    """
    wanted = tuple(
        sorted(
            name
            for name in vars(contract)
            if not name.startswith("_") and callable(getattr(contract, name, None))
        )
    )
    return tuple(name for name in wanted if not callable(getattr(subject, name, None)))


def content_without_a_route(
    blocks: ContextBlocks, *, asked: "Iterable[str]" = (), store: Any = None
) -> "tuple[str, ...]":
    """Content blocks whose resource was neither asked for nor declared.

    This is the second, undeclared access path, stated as a check. A view that put
    artifact content into a block without a declared route would report success for a
    fact no `(channel, projection)` pair reaches — and every downstream reader would
    take it for something the continuity offers.

    A content block with no ``resource`` at all is reported under an empty name rather
    than skipped: a block that cannot name where it came from is unaccounted for, and
    silence is the one answer that must never be given here.
    """
    declared = set() if store is None else set(store.resources())
    allowed = declared | {str(item) for item in asked}
    offenders = []
    for block in blocks.of_kind(BLOCK_CONTENT):
        if block.resource is None:
            offenders.append("<unnamed>")
        elif block.resource not in allowed:
            offenders.append(block.resource)
    return tuple(offenders)


def unproduced_sources(blocks: ContextBlocks, *, expected: "Iterable[str]" = ()) -> "tuple[str, ...]":
    """Kinds the caller declares it built, which produced no block.

    The anti-vacuity check, and the read-side form of the defect composition found on
    the write side: a check handed no subjects evaluates no obligations and reports no
    failures, so "nothing failed" is *true* for a projection that produced nothing at
    all. An empty ``expected`` keeps this records-in/verdicts-out, which is right for a
    caller inspecting one block; a conformance runner passes what it built.

    A kind outside :data:`..blocks.BLOCK_KINDS` raises — an unknown kind is a caller
    mistake, and reporting it as "produced nothing" would make a typo look like a
    finding.
    """
    unknown = sorted({str(kind) for kind in expected} - set(BLOCK_KINDS))
    if unknown:
        raise ValueError(f"unknown block kinds: {unknown}; expected {BLOCK_KINDS}")
    present = {block.kind for block in blocks.blocks}
    return tuple(sorted({str(kind) for kind in expected} - present))


# ---------------------------------------------------------------------------
# Source checks — pure, so both arms can be run
# ---------------------------------------------------------------------------


def sources(root: Any) -> "tuple[tuple[pathlib.Path, str], ...]":
    """Every Python source under ``root``, as ``(path, text)``. Pure."""
    return tuple(
        (path, path.read_text(encoding="utf-8")) for path in sorted(pathlib.Path(root).rglob("*.py"))
    )


def _code(text: str) -> str:
    """``text`` with docstrings removed — prose naming a thing is not code minting it."""
    return re.sub(r'"""(?:.|\n)*?"""', "", text)


def item_prefixes() -> "tuple[str, ...]":
    """Every observation-name prefix the record types mint, **derived from the records**.

    **Both halves.** The declaration half comes from each type's ``as_item()``; the
    content half is ``FoldRecord.RETAINED_PREFIX``, which is minted by a different
    function and would be missed by reading ``as_item`` alone. A derivation that covered
    one half is exactly the defect `AR-2` names — M4's first formulation of E16 checked
    only the content half and passed a fold that recorded nothing — and the first
    version of *this* function reproduced it in the opposite direction, deriving the
    declaration half only and so blind to every retained name.

    Asked of the producers rather than written down here. A second written list is a
    list that can drift from the thing it describes, and this repository has already
    paid for that class of defect three times — the last time after a fix that looked
    complete.
    """
    prefixes = set()
    for record_type in RECORD_TYPES:
        try:
            probe = _probe(record_type)
            item = probe.as_item()
        except Exception:  # boundary: a type that cannot be probed contributes nothing
            continue
        head, separator, _ = item.partition(":")
        if separator and head:
            prefixes.add(head)
    content_half = FoldRecord.RETAINED_PREFIX.rstrip(":")
    if content_half:
        prefixes.add(content_half)
    return tuple(sorted(prefixes))


def _probe(record_type: Any) -> Any:
    """A minimal instance of ``record_type``, for reading its naming off it."""
    import inspect

    parameters = inspect.signature(record_type).parameters
    required = {
        name: ""
        for name, parameter in parameters.items()
        if parameter.default is inspect.Parameter.empty
        and parameter.kind
        in (parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY)
    }
    return record_type(**required)


def minted_record_names(srcs: "Iterable[tuple[pathlib.Path, str]]") -> "tuple[str, ...]":
    """Observation names built by an f-string inside ``srcs``.

    A reader that rebuilds an observation name has to copy the format out of the code
    that mints it, and the two ends can then drift — silently, because both still look
    right. This is the check that found the third instance of that defect here, after
    the first fix looked complete.
    """
    prefixes = item_prefixes()
    found = []
    for path, text in srcs:
        code = _code(text)
        for prefix in prefixes:
            if re.search(r'f"[^"]*' + re.escape(prefix) + r":", code):
                found.append(f"{path.name}:{prefix}")
    return tuple(sorted(set(found)))


def chosen_bounds(srcs: "Iterable[tuple[pathlib.Path, str]]") -> "tuple[str, ...]":
    """Places where this package constructs a `Bound` **with an argument**.

    Re-Positioning §3.3 makes the bounding half policy, and register `B-9` keeps it
    gated on a job. A framework that picked a bound would be answering a question it
    has no criterion for — invisibly, since the result would be well-formed and
    plausible. Constructing ``Bound()`` with nothing is the declared absence of a
    policy and is allowed; ``Bound(limit=...)`` is not.
    """
    found = []
    for path, text in srcs:
        code = _code(text)
        for match in BOUND_CALL.finditer(code):
            arguments = match.group(1).strip()
            if arguments and not arguments.startswith("limit=None"):
                found.append(f"{path.name}: constructs a bound with {arguments!r}")
    return tuple(sorted(set(found)))


def content_reader_names(srcs: "Iterable[tuple[pathlib.Path, str]]") -> "tuple[str, ...]":
    """Every function in ``srcs`` whose body reads an Artifact's payload.

    Attribute-based rather than text-based, so a docstring that *mentions* the payload
    is not read as reading it — and so the attribution is to a named function, which is
    what lets the caller assert each allow-listed reader is actually exercised.
    """
    found = set()
    for _path, text in srcs:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for inner in ast.walk(node):
                if isinstance(inner, ast.Attribute) and inner.attr == "payload":
                    found.add(node.name)
                    break
    return tuple(sorted(found))


def unexercised_readers(srcs: "Iterable[tuple[pathlib.Path, str]]") -> "tuple[str, ...]":
    """Allow-listed readers that no longer exist — a stale allow-list is a blind one.

    An allow-list is a statement about what *may* read content. Once an entry names a
    function that is gone, the list has stopped describing the code and started
    describing a memory of it, and the next reader added would be compared against a
    list that no longer means anything.
    """
    present = set(content_reader_names(srcs))
    return tuple(sorted(name for name in CONTENT_READERS if name not in present))


def contract_is_declared() -> bool:
    """A detector that inspects nothing reports nothing — so this must be non-empty."""
    return bool(contract_members())



def out_of_order(blocks: Any, *, order: "Iterable[str]" = BLOCK_ORDER) -> "tuple[tuple[int, str, str], ...]":
    """Where a block sequence moves *backwards* through the declared order. ``()`` means conforming.

    `BLOCK_ORDER` is not decoration: `Bound.applied_to` drops from the end, so the order
    decides what survives a limit. A sequence that reorders silently changes what every
    bounded consumer sees — and until this function existed, the reference view's own
    docstring was the only statement of the order, with nothing enforcing it (`LL1`: *a
    protocol written in prose is not a protocol*).

    Returns ``(position, kind, why)`` per offending block rather than a boolean, because
    "the context was out of order" without saying where is not enough to fix it.

    Deliberately says nothing about *deviating* from the order. A domain that wants a
    different order states which entry it deviates from and why — and no domain has
    wanted one yet. That is what the deviation half is gated on: a **consumer**, not a
    surface. The declaration surfaces exist and are read (a continuity-level standing
    declaration, and a record carrying `declared_by`; conception §5(a), corrected
    2026-09-19), so this check covers conformance, and the deviation half stays gated
    until a domain needs it. The trigger, and what would fire it, are in
    `docs/design/Q4-Kernel-Context-Limits-and-Prompt-Discipline.md` §6.2 R3.
    """
    sequence = tuple(order)
    index = {kind: position for position, kind in enumerate(sequence)}
    found = []
    highest = -1
    for position, block in enumerate(getattr(blocks, "blocks", ()) or ()):
        current = index.get(block.kind)
        if current is None:
            found.append((position, str(block.kind), f"not one of {sequence}"))
            continue
        if current < highest:
            found.append(
                (position, str(block.kind), f"follows a later kind ({sequence[highest]})")
            )
        highest = max(highest, current)
    return tuple(found)


__all__ = [
    "BOUND_CALL",
    "CONTENT_READERS",
    "chosen_bounds",
    "content_reader_names",
    "content_without_a_route",
    "contract_is_declared",
    "item_prefixes",
    "minted_record_names",
    "out_of_order",
    "missing_members",
    "sources",
    "unexercised_readers",
    "unproduced_sources",
]
