"""Suppress repeated identical evidence requests (successful fetch keys)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from bite_ingestion.recovery.types import RebiteRequest


def fetch_key(
    request_type: str,
    *,
    unit_id: str | None = None,
    span: Mapping[str, Any] | None = None,
    version: str | None = None,
    aggregate_parent: str | None = None,
    reason: str | None = None,
) -> str:
    """Deterministic key for identical successful body fetches."""
    span_s = ""
    if span:
        span_s = f"{span.get('start')}:{span.get('end')}:{span.get('unit', 'char')}"
    parts = [
        str(request_type),
        str(unit_id or ""),
        span_s,
        str(version or ""),
        str(aggregate_parent or ""),
        str(reason or ""),
    ]
    return "|".join(parts)


def request_fetch_key(request: RebiteRequest, *, resolved_unit_id: str | None = None) -> str:
    return fetch_key(
        request.request_type,
        unit_id=resolved_unit_id or request.unit_id,
        span=request.span,
        version=request.version,
        aggregate_parent=request.aggregate_parent,
        reason=request.reason,
    )


@dataclass
class DedupeIndex:
    """Tracks successful body-fetch keys; clarify_sufficiency is not body-deduped the same way."""

    seen: list[str] = field(default_factory=list)

    def __contains__(self, key: str) -> bool:
        return key in self.seen

    def add(self, key: str) -> None:
        if key not in self.seen:
            self.seen.append(key)

    @classmethod
    def from_state_keys(cls, keys: list[str]) -> DedupeIndex:
        return cls(seen=list(keys))
