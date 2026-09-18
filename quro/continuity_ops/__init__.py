"""Upper-layer continuity operations: branch, return, fold.

**Above the Kernel, not in it.** This package is the landing of four milestones'
"Outcome B" verdicts — the operations the Kernel deliberately does not own
(v0.2 §2, §39), expressed over the three methods it does.

The finding it is built on:

```text
relation · return · branch · fold   =   mount(P, C) + a declared record in C

All four are the same call. The Kernel does not branch on which one it is; it never
reads the record. What differs above the boundary is (a) which record type is
declared and (b) which projection the domain publishes.
```

So this is **one module and three record types**, not three subsystems — which is why
it has one package rather than v0.2 §35's `quro/backtrack/`, `quro/fork/`,
`quro/steering/` split. That list predates the isomorphism; the finding supersedes it.
If an operation ever needs a shape the others do not, split it then, not before.

What each operation owes, and what this package therefore provides:

```text
D1  RECEIPT   a domain-declared, Kernel-opaque record committed through update()
D2  ROUTES    a declared (channel, projection) pair, or the fact is measurably
              unreachable from a state-only continuation
D3  LAW       a preservation obligation with BOTH halves — the declaration, and the
              content promised
D4  SOURCES   what the operation took from, declared, so it cannot satisfy a promise
              by pointing at content it never claimed to compress
```

`law.py` states D3 for each record type as a checkable function. Nothing here is a
Kernel norm: the Kernel is unchanged by this package, and design doc §8.2 forbids
reading any choice in it as a Kernel recommendation. The choices it does make are
recorded in `docs/design/Q4-Kernel-Upper-Layer-Decisions.md`, with the measurement
that decided each.

**Reverse dependencies are forbidden.** Nothing in `quro.kernel` may import this
package; `tests/test_continuity_ops.py::ReverseDependencyIsForbidden` reads the source tree to prove it rather
than trusting the claim.
"""

from __future__ import annotations

from .channels import (
    CH_ARTIFACT,
    CH_PROVENANCE,
    CH_RECORD,
    CHANNELS,
    encode_record,
    read_fold_records,
    read_records,
    read_records_any,
    records_reachable_from_state,
)
from .law import (
    ObligationResult,
    check_all,
    check_fold_preservation,
    check_preservation,
    fold_carries_what_it_declared,
    fold_declares_its_sources,
    operation_recorded,
)
from .operations import (
    CARRIED_KEY,
    SUMMARY_KEY,
    OperationError,
    allocate,
    backtrack,
    fold,
)
from .records import (
    PROJECTIONS,
    PROJ_DOMAIN,
    PROJ_NONE,
    PROJ_ON_DEMAND,
    RECORD_KEY,
    RECORD_TYPES,
    BranchAllocation,
    BacktrackRecord,
    ContinuityRecord,
    FoldRecord,
    record_from_payload,
)

#: The route vocabulary is published, not private.
#:
#: `PROJ_*` / `PROJECTIONS` and the two payload keys were module-level in
#: `records.py` and `operations.py` and reachable only by importing those modules
#: directly. That made the *declaration* of a route addressable and the *reading* of
#: one not: a consumer had to reach past the public surface to learn which policies
#: exist, or re-mint the constants — which is the duplicated-vocabulary defect this
#: package records the cost of, one level up.
#:
#: A route that can be declared and not read is a route with one end. This is the
#: other end, and publishing it changes no behaviour.
__all__ = [
    "BranchAllocation",
    "BacktrackRecord",
    "CARRIED_KEY",
    "CH_ARTIFACT",
    "CH_PROVENANCE",
    "CH_RECORD",
    "CHANNELS",
    "ContinuityRecord",
    "FoldRecord",
    "ObligationResult",
    "OperationError",
    "PROJECTIONS",
    "PROJ_DOMAIN",
    "PROJ_NONE",
    "PROJ_ON_DEMAND",
    "RECORD_KEY",
    "RECORD_TYPES",
    "SUMMARY_KEY",
    "allocate",
    "backtrack",
    "check_all",
    "check_fold_preservation",
    "check_preservation",
    "encode_record",
    "fold",
    "fold_carries_what_it_declared",
    "fold_declares_its_sources",
    "operation_recorded",
    "read_fold_records",
    "read_records",
    "read_records_any",
    "record_from_payload",
    "records_reachable_from_state",
]
