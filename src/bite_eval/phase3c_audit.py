"""Phase 3C generalization audit of dependency_dispersion_v0.

New development fixtures only. Does not change the sensor. No routing. No holdout.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from itertools import pairwise
from typing import Any

from bite_eval.phase3c_fixtures import (
    ABS_EDGE_DISTANCE,
    ABS_TAILS,
    COST_LINE_COUNTS,
    DIAGNOSTIC_FEATURES,
    EXPECTED_FORMAT_STATUS,
    QUANTITY_MEANING,
    REL_N_LINES,
    abs_scale_lines,
    cost_lines,
    false_positive_docs,
    format_docs,
    predeclared_expectations,
    rel_scale_lines,
)
from bite_ingestion.profilers.dependency_dispersion import (
    PRIMARY_FEATURE,
    SENSOR_NAME,
    measure,
)

SCHEMA_ID = "bite-phase3c-sensor-generalization/v0.1"
VERDICT_GENERALIZES = "PHASE3C_SENSOR_GENERALIZES"
VERDICT_SCOPED = "PHASE3C_SENSOR_SCOPED"
VERDICT_REVISE = "PHASE3C_SENSOR_REVISE"
VERDICTS = (VERDICT_GENERALIZES, VERDICT_SCOPED, VERDICT_REVISE)


def _snap(text: str) -> dict[str, Any]:
    report = measure({"payload": text, "text": text})
    feats = report.features
    return {
        "n_lines": int(report.evidence["n_lines"]),
        "n_edges": feats["n_edges"],
        **{key: feats[key] for key in DIAGNOSTIC_FEATURES},
        "notes": list(report.notes),
    }


def _status_from_edges(n_edges: float) -> str:
    return "supported" if n_edges > 0.0 else "unsupported"


def _format_rows() -> list[dict[str, Any]]:
    rows = []
    for name, text in format_docs().items():
        snap = _snap(text)
        observed = _status_from_edges(float(snap["n_edges"]))
        rows.append(
            {
                "format": name,
                "predeclared": EXPECTED_FORMAT_STATUS[name],
                "observed": observed,
                "match": observed == EXPECTED_FORMAT_STATUS[name],
                **snap,
            }
        )
    return rows


def _fp_rows() -> list[dict[str, Any]]:
    rows = []
    for name, text in false_positive_docs().items():
        snap = _snap(text)
        rows.append({"case_id": name, **snap})
    return rows


def _cost_rows() -> list[dict[str, Any]]:
    rows = []
    for n in COST_LINE_COUNTS:
        text = "\n".join(cost_lines(n))
        started = time.perf_counter()
        snap = _snap(text)
        elapsed = time.perf_counter() - started
        rows.append(
            {
                "n_lines_requested": n,
                "wall_time_s": elapsed,
                **snap,
            }
        )
    return rows


def _scale_abs_rows() -> list[dict[str, Any]]:
    rows = []
    for label, tail in ABS_TAILS:
        snap = _snap("\n".join(abs_scale_lines(tail)))
        rows.append({"case_id": f"abs_{label}", "tail": tail, **snap})
    return rows


def _scale_rel_rows() -> list[dict[str, Any]]:
    rows = []
    for n in REL_N_LINES:
        snap = _snap("\n".join(rel_scale_lines(n)))
        rows.append({"case_id": f"rel_{n}", **snap})
    return rows


def _strict_decrease(vals: list[float]) -> bool:
    return all(a > b for a, b in pairwise(vals))


def _strict_increase(vals: list[float]) -> bool:
    return all(a < b for a, b in pairwise(vals))


def _equal(vals: list[float]) -> bool:
    return len(set(vals)) == 1


def decide_phase3c_verdict(checks: Mapping[str, bool]) -> str:
    contract = (
        "abs_raw_equal",
        "abs_norm_decreases",
        "rel_raw_increases",
        "rel_norm_equal",
        "kv_supported",
        "oneline_json_supported",
        "sensor_unrevised",
        "format_status_matches_predeclaration",
    )
    if not all(checks[key] for key in contract):
        return VERDICT_REVISE
    limits = (
        "cooccurrence_creates_edges",
        "shared_label_pollutes_mean",
        "blank_inflates_raw",
        "pretty_json_unsupported",
        "csv_unsupported",
        "yaml_unsupported",
        "prose_unsupported",
        "compact_single_line_no_cross_line_edge",
        "cannot_distinguish_reference_from_cooccurrence",
    )
    if any(checks[key] for key in limits):
        return VERDICT_SCOPED
    return VERDICT_GENERALIZES


def build_phase3c_doc() -> dict[str, Any]:
    abs_rows = _scale_abs_rows()
    rel_rows = _scale_rel_rows()
    fmt_rows = _format_rows()
    fp_rows = _fp_rows()
    cost_rows = _cost_rows()
    by_fmt = {row["format"]: row for row in fmt_rows}
    by_fp = {row["case_id"]: row for row in fp_rows}
    kv_raw = float(by_fmt["key_value"]["mean_edge_distance"])
    blank_raw = float(by_fmt["blank_lines"]["mean_edge_distance"])
    pollute = by_fp["true_edge_plus_shared_label"]
    co_edges = [
        by_fp[key]["n_edges"] > 0.0
        for key in (
            "shared_env",
            "shared_service",
            "shared_owner",
            "shared_category",
            "unrelated_records_same_identifier",
        )
    ]
    abs_raw = [float(row["mean_edge_distance"]) for row in abs_rows]
    abs_norm = [float(row["mean_edge_distance_norm"]) for row in abs_rows]
    rel_raw = [float(row["mean_edge_distance"]) for row in rel_rows]
    rel_norm = [float(row["mean_edge_distance_norm"]) for row in rel_rows]
    fmt_match = all(row["match"] for row in fmt_rows)
    t_by_n = {int(row["n_lines_requested"]): float(row["wall_time_s"]) for row in cost_rows}
    ratio_5000_1000 = (
        t_by_n[5000] / t_by_n[1000] if t_by_n.get(1000, 0.0) > 0.0 else None
    )
    checks = {
        "abs_raw_equal": _equal(abs_raw) and abs_raw[0] == float(ABS_EDGE_DISTANCE),
        "abs_norm_decreases": _strict_decrease(abs_norm),
        "rel_raw_increases": _strict_increase(rel_raw),
        "rel_norm_equal": _equal(rel_norm) and rel_norm[0] == 1.0,
        "kv_supported": by_fmt["key_value"]["observed"] == "supported",
        "oneline_json_supported": by_fmt["oneline_json"]["observed"] == "supported",
        "pretty_json_unsupported": by_fmt["pretty_json"]["observed"] == "unsupported",
        "csv_unsupported": by_fmt["csv"]["observed"] == "unsupported",
        "yaml_unsupported": by_fmt["yaml"]["observed"] == "unsupported",
        "prose_unsupported": by_fmt["prose"]["observed"] == "unsupported",
        "compact_single_line_no_cross_line_edge": (
            by_fmt["compact_json_one_line"]["n_edges"] == 0.0
        ),
        "blank_inflates_raw": blank_raw > kv_raw,
        "cooccurrence_creates_edges": all(co_edges),
        "shared_label_pollutes_mean": (
            float(pollute["mean_edge_distance"]) > 1.0
            and float(pollute["n_edges"]) > 1.0
        ),
        "cannot_distinguish_reference_from_cooccurrence": all(co_edges),
        "format_status_matches_predeclaration": fmt_match,
        "sensor_unrevised": True,
        "holdout_unused": True,
        "routing_unconnected": True,
    }
    verdict = decide_phase3c_verdict(checks)
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
        "sensor_behavior_changed": False,
        "sensor_revision": None,
        "routing_feature_choice": "not_decided",
        "purpose": (
            "development-fixture audit of how dependency_dispersion_v0 moves under "
            "scale, line granularity, identifier co-occurrence, format, and cost; "
            "not a Phase 2 rescore and not a routing rule"
        ),
        "sensor_name": SENSOR_NAME,
        "primary_feature": PRIMARY_FEATURE,
        "diagnostic_features": list(DIAGNOSTIC_FEATURES),
        "predeclared": predeclared_expectations(),
        "quantity_meaning": dict(QUANTITY_MEANING),
        "scale_abs": abs_rows,
        "scale_rel": rel_rows,
        "formats": fmt_rows,
        "false_positives": fp_rows,
        "cost": cost_rows,
        "cost_note": (
            "wall times are machine-local; no performance SLO. "
            "v0 scans other lines per value atom."
        ),
        "cost_time_ratio_5000_over_1000": ratio_5000_1000,
        "cost_linear_ratio_5000_over_1000": 5.0,
        "cost_quadratic_ratio_5000_over_1000": 25.0,
        "checks": checks,
        "verdict": verdict,
        "limits": [
            "raw mean_edge_distance is absolute line-index separation",
            "mean_edge_distance_norm is that quantity divided by (n_lines-1)",
            "pretty JSON / CSV / YAML / prose are outside the v0 extractor",
            "blank lines and wrapping change line-index distances",
            "shared env/service/owner/label identifiers become edges",
            "reference vs mere co-occurrence is not distinguished",
        ],
    }


def render_phase3c_md(doc: Mapping[str, Any]) -> str:
    checks = dict(doc.get("checks") or {})
    lines = [
        "# Phase 3C dependency-dispersion sensor generalization",
        "",
        "development fixtures only。Phase 2 evaluation は未使用。routing 未接続。",
        "dependency_dispersion_v0 は未変更。有料 API 未使用。",
        "",
        f"- verdict: **{doc.get('verdict')}**",
        f"- sensor: `{doc.get('sensor_name')}` primary `{doc.get('primary_feature')}`",
        "- routing feature choice: not_decided",
        "",
        "## Quantity meaning",
        "",
        "- `mean_edge_distance`: absolute dependency separation (line-index gap)",
        "- `mean_edge_distance_norm`: relative dependency separation (gap / (n_lines-1))",
        "- routing にどちらを使うかは未決定",
        "",
        "## Scale",
        "",
    ]
    for row in list(doc.get("scale_abs") or []):
        lines.append(
            f"- {row['case_id']}: n_lines={row['n_lines']} "
            f"raw={row['mean_edge_distance']} norm={row['mean_edge_distance_norm']}"
        )
    lines.append("")
    for row in list(doc.get("scale_rel") or []):
        lines.append(
            f"- {row['case_id']}: n_lines={row['n_lines']} "
            f"raw={row['mean_edge_distance']} norm={row['mean_edge_distance_norm']}"
        )
    lines += ["", "## Formats", ""]
    for row in list(doc.get("formats") or []):
        lines.append(
            f"- {row['format']}: predeclared={row['predeclared']} "
            f"observed={row['observed']} n_edges={row['n_edges']} "
            f"raw={row['mean_edge_distance']}"
        )
    lines += ["", "## False-positive co-occurrence", ""]
    for row in list(doc.get("false_positives") or []):
        lines.append(
            f"- {row['case_id']}: n_edges={row['n_edges']} "
            f"raw={row['mean_edge_distance']}"
        )
    lines += ["", "## Cost", ""]
    for row in list(doc.get("cost") or []):
        lines.append(
            f"- n={row['n_lines_requested']}: wall_time_s={row['wall_time_s']} "
            f"n_edges={row['n_edges']} n_lines={row['n_lines']}"
        )
    lines += [
        "",
        (
            f"- t5000/t1000={doc.get('cost_time_ratio_5000_over_1000')} "
            "(linear=5, quadratic=25; not an SLO)"
        ),
        "",
        "## Checks",
        "",
    ]
    for key, ok in checks.items():
        lines.append(f"- {key}: {'yes' if ok else 'no'}")
    lines += ["", "## Limits", ""]
    for item in list(doc.get("limits") or []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def validate_phase3c_doc(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("paid_api") is not False:
        errs.append("paid_api must be false")
    if doc.get("schema") != SCHEMA_ID:
        errs.append(f"bad schema: {doc.get('schema')!r}")
    if doc.get("routing_connected") is not False:
        errs.append("Phase 3C must not connect routing")
    if doc.get("evaluation_holdout_used") is not False:
        errs.append("Phase 2 evaluation must not be used")
    if doc.get("v0_overwritten") is not False:
        errs.append("v0 must not be overwritten")
    if doc.get("sensor_behavior_changed") is not False:
        errs.append("sensor behavior must not change silently")
    if doc.get("sensor_revision") is not None:
        errs.append("unexpected sensor revision")
    if doc.get("verdict") not in VERDICTS:
        errs.append(f"bad verdict: {doc.get('verdict')!r}")
    if doc.get("routing_feature_choice") != "not_decided":
        errs.append("must not pick a routing feature")
    if list(doc.get("diagnostic_features") or []) != list(DIAGNOSTIC_FEATURES):
        errs.append("diagnostic features drifted")
    cost = list(doc.get("cost") or [])
    got_n = [int(row.get("n_lines_requested") or 0) for row in cost]
    if got_n != list(COST_LINE_COUNTS):
        errs.append(f"cost sizes drifted: {got_n}")
    return errs
