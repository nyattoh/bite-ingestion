"""EvalHarness — offline synthetic smoke runner with token + quality placeholders."""

from __future__ import annotations

import json
import time
import traceback
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bite_eval.accounting.estimate import LOCAL_ESTIMATE_LABEL, estimate_tokens_char4
from bite_eval.accounting.ledger import TokenLedger
from bite_eval.artifacts.ledger import ArtifactLedger, sha256_hex


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


PLACEHOLDER_METRICS: tuple[str, ...] = (
    "quality",
    "evidence_recall_visible",
    "evidence_recall_recoverable",
    "provenance",
    "latency",
)


def _soft_get_baseline(method_id: str) -> Any | None:
    """Optional wrap of bite_eval.baselines.get_baseline (soft import)."""
    try:
        from bite_eval.baselines import get_baseline  # type: ignore[attr-defined]

        return get_baseline(method_id)
    except Exception:  # noqa: BLE001 — soft: baselines may be absent on partial overlay
        return None


def _extract_text(packet: Mapping[str, object]) -> str:
    for key in ("document", "text", "content", "raw_context"):
        v = packet.get(key)
        if isinstance(v, str):
            return v
    ve = packet.get("visible_evidence")
    if isinstance(ve, str):
        return ve
    return ""


class EvalHarness:
    """Offline smoke eval: never calls paid APIs; records T_total buckets.

    Quality / recall / provenance / latency fields are present; values may be
    null/TBD for smoke. Failures are retained in the manifest (never silently
    dropped).
    """

    def __init__(
        self,
        *,
        artifact_root: str | Path | None = None,
        persist: bool = True,
    ) -> None:
        self.artifact_root = Path(artifact_root) if artifact_root else Path(".")
        self.persist = persist
        self._artifact_ledger = (
            ArtifactLedger(self.artifact_root) if persist else None
        )

    def run_smoke(
        self,
        method_id: str,
        packet: Mapping[str, object],
        context: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        """Run one offline synthetic smoke evaluation for method_id."""
        ctx = dict(context or {})
        ledger = TokenLedger()
        ledger.set_cache_policy(str(ctx.get("cache_policy", "TBD")))

        t0 = time.perf_counter()
        status = "ok"
        reason: str | None = None
        method_output: dict[str, object] | None = None
        error_trace: str | None = None

        # DC-2: deterministic preprocess — tokens=0; CPU/wall separate
        text = _extract_text(packet)
        preprocess_t0 = time.perf_counter()
        text_hash = sha256_hex(text) if text else ""
        preprocess_ms = (time.perf_counter() - preprocess_t0) * 1000.0
        ledger.record(
            {
                "category": "target",
                "kind": "deterministic_preprocess",
                "tokens_in": 0,
                "tokens_out": 0,
                "cpu_ms": preprocess_ms,
                "wall_ms": preprocess_ms,
                "text_hash": text_hash,
                "note": "DC-2 preprocess tokens forced 0",
            }
        )

        # Optional profiler/router LLM stubs from context (synthetic counts only)
        self._record_overhead_stubs(ledger, ctx)

        try:
            adapter = _soft_get_baseline(method_id)
            if adapter is not None and hasattr(adapter, "run"):
                out = dict(adapter.run(packet, ctx))
                method_output = out
                status = str(out.get("status", "ok"))
                reason = out.get("reason") if isinstance(out.get("reason"), str) else None
                acc = out.get("accounting")
                if isinstance(acc, Mapping):
                    ledger.merge_baseline_accounting(acc)
                # Synthetic target call: visible evidence as local estimate (proxy)
                visible = out.get("visible_evidence", "")
                vis_text = visible if isinstance(visible, str) else str(visible)
                # Only count target if not already counted via baseline accounting
                # Represent as one synthetic target call (offline stub — not paid)
                call_id = f"smoke_target:{method_id}:{text_hash[:12]}"
                tin = estimate_tokens_char4(vis_text)
                # Synthetic stub "response" tokens from context if provided
                stub_out = _as_int(ctx.get("stub_target_out_tokens"), 0)
                ledger.record(
                    {
                        "category": "target",
                        "kind": "local_estimate",
                        "call_id": call_id,
                        "tokens_in": tin,
                        "tokens_out": stub_out,
                        "estimate_source": LOCAL_ESTIMATE_LABEL,
                        "note": "offline smoke; not provider usage",
                    }
                )
                # Re-bite placeholder from accounting / context
                if method_id.endswith("rebite") or ctx.get("rebite"):
                    rebite_tokens = _as_int(ctx.get("stub_rebite_tokens"), 0)
                    if rebite_tokens:
                        ledger.record(
                            {
                                "category": "rebite",
                                "kind": "local_estimate",
                                "call_id": f"smoke_rebite:{method_id}:{text_hash[:12]}",
                                "tokens_in": rebite_tokens,
                                "tokens_out": 0,
                                "estimate_source": LOCAL_ESTIMATE_LABEL,
                            }
                        )
            else:
                # Pure synthetic path without baseline adapters
                method_output = self._synthetic_method(method_id, packet, ctx, ledger)
                status = str(method_output.get("status", "ok"))
                raw_reason = method_output.get("reason")
                reason = raw_reason if isinstance(raw_reason, str) else None
        except Exception as exc:  # noqa: BLE001 — retain failure in manifest
            status = "failed"
            reason = f"harness exception: {exc}"
            error_trace = traceback.format_exc()
            method_output = {
                "status": "failed",
                "reason": reason,
                "baseline_id": method_id,
            }

        wall_ms = (time.perf_counter() - t0) * 1000.0
        totals = dict(ledger.totals())

        # Placeholders — fields present; values null/TBD for smoke (D-2: no numeric Go)
        metrics: dict[str, object] = {
            "quality": ctx.get("quality", None),
            "evidence_recall_visible": ctx.get("evidence_recall_visible", None),
            "evidence_recall_recoverable": ctx.get("evidence_recall_recoverable", None),
            "provenance": ctx.get("provenance", None),
            "latency": {
                "wall_ms": wall_ms,
                "cpu_ms": totals.get("cpu_ms"),
                "note": "smoke wall clock; not calibrated",
            },
        }
        # Allow explicit TBD string
        for k in PLACEHOLDER_METRICS:
            if k == "latency":
                continue
            if metrics.get(k) is None:
                metrics[k] = None  # null placeholder; thresholds TBD

        manifest: dict[str, object] = {
            "schema": "bite-run-manifest/v0.1",
            "method_id": method_id,
            "status": status,
            "reason": reason,
            "offline": True,
            "paid_api": False,
            "synthetic": True,
            "packet_digest": sha256_hex(
                str(
                    sorted(
                        (k, packet[k])
                        for k in packet
                        if k not in {"prompt", "raw_prompt", "api_key"}
                    )
                )
            ),
            "text_hash": text_hash,
            "input_fingerprint": None,  # filled below
            "token_buckets": {
                "T_profiler": totals.get("T_profiler"),
                "T_router": totals.get("T_router"),
                "T_target_in": totals.get("T_target_in"),
                "T_target_out": totals.get("T_target_out"),
                "T_rebite": totals.get("T_rebite"),
                "T_baseline": totals.get("T_baseline"),
                "T_calls_other": totals.get("T_calls_other"),
                "sum_calls_in_out": totals.get("sum_calls_in_out"),
            },
            "T_total": totals.get("T_total"),
            "token_totals": totals,
            "ledger_rows": ledger.rows(),
            "dc_violations": ledger.violations(),
            "metrics": metrics,
            "method_output": method_output,
            "error_trace": error_trace,
            "gates": {
                "numeric_thresholds": "TBD",
                "go_pivot_stop": "not_run",
                "note": "D-2: no confirmatory Go/Pivot/Stop judgments in smoke",
            },
            "estimate_disclaimer": (
                f"Local estimates use {LOCAL_ESTIMATE_LABEL}; "
                "not provider usage. Provider fields preferred when present."
            ),
        }

        # Stable resume key (method + packet + token buckets + status; no clocks)
        fp_payload = {
            "method_id": method_id,
            "packet_digest": manifest["packet_digest"],
            "text_hash": text_hash,
            "status": status,
            "token_buckets": manifest["token_buckets"],
            "T_total": manifest["T_total"],
            "force_fail": bool(ctx.get("force_fail")),
            "stubs": {
                k: ctx.get(k)
                for k in (
                    "stub_profiler_tokens",
                    "stub_router_tokens",
                    "stub_rebite_tokens",
                    "stub_target_out_tokens",
                    "cache_policy",
                )
                if k in ctx
            },
        }
        manifest["input_fingerprint"] = sha256_hex(
            json.dumps(fp_payload, sort_keys=True, default=str)
        )

        # Never write secrets
        if self._artifact_ledger is not None:
            written = self._artifact_ledger.write_run(manifest)
            manifest["run_id"] = written.get("run_id")
            manifest["content_digest"] = written.get("content_digest")
            manifest["resumed"] = written.get("resumed", False)
            manifest["artifact_path"] = written.get("artifact_path")
        else:
            # Stable digest even without persist
            from bite_eval.artifacts.ledger import content_digest

            # provisional without timestamps
            provisional = {
                k: v
                for k, v in manifest.items()
                if k not in {"run_id", "created_at", "updated_at", "artifact_path", "resumed"}
            }
            manifest["content_digest"] = content_digest(provisional)

        return manifest

    def _record_overhead_stubs(self, ledger: TokenLedger, ctx: Mapping[str, object]) -> None:
        """Optional synthetic profiler/router LLM overhead from context (DC-6)."""
        prof = _as_int(ctx.get("stub_profiler_tokens"), 0)
        if prof:
            ledger.record(
                {
                    "category": "profiler",
                    "kind": "local_estimate",
                    "call_id": "smoke_profiler",
                    "tokens_in": prof,
                    "tokens_out": 0,
                    "estimate_source": LOCAL_ESTIMATE_LABEL,
                    "note": "DC-6 profiler(LLM) counted when present",
                }
            )
        else:
            # Deterministic profiler path: 0 tokens
            ledger.record(
                {
                    "category": "profiler",
                    "kind": "deterministic",
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "cpu_ms": _as_float(ctx.get("stub_profiler_cpu_ms"), 0.0),
                    "note": "DC-2 deterministic profiler",
                }
            )
        rout = _as_int(ctx.get("stub_router_tokens"), 0)
        if rout:
            ledger.record(
                {
                    "category": "router",
                    "kind": "local_estimate",
                    "call_id": "smoke_router",
                    "tokens_in": rout,
                    "tokens_out": 0,
                    "estimate_source": LOCAL_ESTIMATE_LABEL,
                    "note": "DC-6 router(LLM) counted when present",
                }
            )
        else:
            ledger.record(
                {
                    "category": "router",
                    "kind": "deterministic",
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "cpu_ms": _as_float(ctx.get("stub_router_cpu_ms"), 0.0),
                    "note": "DC-2 deterministic router/policy",
                }
            )

    def _synthetic_method(
        self,
        method_id: str,
        packet: Mapping[str, object],
        ctx: Mapping[str, object],
        ledger: TokenLedger,
    ) -> dict[str, object]:
        """Fallback when baselines package is unavailable."""
        text = _extract_text(packet)
        if ctx.get("force_fail"):
            return {
                "baseline_id": method_id,
                "status": "failed",
                "reason": "force_fail context flag",
                "visible_evidence": "",
                "accounting": {
                    "baseline_router_tokens": 0,
                    "baseline_compressor_tokens": 0,
                },
            }
        tin = estimate_tokens_char4(text)
        call_id = f"smoke_synth:{method_id}"
        ledger.record(
            {
                "category": "target",
                "kind": "local_estimate",
                "call_id": call_id,
                "tokens_in": tin,
                "tokens_out": _as_int(ctx.get("stub_target_out_tokens"), 0),
                "estimate_source": LOCAL_ESTIMATE_LABEL,
            }
        )
        return {
            "baseline_id": method_id,
            "status": "ok",
            "visible_evidence": text,
            "accounting": {
                "baseline_router_tokens": 0,
                "baseline_compressor_tokens": 0,
            },
            "baseline_trace": {"synthetic_fallback": True, "method_id": method_id},
        }


__all__ = ["PLACEHOLDER_METRICS", "EvalHarness"]
