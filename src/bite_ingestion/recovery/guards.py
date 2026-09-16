"""Access control, withdrawn/forbidden, version freshness, injection-suspect refusal."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from bite_ingestion.recovery.source_store import SourceRecord, SourceStatus
from bite_ingestion.recovery.types import OutcomeCode


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    outcome: str | None = None
    message: str = ""


def check_access(
    record: SourceRecord | None,
    *,
    refuse_injection_suspect: bool = True,
) -> GuardDecision:
    """Refuse withdrawn / forbidden / (optionally) injection_suspect sources."""
    if record is None:
        return GuardDecision(False, OutcomeCode.RECOVER_MISS.value, "source record missing")
    status = str(record.status)
    if status == SourceStatus.WITHDRAWN.value:
        return GuardDecision(False, OutcomeCode.REFUSED_WITHDRAWN.value, "source withdrawn")
    if status == SourceStatus.FORBIDDEN.value:
        return GuardDecision(False, OutcomeCode.REFUSED_FORBIDDEN.value, "source forbidden")
    if refuse_injection_suspect and status == SourceStatus.INJECTION_SUSPECT.value:
        return GuardDecision(
            False,
            OutcomeCode.REFUSED_INJECTION_SUSPECT.value,
            "injection_suspect refused by policy",
        )
    # quarantined-with-injection tag also refused when policy on
    if refuse_injection_suspect and "injection_suspect" in (record.reason_tags or []):
        return GuardDecision(
            False,
            OutcomeCode.REFUSED_INJECTION_SUSPECT.value,
            "injection_suspect tag refused by policy",
        )
    return GuardDecision(True, None, "ok")


def check_version_freshness(
    record: SourceRecord,
    *,
    request_version: str | None,
    request_stale: bool | None = None,
    locator: Mapping[str, Any] | None = None,
) -> GuardDecision:
    """Fail when version mismatches and stale is asserted / recorded.

    Rules (v0.1, deterministic):
    - If request_version is set and record.version is set and they differ:
        - if request_stale is True OR record.stale is True OR locator.get('stale') is True
          → stale_or_broken_locator
        - else → still fail closed as stale_or_broken_locator (do not present wrong version
          as current). Caller wanting a specific version should use fetch_by_version against
          a matching store record.
    - If locator span is malformed (end < start) → stale_or_broken_locator
    """
    loc = dict(locator or {})
    span = loc.get("span") if isinstance(loc.get("span"), Mapping) else None
    if span is not None:
        try:
            start = int(span.get("start", 0))
            end = int(span.get("end", 0))
        except (TypeError, ValueError):
            return GuardDecision(
                False, OutcomeCode.STALE_OR_BROKEN_LOCATOR.value, "broken span types"
            )
        if end < start:
            return GuardDecision(
                False, OutcomeCode.STALE_OR_BROKEN_LOCATOR.value, "broken span end < start"
            )

    loc_stale = bool(loc.get("stale", False))
    stale_flag = bool(request_stale) or bool(record.stale) or loc_stale

    if (request_version is not None and record.version is not None) and (str(request_version) != str(record.version)):
        # Always fail mismatch — never present old as new
        return GuardDecision(
            False,
            OutcomeCode.STALE_OR_BROKEN_LOCATOR.value,
            f"version mismatch request={request_version!r} store={record.version!r}"
            + (" stale=true" if stale_flag else ""),
        )

    if stale_flag and request_version is not None and record.version is not None:
        # redundant path kept for clarity when versions equal but stale asserted oddly
        pass

    # Explicit: request says stale=true with any version pin → refuse presenting as fresh
    if (request_stale is True and request_version is not None) and (record.version is not None and str(request_version) != str(record.version)):
        return GuardDecision(
            False,
            OutcomeCode.STALE_OR_BROKEN_LOCATOR.value,
            "stale=true with version mismatch",
        )

    return GuardDecision(True, None, "fresh")


def is_injection_suspect_text(text: str) -> bool:
    """Lightweight synthetic detector for fixtures (not a production classifier)."""
    markers = (
        "<<<INJECT",
        "ignore previous instructions",
        "IGNORE PREVIOUS",
        "system prompt override",
    )
    low = text.lower()
    for m in markers:
        if m.lower() in low:
            return True
    return False
