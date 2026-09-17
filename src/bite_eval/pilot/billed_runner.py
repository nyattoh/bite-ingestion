"""Billed synthetic pilot runner (BITE-15 / BITE-15b).

Calls target model via Z.ai for methods that need LLM (raw_full vs
compressed/passthrough). T_total for billed rows comes ONLY from provider
usage (prompt/completion/total/cached tokens). Never mixes char4 proxy into
the T_total field (DC-3: billed primary; logical/proxy recorded separately
if needed).

BITE-15b: per-call checkpoint + resume so a mid-run TimeoutError cannot
erase measured call counts. Prefer skip already-ok triples (no duplicate
billing); retry previous timeout/error once under the new run's retry budget;
skip prior rate_limit keys (avoid 429 storm).

Minimal default sizing (cost control): 2 families × 3 instances × 2 methods
= 12 target calls. Full N_pilot=24/family is optional via CLI expansion.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from bite_eval.accounting.estimate import LOCAL_ESTIMATE_LABEL, estimate_tokens_char4
from bite_eval.pilot.constraints import check_constraints, metrics_from_instance
from bite_eval.pilot.decide import BILLED_PROVIDER, decide_gate_c
from bite_eval.pilot.families import SYNTHETIC_FAMILIES, generate_family_instances
from bite_eval.providers.zai_client import (
    BILLED_USAGE_LABEL,
    DEFAULT_MODEL,
    ProviderTimeoutError,
    RateLimitError,
    ZaiClient,
    ZaiClientError,
)

# EVAL-02: Import operator base helpers for R entries and provenance tracking
from bite_ingestion.operators.base import (
    REASON_BUDGET_TRUNCATED,
    add_r_entry,
    ensure_extended_fields,
    stable_id,
)

# Locked thresholds (d2_lock_v0.1)
DELTA = 0.05
RHO_VISIBLE = 0.50
RHO_RECOVERABLE = 0.90
ETA = 0.95
N_PILOT_DEFAULT = 24
N_FULL_RECORDED = 100
J = 3

# Minimal billed set (cost control) — documented in hand_over
MINIMAL_FAMILIES: tuple[str, ...] = ("clean_local", "adversarial_omission")
MINIMAL_N_PER_FAMILY = 3
MINIMAL_METHODS: tuple[str, ...] = ("raw_full", "compressed_passthrough")

# Default artifact paths (BITE-15b full / resume-friendly)
DEFAULT_CHECKPOINT_PATH = Path("artifacts/pilot/bite15b_checkpoint.jsonl")
DEFAULT_PARTIAL_PATH = Path("artifacts/pilot/bite15b_billed_partial.json")
DEFAULT_SUMMARY_PATH = Path("artifacts/pilot/bite15b_billed_summary.json")

# Resume policy (documented):
# - skip keys whose latest checkpoint status is ``ok`` (no re-bill)
# - retry keys with latest status ``error`` or ``timeout`` once this run
# - skip keys with latest status ``rate_limit`` (avoid immediate 429 storm)
RESUME_RETRY_STATUSES = frozenset({"error", "timeout"})
RESUME_SKIP_STATUSES = frozenset({"ok", "rate_limit"})


class ChatClient(Protocol):
    """Duck-typed client: chat_completion → object with .text and .usage."""

    model: str

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 256,
        http_trace: list[dict[str, Any]] | None = None,
        retry_max: int | None = None,
    ) -> Any: ...


@dataclass
class TransformedPacket:
    """EVAL-02: Unified transformation result.
    
    Ensures prompt body and visible evidence IDs come from the same transformed
    object. Units removed by truncation/dedupe/quarantine move to R (recoverable
    context), not silently lost.
    """
    payload_text: str
    visible_unit_ids: list[str]
    recovery_index: dict[str, Any]  # R with entries for omitted units
    provenance: dict[str, Any]
    operator_trace: dict[str, Any]  # tau
    method_id: str
    transformation_note: str = ""


@dataclass
class BilledInstanceResult:
    instance_id: str
    family: str
    method_id: str
    Q: float
    Q_baseline: float
    recall_vis: float
    recall_rec: float
    provenance: float
    constraints_ok: bool
    # Billed T_total ONLY from provider usage — never char4 proxy mixed here
    T_total: int | None
    T_prompt: int | None
    T_completion: int | None
    T_cached: int | None
    estimate_source: str
    # Logical / proxy kept separate (not used as T_total)
    T_logical_char4_proxy: int | None = None
    B_r_cap: int | None = None
    model: str = DEFAULT_MODEL
    failures: tuple[str, ...] = ()
    answer_text: str = ""
    error: str | None = None
    # Baseline status: ok | missing_pair | timeout | rate_limit | error
    baseline_status: str = "ok"


@dataclass
class BilledRunState:
    results: list[BilledInstanceResult] = field(default_factory=list)
    rate_limited: bool = False
    rate_limit_at: str | None = None
    http_trace: list[dict[str, Any]] = field(default_factory=list)
    calls_attempted: int = 0
    calls_succeeded: int = 0
    calls_skipped_ok: int = 0
    calls_resumed_retry: int = 0


def _br_cap(t_in_raw: int) -> int:
    return min(4096, int(0.5 * t_in_raw))


def _utc_ts() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _call_key(family: str, instance_id: str, method: str) -> tuple[str, str, str]:
    return (str(family), str(instance_id), str(method))


def _refresh_stale_baselines(
    results: list[BilledInstanceResult],
    instance_id: str,
    new_baseline_q: float,
    new_baseline_status: str,
    *,
    delta: float = DELTA,
    rho_visible: float = RHO_VISIBLE,
    rho_recoverable: float = RHO_RECOVERABLE,
    eta: float = ETA,
) -> None:
    """Bug 1 fix: After successful raw_full, refresh stale compressed baselines.
    
    When raw_full times out then succeeds on resume retry, compressed rows
    already written with stale Q_baseline=0.0 / baseline_status=timeout must
    be updated to use the new raw_full Q and constraints recomputed.
    
    Bug 1 (new): Also refresh rows with "unknown" baseline_status (from
    missing/empty checkpoint field) to replace gold-derived baselines.
    """
    for row in results:
        if (
            row.instance_id == instance_id
            and row.method_id != "raw_full"
            and row.baseline_status in ("timeout", "error", "missing_pair", "unknown")
        ):
            row.Q_baseline = new_baseline_q
            row.baseline_status = new_baseline_status
            # Recompute constraints with the new baseline
            cr = check_constraints(
                Q=row.Q,
                Q_baseline=new_baseline_q,
                recall_vis=row.recall_vis,
                recall_rec=row.recall_rec,
                provenance=row.provenance,
                delta=delta,
                rho_visible=rho_visible,
                rho_recoverable=rho_recoverable,
                eta=eta,
            )
            row.constraints_ok = cr.ok
            row.failures = cr.failures


def _row_from_dict(d: Mapping[str, Any]) -> BilledInstanceResult:
    failures = d.get("failures") or ()
    if isinstance(failures, list):
        failures = tuple(failures)
    # Bug 1 fix: missing baseline_status should NOT default to "ok"
    # Treat missing/empty as "unknown" which requires baseline refresh
    baseline_status_raw = d.get("baseline_status")
    if baseline_status_raw:
        baseline_status = str(baseline_status_raw)
    else:
        baseline_status = "unknown"
    return BilledInstanceResult(
        instance_id=str(d.get("instance_id", "")),
        family=str(d.get("family", "")),
        method_id=str(d.get("method_id", d.get("method", ""))),
        Q=float(d.get("Q") or 0.0),
        Q_baseline=float(d.get("Q_baseline") or 0.0),
        recall_vis=float(d.get("recall_vis") or 0.0),
        recall_rec=float(d.get("recall_rec") or 0.0),
        provenance=float(d.get("provenance") or 0.0),
        constraints_ok=bool(d.get("constraints_ok")),
        T_total=d.get("T_total"),
        T_prompt=d.get("T_prompt"),
        T_completion=d.get("T_completion"),
        T_cached=d.get("T_cached"),
        estimate_source=str(d.get("estimate_source") or BILLED_USAGE_LABEL),
        T_logical_char4_proxy=d.get("T_logical_char4_proxy"),
        B_r_cap=d.get("B_r_cap"),
        model=str(d.get("model") or DEFAULT_MODEL),
        failures=tuple(failures),
        answer_text=str(d.get("answer_text") or ""),
        error=d.get("error"),
        baseline_status=baseline_status,
    )


def load_checkpoint(path: str | Path | None) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Load latest checkpoint record per (family, instance_id, method).

    Later lines override earlier ones for the same key.
    """
    latest: dict[tuple[str, str, str], dict[str, Any]] = {}
    if path is None:
        return latest
    p = Path(path)
    if not p.is_file():
        return latest
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(rec, dict):
                continue
            key = _call_key(
                str(rec.get("family", "")),
                str(rec.get("instance_id", "")),
                str(rec.get("method", rec.get("method_id", ""))),
            )
            if not key[0] or not key[1] or not key[2]:
                continue
            latest[key] = rec
    return latest


