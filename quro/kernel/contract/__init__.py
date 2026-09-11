"""Contract surface: laws and conformance helpers (design doc §20, §21)."""

from .conformance import (
    CONTROL_METHOD_NAMES,
    assert_facade_closed,
    assert_position_fidelity,
    assert_recoverability_preserved,
    facade_is_closed,
    forbidden_control_methods,
)
from .laws import BOUNDARY_LAWS, MOUNT_LAWS, Law, all_laws, law

__all__ = [
    "BOUNDARY_LAWS",
    "CONTROL_METHOD_NAMES",
    "Law",
    "MOUNT_LAWS",
    "all_laws",
    "assert_facade_closed",
    "assert_position_fidelity",
    "assert_recoverability_preserved",
    "facade_is_closed",
    "forbidden_control_methods",
    "law",
]
