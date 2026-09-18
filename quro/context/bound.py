"""`Bound` — the declared slot, and the explicit absence of a policy.

Re-Positioning §3.3 names "ContextView's bounding half" as **policy rather than
machinery**, and a policy has no correctness criterion:

```text
Phase 6  ContextView's bounding half  — what a bound should be is a policy
```

Register entry `B-9` puts it in the backlog, waiting for a **job** — an application
with a real context budget to bound against. `SEMANTICS.md` §124 pre-decides the
question in the design's own words:

> I would *not* spend time yet defining HINTS token budgets or generic context-budget
> policies.

So this module ships **the slot and its absence**, and never a value:

```text
the slot       a Bound is a declared input to every view, window and block set
the absence    UNBOUNDED — no limit, which is not a policy but the lack of one
never a value  no module under quro/context/ constructs a bounded one
```

The last line is a checkable claim and `checks` checks it. A framework that picked a
bound would be answering a question it has no criterion for, and would do it
invisibly — the result would be well-formed, plausible and unfalsifiable.

A bounded `Bound` is entirely legitimate for a *consumer* to declare. What the
framework may not do is choose one on the consumer's behalf.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Bound:
    """A declared limit on how much a projection may carry.

    ``limit=None`` is the absence of a declared limit. It is deliberately the *default*
    rather than a number: an omitted bound must mean "none was declared", never "the
    framework's opinion applied silently".
    """

    limit: "int | None" = None

    def __post_init__(self) -> None:
        if self.limit is not None:
            bound = int(self.limit)
            if bound < 0:
                raise ValueError(f"a bound is not negative: {bound}")
            object.__setattr__(self, "limit", bound)

    @classmethod
    def of(cls, limit: "int | None") -> "Bound":
        return cls(limit=limit)

    @property
    def declared(self) -> bool:
        """Whether a limit was declared at all. ``False`` is the absence of a policy."""
        return self.limit is not None

    def applied_to(self, items: "tuple[Any, ...]") -> "tuple[Any, ...]":
        """The items that survive the declared bound, in their declared order.

        Truncation drops from the **end** and never re-orders, because ordering is a
        declared responsibility of the view (v0.2 §24.5) and a bound that shuffled
        would be making a selection decision it was not asked to make.
        """
        if self.limit is None:
            return tuple(items)
        return tuple(items[: self.limit])


#: The declared absence of a policy. Not a default *value* — the lack of one.
UNBOUNDED = Bound()


__all__ = ["UNBOUNDED", "Bound"]
