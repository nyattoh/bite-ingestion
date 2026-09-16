"""In-memory synthetic SourceStore for Recover unit tests.

NO shell, NO SQL, NO network. unit_id → text/version/uri/status only.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SourceStatus(str, Enum):
    OK = "ok"
    WITHDRAWN = "withdrawn"
    FORBIDDEN = "forbidden"
    INJECTION_SUSPECT = "injection_suspect"
    QUARANTINED = "quarantined"


@dataclass
class SourceRecord:
    unit_id: str
    text: str
    version: str | None = None
    uri: str | None = None
    status: str = SourceStatus.OK.value
    reason_tags: list[str] = field(default_factory=list)
    aggregate_parent: str | None = None
    span: dict[str, Any] | None = None
    stale: bool = False
    media_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "text": self.text,
            "version": self.version,
            "uri": self.uri,
            "status": self.status,
            "reason_tags": list(self.reason_tags),
            "aggregate_parent": self.aggregate_parent,
            "span": dict(self.span) if self.span else None,
            "stale": self.stale,
            "media_type": self.media_type,
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> SourceRecord:
        span = data.get("span")
        tags = data.get("reason_tags") or []
        if isinstance(tags, str):
            tags = [tags]
        return cls(
            unit_id=str(data["unit_id"]),
            text=str(data.get("text", "")),
            version=_opt_str(data.get("version")),
            uri=_opt_str(data.get("uri") or data.get("source_uri")),
            status=str(data.get("status", SourceStatus.OK.value)),
            reason_tags=[str(t) for t in tags],
            aggregate_parent=_opt_str(data.get("aggregate_parent")),
            span=dict(span) if isinstance(span, Mapping) else None,
            stale=bool(data.get("stale", False)),
            media_type=_opt_str(data.get("media_type")),
        )


def _opt_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v)
    return s if s else None


class SourceStore:
    """Deterministic in-memory map of unit_id → SourceRecord."""

    def __init__(self, records: Iterable[SourceRecord | Mapping[str, Any]] | None = None) -> None:
        self._by_id: dict[str, SourceRecord] = {}
        if records:
            for r in records:
                self.put(r)

    def put(self, record: SourceRecord | Mapping[str, Any]) -> None:
        rec = record if isinstance(record, SourceRecord) else SourceRecord.from_mapping(record)
        self._by_id[rec.unit_id] = rec

    def get(self, unit_id: str) -> SourceRecord | None:
        return self._by_id.get(unit_id)

    def __contains__(self, unit_id: str) -> bool:
        return unit_id in self._by_id

    def unit_ids(self) -> list[str]:
        return sorted(self._by_id.keys())

    def members_of_aggregate(self, aggregate_parent: str) -> list[SourceRecord]:
        out = [r for r in self._by_id.values() if r.aggregate_parent == aggregate_parent]
        out.sort(key=lambda r: r.unit_id)
        return out

    def by_version(self, *, uri: str | None, version: str) -> list[SourceRecord]:
        out: list[SourceRecord] = []
        for r in self._by_id.values():
            if r.version == version and (uri is None or r.uri == uri):
                out.append(r)
        out.sort(key=lambda r: r.unit_id)
        return out

    def slice_text(self, unit_id: str, span: Mapping[str, Any] | None) -> str | None:
        rec = self.get(unit_id)
        if rec is None:
            return None
        if not span:
            return rec.text
        start = int(span.get("start", 0))
        end = int(span.get("end", len(rec.text)))
        unit = str(span.get("unit", "char"))
        if unit not in ("char", "byte", "line"):
            return None
        if unit == "line":
            lines = rec.text.splitlines(keepends=True)
            if start < 0 or end > len(lines) or start > end:
                return None
            return "".join(lines[start:end])
        # char / byte: treat as char offsets into unicode string (synthetic)
        if start < 0 or end > len(rec.text) or start > end:
            return None
        return rec.text[start:end]

    def to_dict(self) -> dict[str, Any]:
        return {uid: self._by_id[uid].to_dict() for uid in self.unit_ids()}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SourceStore:
        store = cls()
        for uid, payload in sorted(data.items(), key=lambda kv: str(kv[0])):
            if isinstance(payload, Mapping):
                row = dict(payload)
                row.setdefault("unit_id", uid)
                store.put(row)
        return store
