"""Phase 3K calibration of structural_redundancy_v1 on frozen p3k fixtures.

Does not change deterministic_v0, v1, or routing. Does not open evaluation.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bite_bench.phase3k import (
    FORMATS,
    GENERATION,
    K1_VERDICTS,
    PRIMARY_FEATURE,
    PROTOCOL_FROZEN,
    REVISION,
    SENSOR_NAME,
    VERDICT_BLOCKED,
    VERDICT_PARTIAL,
    VERDICT_READY,
    development_surfaces,
    freeze_manifest,
    refuse_evaluation,
    sensor_source_unit,
)
from bite_ingestion.profilers.structural_redundancy_v1 import measure

SCHEMA_ID = "bite-phase3k-structural-redundancy/v0.1"
PROTOCOL_COMMIT_SHA = "526601b68a0eec9861b012ef5ddc67078447bf36"
COMPARE_KEYS = (
    "n_records",
    "n_unique_records",
    "n_duplicate_records",
    "duplicate_unit_ratio",
)
_REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = _REPO / "artifacts" / "phase3k"
RESULT_PATH = ARTIFACT_DIR / "structural-redundancy.json"
RESULT_MD_PATH = ARTIFACT_DIR / "structural-redundancy.md"
PHASE3J_PATH = _REPO / "artifacts" / "phase3j" / "texture-observability.json"
V0_PY = _REPO / "src" / "bite_ingestion" / "profilers" / "deterministic.py"
SENSOR_PY = _REPO / "src" / "bite_ingestion" / "profilers" / "structural_redundancy_v1.py"


def _observed(report: Any) -> dict[str, Any]:
    diag = dict(report.diagnostics)
    return {
        PRIMARY_FEATURE: float(report.features[PRIMARY_FEATURE]),
        "n_records": diag["n_records"],
        "n_unique_records": diag["n_unique_records"],
        "n_duplicate_records": diag["n_duplicate_records"],
        "max_multiplicity": diag["max_multiplicity"],
        "parsed_format": diag["parsed_format"],
        "fail_closed": report.fail_closed,
    }


def _mismatches(expect: Mapping[str, Any], observed: Mapping[str, Any]) -> dict[str, Any]:
    diff: dict[str, Any] = {}
    for key, expected in expect.items():
        got = observed.get(key)
        if got != expected:
            diff[key] = {"expected": expected, "observed": got}
    return diff


def _premise_errors() -> list[str]:
    errs: list[str] = []
    freeze = freeze_manifest()
    if freeze.get("verdict") != PROTOCOL_FROZEN:
        errs.append("K0 freeze drifted")
    if freeze.get("revision") != REVISION:
        errs.append("K0 revision drifted")
    if not PHASE3J_PATH.is_file():
        errs.append("Phase 3J artifact missing")
    else:
        phase3j = json.loads(PHASE3J_PATH.read_text(encoding="utf-8"))
        if phase3j.get("verdict") != "PHASE3J_TEXTURE_SENSOR_REVISION_REQUIRED":
            errs.append("Phase 3J verdict rewritten")
    v0 = V0_PY.read_text(encoding="utf-8")
    if 'FEATURE_KEYS = ("b", "r", "s", "k", "a", "l", "p", "u")' not in v0:
        errs.append("deterministic_v0 feature keys changed")
    if "dup_line_ratio" not in v0:
        errs.append("deterministic_v0.r formula missing")
    sensor = SENSOR_PY.read_text(encoding="utf-8")
    if "exact_dup_pairs" in sensor or "p3k-" in sensor or "p3j-" in sensor:
        errs.append("sensor hard-codes fixture identifiers")
    if "for i," in sensor and "for j," in sensor:
        errs.append("pairwise search present")
    return errs


def _measure_row(surface: Mapping[str, Any]) -> dict[str, Any]:
    refuse_evaluation(str(surface["case_id"]))
    src = sensor_source_unit(str(surface["payload"]))
    report = measure(src)
    observed = _observed(report)
    expect = dict(surface["expect"])
    mismatches = _mismatches(expect, observed)
    return {
        "case_id": surface["case_id"],
        "family": surface["family"],
        "replica": surface["replica"],
        "format": surface["format"],
        "split": surface["split"],
        "generation": GENERATION,
        "expect": expect,
        "observed": observed,
        "match": not mismatches,
        "mismatches": mismatches,
        "notes": list(report.notes),
    }


def _format_invariance(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in rows:
        if row["format"] == "contract":
            continue
        groups.setdefault((str(row["family"]), int(row["replica"])), []).append(row)
    out: list[dict[str, Any]] = []
    for (family, replica), items in groups.items():
        by_fmt = {str(item["format"]): item["observed"] for item in items}
        values = [
            tuple(by_fmt[fmt][key] for key in COMPARE_KEYS)
            for fmt in FORMATS
            if fmt in by_fmt
        ]
        ok = len(values) == len(FORMATS) and len(set(values)) == 1
        out.append(
            {
                "family": family,
                "replica": replica,
                "ok": ok,
                "per_format": {
                    fmt: {key: by_fmt[fmt][key] for key in COMPARE_KEYS}
                    for fmt in FORMATS
                    if fmt in by_fmt
                },
            }
        )
    return out


def _reorder_ok(rows: list[dict[str, Any]]) -> bool:
    by_id = {row["case_id"]: row for row in rows}
    for replica in (0, 1):
        for fmt in FORMATS:
            left = by_id[f"p3k-exact_dup_pairs-r{replica}-{fmt}"]["observed"]
            right = by_id[f"p3k-reordered_duplicates-r{replica}-{fmt}"]["observed"]
            if any(left[key] != right[key] for key in COMPARE_KEYS):
                return False
    return True


def run_validation() -> dict[str, Any]:
    blocked = _premise_errors()
    rows: list[dict[str, Any]] = []
    try:
        for surface in development_surfaces():
            rows.append(_measure_row(surface))
    except Exception as exc:  # noqa: BLE001
        blocked.append(str(exc))
    blob = json.dumps(rows, sort_keys=True)
    if "p3f-" in blob:
        blocked.append("p3f identifier leaked")
    if any("-r2-" in str(row.get("case_id")) or "-r3-" in str(row.get("case_id")) for row in rows):
        blocked.append("p3k evaluation opened")
    invariance = _format_invariance(rows) if rows else []
    family_ok = all(row["match"] for row in rows if row.get("format") != "contract")
    contract_ok = all(row["match"] for row in rows if row.get("format") == "contract")
    format_ok = bool(invariance) and all(item["ok"] for item in invariance)
    reorder_ok = bool(rows) and _reorder_ok(rows)
    checks = {
        "family_expects": family_ok,
        "contract_fail_closed": contract_ok,
        "format_invariance": format_ok,
        "reorder_invariance": reorder_ok,
        "evaluation_sealed": not any(
            "-r2-" in str(row.get("case_id")) or "-r3-" in str(row.get("case_id")) for row in rows
        ),
    }
    if blocked or not contract_ok:
        verdict = VERDICT_BLOCKED
    elif all(checks.values()):
        verdict = VERDICT_READY
    else:
        verdict = VERDICT_PARTIAL
    if verdict not in K1_VERDICTS:
        verdict = VERDICT_BLOCKED
        blocked.append("verdict not in frozen set")
    return {
        "schema": SCHEMA_ID,
        "revision": "phase3k-structural-redundancy-v0.1",
        "protocol_revision": REVISION,
        "protocol_commit_sha": PROTOCOL_COMMIT_SHA,
        "verdict": verdict,
        "blocked_reasons": blocked,
        "paid_api": False,
        "offline": True,
        "synthetic": True,
        "research_conclusion": False,
        "p3f_evaluation_holdout_used": False,
        "phase3j_verdict_unchanged": "PHASE3J_TEXTURE_SENSOR_REVISION_REQUIRED",
        "sensor_name": SENSOR_NAME,
        "primary_feature": PRIMARY_FEATURE,
        "v0_overwritten": False,
        "v1_unchanged": True,
        "a_unchanged": True,
        "k_unchanged": True,
        "no_threshold": True,
        "profiler_changed": False,
        "rule_policy_changed": False,
        "rule_policy_executed": False,
        "routing_connected": False,
        "n_rows": len(rows),
        "n_matched": sum(1 for row in rows if row["match"]),
        "checks": checks,
        "format_invariance": invariance,
        "rows": rows,
    }


def validate_phase3k_result(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("protocol_commit_sha") != PROTOCOL_COMMIT_SHA:
        errs.append("protocol commit SHA mismatch")
    if doc.get("verdict") not in K1_VERDICTS:
        errs.append("verdict not in frozen set")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation opened")
    if doc.get("rule_policy_executed") is not False:
        errs.append("routing executed")
    if doc.get("v0_overwritten") is not False:
        errs.append("deterministic_v0 overwritten")
    if doc.get("no_threshold") is not True:
        errs.append("threshold added")
    blob = json.dumps(doc, sort_keys=True)
    if "p3f-" in blob:
        errs.append("p3f identifier leaked")
    for row in doc.get("rows") or []:
        if not str(row.get("case_id", "")).startswith("p3k-"):
            errs.append(f"non-p3k case {row.get('case_id')}")
        if row.get("split") != "development":
            errs.append("non-development row")
    return errs


def render_md(doc: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 3K structural redundancy v1",
        "",
        f"verdict: `{doc.get('verdict')}`",
        f"protocol SHA: `{doc.get('protocol_commit_sha')}`",
        f"matched: {doc.get('n_matched')}/{doc.get('n_rows')}",
        "routing connected: `false`",
        "deterministic_v0 overwritten: `false`",
        "",
        "## Checks",
        "",
    ]
    for key, ok in dict(doc.get("checks") or {}).items():
        lines.append(f"- {key}: `{ok}`")
    lines.extend(["", "BITE wins / Go ではない。", ""])
    reasons = list(doc.get("blocked_reasons") or [])
    if reasons:
        lines.append("blocked:")
        lines.extend(f"- {reason}" for reason in reasons)
        lines.append("")
    return "\n".join(lines)


def write_artifacts(doc: Mapping[str, Any] | None = None) -> tuple[Path, Path]:
    if doc is None:
        doc = run_validation()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    RESULT_MD_PATH.write_text(render_md(doc), encoding="utf-8")
    return RESULT_PATH, RESULT_MD_PATH


if __name__ == "__main__":
    write_artifacts()