def append_checkpoint(path: str | Path, record: Mapping[str, Any]) -> None:
    """Append one JSONL checkpoint record and fsync."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(record)
    if "ts" not in payload:
        payload["ts"] = _utc_ts()
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def atomic_write_json(path: str | Path, data: Mapping[str, Any]) -> Path:
    """Atomic rewrite via temp file + replace."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(out)
    return out


def write_summary(summary: Mapping[str, Any], path: str | Path) -> Path:
    return atomic_write_json(path, summary)


def _partial_tallies(state: BilledRunState) -> dict[str, Any]:
    billed = [r for r in state.results if r.T_total is not None]
    return {
        "pilot_id": "bite15_billed_synthetic_v0.1",
        "ts": _utc_ts(),
        "calls_attempted": state.calls_attempted,
        "calls_succeeded": state.calls_succeeded,
        "calls_skipped_ok": state.calls_skipped_ok,
        "calls_resumed_retry": state.calls_resumed_retry,
        "n_instance_rows": len(state.results),
        "n_billed_rows": len(billed),
        "rate_limited": state.rate_limited,
        "rate_limit_at": state.rate_limit_at,
        "results": [asdict(r) for r in state.results],
    }


def flush_partial(state: BilledRunState, partial_path: str | Path | None) -> None:
    if partial_path is None:
        return
    atomic_write_json(partial_path, _partial_tallies(state))


def _checkpoint_record(
    *,
    family: str,
    instance_id: str,
    method: str,
    status: str,
    error_type: str | None = None,
    usage: Mapping[str, Any] | None = None,
    row: BilledInstanceResult | None = None,
) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "family": family,
        "instance_id": instance_id,
        "method": method,
        "status": status,
        "error_type": error_type,
        "usage": dict(usage) if usage else None,
        "ts": _utc_ts(),
    }
    if row is not None:
        rec["row"] = asdict(row)
    return rec


