"""Phase 3L first-open evaluation of structural_redundancy_v1 on p3k r2/r3.

Does not change the sensor, p3k split, FAMILY_EXPECT, or routing.
Does not open p3f evaluation. Does not remeasure development.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bite_bench.phase3k import (
    EVALUATION_REPLICAS,
    FORMATS,
    GENERATION,
    refuse_p3f_evaluation,
)
from bite_bench.phase3l import (
    COMPARE_KEYS,
    EXPECT_KEYS,
    K0_COMMIT_SHA,
    L1_VERDICTS,
    N_EVAL_SURFACES,
    NEGATIVE_FAMILIES,
    PROTOCOL_FROZEN,
    REVISION,
    VERDICT_BLOCKED,
    VERDICT_CONFIRMED,
    VERDICT_FAILED,
    evaluation_case_ids,
    evaluation_surfaces,
    freeze_manifest,
    locked_hashes,
)
from bite_ingestion.profilers.structural_redundancy_v1 import measure

SCHEMA_ID = "bite-phase3l-redundancy-first-open/v0.1"
PROTOCOL_COMMIT_SHA = "d365d0b1bd4cb3dcdad617ed4e78df19fdf23ce6"
_REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = _REPO / "artifacts" / "phase3l"
RESULT_PATH = ARTIFACT_DIR / "redundancy-first-open.json"
RESULT_MD_PATH = ARTIFACT_DIR / "redundancy-first-open.md"
PHASE3K_PATH = _REPO / "artifacts" / "phase3k" / "structural-redundancy.json"


def _observed(report: Any) -> dict[str, Any]:
    diag = dict(report.diagnostics)
    return {
        "duplicate_unit_ratio": float(report.features["duplicate_unit_ratio"]),
        "n_records": diag["n_records"],
        "n_unique_records": diag["n_unique_records"],
        "n_duplicate_records": diag["n_duplicate_records"],
        "max_multiplicity": diag["max_multiplicity"],
        "fail_closed": report.fail_closed,
    }


def _mismatches(expect: Mapping[str, Any], observed: Mapping[str, Any]) -> dict[str, Any]:
    diff: dict[str, Any] = {}
    for key in EXPECT_KEYS:
        expected = expect[key]
        got = observed.get(key)
        if got != expected:
            diff[key] = {"expected": expected, "observed": got}
    return diff


def _premise_errors() -> list[str]:
    errs: list[str] = []
    freeze = freeze_manifest()
    if freeze.get("verdict") != PROTOCOL_FROZEN:
        errs.append("L0 freeze drifted")
    if freeze.get("revision") != REVISION:
        errs.append("L0 revision drifted")
    if freeze.get("k0_commit_sha") != K0_COMMIT_SHA:
        errs.append("K0 SHA drifted")
    if freeze.get("locked_hashes") != locked_hashes():
        errs.append("locked blob hashes drifted")
    if list(freeze.get("evaluation_case_ids") or []) != evaluation_case_ids():
        errs.append("evaluation case ids drifted")
    if not PHASE3K_PATH.is_file():
        errs.append("Phase 3K artifact missing")
    else:
        phase3k = json.loads(PHASE3K_PATH.read_text(encoding="utf-8"))
        if phase3k.get("verdict") != "PHASE3K_REDUNDANCY_SENSOR_READY":
            errs.append("Phase 3K verdict rewritten")
    return errs


def _measure_row(surface: Mapping[str, Any]) -> dict[str, Any]:
    refuse_p3f_evaluation(str(surface["case_id"]))
    src = {"payload": str(surface["payload"]), "text": str(surface["payload"])}
    report = measure(src)
    observed = _observed(report)
    mismatches = _mismatches(dict(surface["expect"]), observed)
    return {
        "case_id": surface["case_id"],
        "family": surface["family"],
        "replica": surface["replica"],
        "format": surface["format"],
        "split": "evaluation",
        "generation": GENERATION,
        "expect": {key: surface["expect"][key] for key in EXPECT_KEYS},
        "observed": observed,
        "match": not mismatches,
        "mismatches": mismatches,
    }


def _format_invariance(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in rows:
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
    for replica in EVALUATION_REPLICAS:
        for fmt in FORMATS:
            left = by_id[f"p3k-exact_dup_pairs-r{replica}-{fmt}"]["observed"]
            right = by_id[f"p3k-reordered_duplicates-r{replica}-{fmt}"]["observed"]
            if any(left[key] != right[key] for key in COMPARE_KEYS):
                return False
    return True


def _negatives_ok(rows: list[dict[str, Any]]) -> bool:
    return all(
        row["observed"]["duplicate_unit_ratio"] == 0.0
        for row in rows
        if row["family"] in NEGATIVE_FAMILIES
    )


def run_evaluation() -> dict[str, Any]:
    blocked = _premise_errors()
    rows: list[dict[str, Any]] = []
    try:
        for surface in evaluation_surfaces():
            rows.append(_measure_row(surface))
    except Exception as exc:  # noqa: BLE001
        blocked.append(str(exc))
    ids = [str(row.get("case_id")) for row in rows]
    if ids != evaluation_case_ids():
        blocked.append("evaluation set mismatch")
    if len(rows) != N_EVAL_SURFACES:
        blocked.append(f"expected {N_EVAL_SURFACES} rows, got {len(rows)}")
    if any(row.get("split") != "evaluation" for row in rows):
        blocked.append("non-evaluation row")
    if any(int(row.get("replica") or -1) not in EVALUATION_REPLICAS for row in rows):
        blocked.append("development replica remeasured")
    blob = json.dumps(rows, sort_keys=True)
    if "p3f-" in blob:
        blocked.append("p3f identifier leaked")
    invariance = _format_invariance(rows) if rows else []
    expects_ok = bool(rows) and all(row["match"] for row in rows)
    format_ok = bool(invariance) and all(item["ok"] for item in invariance)
    reorder_ok = bool(rows) and _reorder_ok(rows)
    negatives_ok = bool(rows) and _negatives_ok(rows)
    checks = {
        "n_60": len(rows) == N_EVAL_SURFACES,
        "frozen_expects": expects_ok,
        "format_invariance": format_ok,
        "reorder_invariance": reorder_ok,
        "negative_controls": negatives_ok,
        "locked_blobs_unchanged": not any("hashes drifted" in item for item in blocked),
    }
    if blocked:
        verdict = VERDICT_BLOCKED
    elif all(checks.values()):
        verdict = VERDICT_CONFIRMED
    else:
        verdict = VERDICT_FAILED
    if verdict not in L1_VERDICTS:
        verdict = VERDICT_BLOCKED
        blocked.append("verdict not in frozen set")
    return {
        "schema": SCHEMA_ID,
        "revision": "phase3l-redundancy-first-open-v0.1",
        "protocol_revision": REVISION,
        "protocol_commit_sha": PROTOCOL_COMMIT_SHA,
        "k0_commit_sha": K0_COMMIT_SHA,
        "verdict": verdict,
        "blocked_reasons": blocked,
        "paid_api": False,
        "offline": True,
        "synthetic": True,
        "research_conclusion": False,
        "p3f_evaluation_holdout_used": False,
        "phase3k_verdict_unchanged": "PHASE3K_REDUNDANCY_SENSOR_READY",
        "claim_boundary": "same frozen families / new replica values",
        "not_claimed": ["unseen morphology", "external generalization"],
        "sensor_unchanged": True,
        "p3k_generation_unchanged": True,
        "p3k_split_unchanged": True,
        "family_expect_unchanged": True,
        "v0_overwritten": False,
        "v1_unchanged": True,
        "a_unchanged": True,
        "k_unchanged": True,
        "no_threshold": True,
        "redundancy_threshold_set": False,
        "rule_policy_changed": False,
        "rule_policy_executed": False,
        "routing_connected": False,
        "contract_fail_closed_scored": False,
        "n_rows": len(rows),
        "n_matched": sum(1 for row in rows if row["match"]),
        "checks": checks,
        "format_invariance": invariance,
        "rows": rows,
    }


def validate_phase3l_result(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("protocol_commit_sha") != PROTOCOL_COMMIT_SHA:
        errs.append("protocol commit SHA mismatch")
    if doc.get("k0_commit_sha") != K0_COMMIT_SHA:
        errs.append("K0 SHA mismatch")
    if doc.get("verdict") not in L1_VERDICTS:
        errs.append("verdict not in frozen set")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation opened")
    if doc.get("routing_connected") is not False:
        errs.append("routing connected")
    if doc.get("redundancy_threshold_set") is not False:
        errs.append("redundancy threshold set")
    if doc.get("rule_policy_changed") is not False:
        errs.append("RulePolicy changed")
    if doc.get("sensor_unchanged") is not True:
        errs.append("sensor changed")
    blob = json.dumps(doc, sort_keys=True)
    if "p3f-" in blob:
        errs.append("p3f identifier leaked")
    for row in doc.get("rows") or []:
        cid = str(row.get("case_id", ""))
        if not cid.startswith("p3k-"):
            errs.append(f"non-p3k case {cid}")
        if row.get("split") != "evaluation":
            errs.append("non-evaluation row")
        if "-r0-" in cid or "-r1-" in cid:
            errs.append("development remeasured")
    return errs


def render_md(doc: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 3L structural redundancy first-open evaluation",
        "",
        f"verdict: `{doc.get('verdict')}`",
        f"protocol SHA: `{doc.get('protocol_commit_sha')}`",
        f"matched: {doc.get('n_matched')}/{doc.get('n_rows')}",
        "routing_connected: `false`",
        "redundancy_threshold_set: `false`",
        "rule_policy_changed: `false`",
        "claim: `same frozen families / new replica values`",
        "",
        "## Checks",
        "",
    ]
    for key, ok in dict(doc.get("checks") or {}).items():
        lines.append(f"- {key}: `{ok}`")
    lines.extend(["", "## Cross-format", "", "| family | replica | ok |", "|---|---|---|"])
    for item in doc.get("format_invariance") or []:
        lines.append(
            f"| {item.get('family')} | {item.get('replica')} | {item.get('ok')} |"
        )
    lines.extend(["", "BITE wins / Go ではない。unseen morphology 評価ではない。", ""])
    reasons = list(doc.get("blocked_reasons") or [])
    if reasons:
        lines.append("blocked:")
        lines.extend(f"- {reason}" for reason in reasons)
        lines.append("")
    return "\n".join(lines)


def write_artifacts(doc: Mapping[str, Any] | None = None) -> tuple[Path, Path]:
    if doc is None:
        doc = run_evaluation()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    RESULT_MD_PATH.write_text(render_md(doc), encoding="utf-8")
    return RESULT_PATH, RESULT_MD_PATH


if __name__ == "__main__":
    write_artifacts()
