"""Conformance helpers shared by the K1–K11 suite (design doc §20, §21).

These helpers make kernel invariants assertable rather than merely documented.
"""

from __future__ import annotations

import inspect
from typing import Any, Iterable

from ..model.interpretation import InterpretationIdentity
from ..model.position import SemanticPosition
from ..model.state import ExecutionState

#: Names the Kernel facade must never expose (design doc §18).
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
    """Which forbidden control methods (if any) leak onto the facade."""
    return tuple(name for name in CONTROL_METHOD_NAMES if hasattr(kernel, name))


def facade_is_closed(kernel: Any) -> bool:
    """True when the Kernel facade exposes no control authority (§18, §19)."""
    return not forbidden_control_methods(kernel)


def assert_facade_closed(kernel: Any) -> None:
    leaked = forbidden_control_methods(kernel)
    assert not leaked, f"Kernel facade must not expose control methods: {leaked}"


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
    "CONTROL_METHOD_NAMES",
    "JUDGEMENT_TOKENS",
    "assert_facade_closed",
    "assert_interpretation_is_opaque",
    "assert_no_judgement_leakage",
    "assert_position_fidelity",
    "assert_recoverability_preserved",
    "facade_is_closed",
    "forbidden_control_methods",
    "judgement_leaks",
    "judgement_parameters",
]
