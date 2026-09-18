"""`ArtifactStore` and `get_artifact` — v0.2 §38 phase 5.

```text
get_artifact : ArtifactId -> Artifact
```

The demand-driven retrieval primitive. §26's flow is the whole reason it exists:

```text
semantic summary -> HINTS -> Agent chooses -> resource access -> full resource
```

## The store is a view, not an owner

`ExecutionContinuity` is the canonical owner of its Artifacts. This store is derived
from one and holds **no content and no cache** — only the continuity it reads. v0.2
§23's rule is the reason it is shaped this way rather than as a dictionary of artifacts:

```text
A lower-level projection must not become the canonical owner of the information it
projects.
```

A store that cached would be exactly the second source of truth M2's `NC-1` control was
built to detect, and the detection is not hypothetical: it is the single defect class
this whole landing is arranged around. So the store is a *capability surface* —
`resources()`, `declares()`, `artifact()` — and every answer is computed from the
continuity at call time.

## Why `get_artifact` takes a store and not a continuity

"Ask anybody for anything" must not be a blessed call. Taking a store makes the request
carry its own scope — the resource set a record declared — which is the same
relationship ``mount(position, continuity)`` has to its continuity. The discipline is
carried by the shape of the call, so a caller who bypasses it is building on undefined
behaviour rather than on a hole the framework left in its own code.

## The two refusals

``undeclared`` and ``unavailable`` are different answers about different layers, and
this module never collapses them:

```text
undeclared    no record declared this askable-for — the route does not exist
unavailable   a record declared it, and the durable content is not there
```

A malformed request — a resource name of the wrong type — raises ``ContextError``
instead, because that is a caller mistake and not a statement the durable state can
make.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from quro.kernel import Artifact, Err, Ok, Result

from .routes import (
    UNAVAILABLE,
    UNDECLARED,
    ContextError,
    RouteRefusal,
    declared_resources,
)


def _known(continuity: Any, resource: str) -> "Artifact | None":
    """The named Artifact, by its stable logical identity — never by position.

    §57: a resource's identity must not depend on physical storage topology, so the
    lookup is by declared name and nothing else.
    """
    for artifact in getattr(continuity, "artifacts", ()) or ():
        if artifact.id.name == resource:
            return artifact
    return None


@dataclass(frozen=True)
class ArtifactStore:
    """A continuity *viewed as a declared resource set*.

    No ``resources=`` parameter. The set is derived from the records
    (:func:`..routes.declared_resources`) so there is exactly one producer — a store
    built from an argument list would let the route be widened without touching a
    record, which is the shape this landing exists to make impossible.
    """

    continuity: Any

    @classmethod
    def of(cls, continuity: Any) -> "ArtifactStore":
        return cls(continuity=continuity)

    def resources(self) -> "tuple[str, ...]":
        """The resources this store makes askable-for. Derived on every call."""
        return declared_resources(self.continuity)

    def declares(self, resource: str) -> bool:
        return str(resource) in self.resources()

    def artifact(self, resource: str) -> "Artifact | None":
        """The raw lookup. Prefer :func:`get_artifact`, which reports *why*."""
        return _known(self.continuity, str(resource))


def get_artifact(store: ArtifactStore, resource: str) -> "Result[Artifact, RouteRefusal]":
    """Load one declared resource.

    The resource must be declared askable-for **and** present. Both refusals are
    values, so a caller can distinguish "nobody declared this" from "the declaration
    was not kept" without inspecting a message.

    Deliberately does **not** fall back to a broader search when the resource is
    undeclared. A retrieval primitive that answered a request no record declared would
    be the second, undeclared access path — it would report success for a fact that no
    declared route reaches, which is the defect class this package is built around.
    """
    if not isinstance(resource, str) or not resource:
        raise ContextError(f"a resource is a non-empty name, not {resource!r}")

    if not store.declares(resource):
        return Err(
            RouteRefusal(
                kind=UNDECLARED,
                subject=resource,
                detail=(
                    "no record in this continuity declares this resource askable-for; "
                    "a route must be declared before it can be used"
                ),
            )
        )

    artifact = store.artifact(resource)
    if artifact is None:
        return Err(
            RouteRefusal(
                kind=UNAVAILABLE,
                subject=resource,
                detail=(
                    "a record declared this resource and the durable content is not "
                    "present in the continuity"
                ),
            )
        )
    return Ok(artifact)


__all__ = ["ArtifactStore", "get_artifact"]
