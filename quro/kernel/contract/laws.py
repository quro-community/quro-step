"""The closed Kernel contract laws (design doc §20).

These are the laws the minimal Kernel is governed by. They are data, not
documentation only: the conformance suite references them, and `make laws`
prints them.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Law:
    id: str
    name: str
    statement: str


MOUNT_LAWS = (
    Law("M1", "Position Fidelity", "mount(P, C) = S  =>  positionOf(S) = P"),
    Law("M2", "No Hidden Position Substitution", "Mount must not silently replace the requested Position."),
    Law(
        "M3",
        "Structural Resolution Correctness",
        "The mounted unit must correspond to the unit designated by the Position under the applicable Continuity/Plan relation.",
    ),
    Law("M4", "Occurrence Preservation", "X#0 != X#1 even when UnitId(X#0) = UnitId(X#1)."),
    Law("M5", "Mount Purity", "Equivalent mount(P, C) calls produce equivalent state and do not mutate C."),
    Law("M6", "Occurrence Identity", "Occurrence identity is reconstructable independently of arbitrary domain detail."),
    Law("M7", "Conversation Independence", "A declared recoverable Position can be reconstructed without the historical Agent conversation."),
)

BOUNDARY_LAWS = (
    Law("E1", "Domain Payload Non-Interference", "Domain payload cannot encode hidden Position/control decisions."),
    Law("E2", "Update Non-Destructiveness", "Previously recoverable Positions remain recoverable after a successful update."),
    Law("E3", "Failure Does Not Auto-Advance", "Failure does not implicitly invoke update or next-position establishment."),
    Law("E4", "Live-by-Default Re-entry", "mount(P, C) uses live/current Continuity unless an explicit pinned extension is introduced."),
    Law("E5", "Provenance Sufficiency", "Provenance must preserve Position + InstanceId for every Artifact occurrence."),
)

INTERPRETATION_LAWS = (
    Law(
        "E6",
        "Named-Interpretation Requirement",
        "mount(P, C, I): I must be resolvable without any ambient or registry-default "
        "fallback; must be a stable, serializable reference; a foreign I fails explicitly "
        "as MountFailure; I is preserved across update unless changed by a named operation; "
        "determinism (M3/M5) is defined per fixed I, not across I.",
    ),
    Law(
        "E7",
        "Dependency Closure Ownership",
        "For a declared recoverable Position under I there must exist some explicit set of "
        "record and non-record dependencies whose removal changes the declared semantics; "
        "each identified dependency has an explicit owner whose preservation contract "
        "governs it across update/fork/backtrack/fold. No prefix or algebra is required.",
    ),
    Law(
        "E8",
        "Nominal Resolution Only",
        "Under stabilityContract = nominal (the default), a resolved InterpretationIdentity "
        "carries no cross-environment semantic equivalence guarantee. This is the "
        "correctly-scoped default, not a gap for mount to close.",
    ),
    Law(
        "E9",
        "Declared Stability Contract",
        "A Checkpoint may declare stabilityContract = pinned with a pinnedFingerprint. mount "
        "must verify the fingerprint at resolution time and fail explicitly "
        "(MountFailure(InterpretationDrift)) on mismatch, never silently proceed. Under "
        "nominal no such check occurs and none may be implied.",
    ),
    Law(
        "E10",
        "Branch-Sensitivity Must Be Declared",
        "FORWARD CONSTRAINT, not Kernel-enforceable: preservation of an "
        "InterpretationIdentity across a Backtrack transition must not be assumed sound by "
        "default; a branch-sensitive interpretation must be an explicit declaration the "
        "Backtrack mechanism consults once it is specified. The Kernel does not implement "
        "Backtrack and cannot enforce this today.",
    ),
    Law(
        "E11",
        "Identity Is Not Equivalence",
        "Resolution equality neither implies nor is implied by semantic equivalence of what "
        "is delivered: different identities may be domain-declared aliases of one meaning, "
        "and one identity may legitimately resolve to different meanings across environments "
        "or hidden dependencies. Differing I producing the same state is not an impurity, "
        "and same I producing differing state is not evidence of a mount defect.",
    ),
    Law(
        "E12",
        "Fingerprint Verifies, Does Not Judge",
        "A pinnedFingerprint is a verification artifact over its declared coverage only. "
        "Equality is evidence of no drift within what was hashed, never evidence of semantic "
        "equivalence. Inequality is evidence of drift only under a pinned contract; under "
        "nominal it carries no claim at all.",
    ),
    Law(
        "E13",
        "Semantic Equivalence Is Domain-Owned",
        "Whether two resolved interpretations mean the same thing is a domain judgement over "
        "delivered semantics and declared dependencies — never over the written "
        "InterpretationIdentity and never over a Fingerprint. The Kernel facade must not "
        "offer, imply, or be extended to offer a built-in equivalence operator over identity "
        "or fingerprint.",
    ),
)

ALL_LAWS = MOUNT_LAWS + BOUNDARY_LAWS + INTERPRETATION_LAWS

_LAW_INDEX = {item.id: item for item in ALL_LAWS}


def all_laws() -> "tuple[Law, ...]":
    return ALL_LAWS


def law(law_id: str) -> Law:
    return _LAW_INDEX[law_id.upper()]


__all__ = ["ALL_LAWS", "BOUNDARY_LAWS", "INTERPRETATION_LAWS", "Law", "MOUNT_LAWS", "all_laws", "law"]
