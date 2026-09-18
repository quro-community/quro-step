"""Above-kernel context machinery: the read side of the route discipline.

**Above the Kernel, not in it.** This package is v0.2 §38's **phase 5** (`ArtifactStore`,
`get_artifact`, `Window`) and **phase 6** (`ContextView`, `ContextBlocks`, `HINTS`,
resource access) — the two phases the topology of `docs/mvp/m5/` records as never
having been started on either side of M1–M4.

The finding it is built on is `AR-4`: **durability is not reachability**, and a declared
route closes the gap — never a field.

```text
relation · return · branch · fold   =   mount(P, C) + a declared record in C
                                                   ↓
                            and the record declares a (channel, projection) pair
                                                   ↓
        PROJ_NONE       the Kernel's own reference projection publishes it
        PROJ_DOMAIN     the domain's own projection publishes it
        PROJ_ON_DEMAND  it is NOT published — it is fetched, by an explicit ask
```

## What was missing

`continuity_ops` declares all three. Two had readers. The third —

```text
PROJ_ON_DEMAND   materialised through a resource the domain declares reachable
```

— was **a name with no mechanism**. `law.py` states the preservation obligations over
an observation vocabulary "so the same check runs against a mounted state, a domain
projection, **a declared on-demand resource**, or a fresh interpreter", and nothing in
`src/` has ever produced that fourth thing. This package is it.

So this is the **first consumer of the route discipline that reads rather than writes**,
which is the point rather than an implementation detail: a declaration and its consumer
written by the same hand share an assumption that only a second author can find.

## The two things it must never become

```text
F1  a SECOND SOURCE OF TRUTH
    It caches or owns artifact content instead of reading it back out of the durable
    continuity. v0.2 §23: "A lower-level projection must not become the canonical
    owner of the information it projects." So `ArtifactStore` holds no content and no
    cache, and `Window` carries names and never Artifacts.

F2  a SECOND, UNDECLARED ACCESS PATH
    It reaches artifact content without a declared (channel, projection) pair, and so
    reports success for a fact that a state-only continuation cannot reach. So
    `get_artifact` refuses an undeclared resource rather than falling back to a wider
    search, and a content block is built only for a resource that is declared
    *and* present.
```

Both are shapes that cannot be built rather than disciplines a reader has to maintain,
which is the only kind of guarantee that survives a later author.

## What it deliberately does not do

```text
no summarize        §24.5 names `summarize` as a responsibility and it is absent: a
                    summarizer REDUCES information, and AR-3 says such an operation
                    owes its preservation law BEFORE it is implemented. No such law
                    exists for context summarization. What ships is selection and
                    naming, which reduce nothing.
no bound chosen     §3.3 makes the bounding half policy and register B-9 keeps it
                    gated on a job. The slot ships; its absence ships; a check forbids
                    the framework from choosing a value.
no ranking          a judgement over domain meaning, which is E13's assignment.
no codec            register B-10 stands. This package is deterministic over the
                    continuity by construction, so it composes with whatever codec
                    lands, and neither needs nor provides one.
no Kernel law       nothing here changes the Kernel. `make laws` prints 22 before and
                    after; no new tier-1 or tier-2 law is minted.
```

**Reverse dependencies are forbidden** — and here the Kernel already agrees: it names
``quro.context`` among the packages nothing in it may import. This package's own tests
check the direction by reading source rather than trusting it, the same way
``quro/continuity_ops/`` does.
"""

from __future__ import annotations

from .blocks import (
    BLOCK_CONTENT,
    BLOCK_DECLARED,
    BLOCK_KINDS,
    BLOCK_NAMED,
    Block,
    ContextBlocks,
)
from .bound import UNBOUNDED, Bound
from .checks import (
    CONTENT_READERS,
    chosen_bounds,
    content_reader_names,
    content_without_a_route,
    contract_is_declared,
    item_prefixes,
    minted_record_names,
    missing_members,
    sources,
    unexercised_readers,
    unproduced_sources,
)
from .hints import (
    HINT_ANCHOR,
    HINT_DECLARED,
    HINT_KINDS,
    HINT_RESOURCE,
    HINTS,
    Hint,
)
from .routes import (
    REFUSAL_KINDS,
    UNAVAILABLE,
    UNDECLARED,
    ContextError,
    RouteRefusal,
    carried_ledger,
    declared_records,
    declared_resources,
    declares,
    deliver_through,
)
from .store import ArtifactStore, get_artifact
from .view import ContextView, ReferenceContextView, contract_members
from .window import (
    SELECTIONS,
    SELECTION_ALL,
    SELECTION_RECOVERABLE,
    Window,
)

__all__ = [
    "ArtifactStore",
    "BLOCK_CONTENT",
    "BLOCK_DECLARED",
    "BLOCK_KINDS",
    "BLOCK_NAMED",
    "Block",
    "Bound",
    "CONTENT_READERS",
    "ContextBlocks",
    "ContextError",
    "ContextView",
    "HINTS",
    "HINT_ANCHOR",
    "HINT_DECLARED",
    "HINT_KINDS",
    "HINT_RESOURCE",
    "Hint",
    "REFUSAL_KINDS",
    "ReferenceContextView",
    "RouteRefusal",
    "SELECTIONS",
    "SELECTION_ALL",
    "SELECTION_RECOVERABLE",
    "UNAVAILABLE",
    "UNDECLARED",
    "UNBOUNDED",
    "Window",
    "carried_ledger",
    "chosen_bounds",
    "content_reader_names",
    "content_without_a_route",
    "contract_is_declared",
    "contract_members",
    "item_prefixes",
    "declared_records",
    "declared_resources",
    "declares",
    "deliver_through",
    "get_artifact",
    "minted_record_names",
    "missing_members",
    "sources",
    "unexercised_readers",
    "unproduced_sources",
]
