"""Phase 3N first-open evaluation protocol (N0).

Opens frozen p3m evaluation replicas 2/3. Does not measure in this module.
Does not change policy, predicates, operators, sensors, fixtures, or RulePolicy.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from itertools import product
from pathlib import Path
from typing import Any

from bite_bench.phase3m import (
    DISPERSIONS,
    EVALUATION_REPLICAS,
    GENERATION,
    HIGH_SEQUENCES,
    OPERATOR_ORDER,
    POLICY_NAME,
    SAFETY_KEYS,
    TEXTURES,
    Dispersion,
    EvaluationSealError,
    Texture,
    case_id,
    expected_sequence,
    gold_unit_ids,
    planned_case_ids,
    records_for,
    refuse_p3f_evaluation,
    split_manifest,
    split_of_replica,
    unit_id_for,
)

SCHEMA_ID = "bitebench-phase3n-conditional-routing-first-open-freeze/v0.1"
REVISION = "phase3n-conditional-routing-first-open-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE3N_CONDITIONAL_ROUTING_HOLDOUT_PROTOCOL_FROZEN"
VERDICT_CONFIRMED = "PHASE3N_CONDITIONAL_ROUTING_HOLDOUT_CONFIRMED"
VERDICT_FAILED = "PHASE3N_CONDITIONAL_ROUTING_HOLDOUT_FAILED"
VERDICT_BLOCKED = "PHASE3N_CONDITIONAL_ROUTING_HOLDOUT_BLOCKED"
N1_VERDICTS = (VERDICT_CONFIRMED, VERDICT_FAILED, VERDICT_BLOCKED)
M0_COMMIT_SHA = "ad95ed8bb0a60ec6c3a10c4a9ccc96f395bcf702"
M1_COMMIT_SHA = "5adf1637906874394fb9a89285cf373638a29e37"
N_EVAL_SURFACES = 48
CLAIM_BOUNDARY = "same frozen p3m texture families / new replica identifiers"
LOCKED_GIT_BLOBS = {
    "src/bite_ingestion/policies/conditional_texture_policy_v1.py": (
        "f592c2850e86beec68463dbac30a1910e057fb8b"
    ),
    "src/bite_ingestion/operators/preflight.py": (
        "b3cc6946f515b3ca6f025500a4ffdad45c111eea"
    ),
    "src/bite_ingestion/operators/untangle.py": (
        "2951b7542f96674930e750e438891ca772b46896"
    ),
    "src/bite_ingestion/operators/integrate.py": (
        "68e34becd80e7e803f511ec57ea7a23c2aaa1240"
    ),
    "src/bite_ingestion/profilers/dependency_dispersion_v1.py": (
        "890d777bb8179df27c8aeba35f1efebc133dd8eb"
    ),
    "src/bite_ingestion/profilers/structural_redundancy_v1.py": (
        "aca6fcd6664f9942b9f72a0d2fd171bfbfe41a35"
    ),
    "benchmarks/spec/phase3m-split-manifest.json": (
        "8514cc515a2adeb32cb2840e6337e1042dcc6089"
    ),
    "src/bite_ingestion/policies/rule_policy.py": (
        "06b77e35776e053ed66baf7e0fc0ef17ba639b89"
    ),
    "benchmarks/spec/phase3m-conditional-routing-freeze.json": (
        "62e8120f88c790b59bb2d9a3d65ddb8a0983549e"
    ),
    "artifacts/phase3m/conditional-routing.json": (
        "0efaae5704b9972906193c189fed1b63daa65882"
    ),
    "artifacts/phase3m/composition-safety.json": (
        "665f00626aa99f2efe45611066484c1c9b5076e5"
    ),
}

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase3n-conditional-routing-first-open-freeze.json"
LOCKED_PATH = _REPO / "benchmarks" / "spec" / "phase3n-locked-blobs.json"


def git_blob_sha(path: str) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", f"HEAD:{path}"],
        cwd=_REPO,
        text=True,
    ).strip()


def observed_git_blobs() -> dict[str, str]:
    return {path: git_blob_sha(path) for path in LOCKED_GIT_BLOBS}


def evaluation_case_ids() -> list[str]:
    return [
        case_id(texture, dispersion, replica)
        for texture, dispersion, replica in product(
            TEXTURES, DISPERSIONS, EVALUATION_REPLICAS
        )
    ]


def split_evaluation_ids() -> list[str]:
    return [
        str(row["case_id"])
        for row in split_manifest()["cases"]
        if int(row["replica"]) in EVALUATION_REPLICAS
    ]


def evaluation_surface(
    texture: Texture, dispersion: Dispersion, replica: int
) -> dict[str, Any]:
    cid = case_id(texture, dispersion, replica)
    refuse_p3f_evaluation(cid)
    if replica not in EVALUATION_REPLICAS:
        raise EvaluationSealError(f"p3m development sealed from 3N remeasure: {cid}")
    records = records_for(texture, dispersion, replica)
    dest_index = 1 if dispersion == "low" else len(records) - 1
    ids: list[str] = []
    for index, _row in enumerate(records):
        if index == 0:
            ids.append(gold_unit_ids(replica)[0])
        elif index == dest_index:
            ids.append(gold_unit_ids(replica)[1])
        else:
            ids.append(
                unit_id_for(
                    replica,
                    index,
                    trailing=dispersion == "low" and index > dest_index,
                )
            )
    texts = [f"{key}={value}" for key, value in records]
    return {
        "case_id": cid,
        "generation": GENERATION,
        "texture": texture,
        "dispersion": dispersion,
        "replica": replica,
        "split": split_of_replica(replica),
        "format": "key_value",
        "unit_ids": ids,
        "unit_texts": texts,
        "payload": "\n".join(texts),
        "gold_unit_ids": gold_unit_ids(replica),
        "expected_sequence": list(expected_sequence(texture, dispersion)),
        "n_records": len(records),
    }


def evaluation_surfaces() -> list[dict[str, Any]]:
    return [
        evaluation_surface(texture, dispersion, replica)
        for texture, dispersion, replica in product(
            TEXTURES, DISPERSIONS, EVALUATION_REPLICAS
        )
    ]


def locked_blob_manifest() -> dict[str, Any]:
    return {
        "schema": "bitebench-phase3n-locked-blobs/v0.1",
        "m0_commit_sha": M0_COMMIT_SHA,
        "m1_commit_sha": M1_COMMIT_SHA,
        "git_blob_sha": dict(LOCKED_GIT_BLOBS),
        "unchanged": [
            "predicate",
            "threshold",
            "fixture",
            "expected_sequence",
            "preflight",
            "operator",
            "sensor",
            "RulePolicy",
        ],
        "no_new_cases": True,
        "no_new_format": True,
        "no_tolerance": True,
        "on_failed": "do not retune predicates in this PR",
    }


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
        "premise": "PHASE3M_CONDITIONAL_ROUTING_READY",
        "m0_commit_sha": M0_COMMIT_SHA,
        "m1_commit_sha": M1_COMMIT_SHA,
        "locked_git_blobs": dict(LOCKED_GIT_BLOBS),
        "policy_name": POLICY_NAME,
        "generation": GENERATION,
        "p3m_generation_unchanged": True,
        "p3m_split_unchanged": True,
        "expected_sequence_unchanged": True,
        "predicate_unchanged": True,
        "threshold_unchanged": True,
        "fixture_unchanged": True,
        "preflight_unchanged": True,
        "operator_unchanged": True,
        "sensor_unchanged": True,
        "rule_policy_unchanged": True,
        "no_new_cases": True,
        "no_new_format": True,
        "tolerance": False,
        "remeasure_development": False,
        "p3f_evaluation_holdout_used": False,
        "replicas": list(EVALUATION_REPLICAS),
        "textures": list(TEXTURES),
        "dispersions": list(DISPERSIONS),
        "formats": ["key_value"],
        "n_evaluation_surfaces": N_EVAL_SURFACES,
        "evaluation_case_ids": ids,
        "high_sequences": {key: list(value) for key, value in HIGH_SEQUENCES.items()},
        "mid_low_sequence": [],
        "operator_order": list(OPERATOR_ORDER),
        "cut_in_conditional_map": False,
        "composition_safety": list(SAFETY_KEYS),
        "token_reduction": "diagnostic_only",
        "no_winner_score": True,
        "gold_isolation": {
            "scorer_only": ["gold_unit_ids", "expected_sequence", "texture"],
            "forbidden_on_sensors_preflight_policy": [
                "texture",
                "expected_sequence",
                "gold_unit_ids",
                "route",
                "operator",
                "answer",
            ],
        },
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "unseen texture",
            "unseen serialization",
            "external corpus generalization",
            "BITE superiority",
        ],
        "routing": {
            "policy": POLICY_NAME,
            "rule_policy_changed": False,
            "rule_policy_executed": False,
            "no_new_a_threshold": True,
            "no_new_k_threshold": True,
            "no_v1_edges_as_integrate_context": True,
            "cut_in_conditional_map": False,
        },
        "on_failed": "do not retune predicates or thresholds in this PR",
        "n1_verdicts": list(N1_VERDICTS),
        "verdict_rule": {
            "PHASE3N_CONDITIONAL_ROUTING_HOLDOUT_CONFIRMED": (
                "48/48 expected sequence exact; 48/48 composition safety; "
                "locked blobs unchanged; evaluation set exact; no CUT; no leak; "
                "p3f unopened"
            ),
            "PHASE3N_CONDITIONAL_ROUTING_HOLDOUT_FAILED": (
                "one or more sequence or safety mismatches"
            ),
            "PHASE3N_CONDITIONAL_ROUTING_HOLDOUT_BLOCKED": (
                "protocol drift, set mismatch, leak, or measurement cannot run"
            ),
        },
    }


def validate_phase3n_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("revision") != REVISION:
        errs.append("revision mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("protocol not frozen")
    if doc.get("premise") != "PHASE3M_CONDITIONAL_ROUTING_READY":
        errs.append("premise drifted")
    if doc.get("m0_commit_sha") != M0_COMMIT_SHA:
        errs.append("M0 SHA drifted")
    if doc.get("m1_commit_sha") != M1_COMMIT_SHA:
        errs.append("M1 SHA drifted")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("remeasure_development") is not False:
        errs.append("must not remeasure development")
    if doc.get("tolerance") is not False:
        errs.append("must not add tolerance")
    if doc.get("no_new_cases") is not True:
        errs.append("must not add cases")
    if list(doc.get("evaluation_case_ids") or []) != evaluation_case_ids():
        errs.append("evaluation case ids drifted")
    if list(doc.get("evaluation_case_ids") or []) != split_evaluation_ids():
        errs.append("evaluation ids are not the M0 split replica 2/3 set")
    if doc.get("n_evaluation_surfaces") != N_EVAL_SURFACES:
        errs.append("evaluation surface count drifted")
    if dict(doc.get("locked_git_blobs") or {}) != LOCKED_GIT_BLOBS:
        errs.append("locked git blobs drifted")
    if any(not item.startswith("p3m-") for item in evaluation_case_ids()):
        errs.append("non-p3m evaluation id")
    extra = set(evaluation_case_ids()) - set(planned_case_ids())
    if extra:
        errs.append("evaluation ids not in M0 plan")
    return errs


def write_freeze() -> tuple[Path, Path]:
    FREEZE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FREEZE_PATH.write_text(
        json.dumps(freeze_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    LOCKED_PATH.write_text(
        json.dumps(locked_blob_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return FREEZE_PATH, LOCKED_PATH


if __name__ == "__main__":
    write_freeze()
