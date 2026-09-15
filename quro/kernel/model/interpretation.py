"""The Interpretation contract — identity, fingerprint, stability (E6, E8, E9).

Interleaved reconstruction is not one reading but three independent axes:
implementation, scope and *interpretation*. This module fixes only the last
one's Kernel-facing vocabulary::

    InterpretationIdentity = Ref<Name>     // opaque, stable, serializable
    Fingerprint            = Opaque<Hash>  // equality-comparable only
    StabilityContract      = nominal | pinned

The Kernel treats ``InterpretationIdentity`` as an *opaque semantic reference*
(frozen contract K-IC-01): it may participate in reconstruction, be persisted,
be restored and be handed to an external resolver, but the Kernel guarantees
nothing about what it *means*. In particular::

    Identity Equality   !=  Semantic Equivalence          (K-IC-02, E11)
    Fingerprint Match   !=  Semantic Equivalence          (K-IC-03, E12)
    Semantic Equivalence is domain-owned                  (K-IC-04, E13)

Consequences that are enforced by *absence*, not by a new type:

* ``InterpretationIdentity`` carries ``(name, version)`` and no content field,
  so a hash can never decide sameness by accident;
* the Kernel never computes a ``Fingerprint`` and never defines its coverage —
  a fingerprint is verification evidence over its declared scope only (E12);
* there is deliberately no ``equivalent(I1, I2)`` operator, no
  ``SemanticEquivalence`` type and no judgement hook anywhere in the Kernel
  facade or its extension slots (E13). A domain that needs an equivalence
  verdict writes its own ``judge(deliveredA, deliveredB, deps) -> bool``
  outside the Kernel, taking delivered semantics as input and never identity or
  a fingerprint.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class InterpretationIdentity:
    """A named, explicit, referential interpretation (E6).

    ``(name, version)`` — comparable, hashable and serializable, which is the
    whole of "which interpretation". It is *not* a bound function, a registry
    handle or a cache key: those are exactly the things that fail to survive a
    process boundary, and a value that carries no declared reading would
    silently resolve to a registry default (the failure mode E6a rules out).
    """

    name: str
    version: str = "v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", str(self.name))
        object.__setattr__(self, "version", str(self.version))

    @property
    def label(self) -> str:
        return f"{self.name}@{self.version}"

    @classmethod
    def of_label(cls, label: str) -> "InterpretationIdentity":
        """Parse ``"name@version"``.

        A bare name parses to ``(name, "")`` — a pair no registry defines, so
        an unnamed identity is *not resolvable* rather than silently defaulted
        (a named reading is required, E6a).
        """
        name, _, version = str(label).partition("@")
        return cls(name=name, version=version)

    @classmethod
    def of(cls, value: "str | InterpretationIdentity") -> "InterpretationIdentity":
        if isinstance(value, InterpretationIdentity):
            return value
        return cls.of_label(value)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.label


@dataclass(frozen=True)
class Fingerprint:
    """An opaque, equality-comparable verification value (E9, E12).

    The Kernel never computes it and never defines what it covers: computing
    and declaring coverage are domain-owned. It exists so a ``pinned``
    checkpoint can *verify* that the resolved reading matches the declared
    verification boundary — never so it can judge meaning.
    """

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", str(self.value))

    @classmethod
    def of(cls, value: "str | Fingerprint") -> "Fingerprint":
        return value if isinstance(value, Fingerprint) else cls(str(value))

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class StabilityContract(str, Enum):
    """How strongly a Checkpoint pins the resolved interpretation (E8, E9).

    ``NOMINAL`` is the default and claims nothing across environments;
    ``PINNED`` adds a fingerprint verification and fails explicitly on drift.
    """

    NOMINAL = "nominal"
    PINNED = "pinned"


# ---------------------------------------------------------------------------
# G1 — the declared boundary between "additive" (E6) and "must refuse" (E6a)
# ---------------------------------------------------------------------------
#: A continuity whose undeclared interpretation is treated as the legacy
#: single-reading case: no declaration means *no identity*, never a fabricated
#: one. This is the pre-G1 behaviour, preserved as an explicit declaration.
LEGACY_EXEMPT = "legacy-exempt"

#: A continuity that *must* declare an interpretation at every recoverable
#: Position: an undeclared reading is refused explicitly
#: (``MountFailure(InterpretationRequired)``), never exempted by heuristic.
MUST_DECLARE = "must-declare"

#: The closed vocabulary of G1's classification. This decision is a per-domain
#: declaration, never a Kernel judgement (Closure 0 §8) — the Kernel only names
#: the two options and honours whichever one is declared.
INTERPRETATION_REQUIREMENTS = (LEGACY_EXEMPT, MUST_DECLARE)


class UnknownInterpretation(Exception):
    """A declared ``InterpretationIdentity`` that no resolver can resolve.

    Raised by a domain resolver and mapped by ``mount`` to
    ``MountFailure(UnknownInterpretation)`` — a refusal, never a substitution
    (E6c / M2).
    """


class CrossDomainInterpretation(Exception):
    """A resolvable identity that is foreign to the addressed Continuity.

    Raised by a domain resolver and mapped by ``mount`` to
    ``MountFailure(CrossDomainInterpretation)`` — again a refusal, never a
    compatible-looking default (E6c).
    """


__all__ = [
    "CrossDomainInterpretation",
    "Fingerprint",
    "InterpretationIdentity",
    "StabilityContract",
    "UnknownInterpretation",
]
