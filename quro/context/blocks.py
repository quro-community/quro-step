"""`Block` and `ContextBlocks` — v0.2 §25, and `SEMANTICS.md` §63.

```text
Context_t = Projection( ExecutionContinuity_t , ContextView , Policy )

not

Context_t = Context_(t-1) + messages
```

`ContextBlocks` is the left-hand side: what a fresh Agent conversation is constructed
from. It is **derived**, every time, from durable state — which is what makes fresh
conversations, lazy loading, model replacement and process restart all follow from the
same law instead of each needing a mechanism.

`SEMANTICS.md` §63 makes context block-oriented: blocks "have semantic identity and may
be independently ordered, measured, retained, trimmed, compressed, projected". That is
why a block carries its own kind and label rather than being a single rendered prompt —
a consumer downstream of here is allowed to act on one block without touching another.

## What a block is not

§63 also says a Block "is not the semantic source itself" — it is a *representation and
access policy* for a source. So a block names what it came from; it does not become the
thing it came from. In particular a `content` block carries a **rendered item list**,
never the `Artifact` object, for the same reason a `Window` carries names: the moment a
block held the canonical object, the projection would have become an owner.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .bound import UNBOUNDED, Bound

#: An Artifact offered by name and not loaded — the agent may ask for it later.
BLOCK_NAMED = "named"

#: A record's own declared items. Nothing is computed and nothing is reduced.
BLOCK_DECLARED = "declared"

#: A resource the agent asked for, rendered. The only kind that carries loaded items.
BLOCK_CONTENT = "content"

BLOCK_KINDS = (BLOCK_NAMED, BLOCK_DECLARED, BLOCK_CONTENT)


@dataclass(frozen=True)
class Block:
    """One named, independently addressable piece of a context projection."""

    kind: str
    label: str
    resource: "str | None" = None
    items: "tuple[str, ...]" = ()

    def __post_init__(self) -> None:
        if self.kind not in BLOCK_KINDS:
            raise ValueError(f"unknown block kind: {self.kind!r}; expected {BLOCK_KINDS}")
        object.__setattr__(self, "label", str(self.label))
        object.__setattr__(self, "items", tuple(str(item) for item in self.items))
        if self.resource is not None:
            object.__setattr__(self, "resource", str(self.resource))

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "label": self.label,
            "resource": self.resource,
            "items": list(self.items),
        }


@dataclass(frozen=True)
class ContextBlocks:
    """An ordered projection into Agent context, ready for a fresh conversation."""

    blocks: "tuple[Block, ...]" = ()
    bound: Bound = UNBOUNDED
    truncated: bool = False
    dropped: "tuple[Block, ...]" = ()
    #: Resources a caller asked for that produced no block. Empty is the ordinary case;
    #: a non-empty tuple is the difference between "the agent asked for nothing" and
    #: "the agent asked and was quietly given nothing", and those must not be the same
    #: value. See the module note below.
    unavailable: "tuple[str, ...]" = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "blocks", tuple(self.blocks))
        object.__setattr__(self, "dropped", tuple(self.dropped))
        object.__setattr__(
            self, "unavailable", tuple(str(item) for item in self.unavailable)
        )

    def items(self) -> "tuple[str, ...]":
        """Every item across every block, in block order."""
        return tuple(item for block in self.blocks for item in block.items)

    def of_kind(self, kind: str) -> "tuple[Block, ...]":
        return tuple(block for block in self.blocks if block.kind == kind)

    def labels(self) -> "tuple[str, ...]":
        return tuple(block.label for block in self.blocks)

    def as_dict(self) -> dict:
        return {
            "blocks": [block.as_dict() for block in self.blocks],
            "bound": self.bound.limit,
            "truncated": self.truncated,
            "dropped": [block.as_dict() for block in self.dropped],
            "unavailable": list(self.unavailable),
        }


__all__ = [
    "BLOCK_CONTENT",
    "BLOCK_DECLARED",
    "BLOCK_KINDS",
    "BLOCK_NAMED",
    "Block",
    "ContextBlocks",
]
