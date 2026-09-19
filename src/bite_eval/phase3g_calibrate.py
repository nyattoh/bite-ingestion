"""Phase 3G calibration-only lock of v1 feature candidate and thresholds.

Uses Phase 3F v0.3 only. Does not open evaluation. Does not change v1 or RulePolicy.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from itertools import product
from pathlib import Path
from typing import Any

from bite_bench.models import Fact
from bite_bench.phase3f import (
    ADVERSARIAL_KINDS,
    CALIBRATION_REPLICAS,
    CANDIDATES,
    COLLAPSE_FRACTION,
    DISPERSIONS,
    FORMATS,
    SCALES,
    Dispersion,
    Fmt,
    Phase3FCell,
    adversarial_case,
    adversarial_surface,
    bin_is_elevated,
    bin_ordering_holds,
    candidate_ordering_holds,
    design_cells,
    freeze_manifest,
    intended_edges,
    is_negative_adversarial_case,
    layout_facts,
    make_canonical,
    make_surface,
    scale_stability_holds,
    select_best_candidate,
    select_best_grid_point,
    sensor_source_unit,
    split_for_replica,
)
from bite_bench.phase3f import REVISION as PHASE3F_REVISION
from bite_ingestion.profilers.dependency_dispersion_v1 import FEATURE_KEYS, measure

SCHEMA_ID = "bite-phase3g-calibration-lock/v0.1"
VERDICT_LOCKED = "PHASE3G_CALIBRATION_LOCKED"
VERDICT_BLOCKED = "PHASE3G_CALIBRATION_BLOCKED"
VERDICTS = (VERDICT_LOCKED, VERDICT_BLOCKED)
N_PRIMARY = 108
N_ADVERSARIAL = 24
N_TOTAL = 132

_REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = _REPO / "artifacts" / "phase3g"
MEASURE_PATH = ARTIFACT_DIR / "calibration-measurements.json"
GRID_PATH = ARTIFACT_DIR / "calibration-grid-search.json"
LOCK_PATH = ARTIFACT_DIR / "calibration-lock.json"
LOCK_MD_PATH = ARTIFACT_DIR / "calibration-lock.md"
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase3f-routing-calibration-freeze-v0.3.json"


class EvaluationSealError(RuntimeError):
    """Evaluation split is sealed. Fail closed before payload generation."""


def refuse_if_evaluation(*, split: str, replica: int) -> None:
    if replica not in CALIBRATION_REPLICAS or split != "calibration":
        raise EvaluationSealError(
            f"evaluation sealed: refused split={split!r} replica={replica}"
        )


def _ordered_facts(cell: Phase3FCell, dispersion: Dispersion) -> tuple[Fact, ...]:
    canonical = make_canonical(cell)
    dep = [f for f in canonical.facts if f.fact_id.startswith(f"{cell.case_id}-d")]
    noise = [f for f in canonical.facts if f.fact_id.startswith(f"{cell.case_id}-n")]
    return layout_facts(dep, noise, cell.shape, dispersion)


def _undirected(edges: Sequence[Mapping[str, Any]]) -> set[frozenset[int]]:
    return {frozenset((int(row["src"]), int(row["dst"]))) for row in edges}


def _intended_index_pairs(
    ordered_ids: Sequence[str], intended: Sequence[Sequence[str]]
) -> set[frozenset[int]]:
    index = {fact_id: i for i, fact_id in enumerate(ordered_ids)}
    pairs: set[frozenset[int]] = set()
    for pair in intended:
        pairs.add(frozenset((index[pair[0]], index[pair[1]])))
    return pairs


def _score_edges(
    observed: set[frozenset[int]], intended: set[frozenset[int]]
) -> dict[str, float]:
    extra = observed - intended
    n_obs = float(len(observed))
    n_int = float(len(intended))
    extra_n = float(len(extra))
    tp = float(len(observed & intended))
    precision = (tp / n_obs) if n_obs else (1.0 if n_int == 0.0 else 0.0)
    return {
        "n_observed_undirected": n_obs,
        "n_intended": n_int,
        "extra_edge_count": extra_n,
        "edge_precision": precision,
    }


def _features(report: Any) -> dict[str, float]:
    return {key: float(report.features[key]) for key in FEATURE_KEYS}


def measure_calibration_primary(
    cell: Phase3FCell, dispersion: Dispersion, fmt: Fmt
) -> dict[str, Any]:
    refuse_if_evaluation(split=cell.split, replica=cell.replica)
    surf = make_surface(cell, dispersion, fmt)
    ordered = _ordered_facts(cell, dispersion)
    report = measure(sensor_source_unit(surf["payload"]))
    observed = _undirected(report.edges)
    intended = _intended_index_pairs(
        [fact.fact_id for fact in ordered], intended_edges(cell)
    )
    scored = _score_edges(observed, intended)
    return {
        "surface_id": surf["surface_id"],
        "case_id": cell.case_id,
        "family": "primary",
        "split": cell.split,
        "scale": cell.scale,
        "shape": cell.shape,
        "replica": cell.replica,
        "dispersion": dispersion,
        "format": fmt,
        "fail_closed": report.fail_closed,
        "features": _features(report),
        **scored,
    }


def measure_calibration_adversarial(kind: str, replica: int, fmt: Fmt) -> dict[str, Any]:
    refuse_if_evaluation(split=split_for_replica(replica), replica=replica)
    spec = adversarial_case(kind, replica)
    surf = adversarial_surface(kind, replica, fmt)
    facts = tuple(Fact(**row) for row in spec["facts"])
    report = measure(sensor_source_unit(surf["payload"]))
    observed = _undirected(report.edges)
    intended = _intended_index_pairs(
        [fact.fact_id for fact in facts], spec["intended_edges"]
    )
    scored = _score_edges(observed, intended)
    return {
        "surface_id": surf["surface_id"],
        "case_id": spec["case_id"],
        "family": "adversarial",
        "kind": kind,
        "split": spec["split"],
        "replica": replica,
        "format": fmt,
        "fail_closed": report.fail_closed,
        "intended_empty": is_negative_adversarial_case(spec["intended_edges"]),
        "features": _features(report),
        **scored,
    }


def bin_univariate(x: float, t_low: float, t_high: float) -> str:
    if x <= t_low:
        return "low"
    if x >= t_high:
        return "high"
    return "mid"


def bin_candidate(candidate_id: str, features: Mapping[str, float], point: Mapping[str, Any]) -> str:
    raw = float(features["mean_edge_distance"])
    norm = float(features["mean_edge_distance_norm"])
    if candidate_id == "A_mean_edge_distance":
        return bin_univariate(raw, float(point["T_low"]), float(point["T_high"]))
    if candidate_id == "B_mean_edge_distance_norm":
        return bin_univariate(norm, float(point["T_low"]), float(point["T_high"]))
    if candidate_id == "C_raw_and_norm":
        if raw >= float(point["T_raw_high"]) and norm >= float(point["T_norm_high"]):
            return "high"
        if raw <= float(point["T_raw_low"]) and norm <= float(point["T_norm_low"]):
            return "low"
        return "mid"
    raise ValueError(candidate_id)


def enumerate_frozen_grid(candidate_id: str, grids: Mapping[str, Any]) -> list[dict[str, Any]]:
    spec = dict(grids[candidate_id])
    points: list[dict[str, Any]] = []
    if candidate_id == "C_raw_and_norm":
        for t_raw_low, t_raw_high, t_norm_low, t_norm_high in product(
            spec["T_raw_low"], spec["T_raw_high"], spec["T_norm_low"], spec["T_norm_high"]
        ):
            if t_raw_low < t_raw_high and t_norm_low < t_norm_high:
                points.append(
                    {
                        "T_raw_low": t_raw_low,
                        "T_raw_high": t_raw_high,
                        "T_norm_low": t_norm_low,
                        "T_norm_high": t_norm_high,
                    }
                )
        return points
    for t_low, t_high in product(spec["T_low"], spec["T_high"]):
        if t_low < t_high:
            points.append({"T_low": t_low, "T_high": t_high})
    return points


def _lookup(
    rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str, str], Mapping[str, float]]:
    out: dict[tuple[str, str, str], Mapping[str, float]] = {}
    for row in rows:
        if row["family"] != "primary":
            continue
        out[(str(row["case_id"]), str(row["dispersion"]), str(row["format"]))] = row["features"]
    return out


def pre_threshold_metrics(
    candidate_id: str, primary_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    by = _lookup(primary_rows)
    cells = design_cells("calibration")
    n_order = 0
    for cell in cells:
        ok = True
        for fmt in FORMATS:
            raw = [
                float(by[(cell.case_id, disp, fmt)]["mean_edge_distance"])
                for disp in DISPERSIONS
            ]
            norm = [
                float(by[(cell.case_id, disp, fmt)]["mean_edge_distance_norm"])
                for disp in DISPERSIONS
            ]
            if not candidate_ordering_holds(
                candidate_id,
                raw_near=raw[0],
                raw_medium=raw[1],
                raw_far=raw[2],
                norm_near=norm[0],
                norm_medium=norm[1],
                norm_far=norm[2],
            ):
                ok = False
                break
        if ok:
            n_order += 1
    n_scale = 0
    for replica in CALIBRATION_REPLICAS:
        replica_ok = True
        for fmt in FORMATS:
            raw_medium: dict[str, float] = {
                scale: float(
                    by[(f"p3f-{scale}-one_hop-r{replica}", "medium", fmt)][
                        "mean_edge_distance"
                    ]
                )
                for scale in SCALES
            }
            norm_far: dict[str, float] = {
                scale: float(
                    by[(f"p3f-{scale}-one_hop-r{replica}", "far", fmt)][
                        "mean_edge_distance_norm"
                    ]
                )
                for scale in SCALES
            }
            if not scale_stability_holds(
                candidate_id,
                raw_one_hop_medium=raw_medium,
                norm_one_hop_far=norm_far,
            ):
                replica_ok = False
                break
        if replica_ok:
            n_scale += 1
    row: dict[str, Any] = {
        "id": candidate_id,
        "continuous_dispersion_ordering_coverage": n_order / len(cells),
        "scale_stability": n_scale / len(CALIBRATION_REPLICAS),
        "n_ordering_cells": len(cells),
        "n_scale_replicas": len(CALIBRATION_REPLICAS),
    }
    if candidate_id == "C_raw_and_norm":
        row["continuous_score"] = None
        row["weighted_sum"] = False
    elif candidate_id == "A_mean_edge_distance":
        row["continuous_score"] = "mean_edge_distance"
    else:
        row["continuous_score"] = "mean_edge_distance_norm"
    return row


def evaluate_grid_point(
    candidate_id: str,
    point: Mapping[str, Any],
    primary_rows: Sequence[Mapping[str, Any]],
    adv_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    bins = [bin_candidate(candidate_id, row["features"], point) for row in primary_rows]
    dist = Counter(bins)
    n = len(primary_rows)
    non_collapse = all((dist[label] / n) < COLLAPSE_FRACTION for label in ("low", "mid", "high"))
    negatives = [row for row in adv_rows if row.get("intended_empty")]
    elevated = sum(
        1
        for row in negatives
        if bin_is_elevated(bin_candidate(candidate_id, row["features"], point))
    )
    neg_rate = elevated / len(negatives) if negatives else 0.0
    n_order = 0
    n_order_denom = 0
    n_fmt = 0
    n_fmt_denom = 0
    cells = design_cells("calibration")
    by_bin: dict[tuple[str, str, str], str] = {}
    for row in primary_rows:
        by_bin[(str(row["case_id"]), str(row["dispersion"]), str(row["format"]))] = (
            bin_candidate(candidate_id, row["features"], point)
        )
    for cell in cells:
        for fmt in FORMATS:
            n_order_denom += 1
            if bin_ordering_holds(
                by_bin[(cell.case_id, "near", fmt)],
                by_bin[(cell.case_id, "medium", fmt)],
                by_bin[(cell.case_id, "far", fmt)],
            ):
                n_order += 1
        for disp in DISPERSIONS:
            n_fmt_denom += 1
            if by_bin[(cell.case_id, disp, "key_value")] == by_bin[(cell.case_id, disp, "json")]:
                n_fmt += 1
    row = dict(point)
    row.update(
        {
            "bin_distribution": {k: int(dist[k]) for k in ("low", "mid", "high")},
            "non_collapse": non_collapse,
            "negative_adversarial_elevated_bin_rate": neg_rate,
            "bin_ordering_coverage": n_order / n_order_denom,
            "format_consistency": n_fmt / n_fmt_denom,
        }
    )
    return row


def _blocked_reasons(
    freeze: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    committed: Mapping[str, Any],
) -> list[str]:
    reasons: list[str] = []
    if freeze.get("revision") != PHASE3F_REVISION:
        reasons.append("freeze_revision_mismatch")
    if committed != freeze:
        reasons.append("committed_freeze_mismatch")
    if freeze.get("revision") != "phase3f-routing-calibration-freeze-v0.3":
        reasons.append("not_v0.3")
    if len(rows) != N_TOTAL:
        reasons.append(f"expected_{N_TOTAL}_rows_got_{len(rows)}")
    if any(row.get("replica") not in CALIBRATION_REPLICAS for row in rows):
        reasons.append("evaluation_seal_broken")
    if any(row.get("split") != "calibration" for row in rows):
        reasons.append("evaluation_seal_broken")
    if any(row.get("fail_closed") for row in rows):
        reasons.append("sensor_fail_closed")
    n_primary = sum(1 for row in rows if row["family"] == "primary")
    n_adv = sum(1 for row in rows if row["family"] == "adversarial")
    if n_primary != N_PRIMARY or n_adv != N_ADVERSARIAL:
        reasons.append("catalog_count_mismatch")
    return reasons


def run_calibration() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    freeze = freeze_manifest()
    committed = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    primary = [
        measure_calibration_primary(cell, disp, fmt)
        for cell in design_cells("calibration")
        for disp, fmt in product(DISPERSIONS, FORMATS)
    ]
    adversarial = [
        measure_calibration_adversarial(kind, replica, fmt)
        for kind, replica, fmt in product(ADVERSARIAL_KINDS, CALIBRATION_REPLICAS, FORMATS)
    ]
    rows = primary + adversarial
    extra_obs = sum(float(row["extra_edge_count"]) for row in rows)
    n_obs = sum(float(row["n_observed_undirected"]) for row in rows)
    fp_rate = extra_obs / n_obs if n_obs else 0.0
    true_dep = [
        {
            "surface_id": row["surface_id"],
            "edge_precision": row["edge_precision"],
            "extra_edge_count": row["extra_edge_count"],
        }
        for row in adversarial
        if row.get("kind") == "true_dep_plus_misleading_suffix"
    ]
    measurements = {
        "schema": "bite-phase3g-calibration-measurements/v0.1",
        "freeze_revision": PHASE3F_REVISION,
        "paid_api": False,
        "evaluation_outcomes_open": False,
        "evaluation_holdout_used": False,
        "n_primary": N_PRIMARY,
        "n_adversarial": N_ADVERSARIAL,
        "n_total": len(rows),
        "sensor": "dependency_dispersion_v1",
        "feature_keys": list(FEATURE_KEYS),
        "sensor_diagnostics": {
            "edge_false_positive_rate": fp_rate,
            "used_in_threshold_grid_objective": False,
            "used_in_candidate_selection": False,
            "sensor_revised": False,
        },
        "true_dep_plus_misleading_suffix": true_dep,
        "rows": rows,
    }
    grids = (freeze.get("threshold_search") or {}).get("grids") or {}
    pre = {cid: pre_threshold_metrics(cid, primary) for cid in CANDIDATES}
    cand_docs: dict[str, Any] = {}
    comparable: list[dict[str, Any]] = []
    for cid in CANDIDATES:
        points = [
            evaluate_grid_point(cid, point, primary, adversarial)
            for point in enumerate_frozen_grid(cid, grids)
        ]
        best = select_best_grid_point(points)
        if best is None:
            cand_docs[cid] = {
                "status": "candidate_ineligible",
                "n_points": len(points),
                "n_eligible": 0,
                "best": None,
                "pre_threshold": pre[cid],
                "points": points,
            }
            continue
        cand_docs[cid] = {
            "status": "eligible",
            "n_points": len(points),
            "n_eligible": sum(1 for point in points if point["non_collapse"]),
            "best": best,
            "pre_threshold": pre[cid],
            "points": points,
        }
        comparable.append(
            {
                "id": cid,
                "non_collapse": True,
                "continuous_dispersion_ordering_coverage": pre[cid][
                    "continuous_dispersion_ordering_coverage"
                ],
                "scale_stability": pre[cid]["scale_stability"],
                "format_consistency": best["format_consistency"],
            }
        )
    blocked = _blocked_reasons(freeze, rows, committed)
    winner = select_best_candidate(comparable)
    if winner is None:
        blocked.append("all_candidates_ineligible")
    if blocked:
        verdict = VERDICT_BLOCKED
        selected = None
        thresholds = None
    else:
        verdict = VERDICT_LOCKED
        selected = winner["id"] if winner else None
        thresholds = dict(cand_docs[selected]["best"]) if selected else None
        if thresholds is not None:
            for key in (
                "bin_distribution",
                "non_collapse",
                "negative_adversarial_elevated_bin_rate",
                "bin_ordering_coverage",
                "format_consistency",
            ):
                thresholds.pop(key, None)
    grid_search = {
        "schema": "bite-phase3g-calibration-grid-search/v0.1",
        "freeze_revision": PHASE3F_REVISION,
        "grids_extended": False,
        "tolerance_added": False,
        "candidates": cand_docs,
        "comparable_ids": [row["id"] for row in comparable],
        "selected_id": selected,
    }
    lock = {
        "schema": SCHEMA_ID,
        "revision": "phase3g-calibration-lock-v0.1",
        "verdict": verdict,
        "blocked_reasons": blocked,
        "offline": True,
        "paid_api": False,
        "synthetic": True,
        "research_conclusion": False,
        "routing_connected": False,
        "rule_policy_changed": False,
        "v1_sensor_changed": False,
        "evaluation_holdout_used": False,
        "evaluation_outcomes_open": False,
        "freeze_revision": PHASE3F_REVISION,
        "operator_map_selected": False,
        "selected_operator_map": None,
        "high_bin_mapped_to_operator": False,
        "selected_candidate": selected,
        "selected_thresholds": thresholds,
        "pre_threshold_metrics": pre,
        "sensor_diagnostics": measurements["sensor_diagnostics"],
        "n_signal_not_used": True,
        "integrate_rate_not_used": True,
        "edge_fp_not_used_for_selection": True,
        "phase3g_selects": ["feature_candidate_A_B_C", "threshold_values"],
        "phase3g_does_not_select": [
            "M1_locality_for_integrate",
            "M2_spread_needs_gather",
        ],
    }
    return measurements, grid_search, lock


def render_lock_md(lock: Mapping[str, Any], grid: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 3G calibration lock",
        "",
        "Phase 3F v0.3 のみ。calibration split だけ測定。evaluation 未開封。RulePolicy 未接続。",
        "",
        f"- verdict: **{lock.get('verdict')}**",
        f"- selected_candidate: `{lock.get('selected_candidate')}`",
        f"- selected_thresholds: `{lock.get('selected_thresholds')}`",
        f"- operator_map_selected: {lock.get('operator_map_selected')}",
        f"- blocked_reasons: {lock.get('blocked_reasons')}",
        "",
        "## Pre-threshold",
        "",
    ]
    for cid, row in dict(lock.get("pre_threshold_metrics") or {}).items():
        lines.append(
            f"- {cid}: ordering={row.get('continuous_dispersion_ordering_coverage')} "
            f"scale={row.get('scale_stability')} score={row.get('continuous_score')}"
        )
    lines += ["", "## Candidates", ""]
    for cid, row in dict(grid.get("candidates") or {}).items():
        lines.append(
            f"- {cid}: {row.get('status')} eligible_points={row.get('n_eligible')}/{row.get('n_points')}"
        )
    lines.append("")
    return "\n".join(lines)


def validate_phase3g_lock(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append(f"bad schema: {doc.get('schema')!r}")
    if doc.get("paid_api") is not False:
        errs.append("paid_api must be false")
    if doc.get("routing_connected") is not False:
        errs.append("must not connect routing")
    if doc.get("rule_policy_changed") is not False:
        errs.append("must not change RulePolicy")
    if doc.get("v1_sensor_changed") is not False:
        errs.append("must not change v1")
    if doc.get("evaluation_holdout_used") is not False:
        errs.append("must not use Phase 2 holdout")
    if doc.get("evaluation_outcomes_open") is not False:
        errs.append("must not open evaluation")
    if doc.get("operator_map_selected") is not False:
        errs.append("must not select M1/M2")
    if doc.get("selected_operator_map") is not None:
        errs.append("operator map must remain unset")
    if doc.get("high_bin_mapped_to_operator") is not False:
        errs.append("must not map high bin to an operator")
    if doc.get("freeze_revision") != PHASE3F_REVISION:
        errs.append("must use Phase 3F v0.3")
    if doc.get("verdict") not in VERDICTS:
        errs.append(f"bad verdict: {doc.get('verdict')!r}")
    if doc.get("verdict") == VERDICT_LOCKED:
        if doc.get("selected_candidate") not in CANDIDATES:
            errs.append("LOCKED requires one of A/B/C")
        if not isinstance(doc.get("selected_thresholds"), Mapping):
            errs.append("LOCKED requires thresholds")
    c_metrics = dict(dict(doc.get("pre_threshold_metrics") or {}).get("C_raw_and_norm") or {})
    if c_metrics.get("continuous_score") is not None:
        errs.append("Candidate C must not have a scalar score")
    if c_metrics.get("weighted_sum") is not False:
        errs.append("Candidate C must not use a weighted sum")
    blob = json.dumps(doc)
    if "operator_sequence" in blob or "T_profiler" in blob:
        errs.append("routing/profiler outcome leaked")
    return errs


def validate_phase3g_measurements(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    rows = list(doc.get("rows") or [])
    if len(rows) != N_TOTAL:
        errs.append(f"expected {N_TOTAL} rows")
    for row in rows:
        if row.get("replica") not in CALIBRATION_REPLICAS:
            errs.append(f"eval replica leaked: {row.get('surface_id')}")
        if row.get("split") != "calibration":
            errs.append(f"non-calibration row: {row.get('surface_id')}")
        sid = str(row.get("surface_id") or "")
        if "-r2-" in sid or "-r3-" in sid or sid.endswith(("-r2", "-r3")):
            errs.append(f"evaluation surface id: {sid}")
    diag = dict(doc.get("sensor_diagnostics") or {})
    if diag.get("used_in_threshold_grid_objective") is not False:
        errs.append("edge FP must not drive the grid")
    if diag.get("sensor_revised") is not False:
        errs.append("must not revise the sensor")
    if doc.get("evaluation_outcomes_open") is not False:
        errs.append("evaluation must stay sealed")
    return errs


def write_artifacts(
    measurements: Mapping[str, Any] | None = None,
    grid: Mapping[str, Any] | None = None,
    lock: Mapping[str, Any] | None = None,
) -> tuple[Path, Path, Path, Path]:
    if measurements is None or grid is None or lock is None:
        measurements, grid, lock = run_calibration()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    MEASURE_PATH.write_text(
        json.dumps(measurements, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    GRID_PATH.write_text(json.dumps(grid, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    LOCK_PATH.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    LOCK_MD_PATH.write_text(render_lock_md(lock, grid), encoding="utf-8")
    return MEASURE_PATH, GRID_PATH, LOCK_PATH, LOCK_MD_PATH


if __name__ == "__main__":
    write_artifacts()
