"""Phase 3J gold-free texture observability audit (J1).

Measures existing features only. Does not change deterministic_v0 or routing.
Does not open p3f evaluation.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bite_bench.phase3j import (
    FORMATS,
    GENERATION,
    LOCKED_CANDIDATE,
    LOCKED_FEATURE,
    LOCKED_T_HIGH,
    LOCKED_T_LOW,
    MAP_VERDICTS,
    N_SURFACES,
    PROFILER_FEATURES,
    PROTOCOL_FROZEN,
    REPLICAS,
    REVISION,
    VERDICT_BLOCKED,
    VERDICT_REVISION,
    VERDICT_SUFFICIENT,
    bin_univariate,
    design_surfaces,
    freeze_manifest,
    profiler_source_unit,
    refuse_p3f_evaluation,
)
from bite_ingestion.profilers.dependency_dispersion_v1 import measure
from bite_ingestion.profilers.deterministic import DeterministicMorphologyProfiler

SCHEMA_ID = "bite-phase3j-texture-observability/v0.1"
PROTOCOL_COMMIT_SHA = "0cc696632e7bb7a01ea99d5141540f5dcd7088a8"
FORBIDDEN_PROFILER_KEYS = (
    "gold",
    "gold_evidence_ids",
    "texture",
    "operator",
    "route",
    "answer",
    "query",
)
_REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = _REPO / "artifacts" / "phase3j"
RESULT_PATH = ARTIFACT_DIR / "texture-observability.json"
RESULT_MD_PATH = ARTIFACT_DIR / "texture-observability.md"
PHASE3H_PATH = _REPO / "artifacts" / "phase3h" / "operator-map-experiment.json"
PHASE3I_PATH = _REPO / "artifacts" / "phase3i" / "composite-provenance.json"
V0_PY = _REPO / "src" / "bite_ingestion" / "profilers" / "deterministic.py"


def _row_value(
    rows: Sequence[Mapping[str, Any]], texture: str, replica: int, fmt: str, key: str
) -> float:
    for row in rows:
        if row["texture"] == texture and row["replica"] == replica and row["format"] == fmt:
            return float(row["features"][key])
    raise KeyError(f"missing {texture} r{replica} {fmt}")


def _format_holds(
    rows: Sequence[Mapping[str, Any]],
    *,
    feature: str,
    left: str,
    rights: tuple[str, ...],
    fmt: str,
) -> bool:
    return all(
        all(
            _row_value(rows, left, replica, fmt, feature)
            > _row_value(rows, right, replica, fmt, feature)
            for right in rights
        )
        for replica in REPLICAS
    )


def _axis(
    rows: Sequence[Mapping[str, Any]],
    *,
    name: str,
    feature: str,
    left: str,
    rights: tuple[str, ...],
) -> dict[str, Any]:
    per_format = {
        fmt: _format_holds(rows, feature=feature, left=left, rights=rights, fmt=fmt)
        for fmt in FORMATS
    }
    values = list(per_format.values())
    return {
        "axis": name,
        "feature": feature,
        "per_format": per_format,
        "observed_all_formats": all(values),
        "format_stable": len(set(values)) == 1,
        "ok": all(values),
    }


def measure_surface(surface: Mapping[str, Any]) -> dict[str, Any]:
    refuse_p3f_evaluation(str(surface["case_id"]))
    src = profiler_source_unit(str(surface["payload"]))
    leaked = [key for key in FORBIDDEN_PROFILER_KEYS if key in src]
    if leaked:
        raise RuntimeError(f"profiler input leaked {leaked}")
    v0 = DeterministicMorphologyProfiler().profile_report(src)
    v1 = measure(src)
    value = float(v1.features[LOCKED_FEATURE])
    label = bin_univariate(value)
    return {
        "surface_id": surface["surface_id"],
        "case_id": surface["case_id"],
        "generation": GENERATION,
        "split": surface["split"],
        "texture": surface["texture"],
        "replica": surface["replica"],
        "format": surface["format"],
        "features": {key: float(v0.features[key]) for key in PROFILER_FEATURES},
        "mean_edge_distance": value,
        "bin": label,
        "v0_fail_closed": v0.fail_closed,
        "v1_fail_closed": v1.fail_closed,
        "high": label == "high" and not v1.fail_closed,
    }


def _premise_errors() -> list[str]:
    errs: list[str] = []
    freeze = freeze_manifest()
    if freeze.get("verdict") != PROTOCOL_FROZEN:
        errs.append("J0 freeze drifted")
    if freeze.get("revision") != REVISION:
        errs.append("J0 revision drifted")
    if not PHASE3H_PATH.is_file() or not PHASE3I_PATH.is_file():
        errs.append("prior artifacts missing")
        return errs
    phase3h = json.loads(PHASE3H_PATH.read_text(encoding="utf-8"))
    phase3i = json.loads(PHASE3I_PATH.read_text(encoding="utf-8"))
    if phase3h.get("verdict") != "PHASE3H_CONDITIONAL_MAP_REQUIRED":
        errs.append("Phase 3H verdict rewritten")
    if phase3i.get("verdict") != "PHASE3I_COMPOSITE_PROVENANCE_VALIDATED":
        errs.append("Phase 3I verdict rewritten")
    if not V0_PY.is_file():
        errs.append("deterministic_v0 missing")
    return errs


def run_audit() -> dict[str, Any]:
    blocked = _premise_errors()
    surfaces = design_surfaces()
    rows: list[dict[str, Any]] = []
    try:
        for surface in surfaces:
            rows.append(measure_surface(surface))
    except Exception as exc:  # noqa: BLE001
        blocked.append(str(exc))
    if len(rows) != N_SURFACES:
        blocked.append(f"expected {N_SURFACES} rows, got {len(rows)}")
    high_ok = bool(rows) and all(row["high"] for row in rows)
    if not high_ok:
        blocked.append("high bin not confirmed on every p3j surface")
    if any(row.get("v0_fail_closed") for row in rows):
        blocked.append("deterministic_v0 fail-closed")
    blob = json.dumps(rows, sort_keys=True)
    if "p3f-" in blob:
        blocked.append("p3f identifier leaked")

    axes = []
    if rows and not blocked:
        axes = [
            _axis(
                rows,
                name="redundancy",
                feature="r",
                left="redundant",
                rights=("neutral", "unique_reference"),
            ),
            _axis(rows, name="anomaly", feature="a", left="anomalous", rights=("neutral",)),
            _axis(
                rows,
                name="reference",
                feature="k",
                left="unique_reference",
                rights=("neutral",),
            ),
        ]
    if blocked:
        verdict = VERDICT_BLOCKED
    elif axes and all(axis["ok"] for axis in axes):
        verdict = VERDICT_SUFFICIENT
    else:
        verdict = VERDICT_REVISION
    if verdict not in MAP_VERDICTS:
        verdict = VERDICT_BLOCKED
        blocked.append("verdict not in frozen set")
    return {
        "schema": SCHEMA_ID,
        "revision": "phase3j-texture-observability-v0.1",
        "protocol_revision": REVISION,
        "protocol_commit_sha": PROTOCOL_COMMIT_SHA,
        "verdict": verdict,
        "blocked_reasons": blocked,
        "paid_api": False,
        "offline": True,
        "synthetic": True,
        "research_conclusion": False,
        "p3f_evaluation_holdout_used": False,
        "phase3h_verdict_unchanged": "PHASE3H_CONDITIONAL_MAP_REQUIRED",
        "phase3i_verdict_unchanged": "PHASE3I_COMPOSITE_PROVENANCE_VALIDATED",
        "locked_candidate": LOCKED_CANDIDATE,
        "locked_thresholds": {"T_low": LOCKED_T_LOW, "T_high": LOCKED_T_HIGH},
        "v1_sensor_changed": False,
        "profiler_changed": False,
        "rule_policy_changed": False,
        "rule_policy_executed": False,
        "routing_connected": False,
        "no_new_absolute_threshold": True,
        "high_confirmed": high_ok,
        "n_surfaces": len(rows),
        "axes": axes,
        "rows": rows,
    }


def validate_phase3j_result(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("protocol_commit_sha") != PROTOCOL_COMMIT_SHA:
        errs.append("protocol commit SHA mismatch")
    if doc.get("verdict") not in MAP_VERDICTS:
        errs.append("verdict not in frozen set")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation opened")
    if doc.get("rule_policy_executed") is not False:
        errs.append("routing executed")
    if doc.get("profiler_changed") is not False:
        errs.append("profiler changed")
    if doc.get("no_new_absolute_threshold") is not True:
        errs.append("absolute threshold added")
    if doc.get("locked_candidate") != LOCKED_CANDIDATE:
        errs.append("candidate A changed")
    blob = json.dumps(doc, sort_keys=True)
    if "p3f-" in blob:
        errs.append("p3f identifier leaked")
    for row in doc.get("rows") or []:
        if not str(row.get("surface_id", "")).startswith("p3j-"):
            errs.append(f"non-p3j surface {row.get('surface_id')}")
        if row.get("split") != "development":
            errs.append("non-development row")
    return errs


def render_md(doc: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 3J texture observability",
        "",
        f"verdict: `{doc.get('verdict')}`",
        f"protocol SHA: `{doc.get('protocol_commit_sha')}`",
        f"high confirmed: `{doc.get('high_confirmed')}`",
        "routing executed: `false`",
        "profiler changed: `false`",
        "",
        "## Contrast",
        "",
        "| axis | feature | observed all formats | format stable | ok |",
        "|---|---|---|---|---|",
    ]
    for axis in doc.get("axes") or []:
        lines.append(
            f"| {axis.get('axis')} | {axis.get('feature')} | "
            f"{axis.get('observed_all_formats')} | {axis.get('format_stable')} | "
            f"{axis.get('ok')} |"
        )
    lines.extend(["", "## Format direction", "", "| axis | key_value | compact_json | pretty_json |", "|---|---|---|---|"])
    for axis in doc.get("axes") or []:
        per = dict(axis.get("per_format") or {})
        lines.append(
            f"| {axis.get('axis')} | {per.get('key_value')} | "
            f"{per.get('compact_json')} | {per.get('pretty_json')} |"
        )
    lines.extend(["", "BITE wins / Go ではない。", ""])
    reasons = list(doc.get("blocked_reasons") or [])
    if reasons:
        lines.append("blocked:")
        lines.extend(f"- {reason}" for reason in reasons)
        lines.append("")
    return "\n".join(lines)


def write_artifacts(doc: Mapping[str, Any] | None = None) -> tuple[Path, Path]:
    if doc is None:
        doc = run_audit()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    RESULT_MD_PATH.write_text(render_md(doc), encoding="utf-8")
    return RESULT_PATH, RESULT_MD_PATH


if __name__ == "__main__":
    write_artifacts()
