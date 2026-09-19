"""Phase 3L first-open evaluation protocol (L0).

Opens frozen p3k evaluation replicas 2/3. Does not measure in this module.
Does not change structural_redundancy_v1, p3k generation, split, or routing.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from itertools import product
from pathlib import Path
from typing import Any

from bite_bench.phase3k import (
    EVALUATION_REPLICAS,
    FAMILIES,
    FAMILY_EXPECT,
    FORMATS,
    GENERATION,
    SENSOR_NAME,
    family_case_id,
    records_for,
    render_payload,
    split_manifest,
)

SCHEMA_ID = "bitebench-phase3l-redundancy-first-open-freeze/v0.1"
REVISION = "phase3l-redundancy-first-open-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE3L_REDUNDANCY_HOLDOUT_PROTOCOL_FROZEN"
VERDICT_CONFIRMED = "PHASE3L_REDUNDANCY_HOLDOUT_CONFIRMED"
VERDICT_FAILED = "PHASE3L_REDUNDANCY_HOLDOUT_FAILED"
VERDICT_BLOCKED = "PHASE3L_REDUNDANCY_HOLDOUT_BLOCKED"
L1_VERDICTS = (VERDICT_CONFIRMED, VERDICT_FAILED, VERDICT_BLOCKED)
K0_COMMIT_SHA = "526601b68a0eec9861b012ef5ddc67078447bf36"
N_EVAL_SURFACES = 60
COMPARE_KEYS = (
    "n_records",
    "n_unique_records",
    "n_duplicate_records",
    "duplicate_unit_ratio",
)
EXPECT_KEYS = (
    "n_records",
    "n_unique_records",
    "n_duplicate_records",
    "max_multiplicity",
    "duplicate_unit_ratio",
    "fail_closed",
)
NEGATIVE_FAMILIES = (
    "all_unique",
    "same_key_diff_value",
    "same_value_diff_key",
    "common_prefix",
    "common_suffix",
    "identifier_substring",
)

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase3l-redundancy-first-open-freeze.json"
PHASE3K_ARTIFACT = _REPO / "artifacts" / "phase3k" / "structural-redundancy.json"
SENSOR_PY = _REPO / "src" / "bite_ingestion" / "profilers" / "structural_redundancy_v1.py"
SPLIT_JSON = _REPO / "benchmarks" / "spec" / "phase3k-split-manifest.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def family_expect_sha() -> str:
    blob = json.dumps(FAMILY_EXPECT, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def locked_hashes() -> dict[str, str]:
    return {
        "phase3k_ready_artifact": sha256_file(PHASE3K_ARTIFACT),
        "sensor_source_blob": sha256_file(SENSOR_PY),
        "p3k_split_manifest": sha256_file(SPLIT_JSON),
        "k0_family_expect": family_expect_sha(),
    }


def evaluation_case_ids() -> list[str]:
    return [
        family_case_id(family, replica, fmt)
        for family, replica, fmt in product(FAMILIES, EVALUATION_REPLICAS, FORMATS)
    ]


def split_evaluation_ids() -> list[str]:
    return [
        str(row["case_id"])
        for row in split_manifest()["cases"]
        if int(row["replica"]) in EVALUATION_REPLICAS and row["format"] != "contract"
    ]


def evaluation_surfaces() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family, replica, fmt in product(FAMILIES, EVALUATION_REPLICAS, FORMATS):
        records = records_for(family, replica)
        rows.append(
            {
                "case_id": family_case_id(family, replica, fmt),
                "generation": GENERATION,
                "family": family,
                "replica": replica,
                "format": fmt,
                "split": "evaluation",
                "payload": render_payload(records, fmt),
                "n_canonical_records": len(records),
                "expect": dict(FAMILY_EXPECT[family]),
            }
        )
    return rows


def freeze_manifest() -> dict[str, Any]:
    ids = evaluation_case_ids()
    return {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "verdict": PROTOCOL_FROZEN,
        "paid_api": False,
        "offline": True,
        "synthetic": True,
        "research_conclusion": False,
        "premise": "PHASE3K_REDUNDANCY_SENSOR_READY",
        "k0_commit_sha": K0_COMMIT_SHA,
        "locked_hashes": locked_hashes(),
        "sensor_name": SENSOR_NAME,
        "generation": GENERATION,
        "p3k_generation_unchanged": True,
        "p3k_split_unchanged": True,
        "family_expect_unchanged": True,
        "sensor_unchanged": True,
        "replicas": list(EVALUATION_REPLICAS),
        "families": list(FAMILIES),
        "formats": list(FORMATS),
        "n_evaluation_surfaces": N_EVAL_SURFACES,
        "evaluation_case_ids": ids,
        "no_new_cases": True,
        "remeasure_development": False,
        "p3f_evaluation_holdout_used": False,
        "contract_fail_closed_not_scored": True,
        "no_threshold": True,
        "no_per_format_threshold": True,
        "redundancy_threshold_set": False,
        "tolerance": False,
        "claim_boundary": "same frozen families / new replica values",
        "not_claimed": ["unseen morphology", "external generalization"],
        "expect_keys": list(EXPECT_KEYS),
        "format_invariance_keys": list(COMPARE_KEYS),
        "negative_families": list(NEGATIVE_FAMILIES),
        "routing": {
            "rule_policy_changed": False,
            "rule_policy_executed": False,
            "routing_connected": False,
            "redundancy_threshold_set": False,
        },
        "on_failed": "do not patch sensor in this PR",
        "l1_verdicts": list(L1_VERDICTS),
        "verdict_rule": {
            "PHASE3L_REDUNDANCY_HOLDOUT_CONFIRMED": (
                "60/60 frozen expects exact; cross-format exact; "
                "reorder exact; negatives ratio==0; locked blobs unchanged"
            ),
            "PHASE3L_REDUNDANCY_HOLDOUT_FAILED": "one or more evaluation mismatches",
            "PHASE3L_REDUNDANCY_HOLDOUT_BLOCKED": (
                "protocol drift, evaluation set mismatch, or measurement cannot run"
            ),
        },
    }


def validate_phase3l_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("revision") != REVISION:
        errs.append("revision mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("protocol not frozen")
    if doc.get("k0_commit_sha") != K0_COMMIT_SHA:
        errs.append("K0 SHA drifted")
    if doc.get("premise") != "PHASE3K_REDUNDANCY_SENSOR_READY":
        errs.append("premise drifted")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("no_threshold") is not True:
        errs.append("must not add thresholds")
    if doc.get("remeasure_development") is not False:
        errs.append("must not remeasure development")
    if list(doc.get("evaluation_case_ids") or []) != evaluation_case_ids():
        errs.append("evaluation case ids drifted")
    if list(doc.get("evaluation_case_ids") or []) != split_evaluation_ids():
        errs.append("evaluation ids are not the K0 split replica 2/3 set")
    if doc.get("n_evaluation_surfaces") != N_EVAL_SURFACES:
        errs.append("evaluation surface count drifted")
    if len(evaluation_case_ids()) != N_EVAL_SURFACES:
        errs.append("evaluation id count is not 60")
    if dict(doc.get("locked_hashes") or {}) != locked_hashes():
        errs.append("locked blob hashes drifted")
    routing = dict(doc.get("routing") or {})
    if routing.get("routing_connected") is not False:
        errs.append("must not connect routing")
    if routing.get("redundancy_threshold_set") is not False:
        errs.append("must not set redundancy threshold")
    return errs


def write_freeze() -> Path:
    FREEZE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FREEZE_PATH.write_text(
        json.dumps(freeze_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return FREEZE_PATH


if __name__ == "__main__":
    write_freeze()