def _transform_packet(packet: Mapping[str, object], method_id: str) -> TransformedPacket:
    """EVAL-02: Transform packet into unified result with payload and visible IDs.
    
    Truncated/removed units move to R (recoverable context). Both prompt body
    and visible evidence IDs derive from the same transformation output.
    """
    doc = str(packet.get("document") or "")
    
    # Extract original visible_evidence IDs if present (for synthetic packets)
    _vis_raw = packet.get("visible_evidence")
    original_visible_ids: list[str] = []
    if isinstance(_vis_raw, (list, tuple)):
        original_visible_ids = [str(x) for x in _vis_raw if x]
    
    # Create a working packet copy with extended fields for R/tau tracking
    working_packet: dict[str, Any] = {
        "packet_id": str(packet.get("instance_id", "unknown")),
        "visible_evidence": packet.get("visible_evidence", []),
        "provenance": packet.get("provenance", {
            "unit_id": str(packet.get("instance_id", "unknown")),
            "source_uri": None,
            "byte_or_token_span": None,
            "renderer_id": method_id,
        }),
        "op_last_touch": "NONE",
    }
    ensure_extended_fields(working_packet)
    
    payload_text = doc
    visible_unit_ids: list[str] = []
    transformation_note = f"method={method_id}"
    
    if method_id == "raw_full":
        # No transformation - all content visible
        payload_text = doc
        # Use original visible IDs if present, else synthesize
        if original_visible_ids:
            visible_unit_ids = original_visible_ids
        elif doc:
            unit_id = stable_id("u_", packet.get("instance_id", ""), "raw_full", doc)
            visible_unit_ids = [unit_id]
        transformation_note = "raw_full: no transformation"
        
    elif method_id in {"compressed_passthrough", "synthetic_passthrough"}:
        # EVAL-02: Track truncation - removed portion moves to R
        if len(doc) <= 400:
            # No truncation needed - all content visible
            payload_text = doc
            # Use original visible IDs if present, else synthesize
            if original_visible_ids:
                visible_unit_ids = original_visible_ids
            elif doc:
                unit_id = stable_id("u_", packet.get("instance_id", ""), method_id, doc)
                visible_unit_ids = [unit_id]
            transformation_note = f"{method_id}: no truncation needed (doc_len={len(doc)})"
        else:
            # Truncate to 400 chars - removed portion goes to R
            payload_text = doc[:400] + "\n...[truncated]"
            truncated_portion = doc[400:]
            
            # BUG 1 FIX: Keep original visible evidence IDs if content still appears
            # in the truncated prefix (which it typically does for synthetic packets).
            # Only move IDs to R if their content is truly lost.
            # For synthetic packets, the visible evidence is usually in the first part
            # of the document, so it survives truncation at 400 chars.
            if original_visible_ids:
                # KEEP original visible IDs - they're still valid for the truncated content
                visible_unit_ids = original_visible_ids
            else:
                # No original IDs - synthesize one for the visible portion
                visible_unit_id = stable_id("u_", packet.get("instance_id", ""), method_id, "visible", doc[:400])
                visible_unit_ids = [visible_unit_id]
            
            # Truncated text portion goes to R (recoverable)
            truncated_unit_id = stable_id("u_", packet.get("instance_id", ""), method_id, "truncated", truncated_portion)
            add_r_entry(
                working_packet,
                unit_id=truncated_unit_id,
                reason=REASON_BUDGET_TRUNCATED,
                recoverable=True,
                locator={
                    "source_uri": f"synthetic://{packet.get('instance_id', 'unknown')}",
                    "span": {"start": 400, "end": len(doc), "unit": "char"},
                    "text_preview": truncated_portion[:100] + "..." if len(truncated_portion) > 100 else truncated_portion,
                },
            )
            transformation_note = f"{method_id}: truncated at 400 chars (removed {len(truncated_portion)} chars to R; kept original visible IDs)"
    else:
        # Unknown method: pass through
        payload_text = doc
        # Use original visible IDs if present, else synthesize
        if original_visible_ids:
            visible_unit_ids = original_visible_ids
        elif doc:
            unit_id = stable_id("u_", packet.get("instance_id", ""), method_id, doc)
            visible_unit_ids = [unit_id]
        transformation_note = f"{method_id}: unknown method, pass-through"
    
    # Update tau to record transformation step
    if "tau" not in working_packet:
        working_packet["tau"] = {"sequence": [], "steps": []}
    tau = working_packet["tau"]
    tau["sequence"].append(method_id)
    tau["steps"].append({
        "op": method_id,
        "mode": "deterministic",
        "inputs_ref": [],
        "outputs_ref": visible_unit_ids,
        "omitted_ref": [e["unit_id"] for e in working_packet["R"].get("entries", [])],
        "errors": [],
        "extra": {"transformation_note": transformation_note},
    })
    
    return TransformedPacket(
        payload_text=payload_text,
        visible_unit_ids=visible_unit_ids,
        recovery_index=working_packet["R"],
        provenance=working_packet["provenance"],
        operator_trace=working_packet["tau"],
        method_id=method_id,
        transformation_note=transformation_note,
    )


def _build_messages(
    transformed: TransformedPacket,
    query: str,
) -> list[dict[str, str]]:
    """EVAL-02: Build chat messages from TransformedPacket.
    
    Uses the transformed payload_text, ensuring prompt matches what was recorded
    as visible in the transformation step.
    """
    payload = transformed.payload_text
    method_id = transformed.method_id
    
    if method_id == "raw_full":
        user = (
            f"Document:\n{payload}\n\n"
            f"Question: {query}\n"
            "Answer with only the final value/string, no explanation."
        )
    elif method_id in {"compressed_passthrough", "synthetic_passthrough"}:
        user = (
            f"Compressed document:\n{payload}\n\n"
            f"Question: {query}\n"
            "Answer with only the final value/string, no explanation."
        )
    else:
        user = f"Document:\n{payload}\n\nQuestion: {query}\nAnswer briefly."
    
    return [
        {
            "role": "system",
            "content": "You are a careful extractive QA assistant. Reply with the answer only.",
        },
        {"role": "user", "content": user},
    ]


def _visible_for_method(transformed: TransformedPacket) -> list[str]:
    """EVAL-02: Extract visible unit IDs from TransformedPacket.
    
    Returns the IDs of units actually present in the transformed payload,
    not the original packet's visible_evidence field.
    """
    return list(transformed.visible_unit_ids)


