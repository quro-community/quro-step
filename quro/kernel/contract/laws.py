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
    Law(
        "E2",
        "Update Non-Destructiveness",
        "Previously recoverable Positions remain recoverable after a successful update. "
        "The formal form is the same law: update(C, A, prov) = Ok(C') => for every P, "
        "isRecoverable(P, C) => isRecoverable(P, C'); otherwise Err(RecoverabilityViolation(P)). "
        "The design doc spells that formal form E2' (v0.2 §16.3) and the prose form E2 "
        "(v0.2 §20.9); they are one law, and the prime marks the quantified spelling rather "
        "than a second obligation. Note what E2 does NOT constrain: it is a statement about "
        "structural recoverability only. It entails no content-preservation law for any "
        "information-reducing operation -- see E16, and the lemma that motivates it.",
    ),
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

# -- Tier 2: laws the framework states, which the Kernel cannot enforce ---------
#
# E1-E13 above bind the Kernel itself and are checked by the K-suite. The two laws
# below bind mechanisms that live ABOVE the Kernel -- a relation, a branch, a
# return, a fold -- which the Kernel never reads, compares or resolves. They are
# therefore stated here as obligations and conformance-checked elsewhere.
#
# This distinction is load-bearing, not clerical. The Kernel absorbs semantic
# *constraints*, never domain *capabilities*: a law may bind the layer above the
# Kernel without the Kernel gaining any implementation feature. A reader who
# assumes every law in this file has a K-test will under-count what is checked;
# a reader who assumes a law without a K-test is unverified will under-count what
# is settled. Both laws below carry their conformance location explicitly.

KERNEL_ADJACENT_LAWS = (
    Law(
        "E15",
        "Verification-Judgement Separation Is Type-Generic",
        "No function of Kernel-visible facts decides a domain judgement whose subject may "
        "depend on a fact the function's input does not determine. Stated first for "
        "InterpretationIdentity (E11-E13), the separation holds for every Kernel-adjacent "
        "type: relations, branches, returns, folds. A Kernel-performable comparison is "
        "never evidence that two things mean the same, and verification is never judgement. "
        "Conformance: the Kernel enforces its half structurally by absence (K21); the "
        "type-generic half is conformance-checked ABOVE the Kernel, by the milestone "
        "closure that declared it.",
    ),
    Law(
        "E16",
        "Fold Preservation",
        "For every declared-recoverable SemanticPosition P, a fold's own declaration (that it "
        "happened, what it covered, what it summarized) and every fact its retention manifest "
        "promises to retain must remain derivable from mount(P, C') -- through the mounted "
        "state itself, the domain's declared projection, or an on-demand resource the domain "
        "declares reachable -- after any fold applied to C. Representation may change; "
        "required semantics may not. History is never mutated or deleted by a legitimate "
        "fold. The obligation has TWO halves that fail independently, and a conformance check "
        "must exercise each. Conformance lives ABOVE the Kernel, which never sees a fold "
        "record: a reference implementation and a falsification matrix, recorded by the "
        "milestone closure that declared this law. Nothing in this package may name that "
        "package -- the experiment trees are disposable, and a kernel module that cites one "
        "would depend on a directory the project is free to delete.",
    ),
)

ALL_LAWS = MOUNT_LAWS + BOUNDARY_LAWS + INTERPRETATION_LAWS + KERNEL_ADJACENT_LAWS

_LAW_INDEX = {item.id: item for item in ALL_LAWS}


def all_laws() -> "tuple[Law, ...]":
    return ALL_LAWS


def law(law_id: str) -> Law:
    return _LAW_INDEX[law_id.upper()]


def kernel_enforced_laws() -> "tuple[Law, ...]":
    """The laws the Kernel itself enforces and the K-suite checks.

    Tier 1 only. ``all_laws()`` includes the Tier-2 laws above, which bind the
    layer above the Kernel and are conformance-checked there.
    """
    return MOUNT_LAWS + BOUNDARY_LAWS + INTERPRETATION_LAWS


__all__ = [
    "ALL_LAWS",
    "BOUNDARY_LAWS",
    "INTERPRETATION_LAWS",
    "KERNEL_ADJACENT_LAWS",
    "Law",
    "MOUNT_LAWS",
    "all_laws",
    "kernel_enforced_laws",
    "law",
]
