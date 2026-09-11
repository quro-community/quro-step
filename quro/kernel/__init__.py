"""quro.kernel — the minimal unified execution model.

Public surface::

    Kernel.mount(position, continuity)        -> Result[ExecutionState, MountFailure]
    Kernel.execute(state, unit)               -> Result[Artifact, Failure]
    Kernel.update(continuity, artifact, prov) -> Result[ExecutionContinuity, UpdateFailure]

Dependency direction (design doc §35)::

    Higher-Level Modules -> Kernel Facade -> Mount/Execute/Update -> Kernel Model -> Domain Interfaces

Reverse dependencies are forbidden: nothing in this package may import
``quro.steering``, ``quro.recovery``, ``quro.compaction``, ``quro.backtrack``,
``quro.fork``, ``quro.replanning``, ``quro.context`` or ``quro.domain``.
"""

from .contract.conformance import (
    CONTROL_METHOD_NAMES,
    assert_facade_closed,
    facade_is_closed,
    forbidden_control_methods,
)
from .contract.laws import ALL_LAWS, BOUNDARY_LAWS, MOUNT_LAWS, Law, all_laws, law
from .continuity.recoverability import is_recoverable, lost_recoverability
from .continuity.updater import ContinuityUpdater
from .execution.executor import CallableExecutor, Executor, execute_into
from .kernel.facade import Kernel
from .model import (
    Artifact,
    ArtifactId,
    ArtifactPayload,
    BranchId,
    CausalRelation,
    ConversationRecord,
    DEFAULT_BRANCH,
    Err,
    ExecutionContinuity,
    ExecutionPlan,
    ExecutionState,
    ExecUnit,
    Failure,
    FailureReason,
    History,
    InstanceId,
    MountFailure,
    MountFailureKind,
    Ok,
    PathSegment,
    Provenance,
    ProvenanceDetail,
    Record,
    RelationKind,
    Result,
    SemanticPosition,
    SemanticRecord,
    StateDomainPayload,
    Step,
    StepOccurrence,
    ToolTraceRecord,
    UnitId,
    UnitKind,
    UpdateFailure,
    UpdateFailureKind,
    err,
    is_err,
    is_ok,
    ok,
    position_of,
)
from .mount.mounter import Mounter
from .mount.resolver import resolve_unit_at

__all__ = [
    "ALL_LAWS",
    "Artifact",
    "ArtifactId",
    "ArtifactPayload",
    "BOUNDARY_LAWS",
    "BranchId",
    "CONTROL_METHOD_NAMES",
    "CallableExecutor",
    "CausalRelation",
    "ContinuityUpdater",
    "ConversationRecord",
    "DEFAULT_BRANCH",
    "Err",
    "ExecutionContinuity",
    "ExecutionPlan",
    "ExecutionState",
    "ExecUnit",
    "Executor",
    "Failure",
    "FailureReason",
    "History",
    "InstanceId",
    "Kernel",
    "Law",
    "MOUNT_LAWS",
    "MountFailure",
    "MountFailureKind",
    "Mounter",
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
    "all_laws",
    "assert_facade_closed",
    "err",
    "execute_into",
    "facade_is_closed",
    "forbidden_control_methods",
    "is_err",
    "is_ok",
    "is_recoverable",
    "law",
    "lost_recoverability",
    "ok",
    "position_of",
    "resolve_unit_at",
]
