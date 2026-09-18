"""`Window` — v0.2 §38 phase 5, and v0.2 §24.3.

```text
bounded domain-visible projection over Artifact sequence
```

Two prohibitions define it, and both are structural here rather than documented:

**A Window is not the canonical Artifact store.** It is a projection, and v0.2 §23's
rule applies to it as much as to anything else: *a lower-level projection must not
become the canonical owner of the information it projects.* So a `Window` carries
artifact **names** and never `Artifact` objects. There is no field on it that could hold
content, which means "the Window became a store" is not a discipline a reader has to
maintain — it is a shape that cannot be built.

**A Window selects; it does not transform.**

```text
Window([K1..K3]) -> [K1, K2, K3]      selects
fold([K1..K3])   -> K'                transforms
```

That distinction is the design's own (the supplement states it explicitly) and it is why
this module is not part of `continuity_ops`. `fold` declares a preservation obligation
because it *reduces* information; a Window reduces nothing and therefore owes no such
law. Conflating them would attach E16 to an operation that has nothing to preserve.

A Window is **optional** (§24.3). A view may read the continuity, a store, or hints
without one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .bound import UNBOUNDED, Bound

#: Every artifact the continuity carries, in the order it carries them.
SELECTION_ALL = "all-artifacts"

#: Only the artifacts at Positions the continuity declared recoverable.
SELECTION_RECOVERABLE = "declared-recoverable"

SELECTIONS = (SELECTION_ALL, SELECTION_RECOVERABLE)


@dataclass(frozen=True)
class Window:
    """A selected, ordered, bounded set of Artifact *names*."""

    names: "tuple[str, ...]" = ()
    selection: str = SELECTION_ALL
    bound: Bound = UNBOUNDED
    truncated: bool = False
    #: The names the declared bound removed. Kept so truncation is inspectable rather
    #: than merely a flag — a reader can see *what* was dropped, not just that
    #: something was.
    dropped: "tuple[str, ...]" = field(default=())

    def __post_init__(self) -> None:
        object.__setattr__(self, "names", tuple(str(name) for name in self.names))
        object.__setattr__(self, "dropped", tuple(str(name) for name in self.dropped))
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
    ) -> "Window":
        """Select an artifact sequence from ``continuity`` and apply ``bound``."""
        selected = cls._selected(continuity, selection)
        kept = bound.applied_to(selected)
        return cls(
            names=kept,
            selection=selection,
            bound=bound,
            truncated=len(kept) != len(selected),
            dropped=selected[len(kept):],
        )

    @staticmethod
    def _selected(continuity: Any, selection: str) -> "tuple[str, ...]":
        artifacts = tuple(getattr(continuity, "artifacts", ()) or ())
        if selection == SELECTION_ALL:
            return tuple(artifact.id.name for artifact in artifacts)
        if selection == SELECTION_RECOVERABLE:
            # The recoverable half is expressed over Positions, and an Artifact is not
            # a Position: the join is the Artifact's provenance Position. An Artifact
            # with no provenance cannot be placed, and is excluded rather than assumed
            # into the set.
            return tuple(
                artifact.id.name
                for artifact in artifacts
                if _is_recoverable(continuity, getattr(artifact, "provenance", None))
            )
        raise ValueError(
            f"unknown selection: {selection!r}; expected one of {SELECTIONS}"
        )

    def as_dict(self) -> dict:
        return {
            "names": list(self.names),
            "selection": self.selection,
            "bound": self.bound.limit,
            "truncated": self.truncated,
            "dropped": list(self.dropped),
        }


def _is_recoverable(continuity: Any, provenance: Any) -> bool:
    if provenance is None:
        return False
    position = getattr(provenance, "position", None)
    if position is None:
        return False
    marker = getattr(continuity, "is_recoverable", None)
    if not callable(marker):
        return False
    return bool(marker(position))


__all__ = [
    "SELECTIONS",
    "SELECTION_ALL",
    "SELECTION_RECOVERABLE",
    "Window",
]
