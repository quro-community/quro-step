"""Contract surface: laws and conformance helpers (design doc §20, §21)."""

from .conformance import (
    CONTROL_METHOD_NAMES,
    JUDGEMENT_TOKENS,
    assert_facade_closed,
    assert_interpretation_is_opaque,
    assert_no_judgement_leakage,
    assert_position_fidelity,
    assert_recoverability_preserved,
    facade_is_closed,
    forbidden_control_methods,
    judgement_leaks,
    judgement_parameters,
)
from .laws import (
    BOUNDARY_LAWS,
    INTERPRETATION_LAWS,
    MOUNT_LAWS,
    Law,
    all_laws,
    law,
)

__all__ = [
    "BOUNDARY_LAWS",
    "CONTROL_METHOD_NAMES",
    "INTERPRETATION_LAWS",
    "JUDGEMENT_TOKENS",
    "Law",
    "MOUNT_LAWS",
    "all_laws",
    "assert_facade_closed",
    "assert_interpretation_is_opaque",
    "assert_no_judgement_leakage",
    "assert_position_fidelity",
    "assert_recoverability_preserved",
    "facade_is_closed",
    "forbidden_control_methods",
    "judgement_leaks",
    "judgement_parameters",
    "law",
]
