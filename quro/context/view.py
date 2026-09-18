"""`ContextView` — the contract, and the framework's reference implementation.

v0.2 §24.5:

```text
bounded projection into Agent context
```

It answers *"what should this Agent see now?"* It does **not** answer *"what
information exists?"*, does not independently decide *"what does the evidence mean?"*,
and does not decide *"where should investigation go next?"* Its responsibilities are
`select / project / summarize / order / bound` — not `solve`.

## The contract is real, not prose

That description is prose, and a module that merely *resembles* a prose description is
the defect this repository has already paid for once: `continuity_ops/records.py`
records its first version stating its protocol in a docstring, so that `record.channel`
raised `AttributeError` on the first call that used it.

So `ContextView` here is a **`runtime_checkable` Protocol**, and
`checks.missing_members` derives the member list *from the protocol*. The contract and
the check that enforces it read the same place, so they cannot drift — the same device
`ContinuityRecord.observations()` uses to keep a record and its check agreeing.

A Protocol rather than an ABC because this repository's extension points are
*declared*, not *inherited* (G6, `mounter.py`), and because §24.5 leaves the view
domain-facing: a domain's own view must be able to satisfy this contract without
adopting a framework base class.

## What the reference implementation will not do

**It takes no mounted `ExecutionState`.** v0.2 §25's diagram puts `mount` between `C`
and `ContextView`, but the law directly beneath it is
`Context_t = Projection(Continuity_t, ContextView, Policy)` — a function of `C` and the
policy. Accepting a state would invite reading `domain_payload`, and a view that read
facts out of the mounted payload would be reaching them by a second path that no
`(channel, projection)` pair declares. That is the defect this whole landing is built to
make impossible, so the shape of the call prevents it rather than a comment.

**It does not summarize.** `summarize` is one of §24.5's five named responsibilities and
is deliberately absent: a summarizer *reduces* information, and `AR-3` says an
information-reducing operation owes its preservation law **before** it is implemented.
That is why E16 exists and why `fold()` may not compute its own ledger. No such law
exists for context summarization, so none is built. What ships is selection and naming —
a `declared` block carries exactly `record.observations()`, so nothing is computed and
nothing is reduced.

**It chooses no bound.** See `.bound`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Protocol, runtime_checkable

from quro.continuity_ops import read_records_any

from .blocks import (
    BLOCK_CONTENT,
    BLOCK_DECLARED,
    BLOCK_NAMED,
    Block,
    ContextBlocks,
)
from .bound import UNBOUNDED, Bound
from .store import ArtifactStore, get_artifact
from .window import SELECTION_ALL, SELECTIONS, Window


@runtime_checkable
class ContextView(Protocol):
    """What a context view is, structurally — and the one definition of it.

    Methods only, deliberately. A `runtime_checkable` protocol checks *presence*, and a
    data member would make the contract a statement about how a view stores itself
    rather than about what a consumer can do through it. This is also what keeps the
    check in the well-specified part of `runtime_checkable`.
    """

    def blocks(
        self, *, asked: "Iterable[str]" = (), store: "ArtifactStore | None" = None
    ) -> ContextBlocks:
        """What this Agent should see now. Derived; never accumulated."""
        ...

    def as_dict(self) -> dict:
        """A declared, serializable statement of what this view is configured to do."""
        ...


def contract_members() -> "tuple[str, ...]":
    """The members the contract declares, read **from the contract itself**.

    Derived rather than restated, because a member list written down a second time is a
    list that can drift from the thing it describes — and the drift would be invisible,
    since both lists would still look right.
    """
    return tuple(
        sorted(
            name
            for name in vars(ContextView)
            if not name.startswith("_") and callable(getattr(ContextView, name, None))
        )
    )


@dataclass(frozen=True)
class ReferenceContextView:
    """The framework's view: declared selection, declared bound, no policy of its own."""

    continuity: Any
    selection: str = SELECTION_ALL
    bound: Bound = UNBOUNDED

    def __post_init__(self) -> None:
        if self.selection not in SELECTIONS:
            raise ValueError(
                f"unknown selection: {self.selection!r}; expected one of {SELECTIONS}"
            )

    @classmethod
    def of(
        cls,
        continuity: Any,
        *,
        selection: str = SELECTION_ALL,
        bound: Bound = UNBOUNDED,
    ) -> "ReferenceContextView":
        return cls(continuity=continuity, selection=selection, bound=bound)

    def blocks(
        self, *, asked: "Iterable[str]" = (), store: "ArtifactStore | None" = None
    ) -> ContextBlocks:
        """Assemble the projection: names, then declarations, then loaded resources.

        The order is the view's declared order, and it is stable: names first because
        they are what the agent chooses from (§26's flow), declarations next because
        they are the continuity's own record of what happened, and loaded content last
        because it is the only part that was *asked for*.

        A resource that was asked for and did not load contributes no block, and is
        named in ``unavailable`` instead. Dropping it silently would make "asked and
        received nothing" indistinguishable from "asked for nothing" — and a caller
        reading the second as the first is how a context goes quietly missing a fact.
        ``store`` is required exactly when something was asked for; passing ``asked``
        with no store is a caller mistake and raises.
        """
        wanted = tuple(str(item) for item in asked)
        if wanted and store is None:
            raise ValueError(
                "a view cannot load an asked-for resource without a store; "
                "asking is a request against a declared resource set"
            )

        named = self._named_block()
        built = [] if named is None else [named]
        built.extend(self._declared_blocks())

        unavailable = []
        for resource in wanted:
            loaded = self._loaded_block(store, resource)
            if loaded is None:
                unavailable.append(resource)
            else:
                built.append(loaded)

        kept = self.bound.applied_to(tuple(built))
        return ContextBlocks(
            blocks=kept,
            bound=self.bound,
            truncated=len(kept) != len(built),
            dropped=tuple(built[len(kept):]),
            unavailable=tuple(unavailable),
        )

    def _named_block(self) -> "Block | None":
        """The artifact names this view offers, **unbounded**.

        The bound is deliberately not applied here. It is applied once, below, to the
        block sequence — and that is the only level whose result records ``truncated``
        and ``dropped``. Applying it in both places would truncate twice and discard the
        window's own record of what it removed, so an item could go missing with nothing
        saying it had existed.
        """
        window = Window.of(self.continuity, selection=self.selection)
        if not window.names:
            return None
        return Block(kind=BLOCK_NAMED, label="available", items=window.names)

    def _declared_blocks(self) -> "list[Block]":
        return [
            Block(kind=BLOCK_DECLARED, label=record.as_item(), items=record.observations())
            for record in read_records_any(self.continuity)
        ]

    @staticmethod
    def _loaded_block(store: "ArtifactStore | None", resource: str) -> "Block | None":
        """A content block for a resource that is declared **and** present.

        Both conditions are the route. A block built without them would be the second,
        undeclared access path — it would put content in the context that no record
        declared reachable, and every downstream reader would take it for a fact the
        continuity actually offers.
        """
        if store is None:
            return None
        result = get_artifact(store, resource)
        if not result.is_ok():
            return None
        artifact = result.value
        payload = dict(artifact.payload.data)
        return Block(
            kind=BLOCK_CONTENT,
            label=artifact.id.name,
            resource=resource,
            items=tuple(sorted(f"{key}={value!r}" for key, value in payload.items())),
        )

    def as_dict(self) -> dict:
        return {
            "selection": self.selection,
            "bound": self.bound.limit,
        }


__all__ = ["ContextView", "ReferenceContextView", "contract_members"]