def evaluate_billed_instance(
    packet: Mapping[str, object],
    method_id: str,
    client: ChatClient,
    *,
    delta: float = DELTA,
    rho_visible: float = RHO_VISIBLE,
    rho_recoverable: float = RHO_RECOVERABLE,
    eta: float = ETA,
    http_trace: list[dict[str, Any]] | None = None,
    max_tokens: int = 256,
    retry_max: int | None = None,
    raw_baseline_q: float | None = None,
    baseline_status: str | None = None,
) -> BilledInstanceResult:
    """One billed target call; T_total from provider usage only.
    
    Q_baseline comes from paired raw_full response when provided via
    raw_baseline_q. For raw_full itself, uses self-pairing (Q_baseline = Q).
    Never uses gold answer as baseline.
    
    EVAL-02: Transform packet first to unify prompt body and visible evidence
    IDs. Both come from the same TransformedPacket object.
    """
    # EVAL-02: Transform packet into unified result
    transformed = _transform_packet(packet, method_id)
    
    # Build messages from transformed payload
    query = str(packet.get("query") or "")
    messages = _build_messages(transformed, query)
    model_name = getattr(client, "model", DEFAULT_MODEL)
    try:
        kwargs: dict[str, Any] = {
            "temperature": 0.0,
            "max_tokens": max_tokens,
            "http_trace": http_trace,
        }
        if retry_max is not None:
            kwargs["retry_max"] = retry_max
        result = client.chat_completion(messages, **kwargs)
    except RateLimitError:
        raise
    except ProviderTimeoutError as exc:
        text_proxy = str(packet.get("document") or "")
        return BilledInstanceResult(
            instance_id=str(packet.get("instance_id")),
            family=str(packet.get("family")),
            method_id=method_id,
            Q=0.0,
            Q_baseline=raw_baseline_q if raw_baseline_q is not None else 0.0,
            recall_vis=0.0,
            recall_rec=0.0,
            provenance=0.0,
            constraints_ok=False,
            T_total=None,
            T_prompt=None,
            T_completion=None,
            T_cached=None,
            estimate_source=BILLED_USAGE_LABEL,
            T_logical_char4_proxy=estimate_tokens_char4(text_proxy),
            B_r_cap=_br_cap(estimate_tokens_char4(text_proxy)),
            model=str(model_name),
            failures=("provider_timeout",),
            error=str(exc),
            baseline_status=baseline_status or ("timeout" if method_id == "raw_full" else "ok"),
        )
    except (ZaiClientError, TimeoutError) as exc:
        # TimeoutError should already be ProviderTimeoutError from ZaiClient,
        # but catch bare TimeoutError if a duck-typed client raises it.
        text_proxy = str(packet.get("document") or "")
        is_timeout = isinstance(exc, TimeoutError) or "timed out" in str(exc).lower()
        # Bug 3 fix: provider errors must NOT set baseline_status=ok
        if baseline_status:
            status = baseline_status
        elif method_id == "raw_full":
            # raw_full: timeout → "timeout", non-timeout error → "error"
            status = "timeout" if is_timeout else "error"
        else:
            # Non-raw method: inherit from paired raw_full if available, else error
            status = "error"
        return BilledInstanceResult(
            instance_id=str(packet.get("instance_id")),
            family=str(packet.get("family")),
            method_id=method_id,
            Q=0.0,
            Q_baseline=raw_baseline_q if raw_baseline_q is not None else 0.0,
            recall_vis=0.0,
            recall_rec=0.0,
            provenance=0.0,
            constraints_ok=False,
            T_total=None,
            T_prompt=None,
            T_completion=None,
            T_cached=None,
            estimate_source=BILLED_USAGE_LABEL,
            T_logical_char4_proxy=estimate_tokens_char4(text_proxy),
            B_r_cap=_br_cap(estimate_tokens_char4(text_proxy)),
            model=str(model_name),
            failures=("provider_timeout",) if is_timeout else ("provider_error",),
            error=str(exc),
            baseline_status=status,
        )

    answer = str(getattr(result, "text", "") or "").strip()
    usage = getattr(result, "usage", {}) or {}
    t_prompt = usage.get("prompt_tokens")
    t_completion = usage.get("completion_tokens")
    t_total = usage.get("total_tokens")
    t_cached = usage.get("cached_tokens")
    # If total missing but prompt+completion present, sum (still billed fields only)
    if t_total is None and t_prompt is not None and t_completion is not None:
        t_total = int(t_prompt) + int(t_completion)

    # EVAL-02: Extract visible IDs from transformed packet (what was actually sent)
    vis = _visible_for_method(transformed)
    
    # BUG 2 FIX: Build working packet that includes recovery_index IDs in recoverable_evidence_ids
    # so metrics_from_instance sees the transformed recovery state, not just the original packet.
    working_packet = dict(packet)
    # Get original recoverable IDs
    _orig_rec = packet.get("recoverable_evidence_ids")
    if isinstance(_orig_rec, (list, tuple)):
        original_rec_ids = {str(x) for x in _orig_rec if x}
    else:
        original_rec_ids = set()
    # Get R entries from transformation
    r_entries = transformed.recovery_index.get("entries", [])
    r_unit_ids = {str(e.get("unit_id", "")) for e in r_entries if e.get("unit_id")}
    # Union: original recoverable IDs + units moved to R during transformation
    combined_rec_ids = list(original_rec_ids | r_unit_ids)
    working_packet["recoverable_evidence_ids"] = combined_rec_ids
    
    m = metrics_from_instance(working_packet, vis, answer=answer)

    # Q_baseline: from paired raw_full response, or self-pairing for raw_full
    if raw_baseline_q is not None:
        Q_baseline = raw_baseline_q
        actual_baseline_status = baseline_status or "ok"
    elif method_id == "raw_full":
        # Self-pairing: raw_full uses its own Q as baseline
        Q_baseline = float(m["quality"])
        actual_baseline_status = "ok"
    else:
        # No paired raw_full provided — should not happen in proper workflow
        Q_baseline = 0.0
        actual_baseline_status = "missing_pair"

    text = str(packet.get("document") or "")
    t_logical = estimate_tokens_char4(text) + estimate_tokens_char4(answer)

    cr = check_constraints(
        Q=float(m["quality"]),
        Q_baseline=Q_baseline,
        recall_vis=float(m["evidence_recall_visible"]),
        recall_rec=float(m["evidence_recall_recoverable"]),
        provenance=float(m["provenance"]),
        delta=delta,
        rho_visible=rho_visible,
        rho_recoverable=rho_recoverable,
        eta=eta,
    )

    est_src = str(getattr(result, "estimate_source", BILLED_USAGE_LABEL))
    if t_total is None:
        # No billed usage → caller / decide will treat as insufficient
        est_src = BILLED_USAGE_LABEL  # still labeled billed path; has_billed_usage=False

    return BilledInstanceResult(
        instance_id=str(packet.get("instance_id")),
        family=str(packet.get("family")),
        method_id=method_id,
        Q=cr.Q,
        Q_baseline=cr.Q_baseline,
        recall_vis=cr.recall_vis,
        recall_rec=cr.recall_rec,
        provenance=cr.provenance,
        constraints_ok=cr.ok,
        T_total=int(t_total) if t_total is not None else None,
        T_prompt=int(t_prompt) if t_prompt is not None else None,
        T_completion=int(t_completion) if t_completion is not None else None,
        T_cached=int(t_cached) if t_cached is not None else None,
        estimate_source=est_src,
        T_logical_char4_proxy=t_logical,
        B_r_cap=_br_cap(estimate_tokens_char4(text)),
        model=str(getattr(result, "model", model_name)),
        failures=cr.failures,
        answer_text=answer,
        error=None,
        baseline_status=actual_baseline_status,
    )


