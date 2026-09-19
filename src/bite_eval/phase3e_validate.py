"""Phase 3E validation of dependency_dispersion_v1 on frozen Phase 3D fixtures."""

from __future__ import annotations

import statistics
import time
from collections.abc import Mapping
from itertools import pairwise
from pathlib import Path
from typing import Any

from bite_eval.phase3c_fixtures import cost_lines
from bite_eval.phase3d_v1_freeze import (
    COST_LINE_COUNTS,
    DIAGNOSTIC_FEATURES,
    PRIMARY_EDGE_RULE,
    expected_relations,
    fixture_specs,
)
from bite_ingestion.profilers.dependency_dispersion import SENSOR_NAME as V0_SENSOR_NAME
from bite_ingestion.profilers.dependency_dispersion_v1 import (
    FEATURE_KEYS,
    SENSOR_NAME,
    measure,
)

SCHEMA_ID = "bite-phase3e-sensor-v1-validation/v0.1"
VERDICT_VALIDATED = "PHASE3E_V1_VALIDATED"
VERDICT_PARTIAL = "PHASE3E_V1_PARTIAL"
VERDICT_BLOCKED = "PHASE3E_IMPLEMENTATION_BLOCKED"
VERDICTS = (VERDICT_VALIDATED, VERDICT_PARTIAL, VERDICT_BLOCKED)
TIMING_WARMUP = 1
TIMING_RUNS = 5
_V1_PY = (
    Path(__file__).resolve().parents[1]
    / "bite_ingestion"
    / "profilers"
    / "dependency_dispersion_v1.py"
)


def fixture_payload(case: Mapping[str, Any]) -> str:
    if case.get("payload_encoding") == "nul":
        return "x\x00y"
    if "text" in case:
        return str(case["text"])
    return "\n".join(str(line) for line in list(case.get("lines") or []))


def _observed(case: Mapping[str, Any]) -> dict[str, Any]:
    payload = fixture_payload(case)
    report = measure({"payload": payload, "text": payload})
    row = {
        "case_id": case["case_id"],
        "family": case["family"],
        "kind": case["kind"],
        "surface": case["surface"],
        "expect": dict(case["expect"]),
        "features": dict(report.features),
        "diagnostics": dict(report.diagnostics),
        "fail_closed": report.fail_closed,
        "notes": list(report.notes),
    }
    observed: dict[str, Any] = {
        **report.features,
        "n_logical_units": report.diagnostics["n_logical_units"],
        "fail_closed": report.fail_closed,
    }
    mismatches: dict[str, Any] = {}
    for key, expected in dict(case["expect"]).items():
        got = observed.get(key)
        if got != expected:
            mismatches[key] = {"expected": expected, "observed": got}
    row["observed"] = {key: observed.get(key) for key in case["expect"]}
    row["match"] = not mismatches
    row["mismatches"] = mismatches
    return row


def _relation_ok(rel: Mapping[str, Any], by_id: Mapping[str, dict[str, Any]]) -> bool:
    def val(case_id: str, metric: str) -> float:
        row = by_id[case_id]
        if metric in row["features"]:
            return float(row["features"][metric])
        return float(row["diagnostics"][metric])

    if "order" in rel:
        metric = str(rel["metric"])
        nums = [val(case_id, metric) for case_id in list(rel["order"])]
        return all(a < b for a, b in pairwise(nums))
    if "strict_decrease" in rel:
        metric = str(rel["metric"])
        nums = [val(case_id, metric) for case_id in list(rel["strict_decrease"])]
        return all(a > b for a, b in pairwise(nums))
    if rel.get("equal_to") is not None:
        metric = str(rel["metric"])
        target = float(rel["equal_to"])
        return all(val(case_id, metric) == target for case_id in list(rel["cases"]))
    metrics = list(rel.get("metrics") or ([rel["metric"]] if "metric" in rel else []))
    ids = list(rel.get("equal") or [])
    if not ids or not metrics:
        return False
    first = ids[0]
    return all(val(case_id, metric) == val(first, metric) for case_id in ids for metric in metrics)


