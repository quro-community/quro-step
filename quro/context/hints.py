"""`Hint` and `HINTS` — v0.2 §26, and `SEMANTICS.md` §51–§54.

```text
HINTS = navigational semantic summary
```

HINTS answer *"what is important, what exists, and where can I look if I need more?"* —
not *"what did the previous conversation say?"*. The preferred flow is the whole point
of the resource-access layer:

```text
semantic summary -> HINTS -> Agent chooses -> resource access -> full resource
```

## The prohibition is structural here, not documented

§26 lists what HINTS must **not** become: a full artifact dump, a full history dump, a
full resource dump, a compressed transcript. `SEMANTICS.md` §54 adds that an
implementation "must not allow HINTS to become an unbounded substitute for
ExecutionContinuity".

A `Hint` therefore has **no field that could hold content**. It carries a kind, a short
label, and at most the *name* of a resource. The dump §26 forbids is not something a
reader has to notice; it is a shape that cannot be built, because there is nowhere to
put it.

What HINTS may carry is deliberately narrow, and narrower than §26's seven-item list.
Ships here: resource names (the declared route), recoverable Positions (useful
anchors), and the declared items of the records the continuity carries. Deferred
because each needs something that does not exist yet —

```text
unresolved questions   needs a notion of a question
dependency hints       needs a dependency graph
recall guidance        needs a relevance signal
ranking                is a judgement over domain meaning — E13's assignment
```

Each is a *job*, and the register's own rule applies: an entry that cannot state what
it is not defining is unfinished work wearing a label.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from quro.continuity_ops import read_records_any

from .bound import UNBOUNDED, Bound
from .routes import declared_resources

#: An Artifact a record declared askable-for. The hint names it; it does not carry it.
HINT_RESOURCE = "resource"

#: A declared Position a continuation can re-enter.
HINT_ANCHOR = "anchor"

#: A declared operation the continuity carries — its own `as_item()`, never a paraphrase.
HINT_DECLARED = "declared"

HINT_KINDS = (HINT_RESOURCE, HINT_ANCHOR, HINT_DECLARED)


@dataclass(frozen=True)
class Hint:
    """One navigational entry: a kind, a label, and at most a resource *name*.

    There is no content field, and that is the contract. See the module docstring.
    """

    kind: str
    label: str
    resource: "str | None" = None

    def __post_init__(self) -> None:
        if self.kind not in HINT_KINDS:
            raise ValueError(f"unknown hint kind: {self.kind!r}; expected {HINT_KINDS}")
        object.__setattr__(self, "label", str(self.label))
        if self.resource is not None:
            object.__setattr__(self, "resource", str(self.resource))

    def as_dict(self) -> dict:
        return {"kind": self.kind, "label": self.label, "resource": self.resource}


@dataclass(frozen=True)
class HINTS:
    """A compact, navigational projection of what exists and how to reach it."""

    entries: "tuple[Hint, ...]" = ()
    bound: Bound = UNBOUNDED
    truncated: bool = False
    dropped: "tuple[Hint, ...]" = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", tuple(self.entries))
        object.__setattr__(self, "dropped", tuple(self.dropped))

    @classmethod
    def of(cls, continuity: Any, *, bound: Bound = UNBOUNDED) -> "HINTS":
        """Build the navigational projection for ``continuity``.

        Derived from the continuity and nothing else. A `Window` is a *peer* projection
        (§24.3 lists both among what a ContextView may use), not a stage HINTS passes
        through, so taking one here would couple two independent readings of the same
        source and make each depend on the other's bound.
        """
        built = cls._built(continuity)
        kept = bound.applied_to(built)
        return cls(
            entries=kept,
            bound=bound,
            truncated=len(kept) != len(built),
            dropped=built[len(kept):],
        )

    @staticmethod
    def _built(continuity: Any) -> "tuple[Hint, ...]":
        entries = []

        # §26's "useful anchors": a declared Position a continuation can re-enter. Read
        # off the continuity rather than off a Window — a Window's names are artifacts,
        # and calling an artifact an anchor would both misuse the term and duplicate
        # every entry the resource hints already carry.
        for position in sorted(
            getattr(continuity, "all_recoverable", lambda: ())(), key=str
        ):
            entries.append(Hint(kind=HINT_ANCHOR, label=str(position)))

        for resource in declared_resources(continuity):
            entries.append(
                Hint(
                    kind=HINT_RESOURCE,
                    label=f"may be relevant: {resource}",
                    resource=resource,
                )
            )

        for record in read_records_any(continuity):
            entries.append(Hint(kind=HINT_DECLARED, label=record.as_item()))

        return tuple(entries)

    def resources(self) -> "tuple[str, ...]":
        """The resource names this projection offers for the agent to choose from."""
        return tuple(
            entry.resource
            for entry in self.entries
            if entry.kind == HINT_RESOURCE and entry.resource is not None
        )

    def of_kind(self, kind: str) -> "tuple[Hint, ...]":
        return tuple(entry for entry in self.entries if entry.kind == kind)

    def as_dict(self) -> dict:
        return {
            "entries": [entry.as_dict() for entry in self.entries],
            "bound": self.bound.limit,
            "truncated": self.truncated,
            "dropped": [entry.as_dict() for entry in self.dropped],
        }


__all__ = [
    "HINT_ANCHOR",
    "HINT_DECLARED",
    "HINT_KINDS",
    "HINT_RESOURCE",
    "HINTS",
    "Hint",
]
