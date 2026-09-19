"""Phase 4B B0 scorer addendum protocol.

Freezes overlay-v2 rules and Phase 4A addendum notes before any BITE run.
Does not import or run BITE sensors, policies, planners, or operators.
Does not open eval 9 or p3f.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.realstruct1 import sha256_bytes

SCHEMA_ID = "bitebench-phase4b-scorer-addendum-freeze/v0.1"
REVISION = "phase4b-scorer-addendum-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE4B_SCORER_ADDENDUM_FROZEN"
VERDICT_READY = "PHASE4B_REAL_ADAPTER_READY"
VERDICT_PARTIAL = "PHASE4B_REAL_ADAPTER_PARTIAL"
VERDICT_BLOCKED = "PHASE4B_REAL_ADAPTER_BLOCKED"
B1_VERDICTS = (VERDICT_READY, VERDICT_PARTIAL, VERDICT_BLOCKED)
PREMISE = "PHASE4A_REAL_CORPUS_FROZEN"
PHASE3S_VERDICT = "PHASE3S_REFERENCE_SPECIFICITY_FAILED"
PHASE3Q_VERDICT = "PHASE3Q_XFER2_TRANSFER_FAILED"
PHASE3T_VERDICT = "PHASE3T_EXACT_REFERENCE_VALIDATED"
PHASE4A_HEAD = "00fa38250dfe9fee95a1f00d3e8aafbd643324a2"
B0_COMMIT_SHA = "70fa0ce678611db122a74a5fbe730fccf5bf12fb"
B0_FREEZE_BLOB = "51af36d70b29ef74c797ed3f547b8f848319184d"
OVERLAY_V2_BLOB = "0d1388b89bf2c5c2e062472ea2b78a1b1923ad9b"
LOCKED_T_HIGH = 4
DEV_SOURCE_IDS = (
    "rs1-dotenv-linkding",
    "rs1-props-hadoop-log4j",
    "rs1-ini-oe-bitbake",
)
EVAL_SOURCE_IDS = (
    "rs1-dotenv-koel",
    "rs1-dotenv-bookstack",
    "rs1-dotenv-laravel",
    "rs1-props-ratis-log4j",
    "rs1-props-kafka-server",
    "rs1-props-tomcat-logging",
    "rs1-ini-polybar",
    "rs1-ini-gogs",
    "rs1-ini-tegra-common",
)
CLAIM_BOUNDARY = "development evidence on 3 fixed REALSTRUCT-1 documents only"
LOCKED_PHASE4A_BLOBS = {
    "artifacts/phase4a/realstruct-1.json": "7a7b0834e9b66c599492a06dbe116e773eca6320",
    "corpora/realstruct-1/annotations.json": "956da0205dcd034a40413ccf3f728b9897d3c49e",
    "corpora/realstruct-1/manifest.json": "636b7c51d637fdb6ea8cf83546baa7f61bde2ae8",
    "corpora/realstruct-1/split.json": "2be516a478a683b16847536fbbe24c93ee93cdf1",
    "corpora/realstruct-1/licenses.json": "55eda51460fc8ac02c576c3d956210cda8959c71",
    "benchmarks/spec/phase4a-realstruct1-freeze.json": (
        "6e009fb6cf1cb239b8449e402301be15ffd7ed86"
    ),
}
LOCKED_BITE_BLOBS = {
    "src/bite_ingestion/profilers/reference_identity_v1.py": (
        "49dcd367eccdece7a1bd90df0a3f44f0c24ded65"
    ),
    "src/bite_ingestion/profilers/dependency_dispersion_v3.py": (
        "9ec1c46a68d685210898552c879098bf0416e56d"
    ),
    "src/bite_ingestion/policies/conditional_texture_policy_v4.py": (
        "04d46b15424ccbaf02694d7e7ae056b0b6715686"
    ),
    "src/bite_ingestion/policies/projected_actionability_plan_v1.py": (
        "af3737f078a6d91da38999885aea13860350526a"
    ),
    "src/bite_ingestion/profilers/structural_redundancy_v2.py": (
        "8960396c9a91872a1bfb0ccdaeae834d872cf12e"
    ),
    "src/bite_ingestion/logical_record.py": "c6f8cdd455cbc6814141fdb95458a72cc47b7af0",
    "src/bite_ingestion/operators/reduce_v2.py": "d4bafba7dfdd048a0ccad404a8f706202e2157b5",
    "src/bite_ingestion/operators/untangle.py": "2951b7542f96674930e750e438891ca772b46896",
    "src/bite_ingestion/operators/integrate.py": "68e34becd80e7e803f511ec57ea7a23c2aaa1240",
    "src/bite_eval/composition_safety_v2.py": "85560279375b30f737eb3825cce72373be70488e",
}

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase4b-scorer-addendum-freeze.json"
V2_PATH = _REPO / "corpora" / "realstruct-1" / "annotations-v2.json"
DIFF_PATH = _REPO / "artifacts" / "phase4b" / "annotation-diff.json"
MANIFEST_PATH = _REPO / "corpora" / "realstruct-1" / "manifest.json"
SPLIT_PATH = _REPO / "corpora" / "realstruct-1" / "split.json"
PHASE4A_PATH = _REPO / "artifacts" / "phase4a" / "realstruct-1.json"
PHASE3T_PATH = _REPO / "artifacts" / "phase3t" / "exact-reference.json"
PHASE3S_PATH = _REPO / "artifacts" / "phase3s" / "reference-specificity.json"
PHASE3Q_PATH = _REPO / "artifacts" / "phase3q" / "xfer2-transfer.json"


def overlay_v2_sha256() -> str:
    if not V2_PATH.is_file():
        return ""
    return sha256_bytes(V2_PATH.read_bytes())


def raw_sha256_map() -> dict[str, str]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {str(row["source_id"]): str(row["sha256"]) for row in manifest["sources"]}


def freeze_manifest() -> dict[str, Any]:
    return {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "verdict": PROTOCOL_FROZEN,
        "paid_api": False,
        "offline_core_tests": True,
        "research_conclusion": False,
        "premise": PREMISE,
        "phase4a_head_sha": PHASE4A_HEAD,
        "phase3t_verdict": PHASE3T_VERDICT,
        "phase3s_verdict": PHASE3S_VERDICT,
        "phase3q_verdict": PHASE3Q_VERDICT,
        "p3f_evaluation_holdout_used": False,
        "no_xfer3": True,
        "no_bite_execution_in_b0": True,
        "no_eval_execution": True,
        "no_baseline_execution": True,
        "t_high_reference": LOCKED_T_HIGH,
        "dev_source_ids": list(DEV_SOURCE_IDS),
        "eval_source_ids": list(EVAL_SOURCE_IDS),
        "phase4a_legacy_kept": True,
        "phase4a_not_rewritten": True,
        "addendum": {
            "duplicate_groups": (
                "Phase4A duplicate_groups is repeated-assignment-key diagnostic, "
                "not validated exact logical duplicate gold"
            ),
            "explicit_reference_generation": (
                "Phase4A explicit-reference generation was one-pass and can omit "
                "forward references whose destination key occurs later in the same document"
            ),
            "phase4a_remains_frozen": True,
        },
        "overlay_v2": {
            "path": "corpora/realstruct-1/annotations-v2.json",
            "assignment_grammar": "first '=' separator; unchanged from Phase 4A",
            "unsupported_not_negative": True,
            "exact_duplicate_identity": "exact (assignment_key, assignment_value)",
            "repeated_key_groups_are_diagnostic": True,
            "explicit_reference_gold": "${NAME} only",
            "key_index": "two-pass document-wide",
            "forward_and_backward_destinations": True,
            "not_gold": ["$NAME", "${NAME:-x}", "substring", "semantic relation"],
            "missing_annotation_is_not_non_reference": True,
            "forbidden_scorer_fields": [
                "expected BITE route",
                "expected operator sequence",
            ],
        },
        "raw_sha256": raw_sha256_map(),
        "overlay_v2_sha256": overlay_v2_sha256(),
        "locked_phase4a_blobs": dict(LOCKED_PHASE4A_BLOBS),
        "locked_bite_blobs": dict(LOCKED_BITE_BLOBS),
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "real-world generalization",
            "evaluation result",
            "BITE superiority",
        ],
        "b1_verdicts": list(B1_VERDICTS),
    }


def validate_phase4b_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("B0 protocol not frozen")
    if doc.get("premise") != PREMISE:
        errs.append("Phase 4A premise drifted")
    if doc.get("no_eval_execution") is not True:
        errs.append("eval 9 must stay sealed in 4B")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("no_xfer3") is not True:
        errs.append("XFER-3 must not be invented")
    if list(doc.get("dev_source_ids") or []) != list(DEV_SOURCE_IDS):
        errs.append("dev split drifted")
    if list(doc.get("eval_source_ids") or []) != list(EVAL_SOURCE_IDS):
        errs.append("eval split drifted")
    if json.loads(PHASE4A_PATH.read_text(encoding="utf-8")).get("verdict") != PREMISE:
        errs.append("Phase 4A verdict rewritten")
    split = json.loads(SPLIT_PATH.read_text(encoding="utf-8"))
    if list(split.get("development") or []) != list(DEV_SOURCE_IDS):
        errs.append("split.json development drifted")
    if list(split.get("evaluation") or []) != list(EVAL_SOURCE_IDS):
        errs.append("split.json evaluation drifted")
    if json.loads(PHASE3T_PATH.read_text(encoding="utf-8")).get("verdict") != PHASE3T_VERDICT:
        errs.append("Phase 3T verdict rewritten")
    if json.loads(PHASE3S_PATH.read_text(encoding="utf-8")).get("verdict") != PHASE3S_VERDICT:
        errs.append("Phase 3S verdict rewritten")
    if json.loads(PHASE3Q_PATH.read_text(encoding="utf-8")).get("verdict") != PHASE3Q_VERDICT:
        errs.append("Phase 3Q verdict rewritten")
    if V2_PATH.is_file() and doc.get("overlay_v2_sha256") != overlay_v2_sha256():
        errs.append("annotations-v2 hash drifted")
    try:
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
        errs.append("p3f seal did not fire")
    except EvaluationSealError:
        pass
    return errs


def write_freeze() -> Path:
    FREEZE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FREEZE_PATH.write_text(
        json.dumps(freeze_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return FREEZE_PATH