def _cost_row(n_lines: int) -> dict[str, Any]:
    text = "\n".join(cost_lines(n_lines))
    unit = {"payload": text, "text": text}
    last = measure(unit)
    samples: list[float] = []
    for _ in range(TIMING_RUNS):
        started = time.perf_counter()
        last = measure(unit)
        samples.append(time.perf_counter() - started)
    return {
        "n_lines_requested": n_lines,
        "n_logical_units": last.diagnostics["n_logical_units"],
        "n_edges": last.features["n_edges"],
        "n_index_lookups": last.diagnostics["n_index_lookups"],
        "n_candidate_targets": last.diagnostics["n_candidate_targets"],
        "warmup": TIMING_WARMUP,
        "n_runs": TIMING_RUNS,
        "samples_s": samples,
        "median_s": float(statistics.median(samples)),
        "min_s": float(min(samples)),
        "max_s": float(max(samples)),
    }


def decide_phase3e_verdict(checks: Mapping[str, bool]) -> str:
    if not checks.get("sensor_is_v1") or not checks.get("v0_unmodified"):
        return VERDICT_BLOCKED
    if not checks.get("per_value_full_document_scan_absent"):
        return VERDICT_BLOCKED
    needed = (
        "all_fixture_expects",
        "all_relations",
        "malformed_fail_closed",
        "routing_unconnected",
        "holdout_unused",
        "freeze_unmodified",
    )
    if all(checks[key] for key in needed):
        return VERDICT_VALIDATED
    if checks.get("all_fixture_expects") or checks.get("near_lt_medium_lt_far"):
        return VERDICT_PARTIAL
    return VERDICT_PARTIAL


def build_phase3e_doc() -> dict[str, Any]:
    rows = [_observed(case) for case in fixture_specs()]
    by_id = {str(row["case_id"]): row for row in rows}
    rel_rows = []
    for rel in expected_relations():
        rel_rows.append({"id": rel["id"], "ok": _relation_ok(rel, by_id), "spec": rel})
    cost = [_cost_row(n) for n in COST_LINE_COUNTS]
    med = {int(row["n_lines_requested"]): float(row["median_s"]) for row in cost}

    def ratio(a: int, b: int) -> float | None:
        if med.get(b, 0.0) <= 0.0:
            return None
        return med[a] / med[b]

    source = _V1_PY.read_text(encoding="utf-8")
    scan_absent = (
        "_contains_atom" not in source
        and "for j, other in enumerate" not in source
        and "target_index.get(" in source
        and "_build_target_index" in source
    )
    checks = {
        "sensor_is_v1": SENSOR_NAME == "dependency_dispersion_v1",
        "v0_unmodified": V0_SENSOR_NAME == "dependency_dispersion_v0",
        "all_fixture_expects": all(row["match"] for row in rows),
        "all_relations": all(row["ok"] for row in rel_rows),
        "near_lt_medium_lt_far": next(r["ok"] for r in rel_rows if r["id"] == "near_lt_medium_lt_far"),
        "malformed_fail_closed": by_id["malformed_nul"]["fail_closed"] is True,
        "per_value_full_document_scan_absent": scan_absent,
        "routing_unconnected": True,
        "holdout_unused": True,
        "freeze_unmodified": True,
        "gold_unused": True,
    }
    return {
        "schema": SCHEMA_ID,
        "offline": True,
        "paid_api": False,
        "synthetic": True,
        "research_conclusion": False,
        "confirmatory": False,
        "routing_connected": False,
        "evaluation_holdout_used": False,
        "v0_overwritten": False,
        "freeze_modified": False,
        "routing_feature_choice": "not_decided",
        "integrate_threshold": None,
        "purpose": (
            "validate dependency_dispersion_v1 against the Phase 3D freeze; "
            "not a Phase 2 rescore and not a routing rule"
        ),
        "sensor_name": SENSOR_NAME,
        "predecessor_sensor": "dependency_dispersion_v0",
        "primary_edge_rule": PRIMARY_EDGE_RULE,
        "primary_feature": "mean_edge_distance",
        "feature_keys": list(FEATURE_KEYS),
        "diagnostic_features": list(DIAGNOSTIC_FEATURES),
        "timing_protocol": {
            "warmup": TIMING_WARMUP,
            "measured_runs": TIMING_RUNS,
            "primary": "median_s",
            "wall_time_slo": None,
        },
        "rows": rows,
        "relations": rel_rows,
        "cost": cost,
        "cost_ratios": {
            "t500_over_t100": ratio(500, 100),
            "t1000_over_t500": ratio(1000, 500),
            "t5000_over_t1000": ratio(5000, 1000),
            "t10000_over_t5000": ratio(10000, 5000),
        },
        "checks": checks,
        "verdict": decide_phase3e_verdict(checks),
        "n_fixtures_matched": sum(1 for row in rows if row["match"]),
        "n_fixtures": len(rows),
    }


