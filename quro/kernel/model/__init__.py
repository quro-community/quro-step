"""Canonical Kernel object model (design doc §4, §35)."""

from .artifact import Artifact, ArtifactPayload
from .continuity import (
    DEFAULT_BRANCH,
    ExecutionContinuity,
    OccurrenceKey,
)
from .failure import (
    Failure,
    FailureReason,
    MountFailure,
    MountFailureKind,
    UpdateFailure,
    UpdateFailureKind,
)
from .history import (
    ConversationRecord,
    History,
    Record,
    SemanticRecord,
    ToolTraceRecord,
)
from .ids import ArtifactId, BranchId, InstanceId, StepOccurrence, UnitId
from .plan import ExecutionPlan
from .position import PathSegment, SemanticPosition
from .provenance import CausalRelation, Provenance, ProvenanceDetail, RelationKind
from .result import Err, Ok, Result, err, is_err, is_ok, ok
from .state import ExecutionState, StateDomainPayload, position_of
from .unit import ExecUnit, Step, UnitKind
__all__ = [
    "Artifact",
    "ArtifactId",
    "ArtifactPayload",
    "BranchId",
    "CausalRelation",
    "ConversationRecord",
    "DEFAULT_BRANCH",
    "Err",
    "ExecutionContinuity",
    "ExecutionPlan",
    "ExecutionState",
    "ExecUnit",
    "Failure",
    "FailureReason",
    "History",
    "InstanceId",
    "MountFailure",
    "MountFailureKind",
    "OccurrenceKey",
    "Ok",
    "PathSegment",
    "Provenance",
    "ProvenanceDetail",
    "Record",
    "RelationKind",
    "Result",
    "SemanticPosition",
    "SemanticRecord",
    "StateDomainPayload",
    "Step",
    "StepOccurrence",
    "ToolTraceRecord",
    "UnitId",
    "UnitKind",
    "UpdateFailure",
    "UpdateFailureKind",
    "err",
    "is_err",
    "is_ok",
    "ok",
    "position_of",
]
