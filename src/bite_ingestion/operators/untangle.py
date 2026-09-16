"""UNTANGLE operator — quarantine malformed / anomaly / injection / dependency regions."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from bite_ingestion.interfaces.operator import OperatorId

from .base import (
    REASON_QUARANTINED,
    add_r_entry,
    add_recovery_handle,
    append_tau_step,
    deep_copy_packet,
    ensure_units,
    rebuild_visible_from_units,
    sort_units,
    unit_locator,
)

# Structural markers only — TBD-calibrate for richer detectors; no magic score thresholds.
_INJECT_MARKERS = ("<<<INJECT", ">>>INJECT", "{{INJECTION", "<script>", "IGNORE PREVIOUS INSTRUCTIONS")
_ANOMALY_MARKERS = re.compile(r"\b(ERROR|FATAL|EXCEPTION|TRACEBACK|PANIC)\b", re.IGNORECASE)
_DEP_REF = re.compile(r"(?:ref:|#see\s+)([A-Za-z0-9_\-./]+)", re.IGNORECASE)


def _looks_malformed_json(text: str) -> bool:
    s = text.strip()
    if not s:
        return False
    if s[0] not in "{[":
        # Partial JSON fragment heuristic
        return ("{" in s or "[" in s) and (
            s.count("{") != s.count("}") or s.count("[") != s.count("]")
        )
    try:
        json.loads(s)
        return False
    except (json.JSONDecodeError, TypeError):
        return True


def _injection_suspect(text: str) -> bool:
    upper = text.upper()
    for m in _INJECT_MARKERS:
        if m.upper() in upper:
            return True
    return False


def _anomaly_candidate(text: str) -> bool:
    return bool(_ANOMALY_MARKERS.search(text))


def _dependency_refs(text: str) -> list[str]:
    return [m.group(1) for m in _DEP_REF.finditer(text)]


def _classify_unit(unit: Mapping[str, Any], all_ids: set[str]) -> list[str]:
    """Return reason codes for a unit (may be multiple; first is primary for R)."""
    text = str(unit.get("text", ""))
    reasons: list[str] = []
    if _looks_malformed_json(text):
        reasons.append("malformed")
    if _injection_suspect(text):
        reasons.append("injection_suspect")
    if _anomaly_candidate(text):
        reasons.append("anomaly_candidate")
    refs = _dependency_refs(text)
    if refs:
        # edge if any ref points at another known unit id or any ref present
        for r in refs:
            if r in all_ids or r.startswith("u_"):
                reasons.append("dependency_edge")
                break
        else:
            reasons.append("dependency_edge")
    return reasons


def _detect_cycles(edges: list[tuple[str, str]]) -> set[str]:
    """Return unit ids participating in a dependency cycle."""
    graph: dict[str, list[str]] = {}
    for a, b in edges:
        graph.setdefault(a, []).append(b)
    visiting: set[str] = set()
    visited: set[str] = set()
    cyclic: set[str] = set()

    def dfs(node: str, stack: list[str]) -> None:
        if node in visited:
            return
        if node in visiting:
            # mark cycle participants from repeat
            if node in stack:
                idx = stack.index(node)
                for n in stack[idx:]:
                    cyclic.add(n)
            cyclic.add(node)
            return
        visiting.add(node)
        stack.append(node)
        for nxt in graph.get(node, []):
            dfs(nxt, stack)
        stack.pop()
        visiting.discard(node)
        visited.add(node)

    for n in sorted(graph.keys()):
        dfs(n, [])
    return cyclic


class UntangleOperator:
    """Deterministic UNTANGLE: isolate, do not delete; residual+quarantine cover input."""

    id = OperatorId.UNTANGLE

    def apply(
        self,
        packet: Mapping[str, object],
        context: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        _ = context  # reserved; no gold/eval keys consulted
        out = deep_copy_packet(packet)
        units_in = ensure_units(out)
        units_in = sort_units(units_in)
        all_ids = {str(u.get("unit_id", "")) for u in units_in}

        # Build dependency edges from refs
        edges: list[tuple[str, str]] = []
        for u in units_in:
            uid = str(u.get("unit_id", ""))
            for ref in _dependency_refs(str(u.get("text", ""))):
                # Prefer exact unit_id match; else keep symbolic
                edges.append((uid, ref))
        edges = sorted(set(edges))
        cyclic_ids = _detect_cycles([(a, b) for a, b in edges if b in all_ids])

        isolated: list[dict[str, Any]] = []
        residual: list[dict[str, Any]] = []
        reasons_map: dict[str, list[str]] = {}
        r_ids: list[str] = []

        for u in units_in:
            uid = str(u.get("unit_id", ""))
            reasons = _classify_unit(u, all_ids)
            if uid in cyclic_ids and "dependency_cycle" not in reasons:
                reasons = list(reasons) + ["dependency_cycle"]
            reasons = sorted(set(reasons))
            if reasons:
                reasons_map[uid] = reasons
                primary = reasons[0]
                # Prefer strongest quarantine label order
                for preferred in ("injection_suspect", "malformed", "anomaly_candidate", "dependency_cycle", "dependency_edge"):
                    if preferred in reasons:
                        primary = preferred
                        break
                isolated.append({**dict(u), "untangle_reasons": reasons})
                rid = add_r_entry(
                    out,
                    unit_id=uid,
                    reason=REASON_QUARANTINED,
                    recoverable=True,
                    locator=unit_locator(u),
                    extra={"reason_codes": reasons, "primary_reason": primary, "text": u.get("text")},
                )
                r_ids.append(rid)
            else:
                residual.append(dict(u))

        # Coverage invariant: residual + isolated == input set
        iso_ids = {str(u.get("unit_id", "")) for u in isolated}
        res_ids = {str(u.get("unit_id", "")) for u in residual}
        assert iso_ids | res_ids == all_ids
        assert iso_ids.isdisjoint(res_ids)

        if r_ids:
            add_recovery_handle(out, r_ids=sorted(r_ids), op=OperatorId.UNTANGLE)

        residual = sort_units(residual)
        isolated = sort_units(isolated)
        out["units"] = residual
        out["visible_evidence"] = rebuild_visible_from_units(residual)
        out["untangle"] = {
            "isolated": [
                {"unit_id": str(u["unit_id"]), "reasons": reasons_map.get(str(u["unit_id"]), u.get("untangle_reasons", []))}
                for u in isolated
            ],
            "residual_ids": [str(u["unit_id"]) for u in residual],
            "reasons": {k: reasons_map[k] for k in sorted(reasons_map.keys())},
            "dependency_edges": [{"from": a, "to": b} for a, b in edges],
        }
        out["op_status"] = "ok"
        append_tau_step(
            out,
            op=OperatorId.UNTANGLE,
            inputs_ref=sorted(all_ids),
            outputs_ref=[str(u["unit_id"]) for u in residual],
            omitted_ref=sorted(iso_ids),
            extra={
                "untangle.isolated": out["untangle"]["isolated"],
                "untangle.residual_ids": out["untangle"]["residual_ids"],
                "untangle.reasons": out["untangle"]["reasons"],
            },
        )
        return out
