"""Offline synthetic pilot runner (BITE-14).

Uses local_char4_proxy for T_total. Never calls paid APIs.
Decision defaults to insufficient_offline when confirmatory C1–C3
cannot be assessed with billed tokens.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from bite_eval.accounting.estimate import LOCAL_ESTIMATE_LABEL, estimate_tokens_char4
from bite_eval.pilot.constraints import check_constraints, metrics_from_instance
from bite_eval.pilot.decide import decide_gate_c
from bite_eval.pilot.families import SYNTHETIC_FAMILIES, generate_family_instances


def _as_str_list(value: object, default: list[str] | None = None) -> list[str]:
    if default is None:
        default = []
    if value is None:
        return list(default)
    if isinstance(value, (list, tuple, set)):
        return [str(x) for x in value]
    return list(default)


# Locked thresholds (d2_lock_v0.1) — do not invent extras.
DELTA = 0.05
RHO_VISIBLE = 0.50
RHO_RECOVERABLE = 0.90
ETA = 0.95
N_PILOT_DEFAULT = 24
N_FULL_RECORDED = 100
J = 3


@dataclass
class InstanceResult:
    instance_id: str
    family: str
    method_id: str
    Q: float
    Q_baseline: float
    recall_vis: float
    recall_rec: float
    provenance: float
    constraints_ok: bool
    T_total_proxy: int
    T_in_raw_proxy: int
    B_r_cap: int
    estimate_source: str
    failures: tuple[str, ...]


def _br_cap(t_in_raw: int) -> int:
    """B_r = min(4096, floor(0.5 * T_in(raw)))."""
    return min(4096, int(0.5 * t_in_raw))


def _synthetic_method_answer(packet: Mapping[str, object], method_id: str) -> tuple[str | None, list[str]]:
    """Deterministic offline 'methods' for smoke/pilot — no LLM.

    - raw_full: uses full gold answer if visible evidence non-empty OR omission
      family with recoverable ids (simulates recover within J).
    - synthetic_passthrough: same as raw for offline; visible = packet visible
      or recoverable for adversarial_omission.
    """
    gold = str(packet.get("gold_answer", ""))
    vis = _as_str_list(packet.get("visible_evidence"))
    rec = _as_str_list(packet.get("recoverable_evidence_ids"))
    family = str(packet.get("family", ""))

    if method_id in {"raw_full", "synthetic_passthrough"}:
        if vis:
            return gold, vis
        # adversarial_omission: simulate bounded recover using recoverable ids
        if family == "adversarial_omission" and rec:
            return gold, list(vis)  # visible stays empty; recall_rec uses rec
        return gold, vis
    return None, vis


def evaluate_instance(
    packet: Mapping[str, object],
    method_id: str,
    *,
    delta: float = DELTA,
    rho_visible: float = RHO_VISIBLE,
    rho_recoverable: float = RHO_RECOVERABLE,
    eta: float = ETA,
) -> InstanceResult:
    answer, vis = _synthetic_method_answer(packet, method_id)
    m = metrics_from_instance(packet, vis, answer=answer)

    # Baseline Q: raw_full on same packet (offline gold-matched)
    base_answer, base_vis = _synthetic_method_answer(packet, "raw_full")
    m_base = metrics_from_instance(packet, base_vis, answer=base_answer)
    Q_baseline = float(m_base["quality"])

    text = str(packet.get("document") or "")
    t_in = estimate_tokens_char4(text)
    # Proxy T_total: profiler0 + router0 + in + small out
    t_out = estimate_tokens_char4(str(answer or ""))
    t_total = t_in + t_out  # labeled local_char4_proxy

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

    return InstanceResult(
        instance_id=str(packet.get("instance_id")),
        family=str(packet.get("family")),
        method_id=method_id,
        Q=cr.Q,
        Q_baseline=cr.Q_baseline,
        recall_vis=cr.recall_vis,
        recall_rec=cr.recall_rec,
        provenance=cr.provenance,
        constraints_ok=cr.ok,
        T_total_proxy=t_total,
        T_in_raw_proxy=t_in,
        B_r_cap=_br_cap(t_in),
        estimate_source=LOCAL_ESTIMATE_LABEL,
        failures=cr.failures,
    )


def run_pilot(
    *,
    families: Sequence[str] | None = None,
    n_per_family: int = N_PILOT_DEFAULT,
    methods: Sequence[str] = ("raw_full", "synthetic_passthrough"),
    paid_api: bool = False,
) -> dict[str, Any]:
    """Run offline synthetic pilot; return summary + decision label.

    Always labels estimate_source=local_char4_proxy when paid_api=False.
    Confirmatory C1–C3 left as None → decide_gate_c → insufficient_offline.
    """
    fams = list(families) if families is not None else list(SYNTHETIC_FAMILIES)
    per_family: dict[str, Any] = {}
    all_results: list[InstanceResult] = []
    insufficient_offline_notes: list[str] = []

    for fam in fams:
        if fam not in SYNTHETIC_FAMILIES:
            per_family[fam] = {
                "n_target": n_per_family,
                "n_actual": 0,
                "status": "insufficient_offline",
                "reason": "unknown_family",
            }
            insufficient_offline_notes.append(f"unknown_family:{fam}")
            continue
        packets = generate_family_instances(fam, n_per_family)
        n_actual = len(packets)
        fam_results: list[InstanceResult] = []
        for pkt in packets:
            for mid in methods:
                fam_results.append(evaluate_instance(pkt, mid))
        all_results.extend(fam_results)
        ok_rate = (
            sum(1 for r in fam_results if r.constraints_ok) / len(fam_results)
            if fam_results
            else 0.0
        )
        status = "ok" if n_actual >= n_per_family else "insufficient_offline"
        if n_actual < n_per_family:
            insufficient_offline_notes.append(
                f"{fam}:n_actual={n_actual}<n_target={n_per_family}"
            )
        per_family[fam] = {
            "n_target": n_per_family,
            "n_actual": n_actual,
            "n_method_rows": len(fam_results),
            "constraints_ok_rate": ok_rate,
            "status": status,
        }

    n_rows = len(all_results)
    constraints_ok_rate = (
        sum(1 for r in all_results if r.constraints_ok) / n_rows if n_rows else 0.0
    )
    # Systematic fail: majority of rows fail constraints
    systematic_fail = n_rows > 0 and constraints_ok_rate < 0.5

    # C1–C3 not evaluable offline with proxy tokens
    decision = decide_gate_c(
        paid_api=paid_api,
        t_total_estimate_source=LOCAL_ESTIMATE_LABEL,
        constraints_ok_rate=constraints_ok_rate,
        systematic_constraint_fail=systematic_fail,
        c1_t_total_improves_vs_raw_and_best_single=None,
        c2_morphology_beats_length_only=None,
        c3_net_savings_positive=None,
        pivot_scope_trigger=False,
    )

    summary = {
        "pilot_id": "bite14_offline_synthetic_v0.1",
        "paid_api": paid_api,
        "estimate_source": LOCAL_ESTIMATE_LABEL,
        "estimate_source_limitation": (
            "T_total is local_char4_proxy not provider billed; "
            "therefore confirmatory C1–C3 cannot be honestly evaluated offline"
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
        },
        "families_requested": fams,
        "families_run": {
            f: per_family[f]["n_actual"]
            for f in fams
            if f in per_family and per_family[f]["n_actual"] > 0
        },
        "per_family": per_family,
        "n_instance_rows": n_rows,
        "constraints_ok_rate": constraints_ok_rate,
        "decision": decision,
        "decision_reason": (
            "paid_api=false and T_total=local_char4_proxy; "
            "C1/C2/C3 unevaluable → insufficient_offline"
            if decision == "insufficient_offline"
            else f"label={decision}"
        ),
        "insufficient_offline_notes": insufficient_offline_notes,
        "results": [asdict(r) for r in all_results],
    }
    return summary


def write_summary(summary: Mapping[str, Any], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Strip bulky results for a slim sibling if huge — still write full by default
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out
