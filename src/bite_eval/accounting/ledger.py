"""TokenLedger — implements TokenMeter; separate buckets + T_total (BITE-13)."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

from bite_eval.accounting.dc_validators import validate_dc_event, validate_ledger_totals
from bite_eval.accounting.estimate import LOCAL_ESTIMATE_LABEL, estimate_tokens_char4


def _as_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool) or value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _as_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool) or value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


CATEGORY_PROFILER = "profiler"
CATEGORY_ROUTER = "router"
CATEGORY_TARGET = "target"
CATEGORY_REBITE = "rebite"
CATEGORY_OPERATOR = "operator"
CATEGORY_BASELINE_PREFIX = "baseline_"

#: Categories folded into the T_operator (operator / compressor) bucket.
OPERATOR_CATEGORIES = frozenset({CATEGORY_OPERATOR, "compressor"})

KNOWN_CATEGORIES = frozenset(
    {
        CATEGORY_PROFILER,
        CATEGORY_ROUTER,
        CATEGORY_TARGET,
        CATEGORY_REBITE,
        CATEGORY_OPERATOR,
        "compressor",
        "integrate",
        "recover",
        "baseline_router",
        "baseline_compressor",
        "baseline_other",
    }
)


class TokenLedger:
    """In-memory token meter with DC-aware rows and bucket totals.

    T_total = T_profiler + T_router + sum_c (T_in_c + T_out_c)

    Provider usage fields (when present) take precedence over local estimates.
    Local char/4 estimates are labeled as proxy and never silently aliased as
    provider usage.
    """

    def __init__(self) -> None:
        self._rows: list[dict[str, object]] = []
        self._cpu_ms: float = 0.0
        self._wall_ms: float = 0.0
        self._cache_policy: str = "TBD"  # DC-3: consistent policy label
        self._violations: list[str] = []

    # --- TokenMeter Protocol ---

    def record(self, event: Mapping[str, object]) -> None:
        """Append one ledger row. One API call should produce one row (DC-1)."""
        row = self._normalize_event(event)
        for v in validate_dc_event(row):
            self._violations.append(v)
            row.setdefault("dc_flags", [])
            if isinstance(row["dc_flags"], list):
                row["dc_flags"].append(v)
        # DC-2 side fields
        cpu = row.pop("_cpu_ms", None)
        wall = row.pop("_wall_ms", None)
        if isinstance(cpu, (int, float)):
            self._cpu_ms += _as_float(cpu, 0.0)
        if isinstance(wall, (int, float)):
            self._wall_ms += _as_float(wall, 0.0)
        self._rows.append(row)

    def totals(self) -> Mapping[str, int | float | str]:
        """Return bucket totals + T_total + estimate metadata."""
        buckets = self._bucket_sums()
        sum_calls = (
            buckets["T_operator"]
            + buckets["T_target_in"]
            + buckets["T_target_out"]
            + buckets["T_rebite"]
            + buckets["T_baseline"]
            + buckets["T_calls_other"]
        )
        t_total = buckets["T_profiler"] + buckets["T_router"] + sum_calls
        out: dict[str, int | float | str] = {
            "T_profiler": buckets["T_profiler"],
            "T_router": buckets["T_router"],
            "T_operator": buckets["T_operator"],
            "T_target_in": buckets["T_target_in"],
            "T_target_out": buckets["T_target_out"],
            "T_rebite": buckets["T_rebite"],
            "T_baseline": buckets["T_baseline"],
            "T_calls_other": buckets["T_calls_other"],
            "sum_calls_in_out": sum_calls,
            "T_total": t_total,
            "call_count": buckets["call_count"],
            "row_count": len(self._rows),
            "cpu_ms": self._cpu_ms,
            "wall_ms": self._wall_ms,
            "cache_policy": self._cache_policy,
            "local_estimate_label": LOCAL_ESTIMATE_LABEL,
            "formula": (
                "T_total = T_profiler + T_router + T_operator + T_target_in "
                "+ T_target_out + T_rebite + T_baseline + T_calls_other"
            ),
        }
        return out

    # --- helpers ---

    def rows(self) -> list[dict[str, object]]:
        return deepcopy(self._rows)

    def violations(self) -> list[str]:
        combined = list(self._violations)
        combined.extend(validate_ledger_totals(self._rows, dict(self.totals())))
        # unique preserve order
        seen: set[str] = set()
        out: list[str] = []
        for v in combined:
            if v not in seen:
                seen.add(v)
                out.append(v)
        return out

    def set_cache_policy(self, policy: str) -> None:
        """DC-3: record consistent cache policy label (numeric TBD)."""
        self._cache_policy = str(policy)

    def record_text_estimate(
        self,
        *,
        category: str,
        text: str,
        role: str = "in",
        call_id: str | None = None,
        kind: str = "local_estimate",
        provider_usage: Mapping[str, object] | None = None,
    ) -> None:
        """Record tokens from provider_usage if given; else char/4 proxy."""
        event: dict[str, object] = {
            "category": category,
            "kind": kind,
            "estimate_source": LOCAL_ESTIMATE_LABEL,
        }
        if call_id is not None:
            event["call_id"] = call_id
        if provider_usage:
            tin = provider_usage.get("tokens_in", provider_usage.get("prompt_tokens", 0))
            tout = provider_usage.get("tokens_out", provider_usage.get("completion_tokens", 0))
            event["tokens_in"] = _as_int(tin, 0)
            event["tokens_out"] = _as_int(tout, 0)
            event["estimate_source"] = "provider_usage"
            event["kind"] = str(provider_usage.get("kind", "api"))
        else:
            est = estimate_tokens_char4(text)
            if role == "out":
                event["tokens_in"] = 0
                event["tokens_out"] = est
            else:
                event["tokens_in"] = est
                event["tokens_out"] = 0
        self.record(event)

    def merge_baseline_accounting(self, accounting: Mapping[str, object]) -> None:
        """Fold baseline adapter accounting into baseline_*/rebite buckets (DC-5).

        ``rebite_tokens`` (written by ``RecoverEngine._finish``) must reach the
        ``rebite`` bucket, otherwise a re-bite arm gets its extra evidence for
        free and the arm comparison is unfair (DC-6).
        """
        router = _as_int(accounting.get("baseline_router_tokens"), 0)
        compressor = _as_int(accounting.get("baseline_compressor_tokens"), 0)
        rebite = _as_int(accounting.get("rebite_tokens"), 0)
        if rebite:
            self.record(
                {
                    "category": CATEGORY_REBITE,
                    "kind": "baseline",
                    "tokens_in": rebite,
                    "tokens_out": 0,
                    "call_id": f"baseline_rebite:{len(self._rows)}",
                    "estimate_source": "baseline_accounting",
                }
            )
        if router:
            self.record(
                {
                    "category": "baseline_router",
                    "kind": "baseline",
                    "tokens_in": router,
                    "tokens_out": 0,
                    "call_id": f"baseline_router:{len(self._rows)}",
                    "estimate_source": "baseline_accounting",
                }
            )
        if compressor:
            self.record(
                {
                    "category": "baseline_compressor",
                    "kind": "baseline",
                    "tokens_in": compressor,
                    "tokens_out": 0,
                    "call_id": f"baseline_compressor:{len(self._rows)}",
                    "estimate_source": "baseline_accounting",
                }
            )

    def _normalize_event(self, event: Mapping[str, object]) -> dict[str, object]:
        category = str(event.get("category", "target")).strip().lower() or "target"
        kind = str(event.get("kind", event.get("event_kind", "api"))).strip().lower()
        tokens_in = _int(event.get("tokens_in", event.get("t_in", 0)))
        tokens_out = _int(event.get("tokens_out", event.get("t_out", 0)))

        # DC-2 force zero tokens for deterministic preprocess
        if kind in {"deterministic", "preprocess", "cpu_only", "deterministic_preprocess"}:
            tokens_in = 0
            tokens_out = 0

        # DC-4: logical dual-use does not add
        if event.get("dual_use_logical") is True:
            tokens_in = 0
            tokens_out = 0

        row: dict[str, object] = {
            "category": category,
            "kind": kind,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }
        for key in (
            "call_id",
            "api_call_id",
            "estimate_source",
            "provider_usage",
            "dual_use_logical",
            "text_hash",
            "note",
        ):
            if key in event and event[key] is not None:
                row[key] = event[key]
        if "call_id" not in row and "api_call_id" in row:
            row["call_id"] = row["api_call_id"]

        # stash timing separately
        if "cpu_ms" in event:
            row["_cpu_ms"] = event["cpu_ms"]
        if "wall_ms" in event:
            row["_wall_ms"] = event["wall_ms"]

        if "estimate_source" not in row:
            if event.get("provider_usage"):
                row["estimate_source"] = "provider_usage"
            else:
                row["estimate_source"] = LOCAL_ESTIMATE_LABEL

        return row

    def _bucket_sums(self) -> dict[str, int]:
        t_profiler = 0
        t_router = 0
        t_operator = 0
        t_target_in = 0
        t_target_out = 0
        t_rebite = 0
        t_baseline = 0
        t_other = 0
        call_count = 0
        for row in self._rows:
            cat = str(row.get("category", ""))
            tin = _int(row.get("tokens_in", 0))
            tout = _int(row.get("tokens_out", 0))
            total = tin + tout
            kind = str(row.get("kind", ""))
            if kind in {"api", "llm", "model_call", "baseline"} and total:
                call_count += 1
            if cat == CATEGORY_PROFILER:
                t_profiler += total
            elif cat == CATEGORY_ROUTER:
                t_router += total
            elif cat in OPERATOR_CATEGORIES:
                t_operator += total
            elif cat == CATEGORY_TARGET:
                t_target_in += tin
                t_target_out += tout
            elif cat in {CATEGORY_REBITE, "recover"}:
                t_rebite += total
            elif cat.startswith((CATEGORY_BASELINE_PREFIX, "baseline")):
                t_baseline += total
            elif cat == "integrate":
                # DC-6: INTEGRATE counted in sum_c
                t_other += total
            else:
                t_other += total
        return {
            "T_profiler": t_profiler,
            "T_router": t_router,
            "T_operator": t_operator,
            "T_target_in": t_target_in,
            "T_target_out": t_target_out,
            "T_rebite": t_rebite,
            "T_baseline": t_baseline,
            "T_calls_other": t_other,
            "call_count": call_count,
        }


def _int(value: object) -> int:
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


__all__ = [
    "CATEGORY_BASELINE_PREFIX",
    "CATEGORY_OPERATOR",
    "CATEGORY_PROFILER",
    "CATEGORY_REBITE",
    "CATEGORY_ROUTER",
    "CATEGORY_TARGET",
    "KNOWN_CATEGORIES",
    "OPERATOR_CATEGORIES",
    "TokenLedger",
]
