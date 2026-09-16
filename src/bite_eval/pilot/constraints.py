"""Constraint checks from D-2 lock v0.1.

  Q(pi) >= Q_baseline - delta
  Recall_vis >= rho_visible
  Recall_rec >= rho_recoverable
  Prov(pi) >= eta

Locked: delta=0.05, rho_visible=0.50, rho_recoverable=0.90, eta=0.95
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


def _as_str_list(value: object, default: list[str] | None = None) -> list[str]:
    if default is None:
        default = []
    if value is None:
        return list(default)
    if isinstance(value, (list, tuple, set)):
        return [str(x) for x in value]
    return list(default)



@dataclass(frozen=True)
class ConstraintResult:
    ok: bool
    q_ok: bool
    recall_vis_ok: bool
    recall_rec_ok: bool
    prov_ok: bool
    Q: float
    Q_baseline: float
    delta: float
    recall_vis: float
    recall_rec: float
    provenance: float
    failures: tuple[str, ...]


def check_constraints(
    *,
    Q: float,
    Q_baseline: float,
    recall_vis: float,
    recall_rec: float,
    provenance: float,
    delta: float = 0.05,
    rho_visible: float = 0.50,
    rho_recoverable: float = 0.90,
    eta: float = 0.95,
) -> ConstraintResult:
    """Evaluate matched-quality + recall + Prov constraints (lock §3)."""
    failures: list[str] = []
    q_ok = Q >= (Q_baseline - delta)
    if not q_ok:
        failures.append("Q < Q_baseline - delta")
    recall_vis_ok = recall_vis >= rho_visible
    if not recall_vis_ok:
        failures.append("Recall_vis < rho_visible")
    recall_rec_ok = recall_rec >= rho_recoverable
    if not recall_rec_ok:
        failures.append("Recall_rec < rho_recoverable")
    prov_ok = provenance >= eta
    if not prov_ok:
        failures.append("Prov < eta")
    return ConstraintResult(
        ok=not failures,
        q_ok=q_ok,
        recall_vis_ok=recall_vis_ok,
        recall_rec_ok=recall_rec_ok,
        prov_ok=prov_ok,
        Q=Q,
        Q_baseline=Q_baseline,
        delta=delta,
        recall_vis=recall_vis,
        recall_rec=recall_rec,
        provenance=provenance,
        failures=tuple(failures),
    )


def metrics_from_instance(
    packet: Mapping[str, object],
    method_visible: list[str] | tuple[str, ...] | None,
    *,
    answer: str | None,
) -> dict[str, float]:
    """Offline synthetic metrics: accuracy + set recalls + Prov completeness.

    Gold fields expected on packet:
      gold_answer, gold_evidence_ids (list), recoverable_evidence_ids (list),
      provenance_complete_rate (float in [0,1]) optional.
    """
    gold = str(packet.get("gold_answer", ""))
    q = 1.0 if (answer is not None and str(answer).strip() == gold.strip()) else 0.0

    gold_ids = _as_str_list(packet.get("gold_evidence_ids"))
    rec_ids = set(_as_str_list(packet.get("recoverable_evidence_ids"), gold_ids))
    vis = set(_as_str_list(method_visible))
    gold_set = set(gold_ids)

    if gold_set:
        recall_vis = len(gold_set & vis) / len(gold_set)
        recall_rec = len(gold_set & (vis | rec_ids)) / len(gold_set)
    else:
        recall_vis = 1.0
        recall_rec = 1.0

    prov = packet.get("provenance_complete_rate")
    if isinstance(prov, (int, float)):
        provenance = float(prov)
    else:
        # Default: synthetic packets author complete provenance
        provenance = 1.0

    return {
        "quality": q,
        "evidence_recall_visible": recall_vis,
        "evidence_recall_recoverable": recall_rec,
        "provenance": provenance,
    }