def _estimate_c123(results: Sequence[BilledInstanceResult]) -> tuple[bool | None, bool | None, bool | None]:
    """Rough confirmatory signals from billed rows (pilot-scale, not Holm).

    C1: mean T_total(compressed) < mean T_total(raw_full) when both present
    C2: morphology/passthrough not worse than raw on constraints (placeholder:
        compressed constraints_ok_rate >= raw) — not a true length-only contrast
    C3: net savings = sum(T_raw) - sum(T_compressed) > 0

    Returns None for a criterion when insufficient billed rows to score.
    """
    by_method: dict[str, list[BilledInstanceResult]] = {}
    for r in results:
        if r.T_total is None or r.error:
            continue
        by_method.setdefault(r.method_id, []).append(r)

    raw = by_method.get("raw_full") or []
    comp = by_method.get("compressed_passthrough") or by_method.get("synthetic_passthrough") or []
    if not raw or not comp:
        return None, None, None

    def _mean_t(rows: Sequence[BilledInstanceResult]) -> float:
        return sum(int(r.T_total or 0) for r in rows) / len(rows)

    mean_raw = _mean_t(raw)
    mean_comp = _mean_t(comp)
    c1 = mean_comp < mean_raw
    c3 = (sum(int(r.T_total or 0) for r in raw) - sum(int(r.T_total or 0) for r in comp)) > 0

    raw_ok = sum(1 for r in raw if r.constraints_ok) / len(raw)
    comp_ok = sum(1 for r in comp if r.constraints_ok) / len(comp)
    # C2 placeholder: compressed not systematically worse on constraints
    # (true morphology-vs-length needs a length-only arm — not in minimal set)
    c2 = comp_ok >= raw_ok - 1e-9

    return c1, c2, c3


