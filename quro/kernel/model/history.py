"""History — the append-only runtime record substrate (design doc §6).

A record's presence in History does **not** make it semantic truth::

    recorded != authoritative

History is broader than ExecutionContinuity. A conversation trace can exist in
History without ever becoming part of semantic continuity, which is what
preserves Conversation Independence (Law M7).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from .position import SemanticPosition


class Record:
    """Base class for runtime records."""

    @property
    def kind(self) -> str:  # pragma: no cover - overridden
        raise NotImplementedError


@dataclass(frozen=True)
class SemanticRecord(Record):
    """A record classified as continuity-relevant."""

    payload: Mapping[str, Any] = field(default_factory=dict)
    position: "SemanticPosition | None" = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))

    @property
    def kind(self) -> str:
        return "semantic"


@dataclass(frozen=True)
class ConversationRecord(Record):
    """A disposable Agent-conversation trace.

    Deliberately *not* semantic: deleting it must not destroy declared
    recoverability (Law M7 / K1).
    """

    text: str = ""
    role: str = "agent"

    @property
    def kind(self) -> str:
        return "conversation"


@dataclass(frozen=True)
class ToolTraceRecord(Record):
    """A tool invocation trace (runtime record, not semantic truth)."""

    tool: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "detail", MappingProxyType(dict(self.detail)))

    @property
    def kind(self) -> str:
        return "tool-trace"


@dataclass(frozen=True)
class History:
    """Append-only, non-destructive record sequence.

    History append law (§6.1)::

        H' = H ++ [record]

    Recording a new record never removes previously recorded records. Only
    ``append``/``extend`` exist; there is no removal operation on the semantic
    substrate.
    """

    records: "tuple[Record, ...]" = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "records", tuple(self.records))

    # -- append -----------------------------------------------------------
    def append(self, record: Record) -> "History":
        return History(records=self.records + (record,))

    def extend(self, records: "tuple[Record, ...] | list[Record]") -> "History":
        return History(records=self.records + tuple(records))

    # -- read -------------------------------------------------------------
    def __len__(self) -> int:
        return len(self.records)

    def __iter__(self):
        return iter(self.records)

    def __getitem__(self, index):
        return self.records[index]

    def of_kind(self, kind: str) -> "tuple[Record, ...]":
        return tuple(record for record in self.records if record.kind == kind)

    def semantic_records(self) -> "tuple[SemanticRecord, ...]":
        return tuple(r for r in self.records if isinstance(r, SemanticRecord))

    def conversation_records(self) -> "tuple[ConversationRecord, ...]":
        return tuple(r for r in self.records if isinstance(r, ConversationRecord))

    def without_conversation_records(self) -> "History":
        """Drop disposable conversation traces.

        This models *external* Agent-transcript deletion (e.g. an expired LLM
        session), which the architecture forbids from affecting declared
        recoverability. It is not a removal operation on semantic records and
        therefore does not weaken the append-only law.
        """
        return History(
            records=tuple(
                r for r in self.records if not isinstance(r, ConversationRecord)
            )
        )


__all__ = [
    "ConversationRecord",
    "History",
    "Record",
    "SemanticRecord",
    "ToolTraceRecord",
]
