"""Domain resolver boundary for the interpretation axis (E6).

The Kernel requires the *shape* of resolution, never its content::

    resolve(identity) -> Reading | UnknownInterpretation | CrossDomainInterpretation
    fingerprint(resolved) -> Fingerprint?    // only needed under `pinned`

Ownership is a boundary, not a convention (K-IC-04 / E13). The domain provides
``reference resolution``; the Kernel provides ``execution reconstruction`` and
``state continuity``; and the domain — never the Kernel — provides ``meaning
judgement``, ``equivalence rules`` and ``interpretation semantics``.

Consistent with the project's own no-third-party-dependencies discipline, the
Kernel does not *require* a Protocol implementation: it duck-types the resolver
above and keeps the shipped default a plain callable. :class:`DomainResolver` is
offered as an explicit, names-only protocol for domains that want the surface
declared in one place.

**G4 — K16 is a resolver obligation, not a Kernel guarantee.** The Kernel
provides only the two refusal *slots* (``UnknownInterpretation``,
``CrossDomainInterpretation``) and maps them onto ``MountFailure`` kinds. The
judgement "which domain does this identity belong to?" is entirely the domain
resolver's, so the strength of the Kernel's "refusal, never substitution"
guarantee is **bounded by resolver honesty**. This is stated here, in the
domain-adapter contract, so that K16 is an obligation the upper layer must meet
rather than a formality the Kernel merely asserts (see ``RESOLVER_OBLIGATIONS``).
"""

from __future__ import annotations

from typing import Any, Callable, Protocol, runtime_checkable

from ..model.interpretation import InterpretationIdentity

#: ``identity -> reading``. The only capability the Kernel requires.
ResolveFn = Callable[[InterpretationIdentity], Any]

#: G4 — the obligations K16 (cross-domain rejection) places on the domain
#: resolver. The Kernel cannot enforce these; it can only name them, which is
#: exactly the boundary G4 makes explicit.
RESOLVER_OBLIGATIONS: "tuple[str, ...]" = (
    "resolve(identity) either answers with the domain's own reading or raises "
    "UnknownInterpretation / CrossDomainInterpretation explicitly — it never "
    "substitutes a plausible default",
    "a resolvable identity that belongs to another domain is refused as "
    "CrossDomainInterpretation, not silently treated as local",
    "fingerprint(resolved) is computed over the resolver's own declared coverage "
    "only and never over-claims it (E12)",
)


@runtime_checkable
class DomainResolver(Protocol):
    """The declared surface of a domain-owned interpretation resolver."""

    def resolve(self, identity: InterpretationIdentity) -> Any:
        ...  # pragma: no cover - protocol

    def fingerprint(self, resolved: Any) -> Any:
        ...  # pragma: no cover - protocol


class MappingResolver:
    """Reference resolver over a fixed ``identity -> reading`` mapping.

    Deliberately *nominal*: lookup keys on ``(name, version)`` and nothing else,
    so a registry that has drifted answers its old label without complaint. That
    is not a defect — it is E8's measured default, and it is exactly why a
    domain that needs more declares ``pinned`` (E9) and lets the fingerprint be
    verified at mount time.

    An unknown identity is *refused*, never substituted; a domain that also
    wants `CrossDomainInterpretation` for a resolvable-but-foreign identity can
    supply a :meth:`resolver` raising that instead.
    """

    def __init__(self, resolved: "dict[str, Any] | None" = None) -> None:
        self._resolved = {str(key): value for key, value in (resolved or {}).items()}

    def with_resolution(self, identity: "str | InterpretationIdentity", resolved: Any) -> "MappingResolver":
        key = InterpretationIdentity.of(identity).label
        table = dict(self._resolved)
        table[key] = resolved
        return MappingResolver(table)

    def labels(self) -> "tuple[str, ...]":
        return tuple(sorted(self._resolved))

    def resolve(self, identity: InterpretationIdentity) -> Any:
        from ..model.interpretation import UnknownInterpretation

        try:
            return self._resolved[InterpretationIdentity.of(identity).label]
        except KeyError:
            raise UnknownInterpretation(
                f"resolver defines {self.labels()}, not {InterpretationIdentity.of(identity).label!r}"
            ) from None


def resolver(reference: Any) -> "ResolveFn | None":
    """Normalize ``reference`` into an ``identity -> reading`` callable."""
    if reference is None:
        return None
    candidate = getattr(reference, "resolve", None)
    if callable(candidate):
        return candidate
    if callable(reference):
        return reference
    return None


def resolved_fingerprint(resolved: Any) -> Any:
    """The resolved value's *domain-computed* fingerprint, or ``None``.

    ``None`` is never "no claim": under a pinned contract an unverifiable
    resolution is a drift failure (E9/E12).
    """
    return getattr(resolved, "content_fingerprint", None) or getattr(
        resolved, "fingerprint", None
    )


__all__ = ["DomainResolver", "MappingResolver", "ResolveFn", "resolved_fingerprint", "resolver"]
