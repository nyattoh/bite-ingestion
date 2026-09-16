"""Request/response dataclasses and allowed request_type enum (Q_req v0.1)."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RequestType(str, Enum):
    """Allowed Recover request types (BITE-03 §4.1 / BITE-11)."""

    FETCH_UNIT = "fetch_unit"
    FETCH_SPAN = "fetch_span"
    FETCH_AGGREGATE_MEMBERS = "fetch_aggregate_members"
    FETCH_QUARANTINE = "fetch_quarantine"
    FETCH_BY_VERSION = "fetch_by_version"
    CLARIFY_SUFFICIENCY = "clarify_sufficiency"


ALLOWED_REQUEST_TYPES: frozenset[str] = frozenset(rt.value for rt in RequestType)


class OutcomeCode(str, Enum):
    """Stop / result codes for a single recover attempt."""

    SUCCESS = "success"
    RECOVER_MISS = "recover_miss"
    BUDGET_EXHAUSTED = "budget_exhausted"
    INVALID_REQUEST = "invalid_request"
    STALE_OR_BROKEN_LOCATOR = "stale_or_broken_locator"
    REFUSED_WITHDRAWN = "refused_withdrawn"
    REFUSED_FORBIDDEN = "refused_forbidden"
    REFUSED_INJECTION_SUSPECT = "refused_injection_suspect"
    SUPPRESSED_REPEAT = "suppressed_repeat"
    CLARIFY_META = "clarify_meta"


class SufficiencyKind(str, Enum):
    """Distinguish missing evidence vs model indecision (never treat loops as success)."""

    MISSING_EVIDENCE = "missing_evidence"
    MODEL_INDECISION = "model_indecision"
    SUFFICIENT = "sufficient"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RebiteRequest:
    """Schema'd re-bite request (see spec/rebite-request.schema.json)."""

    request_type: str
    request_id: str | None = None
    unit_id: str | None = None
    r_id: str | None = None
    handle_id: str | None = None
    aggregate_parent: str | None = None
    reason: str | None = None
    version: str | None = None
    span: Mapping[str, Any] | None = None
    stale: bool | None = None
    notes: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> RebiteRequest:
        span = data.get("span")
        return cls(
            request_type=str(data.get("request_type", "")),
            request_id=_opt_str(data.get("request_id")),
            unit_id=_opt_str(data.get("unit_id")),
            r_id=_opt_str(data.get("r_id")),
            handle_id=_opt_str(data.get("handle_id")),
            aggregate_parent=_opt_str(data.get("aggregate_parent")),
            reason=_opt_str(data.get("reason")),
            version=_opt_str(data.get("version")),
            span=dict(span) if isinstance(span, Mapping) else None,
            stale=bool(data["stale"]) if "stale" in data and data["stale"] is not None else None,
            notes=_opt_str(data.get("notes")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "request_type": self.request_type,
            "unit_id": self.unit_id,
            "r_id": self.r_id,
            "handle_id": self.handle_id,
            "aggregate_parent": self.aggregate_parent,
            "reason": self.reason,
            "version": self.version,
            "span": dict(self.span) if self.span else None,
            "stale": self.stale,
            "notes": self.notes,
        }


@dataclass
class RecoverState:
    """Mutable recover session state (budgets, dedupe, audit)."""

    calls: int = 0
    rebite_tokens: int = 0
    seen_fetch_keys: list[str] = field(default_factory=list)
    audit_log: list[dict[str, Any]] = field(default_factory=list)
    step_index: int = 0

    def snapshot(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "rebite_tokens": self.rebite_tokens,
            "seen_fetch_keys": list(self.seen_fetch_keys),
            "audit_log": [dict(x) for x in self.audit_log],
            "step_index": self.step_index,
        }


@dataclass
class RecoverResult:
    """Result of RecoverEngine.recover."""

    outcome: str
    packet: dict[str, Any]
    state: RecoverState
    returned_evidence_ids: list[str] = field(default_factory=list)
    estimated_tokens: int = 0
    sufficiency_kind: str | None = None
    meta: dict[str, Any] | None = None
    message: str = ""
    recovery_success: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "returned_evidence_ids": list(self.returned_evidence_ids),
            "estimated_tokens": self.estimated_tokens,
            "sufficiency_kind": self.sufficiency_kind,
            "meta": dict(self.meta) if self.meta else None,
            "message": self.message,
            "recovery_success": self.recovery_success,
            "state": self.state.snapshot(),
            "packet": self.packet,
        }


def _opt_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v)
    return s if s else None


def ensure_packet_recovery_fields(packet: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    """Ensure rebite / accounting / R / tau fields exist (in-place)."""
    if "visible_evidence" not in packet or packet["visible_evidence"] is None:
        packet["visible_evidence"] = []
    if "units" not in packet or packet["units"] is None:
        packet["units"] = []
    if "R" not in packet or not isinstance(packet["R"], Mapping):
        packet["R"] = {"entries": []}
    elif "entries" not in packet["R"]:
        packet["R"] = {**dict(packet["R"]), "entries": []}
    if "tau" not in packet or not isinstance(packet["tau"], Mapping):
        packet["tau"] = {"sequence": [], "steps": []}
    else:
        tau = dict(packet["tau"])
        tau.setdefault("sequence", [])
        tau.setdefault("steps", [])
        packet["tau"] = tau
    if "recovery_handles" not in packet or packet["recovery_handles"] is None:
        packet["recovery_handles"] = []
    if "rebite" not in packet or not isinstance(packet.get("rebite"), Mapping):
        packet["rebite"] = {"steps": []}
    else:
        reb = dict(packet["rebite"])
        reb.setdefault("steps", [])
        packet["rebite"] = reb
    if "accounting" not in packet or not isinstance(packet.get("accounting"), Mapping):
        packet["accounting"] = {"rebite_tokens": 0}
    else:
        acc = dict(packet["accounting"])
        acc.setdefault("rebite_tokens", 0)
        packet["accounting"] = acc
    if "provenance" not in packet or not isinstance(packet.get("provenance"), Mapping):
        packet["provenance"] = {
            "unit_id": "unknown",
            "source_uri": None,
            "byte_or_token_span": None,
            "renderer_id": None,
        }
    if "op_last_touch" not in packet:
        packet["op_last_touch"] = "NONE"
    return packet


def r_entries(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    r = packet.get("R")
    if not isinstance(r, Mapping):
        return []
    entries = r.get("entries") or []
    out: list[dict[str, Any]] = []
    for e in entries:
        if isinstance(e, Mapping):
            out.append(dict(e))
    return out


def recovery_handles(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    handles = packet.get("recovery_handles") or []
    out: list[dict[str, Any]] = []
    for h in handles:
        if isinstance(h, Mapping):
            out.append(dict(h))
    return out


def visible_unit_ids(packet: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()
    for item in packet.get("visible_evidence") or []:
        if not isinstance(item, Mapping):
            continue
        uids = item.get("unit_ids")
        if isinstance(uids, Sequence) and not isinstance(uids, (str, bytes)):
            for u in uids:
                ids.add(str(u))
        eid = item.get("e_id")
        if eid:
            # e_id may encode unit; also check provenance on item
            pass
        if item.get("unit_id"):
            ids.add(str(item["unit_id"]))
    for u in packet.get("units") or []:
        if isinstance(u, Mapping) and u.get("unit_id"):
            # units in packet may include recovered; visible set prefers evidence
            pass
    return ids
