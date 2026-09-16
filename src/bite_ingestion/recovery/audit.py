"""Append-only audit log for Recover attempts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from bite_ingestion.recovery.types import RebiteRequest, RecoverState


@dataclass(frozen=True)
class AuditRecord:
    step_index: int
    request: dict[str, Any]
    outcome: str
    returned_evidence_ids: tuple[str, ...]
    estimated_tokens: int
    message: str = ""
    sufficiency_kind: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "request": dict(self.request),
            "outcome": self.outcome,
            "returned_evidence_ids": list(self.returned_evidence_ids),
            "estimated_tokens": self.estimated_tokens,
            "message": self.message,
            "sufficiency_kind": self.sufficiency_kind,
        }


@dataclass
class AuditLog:
    """Append-only list bound to RecoverState (or standalone)."""

    records: list[dict[str, Any]] = field(default_factory=list)

    def append(
        self,
        *,
        step_index: int,
        request: RebiteRequest | Mapping[str, Any],
        outcome: str,
        returned_evidence_ids: Sequence[str],
        estimated_tokens: int = 0,
        message: str = "",
        sufficiency_kind: str | None = None,
    ) -> dict[str, Any]:
        req_dict = request.to_dict() if isinstance(request, RebiteRequest) else dict(request)
        row = AuditRecord(
            step_index=step_index,
            request=req_dict,
            outcome=outcome,
            returned_evidence_ids=tuple(str(x) for x in returned_evidence_ids),
            estimated_tokens=int(estimated_tokens),
            message=message,
            sufficiency_kind=sufficiency_kind,
        ).to_dict()
        self.records.append(row)
        return row

    def extend_from_state(self, state: RecoverState) -> None:
        for row in state.audit_log:
            self.records.append(dict(row))

    def __len__(self) -> int:
        return len(self.records)

    def to_list(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.records]


def append_audit(
    state: RecoverState,
    *,
    request: RebiteRequest | Mapping[str, Any],
    outcome: str,
    returned_evidence_ids: Sequence[str],
    estimated_tokens: int = 0,
    message: str = "",
    sufficiency_kind: str | None = None,
) -> dict[str, Any]:
    """Append to state.audit_log and bump step_index."""
    log = AuditLog(records=state.audit_log)
    row = log.append(
        step_index=state.step_index,
        request=request,
        outcome=outcome,
        returned_evidence_ids=returned_evidence_ids,
        estimated_tokens=estimated_tokens,
        message=message,
        sufficiency_kind=sufficiency_kind,
    )
    state.step_index += 1
    return row