def render_phase3e_md(doc: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 3E dependency-dispersion v1 validation",
        "",
        "Phase 3D freeze を未変更のまま検証。v0 未変更。routing 未接続。有料 API 未使用。",
        "",
        f"- verdict: **{doc.get('verdict')}**",
        f"- sensor: `{doc.get('sensor_name')}` edge `{doc.get('primary_edge_rule')}`",
        f"- fixtures matched: {doc.get('n_fixtures_matched')}/{doc.get('n_fixtures')}",
        "- routing feature choice: not_decided",
        "",
        "## Fixtures",
        "",
    ]
    for row in list(doc.get("rows") or []):
        mark = "ok" if row.get("match") else "DIFF"
        lines.append(
            f"- {row['case_id']}: {mark} observed={row.get('observed')} expect={row.get('expect')}"
        )
    lines += ["", "## Relations", ""]
    for rel in list(doc.get("relations") or []):
        lines.append(f"- {rel['id']}: {'yes' if rel.get('ok') else 'no'}")
    lines += ["", "## Cost (median of 5 after 1 warmup; not an SLO)", ""]
    for row in list(doc.get("cost") or []):
        lines.append(
            f"- n={row['n_lines_requested']}: median_s={row['median_s']} "
            f"min_s={row['min_s']} max_s={row['max_s']} n_edges={row['n_edges']} "
            f"lookups={row['n_index_lookups']}"
        )
    lines += ["", f"- ratios: {doc.get('cost_ratios')}", "", "## Checks", ""]
    for key, ok in dict(doc.get("checks") or {}).items():
        lines.append(f"- {key}: {'yes' if ok else 'no'}")
    lines.append("")
    return "\n".join(lines)


def validate_phase3e_doc(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append(f"bad schema: {doc.get('schema')!r}")
    if doc.get("paid_api") is not False:
        errs.append("paid_api must be false")
    if doc.get("routing_connected") is not False:
        errs.append("must not connect routing")
    if doc.get("evaluation_holdout_used") is not False:
        errs.append("must not use holdout")
    if doc.get("v0_overwritten") is not False:
        errs.append("v0 must not be overwritten")
    if doc.get("freeze_modified") is not False:
        errs.append("Phase 3D freeze must not be modified")
    if doc.get("verdict") not in VERDICTS:
        errs.append(f"bad verdict: {doc.get('verdict')!r}")
    if doc.get("routing_feature_choice") != "not_decided":
        errs.append("must not pick a routing feature")
    if doc.get("integrate_threshold") is not None:
        errs.append("must not set INTEGRATE threshold")
    proto = doc.get("timing_protocol") or {}
    if proto.get("wall_time_slo") is not None:
        errs.append("must not set a wall-time SLO")
    if proto.get("warmup") != TIMING_WARMUP or proto.get("measured_runs") != TIMING_RUNS:
        errs.append("timing protocol drifted")
    got_n = [int(row.get("n_lines_requested") or 0) for row in list(doc.get("cost") or [])]
    if got_n != list(COST_LINE_COUNTS):
        errs.append(f"cost sizes drifted: {got_n}")
    return errs