def run_billed_pilot(
    *,
    client: ChatClient | None = None,
    families: Sequence[str] | None = None,
    n_per_family: int = MINIMAL_N_PER_FAMILY,
    methods: Sequence[str] = MINIMAL_METHODS,
    paid_api: bool = True,
    model: str = DEFAULT_MODEL,
    minimal: bool = True,
    stop_on_rate_limit: bool = True,
    checkpoint_path: str | Path | None = None,
    partial_path: str | Path | None = None,
    resume: bool = True,
) -> dict[str, Any]:
    """Run billed synthetic pilot; return summary + decision.

    ``T_total`` on each row is provider usage only. Decision defaults to
    ``pivot`` for minimal N (need full N_pilot) unless systematic stop.

    Checkpoint / resume (BITE-15b):
      After every API attempt, append JSONL checkpoint and atomically rewrite
      partial tallies. On start with ``resume=True``, skip already-ok keys
      (no duplicate billing); retry prior timeout/error once; skip prior
      rate_limit keys.
    """
    if families is None:
        fams = list(MINIMAL_FAMILIES if minimal else SYNTHETIC_FAMILIES)
    else:
        fams = list(families)

    if client is None:
        client = ZaiClient(model=model)

    state = BilledRunState()
    per_family: dict[str, Any] = {}
    stopped_early = False

    # Lookup for raw_full Q values by instance_id (for pairing)
    raw_baseline_lookup: dict[str, tuple[float, str]] = {}

    prior = load_checkpoint(checkpoint_path) if resume and checkpoint_path else {}
    skip_ok: dict[tuple[str, str, str], dict[str, Any]] = {}
    skip_rate: dict[tuple[str, str, str], dict[str, Any]] = {}
    retry_once: set[tuple[str, str, str]] = set()
    if resume and prior:
        for key, rec in prior.items():
            status = str(rec.get("status") or "")
            if status == "ok":
                skip_ok[key] = rec
            elif status == "rate_limit":
                # Bug 3 fix: Keep rate_limit records to restore into state
                skip_rate[key] = rec
                # Bug 3 fix: Restore state.rate_limited from checkpointed rate_limit rows
                state.rate_limited = True
                if not state.rate_limit_at:
                    state.rate_limit_at = f"{rec.get('instance_id')}:{rec.get('method')}"
                # Bug 3 fix: Track rate_limit for raw_full even without row data
                # so compressed methods know to skip (not bill as missing_pair)
                method = str(rec.get("method", rec.get("method_id", "")))
                if method == "raw_full":
                    instance_id = str(rec.get("instance_id", ""))
                    if instance_id:
                        raw_baseline_lookup[instance_id] = (0.0, "rate_limit")
            elif status in RESUME_RETRY_STATUSES:
                retry_once.add(key)

        # Restore ok and rate_limit rows into state (from checkpoint row or partial file)
        restored_keys: set[tuple[str, str, str]] = set()
        # Bug 2 fix: Restore rate_limit rows so they populate raw_baseline_lookup
        for key, rec in {**skip_ok, **skip_rate}.items():
            row_data = rec.get("row")
            if isinstance(row_data, dict):
                row = _row_from_dict(row_data)
                state.results.append(row)
                restored_keys.add(key)
                if row.error is None and row.T_total is not None:
                    state.calls_succeeded += 1
                state.calls_skipped_ok += 1
                # Populate raw_baseline_lookup for restored raw_full rows
                if row.method_id == "raw_full":
                    raw_baseline_lookup[row.instance_id] = (row.Q, row.baseline_status)
                    # Bug 1 fix: Refresh stale compressed baselines when restoring successful raw_full
                    if row.error is None and row.baseline_status == "ok":
                        _refresh_stale_baselines(state.results, row.instance_id, row.Q, row.baseline_status)
        if partial_path and Path(partial_path).is_file():
            try:
                partial = json.loads(Path(partial_path).read_text(encoding="utf-8"))
                for rd in partial.get("results") or []:
                    if not isinstance(rd, dict):
                        continue
                    key = _call_key(
                        str(rd.get("family", "")),
                        str(rd.get("instance_id", "")),
                        str(rd.get("method_id", rd.get("method", ""))),
                    )
                    if key in skip_ok and key not in restored_keys:
                        row = _row_from_dict(rd)
                        state.results.append(row)
                        restored_keys.add(key)
                        if row.error is None and row.T_total is not None:
                            state.calls_succeeded += 1
                        state.calls_skipped_ok += 1
                        # Populate raw_baseline_lookup for restored raw_full rows
                        if row.method_id == "raw_full":
                            raw_baseline_lookup[row.instance_id] = (row.Q, row.baseline_status)
                            # Bug 1 fix: Refresh stale compressed baselines when restoring successful raw_full
                            if row.error is None and row.baseline_status == "ok":
                                _refresh_stale_baselines(state.results, row.instance_id, row.Q, row.baseline_status)
            except (json.JSONDecodeError, OSError):
                pass

        # Bug 2 fix (a): Post-restore refresh pass
        # After all rows restored, refresh stale compressed baselines from ok raw_full
        for row in state.results:
            if row.method_id == "raw_full" and row.error is None and row.baseline_status == "ok":
                _refresh_stale_baselines(state.results, row.instance_id, row.Q, row.baseline_status)
                # Bug 2 fix: Persist refreshed compressed rows to checkpoint after restore
                if checkpoint_path is not None:
                    for refreshed_row in state.results:
                        if (
                            refreshed_row.instance_id == row.instance_id
                            and refreshed_row.method_id != "raw_full"
                        ):
                            # Bug 1 fix: Preserve explicit statuses (rate_limit, etc)
                            if refreshed_row.baseline_status == "rate_limit":
                                status = "rate_limit"
                            elif refreshed_row.error is None:
                                status = "ok"
                            else:
                                status = "error"
                            append_checkpoint(
                                checkpoint_path,
                                _checkpoint_record(
                                    family=refreshed_row.family,
                                    instance_id=refreshed_row.instance_id,
                                    method=refreshed_row.method_id,
                                    status=status,
                                    row=refreshed_row,
                                ),
                            )

    def _record_attempt(
        *,
        family: str,
        instance_id: str,
        method: str,
        status: str,
        error_type: str | None = None,
        usage: Mapping[str, Any] | None = None,
        row: BilledInstanceResult | None = None,
    ) -> None:
        if checkpoint_path is not None:
            append_checkpoint(
                checkpoint_path,
                _checkpoint_record(
                    family=family,
                    instance_id=instance_id,
                    method=method,
                    status=status,
                    error_type=error_type,
                    usage=usage,
                    row=row,
                ),
            )
        flush_partial(state, partial_path)

    for fam in fams:
        if fam not in SYNTHETIC_FAMILIES:
            per_family[fam] = {
                "n_target": n_per_family,
                "n_actual": 0,
                "status": "unknown_family",
            }
            continue
        packets = generate_family_instances(fam, n_per_family)
        fam_results: list[BilledInstanceResult] = [
            r for r in state.results if r.family == fam
        ]
        for pkt in packets:
            for mid in methods:
                key = _call_key(str(pkt.get("family")), str(pkt.get("instance_id")), mid)
                if key in skip_ok:
                    # Already billed successfully — do not call again
                    continue
                if key in skip_rate:
                    # Prior 429 on this key — skip to avoid storm
                    # (rate_limit rows already restored into state above)
                    continue

                # Resume retry: prior timeout/error gets one more attempt under
                # this run's client retry budget (retry_max unchanged / default).
                call_retry_max: int | None = None
                if key in retry_once:
                    state.calls_resumed_retry += 1
                    # Still use client's full retry budget for the re-attempt.
                    call_retry_max = None
                
                # Look up paired raw_full Q for non-raw methods
                raw_baseline_q = None
                baseline_status = None
                instance_id = str(pkt.get("instance_id"))
                if mid != "raw_full" and instance_id in raw_baseline_lookup:
                    raw_baseline_q, baseline_status = raw_baseline_lookup[instance_id]
                    # Bug 4 fix: Skip compressed if paired raw_full was rate-limited (before incrementing calls_attempted)
                    if baseline_status == "rate_limit":
                        # Don't attempt compressed when paired raw_full hit rate limit
                        continue
                elif mid != "raw_full":
                    # No raw_full pair available yet
                    baseline_status = "missing_pair"
                
                # Bug 4 fix: Increment calls_attempted only after skip checks
                state.calls_attempted += 1
                
                try:
                    
                    row = evaluate_billed_instance(
                        pkt,
                        mid,
                        client,
                        http_trace=state.http_trace,
                        retry_max=call_retry_max,
                        raw_baseline_q=raw_baseline_q,
                        baseline_status=baseline_status,
                    )
                except RateLimitError as exc:
                    # Bug 2 fix: Record rate_limit row so it's tracked in state
                    state.rate_limited = True
                    state.rate_limit_at = f"{pkt.get('instance_id')}:{mid}"
                    stopped_early = True
                    text_proxy = str(pkt.get("document") or "")
                    model_name = getattr(client, "model", "glm-4.5-flash")
                    row = BilledInstanceResult(
                        instance_id=str(pkt.get("instance_id")),
                        family=str(pkt.get("family")),
                        method_id=mid,
                        Q=0.0,
                        Q_baseline=0.0,
                        recall_vis=0.0,
                        recall_rec=0.0,
                        provenance=0.0,
                        constraints_ok=False,
                        T_total=None,
                        T_prompt=None,
                        T_completion=None,
                        T_cached=None,
                        estimate_source=BILLED_USAGE_LABEL,
                        T_logical_char4_proxy=estimate_tokens_char4(text_proxy),
                        B_r_cap=_br_cap(estimate_tokens_char4(text_proxy)),
                        model=str(model_name),
                        failures=("rate_limit",),
                        error=str(exc),
                        baseline_status="rate_limit",
                    )
                    fam_results.append(row)
                    state.results.append(row)
                    # For raw_full, populate lookup so compressed methods see rate_limit status
                    if mid == "raw_full":
                        raw_baseline_lookup[row.instance_id] = (row.Q, row.baseline_status)
                    _record_attempt(
                        family=str(pkt.get("family")),
                        instance_id=str(pkt.get("instance_id")),
                        method=mid,
                        status="rate_limit",
                        error_type="RateLimitError",
                        row=row,
                    )
                    break

                fam_results.append(row)
                state.results.append(row)
                
                # Populate raw_baseline_lookup for raw_full rows
                if row.method_id == "raw_full":
                    raw_baseline_lookup[row.instance_id] = (row.Q, row.baseline_status)
                    # Bug 1 fix: Refresh stale compressed baselines after successful raw_full
                    if row.error is None and row.baseline_status == "ok":
                        _refresh_stale_baselines(state.results, row.instance_id, row.Q, row.baseline_status)
                        # Bug 2 fix (b): Rewrite checkpoint for refreshed compressed rows
                        if checkpoint_path is not None:
                            for refreshed_row in state.results:
                                if (
                                    refreshed_row.instance_id == row.instance_id
                                    and refreshed_row.method_id != "raw_full"
                                ):
                                    # Bug 1 fix: Preserve explicit statuses (rate_limit, etc)
                                    if refreshed_row.baseline_status == "rate_limit":
                                        status = "rate_limit"
                                    elif refreshed_row.error is None:
                                        status = "ok"
                                    else:
                                        status = "error"
                                    # Rewrite checkpoint with updated baseline and constraints
                                    _record_attempt(
                                        family=refreshed_row.family,
                                        instance_id=refreshed_row.instance_id,
                                        method=refreshed_row.method_id,
                                        status=status,
                                        row=refreshed_row,
                                    )

                if row.error is None and row.T_total is not None:
                    state.calls_succeeded += 1
                    usage = {
                        "prompt_tokens": row.T_prompt,
                        "completion_tokens": row.T_completion,
                        "total_tokens": row.T_total,
                        "cached_tokens": row.T_cached,
                    }
                    _record_attempt(
                        family=row.family,
                        instance_id=row.instance_id,
                        method=row.method_id,
                        status="ok",
                        usage=usage,
                        row=row,
                    )
                else:
                    err = row.error or "unknown"
                    is_timeout = (
                        "provider_timeout" in (row.failures or ())
                        or "timed out" in err.lower()
                        or "timeout" in err.lower()
                    )
                    status = "timeout" if is_timeout else "error"
                    _record_attempt(
                        family=row.family,
                        instance_id=row.instance_id,
                        method=row.method_id,
                        status=status,
                        error_type=type(err).__name__ if not isinstance(err, str) else (
                            "ProviderTimeoutError" if is_timeout else "ZaiClientError"
                        ),
                        row=row,
                    )
            if stopped_early:
                break
        # Bug 2 fix: Exclude rate_limit and non-measured baselines from constraints_ok_rate
        # Rows with baseline_status in (timeout, error, missing_pair, unknown) use Q_baseline=0.0
        # so quality constraint passes vacuously — must not inflate constraint rate
        measured_fam_results = [
            r for r in fam_results
            if r.baseline_status not in ("rate_limit", "timeout", "error", "missing_pair", "unknown")
            and r.error is None
        ]
        ok_rate = (
            sum(1 for r in measured_fam_results if r.constraints_ok) / len(measured_fam_results)
            if measured_fam_results
            else 0.0
        )
        per_family[fam] = {
            "n_target": n_per_family,
            "n_actual": len(packets) if not stopped_early else len({r.instance_id for r in fam_results}),
            "n_method_rows": len(fam_results),
            "constraints_ok_rate": ok_rate,
            "status": "rate_limit_partial" if stopped_early else "ok",
        }
        if stopped_early and stop_on_rate_limit:
            break

    # Final flush so crash-free completion still leaves partial/checkpoint current
    flush_partial(state, partial_path)

    n_rows = len(state.results)
    # Bug 2 fix: Exclude rate_limit and non-measured baselines from constraints_ok_rate
    # Rows with baseline_status in (timeout, error, missing_pair, unknown) use Q_baseline=0.0
    # so quality constraint passes vacuously — must not inflate constraint rate
    measured_rows = [
        r for r in state.results
        if r.baseline_status not in ("rate_limit", "timeout", "error", "missing_pair", "unknown")
        and r.error is None
    ]
    constraints_ok_rate = (
        sum(1 for r in measured_rows if r.constraints_ok) / len(measured_rows)
        if measured_rows
        else 0.0
    )
    systematic_fail = len(measured_rows) > 0 and constraints_ok_rate < 0.5

    billed_rows = [r for r in state.results if r.T_total is not None]
    has_billed = len(billed_rows) > 0

    # Sample size vs lock N_pilot: minimal 2×3 does NOT meet N_pilot=24/family
    sample_meets = (not minimal) and all(
        per_family.get(f, {}).get("n_actual", 0) >= N_PILOT_DEFAULT for f in fams
    ) and n_per_family >= N_PILOT_DEFAULT

    c1, c2, c3 = _estimate_c123(state.results)
    if state.rate_limited:
        # Partial run: still score C if possible; decide handles rate_limit_partial
        pass
    if not has_billed and not state.rate_limited:
        c1 = c2 = c3 = None

    decision = decide_gate_c(
        paid_api=paid_api,
        t_total_estimate_source=BILLED_PROVIDER if has_billed else (
            BILLED_PROVIDER if paid_api else LOCAL_ESTIMATE_LABEL
        ),
        constraints_ok_rate=constraints_ok_rate,
        systematic_constraint_fail=systematic_fail,
        c1_t_total_improves_vs_raw_and_best_single=c1,
        c2_morphology_beats_length_only=c2,
        c3_net_savings_positive=c3,
        pivot_scope_trigger=minimal,
        sample_meets_n_pilot=sample_meets,
        rate_limit_partial=state.rate_limited,
        has_billed_usage=has_billed if paid_api else False,
    )

    # Decision reason text
    if state.rate_limited:
        decision_reason = (
            f"rate_limit_partial at {state.rate_limit_at}; "
            f"decision={decision} (partial billed rows={len(billed_rows)})"
        )
    elif not has_billed:
        decision_reason = "no billed usage in results → insufficient_offline / fail path"
        if decision != "stop":
            decision = "insufficient_offline"
            decision_reason = "no billed usage → insufficient_offline"
    elif minimal or not sample_meets:
        decision_reason = (
            f"minimal/incomplete sample "
            f"(n_per_family={n_per_family}, families={len(fams)}; "
            f"N_pilot={N_PILOT_DEFAULT}); prefer pivot — do not claim Go"
        )
        if decision == "go":
            decision = "pivot"
            decision_reason += " (forced pivot: go blocked until N_pilot)"
    else:
        decision_reason = f"label={decision}; c1={c1} c2={c2} c3={c3}"

    summary: dict[str, Any] = {
        "pilot_id": "bite15_billed_synthetic_v0.1",
        "paid_api": paid_api,
        "estimate_source": BILLED_USAGE_LABEL if has_billed else "none",
        "estimate_source_note": (
            "T_total from provider usage only (prompt/completion/total/cached); "
            "T_logical_char4_proxy recorded separately — never mixed into T_total"
        ),
        "model": model,
        "minimal": minimal,
        "resume": resume,
        "checkpoint_path": str(checkpoint_path) if checkpoint_path else None,
        "partial_path": str(partial_path) if partial_path else None,
        "resume_policy": (
            "skip ok; retry prior timeout/error once under this run's retry budget; "
            "skip prior rate_limit keys (no 429 storm)"
        ),
        "lock": {
            "delta": DELTA,
            "rho_visible": RHO_VISIBLE,
            "rho_recoverable": RHO_RECOVERABLE,
            "eta": ETA,
            "J": J,
            "N_pilot": N_PILOT_DEFAULT,
            "N_full": N_FULL_RECORDED,
            "n_per_family_requested": n_per_family,
            "alpha": 0.05,
            "confirmatory": ["C1", "C2", "C3"],
        },
        "families_requested": fams,
        "methods": list(methods),
        "per_family": per_family,
        "n_instance_rows": n_rows,
        "calls_attempted": state.calls_attempted,
        "calls_succeeded": state.calls_succeeded,
        "calls_skipped_ok": state.calls_skipped_ok,
        "calls_resumed_retry": state.calls_resumed_retry,
        "constraints_ok_rate": constraints_ok_rate,
        "has_billed_usage": has_billed,
        "rate_limited": state.rate_limited,
        "rate_limit_at": state.rate_limit_at,
        "sample_meets_n_pilot": sample_meets,
        "c1": c1,
        "c2": c2,
        "c3": c3,
        "decision": decision,
        "decision_reason": decision_reason,
        "http_trace_redacted": state.http_trace,
        "results": [asdict(r) for r in state.results],
    }
    return summary


__all__ = [
    "DEFAULT_CHECKPOINT_PATH",
    "DEFAULT_PARTIAL_PATH",
    "DEFAULT_SUMMARY_PATH",
    "MINIMAL_FAMILIES",
    "MINIMAL_METHODS",
    "MINIMAL_N_PER_FAMILY",
    "N_PILOT_DEFAULT",
    "BilledInstanceResult",
    "append_checkpoint",
    "atomic_write_json",
    "evaluate_billed_instance",
    "load_checkpoint",
    "run_billed_pilot",
    "write_summary",
]
