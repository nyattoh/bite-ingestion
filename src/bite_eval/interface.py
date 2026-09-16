"""Common evaluation interface for fair baseline adapters (BITE-12)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

STATUS_VALUES = frozenset({"ok", "failed", "overflow", "not_applicable"})


@runtime_checkable
class BaselineAdapter(Protocol):
    """Uniform target for all baselines — same tool permissions as candidate."""

    baseline_id: str

    def run(
        self,
        packet: Mapping[str, object],
        context: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        """Return an output packet with status, visible_evidence, accounting."""
        ...


def empty_accounting(
    *,
    router: int = 0,
    compressor: int = 0,
    extra: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Baseline-side token ledger fields (DC-5: same T_total contract)."""
    out: dict[str, object] = {
        "baseline_router_tokens": int(router),
        "baseline_compressor_tokens": int(compressor),
    }
    if extra:
        out.update(dict(extra))
    return out


def make_output(
    *,
    baseline_id: str,
    status: str,
    visible_evidence: object,
    accounting: Mapping[str, object] | None = None,
    tau: list | None = None,
    baseline_trace: Mapping[str, object] | None = None,
    reason: str | None = None,
    extra: Mapping[str, object] | None = None,
) -> dict[str, object]:
    if status not in STATUS_VALUES:
        raise ValueError(f"invalid status={status!r}; allowed={sorted(STATUS_VALUES)}")
    pkt: dict[str, object] = {
        "baseline_id": baseline_id,
        "status": status,
        "visible_evidence": visible_evidence,
        "accounting": dict(accounting or empty_accounting()),
    }
    if tau is not None:
        pkt["tau"] = list(tau)
    if baseline_trace is not None:
        pkt["baseline_trace"] = dict(baseline_trace)
    if reason is not None:
        pkt["reason"] = reason
    if extra:
        for k, v in extra.items():
            if k not in pkt:
                pkt[k] = v
    # Never silent: failed/overflow/not_applicable must carry a reason when possible
    if status != "ok" and "reason" not in pkt:
        pkt["reason"] = f"status={status}"
    return pkt


def extract_text(packet: Mapping[str, object]) -> str:
    """Pull raw text / document body from a synthetic eval packet."""
    for key in ("document", "text", "content", "raw_context"):
        v = packet.get(key)
        if isinstance(v, str):
            return v
    ve = packet.get("visible_evidence")
    if isinstance(ve, str):
        return ve
    if isinstance(ve, list):
        parts: list[str] = []
        for item in ve:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, Mapping):
                for k in ("text", "content", "span", "body"):
                    if isinstance(item.get(k), str):
                        parts.append(str(item[k]))
                        break
        return "\n".join(parts)
    if isinstance(ve, Mapping):
        for k in ("text", "content", "body"):
            if isinstance(ve.get(k), str):
                return str(ve[k])
    return ""


def extract_query(packet: Mapping[str, object], context: Mapping[str, object] | None) -> str:
    for src in (packet, context or {}):
        for key in ("query", "q", "q_star", "question"):
            v = src.get(key) if isinstance(src, Mapping) else None
            if isinstance(v, str) and v.strip():
                return v
    return ""


def extract_domain(packet: Mapping[str, object], context: Mapping[str, object] | None) -> str:
    for src in (context or {}, packet):
        if not isinstance(src, Mapping):
            continue
        for key in ("domain", "workload_domain", "domain_id"):
            v = src.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip().lower()
    return ""


def extract_morphology(packet: Mapping[str, object], context: Mapping[str, object] | None) -> dict[str, float]:
    for src in (packet, context or {}):
        if not isinstance(src, Mapping):
            continue
        m = src.get("morphology") or src.get("m")
        if isinstance(m, Mapping):
            out: dict[str, float] = {}
            for k, v in m.items():
                try:
                    out[str(k)] = float(v)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    continue
            return out
    return {}


def extract_budget(packet: Mapping[str, object], context: Mapping[str, object] | None) -> dict[str, object]:
    budget: dict[str, object] = {}
    for src in (packet, context or {}):
        if not isinstance(src, Mapping):
            continue
        b = src.get("budget")
        if isinstance(b, Mapping):
            budget.update(dict(b))
        for k in ("n_tokens", "char_len", "task_id", "pre_segmented", "malformed", "max_chars"):
            if k in src and k not in budget:
                budget[k] = src[k]
    # derive char_len if missing
    if "char_len" not in budget:
        text = extract_text(packet)
        if text:
            budget["char_len"] = len(text)
    return budget




def _coerce_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
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


def _coerce_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default

__all__ = [
    "STATUS_VALUES",
    "BaselineAdapter",
    "_coerce_float",
    "_coerce_int",
    "empty_accounting",
    "extract_budget",
    "extract_domain",
    "extract_morphology",
    "extract_query",
    "extract_text",
    "make_output",
]
