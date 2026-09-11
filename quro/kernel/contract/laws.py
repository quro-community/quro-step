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

ALL_LAWS = MOUNT_LAWS + BOUNDARY_LAWS

_LAW_INDEX = {item.id: item for item in ALL_LAWS}


def all_laws() -> "tuple[Law, ...]":
    return ALL_LAWS


def law(law_id: str) -> Law:
    return _LAW_INDEX[law_id.upper()]


__all__ = ["ALL_LAWS", "BOUNDARY_LAWS", "Law", "MOUNT_LAWS", "all_laws", "law"]
