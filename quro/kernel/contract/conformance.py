"""Conformance helpers shared by the K1–K11 suite (design doc §20, §21).

These helpers make kernel invariants assertable rather than merely documented.
"""

from __future__ import annotations

import inspect
from typing import Any, Iterable

from ..model.interpretation import InterpretationIdentity
from ..model.position import SemanticPosition
from ..model.state import ExecutionState

#: Names the Kernel facade has been known to grow. **A diagnostic, not the
#: guarantee** — and deliberately *not* widened when the guarantee was added,
#: for two reasons.
#:
#: First, a blocklist of forbidden names cannot be completed. Three consecutive
#: milestones each injected a facade method this list did not catch, and each
#: reported the miss against whichever detector actually ran:
#:
#:     M2 measured  relate, reconcile                   not in the list
#:     M3 measured  allocate, resolve_backtrack_target  not in the list
#:     M4 measured  discard, resolve_fold_coverage      not in the list
#:
#: while ``backtrack``, ``fork``, ``fold`` and ``compact`` happened to be present.
#: So a green control read as "the boundary is guarded" for the four names that
#: were listed and said nothing about the ones that were not. Three measurements
#: is a pattern, not bad luck: **the list only ever covers the names somebody
#: thought of**, and adding the six names above would just move the boundary of
#: what nobody has thought of yet.
#:
#: Second, three milestones' evidence records measure *this* list, by name, in
#: their committed ``results/``. Widening it would silently invalidate those
#: measurements rather than close the gap they describe.
#:
#: The gap closes by :func:`unexpected_facade_methods` — an allowlist, which is
#: exact and cannot be outgrown. That is what K22/D5 asked for; this tuple stays
#: as the historical diagnostic it always was.
CONTROL_METHOD_NAMES = (
    "next",
    "steer",
    "retry",
    "backtrack",
    "replan",
    "compact",
    "fork",
    "fold",
)

#: The facade's **exact** public surface. Law E13's boundary and design doc §18's
#: "deliberately small" are the same claim: three methods, and nothing else.
#:
#: Checking against this set is strictly stronger than checking against
#: :data:`CONTROL_METHOD_NAMES`, because it does not require anyone to have
#: predicted the name. A facade method nobody anticipated fails it.
ALLOWED_FACADE_METHODS = (
    "mount",
    "execute",
    "update",
)

#: Substrings that would indicate a semantic *judgement* operator (Law E13).
JUDGEMENT_TOKENS = (
    "equivalen",
    "equivalent",
    "judge",
    "judgement",
    "judgment",
    "same_meaning",
    "means_same",
    "supersede",
    "dedup",
)


def _signature_names(callable_object: Any) -> "tuple[str, ...]":
    try:
        signature = inspect.signature(callable_object)
    except (TypeError, ValueError):  # builtins / opaque callables
        return ()
    return tuple(signature.parameters)


def judgement_leaks(target: Any) -> "tuple[str, ...]":
    """Member names on ``target`` that look like a semantic judgement hook.

    Law E13 is enforced by *absence*, and absence is exactly what this detects:
    no ``equivalent(I1, I2)``, no ``judge(...)``, no ``SemanticEquivalence``
    helper anywhere on the Kernel facade, the mounted state, the failure
    boundary or the extension slots — checked structurally, not by convention.
    """
    leaks = []
    for name in dir(target):
        if name.startswith("__"):
            continue
        lowered = name.lower()
        if any(token in lowered for token in JUDGEMENT_TOKENS):
            leaks.append(name)
    return tuple(leaks)


def judgement_parameters(target: Any) -> "tuple[str, ...]":
    """Judgement-looking *parameter* names — including extension-slot ``data`` keys.

    Covers the nominal extension slots too: a domain is free to store whatever
    it likes in ``StateDomainPayload``/``ProvenanceDetail``/``ArtifactPayload``,
    but the Kernel's own boundary may not name a judgement parameter anywhere.
    """
    leaks = []
    callables = [target]
    callables.extend(
        member
        for name in dir(target)
        if not name.startswith("__")
        for member in (getattr(target, name, None),)
        if callable(member)
    )
    for candidate in callables:
        for name in _signature_names(candidate):
            if any(token in name.lower() for token in JUDGEMENT_TOKENS):
                leaks.append(f"{getattr(candidate, '__name__', candidate)}({name})")
    return tuple(sorted(set(leaks)))


