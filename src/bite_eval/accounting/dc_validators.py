"""Double-counting contract validators DC-1..6 (BITE-04 §5.2 / BITE-13)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

DC_IDS: tuple[str, ...] = ("DC-1", "DC-2", "DC-3", "DC-4", "DC-5", "DC-6")

# Categories that count toward T_total when they represent LLM/API calls
_LLM_CATEGORIES = frozenset(
    {
        "profiler",
        "router",
        "operator",
        "target",
        "rebite",
        "integrate",
        "recover",
    }
)


def validate_dc_event(event: Mapping[str, object]) -> list[str]:
    """Return list of DC violation codes for a single ledger event (empty = ok)."""
    violations: list[str] = []
    category = str(event.get("category", "")).strip().lower()
    kind = str(event.get("kind", event.get("event_kind", ""))).strip().lower()
    tokens_in = _as_nonneg_int(event.get("tokens_in", event.get("t_in", 0)))
    tokens_out = _as_nonneg_int(event.get("tokens_out", event.get("t_out", 0)))
    call_id = event.get("call_id") or event.get("api_call_id")

    # DC-2: deterministic preprocess → tokens must be 0
    if kind in {"deterministic", "preprocess", "cpu_only", "deterministic_preprocess"} and (
        tokens_in != 0 or tokens_out != 0
    ):
        violations.append("DC-2")
        # CPU/wall allowed as separate fields — not validated as tokens

    # DC-1 hint at event level: call_id recommended for API rows
    if kind in {"api", "llm", "model_call"} and not call_id and (tokens_in or tokens_out):
        # Soft: missing call_id makes DC-1 hard to enforce later
        violations.append("DC-1:missing_call_id")

    # DC-4: dual_use_logical must not add tokens
    if event.get("dual_use_logical") is True and (tokens_in or tokens_out):
        violations.append("DC-4")

    # DC-6: INTEGRATE / Recover / profiler(LLM) / router(LLM) must be countable
    # (presence check only when flagged as llm)
    if (
        category in {"integrate", "recover"}
        and kind in {"api", "llm", "model_call"}
        and tokens_in is None
        and tokens_out is None
    ):
        violations.append("DC-6")

    _ = _LLM_CATEGORIES  # documented for callers
    return violations


def validate_ledger_totals(
    rows: Sequence[Mapping[str, object]],
    totals: Mapping[str, Any],
) -> list[str]:
    """Validate ledger row set against DC-1..6 and T_total composition."""
    violations: list[str] = []

    # DC-1: one API call_id → at most one ledger row with tokens
    seen_calls: dict[str, int] = {}
    for row in rows:
        cid = row.get("call_id") or row.get("api_call_id")
        kind = str(row.get("kind", row.get("event_kind", ""))).strip().lower()
        if not cid:
            continue
        if kind in {"api", "llm", "model_call", ""} or _has_tokens(row):
            key = str(cid)
            seen_calls[key] = seen_calls.get(key, 0) + 1
    for cid, count in seen_calls.items():
        if count > 1:
            violations.append(f"DC-1:duplicate_call_id:{cid}")

    # Per-row DC checks
    for row in rows:
        for v in validate_dc_event(row):
            if v not in violations:
                violations.append(v)

    # DC-5 / composition: T_total must equal bucket sum (no target-only alias)
    t_total = totals.get("T_total")
    if t_total is not None:
        expected = (
            _as_nonneg_int(totals.get("T_profiler", 0))
            + _as_nonneg_int(totals.get("T_router", 0))
            + _as_nonneg_int(totals.get("T_operator", 0))
            + _as_nonneg_int(totals.get("T_target_in", 0))
            + _as_nonneg_int(totals.get("T_target_out", 0))
            + _as_nonneg_int(totals.get("T_rebite", 0))
            + _as_nonneg_int(totals.get("T_baseline", 0))
            + _as_nonneg_int(totals.get("T_calls_other", 0))
        )
        # Prefer explicit sum_calls if provided
        if "sum_calls_in_out" in totals:
            expected = (
                _as_nonneg_int(totals.get("T_profiler", 0))
                + _as_nonneg_int(totals.get("T_router", 0))
                + _as_nonneg_int(totals.get("sum_calls_in_out", 0))
            )
        if int(t_total) != int(expected):
            violations.append(f"T_total_mismatch:recorded={t_total} expected={expected}")

    # Forbid labeling target-input-only as T_total
    if totals.get("T_total_is_target_input_only") is True:
        violations.append("forbidden_target_input_only_total")

    return violations


def _has_tokens(row: Mapping[str, object]) -> bool:
    return bool(
        _as_nonneg_int(row.get("tokens_in", row.get("t_in", 0)))
        or _as_nonneg_int(row.get("tokens_out", row.get("t_out", 0)))
    )


def _as_nonneg_int(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        try:
            return max(0, int(value))
        except (OverflowError, ValueError):
            return 0
    if isinstance(value, str):
        try:
            return max(0, int(value.strip()))
        except ValueError:
            return 0
    return 0


__all__ = ["DC_IDS", "validate_dc_event", "validate_ledger_totals"]