def forbidden_control_methods(kernel: Any) -> "tuple[str, ...]":
    """Which *named* forbidden control methods (if any) leak onto the facade.

    A diagnostic: it says which known-forbidden name appeared, so a failure is
    legible. It is not the guarantee — see :data:`CONTROL_METHOD_NAMES`.
    """
    return tuple(name for name in CONTROL_METHOD_NAMES if hasattr(kernel, name))


def facade_surface(kernel: Any) -> "tuple[str, ...]":
    """The facade's public method surface, sorted.

    ``type(kernel)`` is inspected rather than the instance, so an instance that
    happens to carry a same-named attribute cannot mask a facade method, and a
    facade method cannot be hidden by shadowing.
    """
    names = (
        name
        for name in dir(type(kernel))
        if not name.startswith("_") and callable(getattr(type(kernel), name, None))
    )
    return tuple(sorted(names))


def unexpected_facade_methods(kernel: Any) -> "tuple[str, ...]":
    """Public methods on the facade that are not one of the three.

    **This is the guarantee.** An allowlist cannot be outgrown by a name nobody
    thought of — which is precisely how a blocklist of forbidden names failed
    three milestones running (see :data:`CONTROL_METHOD_NAMES`). A facade that
    grows *any* public method, for any operation, under any name, fails here.
    """
    allowed = set(ALLOWED_FACADE_METHODS)
    return tuple(name for name in facade_surface(kernel) if name not in allowed)


def facade_is_closed(kernel: Any) -> bool:
    """True when the Kernel facade exposes no control authority (§18, §19).

    Both checks, because they answer different questions and the allowlist alone
    would not say *what* leaked.
    """
    return not forbidden_control_methods(kernel) and not unexpected_facade_methods(kernel)


def facade_surface_is_exact(kernel: Any) -> bool:
    """True when the facade is exactly the three methods — nothing added, nothing lost.

    Compared as sets: :data:`ALLOWED_FACADE_METHODS` is in the canonical
    mount → execute → update reading order, and the surface is sorted for stable
    reporting. The order is documentation, not contract.
    """
    return set(facade_surface(kernel)) == set(ALLOWED_FACADE_METHODS)


def assert_facade_closed(kernel: Any) -> None:
    leaked = forbidden_control_methods(kernel)
    assert not leaked, f"Kernel facade must not expose control methods: {leaked}"
    unexpected = unexpected_facade_methods(kernel)
    assert not unexpected, (
        "Kernel facade must expose exactly "
        f"{ALLOWED_FACADE_METHODS}; found unexpected public methods: {unexpected}"
    )


def assert_position_fidelity(state: ExecutionState, position: SemanticPosition) -> None:
    """Law M1 — positionOf(mount(P, C)) = P."""
    assert state.position == position, (
        f"Position Fidelity violated: mounted {state.position} for requested {position}"
    )


def assert_recoverability_preserved(
    before: "Iterable[SemanticPosition]", after: "Iterable[SemanticPosition]"
) -> None:
    """Law E2 — previously recoverable Positions remain recoverable."""
    before, after = frozenset(before), frozenset(after)
    lost = before - after
    assert not lost, f"recoverability lost for: {sorted(str(p) for p in lost)}"


def assert_no_judgement_leakage(target: Any) -> None:
    """Law E13 — no equivalence/judgement operator on a Kernel boundary."""
    leaked = judgement_leaks(target)
    parameters = judgement_parameters(target)
    assert not leaked and not parameters, (
        "Kernel boundary must not expose or accept semantic judgement: "
        f"members={leaked} parameters={parameters}"
    )


def assert_interpretation_is_opaque(identity: "InterpretationIdentity | None") -> None:
    """Law E11 — an identity carries ``(name, version)`` and nothing that judges.

    The Kernel treats an interpretation reference as opaque (K-IC-01): it may be
    compared and serialized, but it has no content field and no reading attached.
    """
    if identity is None:
        return
    assert identity == InterpretationIdentity.of(identity)
    assert not hasattr(identity, "content_fingerprint")
    assert not hasattr(identity, "reading")


__all__ = [
    "ALLOWED_FACADE_METHODS",
    "CONTROL_METHOD_NAMES",
    "JUDGEMENT_TOKENS",
    "assert_facade_closed",
    "facade_surface",
    "facade_surface_is_exact",
    "unexpected_facade_methods",
    "assert_interpretation_is_opaque",
    "assert_no_judgement_leakage",
    "assert_position_fidelity",
    "assert_recoverability_preserved",
    "facade_is_closed",
    "forbidden_control_methods",
    "judgement_leaks",
    "judgement_parameters",
]
