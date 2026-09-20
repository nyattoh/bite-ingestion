"""Phase 4D D0 measurement-semantics audit contract.

Additive post-open audit. Does not rewrite Phase 4C C0/C1/artifacts/verdict.
Does not retune frozen BITE. Does not open p3f. Does not add baselines.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4b import (
    DEV_SOURCE_IDS,
    EVAL_SOURCE_IDS,
    LOCKED_BITE_BLOBS,
    LOCKED_PHASE4A_BLOBS,
    LOCKED_T_HIGH,
    OVERLAY_V2_BLOB,
)
from bite_bench.phase4c import (
    ADAPTER_BLOB,
    ADAPTER_PATH,
    OVERLAY_V2_SHA256,
    PHASE3Q_VERDICT,
    PHASE3S_VERDICT,
    PHASE3T_VERDICT,
    PHASE4A_VERDICT,
    PHASE4B_EVAL_HARNESS_BLOB,
    PHASE4B_EVAL_PATH,
    PHASE4B_HEAD,
    PHASE4B_LOCK_BLOB,
    PHASE4B_LOCK_PATH,
    overlay_v2_sha256,
)

SCHEMA_ID = "bitebench-phase4d-measurement-semantics-freeze/v0.1"
REVISION = "phase4d-measurement-semantics-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE4D_MEASUREMENT_SEMANTICS_PROTOCOL_FROZEN"
VERDICT_AUDITED = "PHASE4D_MEASUREMENT_SEMANTICS_AUDITED"
VERDICT_PARTIAL = "PHASE4D_MEASUREMENT_SEMANTICS_PARTIAL"
VERDICT_BLOCKED = "PHASE4D_MEASUREMENT_SEMANTICS_BLOCKED"
D1_VERDICTS = (VERDICT_AUDITED, VERDICT_PARTIAL, VERDICT_BLOCKED)
PREMISE = "PHASE4C_REAL_HOLDOUT_MEASURED"
PHASE4C_HEAD = "21035872a377e23ad2c5bd01030e312330de005a"
C0_COMMIT_SHA = "8ed272fc7cd0487386656f2be7120b554be7921a"
C0_FREEZE_BLOB = "8e7dc9196bb5c98e79198263b0d4eeadc6254ff2"
PHASE4C_RESULT_BLOB = "f344bde69d7f963bb78780e967bc59bf639d2942"
PHASE4C_REFERENCE_BLOB = "9d0fd974d72d923f97f7c9dc6f325d7ea1e8a032"
PHASE4C_PROVENANCE_BLOB = "b22d290d1d8f89276c923439b62f5ae1102a9fbb"
PHASE4C_FREEZE_PATH = "benchmarks/spec/phase4c-holdout-first-open-freeze.json"
PHASE4C_RESULT_PATH = "artifacts/phase4c/real-holdout.json"
PHASE4C_REFERENCE_PATH = "artifacts/phase4c/reference-coverage.json"
PHASE4C_PROVENANCE_PATH = "artifacts/phase4c/full-source-provenance.json"
CLAIM_BOUNDARY = "retrospective measurement-semantics audit on REALSTRUCT-1"
AUDIT_SOURCE_IDS = (*DEV_SOURCE_IDS, *EVAL_SOURCE_IDS)
LEGACY_METRIC = "line_pair_recall_legacy"
PHASE4C_SAFETY_PHRASE = "full-source conservation safety 9/9"
FORBIDDEN_PHASE4C_SAFETY_PHRASE = "composition_safety_v2 aggregate ok 9/9"

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase4d-measurement-semantics-freeze.json"
PHASE4C_RESULT = _REPO / PHASE4C_RESULT_PATH
PHASE4A_PATH = _REPO / "artifacts" / "phase4a" / "realstruct-1.json"
PHASE3T_PATH = _REPO / "artifacts" / "phase3t" / "exact-reference.json"
PHASE3S_PATH = _REPO / "artifacts" / "phase3s" / "reference-specificity.json"
PHASE3Q_PATH = _REPO / "artifacts" / "phase3q" / "xfer2-transfer.json"
SPLIT_PATH = _REPO / "corpora" / "realstruct-1" / "split.json"


def _git_blob(path: str) -> str:
    return subprocess.check_output(["git", "hash-object", path], cwd=_REPO, text=True).strip()


def freeze_manifest() -> dict[str, Any]:
    return {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "verdict": PROTOCOL_FROZEN,
        "paid_api": False,
        "offline_core_tests": True,
        "research_conclusion": False,
        "premise": PREMISE,
        "phase4c_head_sha": PHASE4C_HEAD,
        "c0_commit_sha": C0_COMMIT_SHA,
        "c0_freeze_blob": C0_FREEZE_BLOB,
        "phase4c_result_blob": PHASE4C_RESULT_BLOB,
        "phase4c_reference_blob": PHASE4C_REFERENCE_BLOB,
        "phase4c_provenance_blob": PHASE4C_PROVENANCE_BLOB,
        "phase4a_verdict": PHASE4A_VERDICT,
        "phase3t_verdict": PHASE3T_VERDICT,
        "phase3s_verdict": PHASE3S_VERDICT,
        "phase3q_verdict": PHASE3Q_VERDICT,
        "p3f_evaluation_holdout_used": False,
        "no_xfer3": True,
        "no_baseline_added": True,
        "no_bite_retune": True,
        "no_phase4c_rewrite": True,
        "not_second_holdout_evaluation": True,
        "not_confirmatory": True,
        "t_high_reference": LOCKED_T_HIGH,
        "audit_source_ids": list(AUDIT_SOURCE_IDS),
        "dev_source_ids": list(DEV_SOURCE_IDS),
        "eval_source_ids": list(EVAL_SOURCE_IDS),
        "adapter_blob": ADAPTER_BLOB,
        "overlay_v2_blob": OVERLAY_V2_BLOB,
        "overlay_v2_sha256": OVERLAY_V2_SHA256,
        "phase4b_head_sha": PHASE4B_HEAD,
        "phase4b_evaluation_lock_blob": PHASE4B_LOCK_BLOB,
        "phase4b_eval_harness_blob": PHASE4B_EVAL_HARNESS_BLOB,
        "locked_phase4a_blobs": dict(LOCKED_PHASE4A_BLOBS),
        "locked_bite_blobs": dict(LOCKED_BITE_BLOBS),
        "track_a": {
            "legacy_metric_id": LEGACY_METRIC,
            "legacy_metric_preserved": True,
            "gold_identity": "(source_line, NAME, dest_line)",
            "prediction_identity": "(source_line, atom, dest_line)",
            "adjudication": [
                "source assignment value contains literal ${atom}",
                "destination assignment key equals atom case-sensitive exact",
            ],
            "unadjudicated_extra_edges_are_not_fp": True,
            "no_f1": True,
            "no_winner_score": True,
            "do_not_assume_ratis_atom_aware_equals_legacy": True,
        },
        "track_b": {
            "layer_a": "full_source_conservation_safety",
            "layer_a_required": [
                "provenance_completeness == 1",
                "lineage_recall == 1",
                "silent_loss == 0",
                "conservation_untraced == []",
                "unsupported_lost == 0",
                "no_unrelated_overmerge == true",
            ],
            "layer_b": "composition_operator_checks",
            "discrepancy_targets": ["rs1-ini-polybar", "rs1-ini-gogs"],
            "failure_classes": [
                "scorer_scope_mismatch",
                "operator_semantic_failure",
                "full_source_merge_interaction",
                "other",
            ],
            "routing_plane_diagnostic": True,
            "production_operator_code_unchanged": True,
        },
        "phase4c_preservation": {
            "verdict": PREMISE,
            "safety_phrasing": PHASE4C_SAFETY_PHRASE,
            "forbidden_safety_phrasing": FORBIDDEN_PHASE4C_SAFETY_PHRASE,
        },
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "new holdout result",
            "real-world generalization",
            "BITE superiority",
            "second holdout evaluation",
            "confirmatory",
        ],
        "d1_verdicts": list(D1_VERDICTS),
    }


def validate_phase4d_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("D0 protocol not frozen")
    if doc.get("premise") != PREMISE:
        errs.append("Phase 4C premise drifted")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("no_phase4c_rewrite") is not True:
        errs.append("Phase 4C rewrite must stay forbidden")
    if doc.get("not_second_holdout_evaluation") is not True:
        errs.append("must not be a second holdout evaluation")
    if doc.get("not_confirmatory") is not True:
        errs.append("must not be confirmatory")
    if doc.get("no_bite_retune") is not True:
        errs.append("BITE retune must stay forbidden")
    if doc.get("no_baseline_added") is not True:
        errs.append("baselines must not be added")
    if list(doc.get("audit_source_ids") or []) != list(AUDIT_SOURCE_IDS):
        errs.append("audit source ids drifted")
    if list(doc.get("eval_source_ids") or []) != list(EVAL_SOURCE_IDS):
        errs.append("eval split drifted")
    if doc.get("t_high_reference") != LOCKED_T_HIGH:
        errs.append("T_high drifted")
    if doc.get("c0_freeze_blob") != C0_FREEZE_BLOB:
        errs.append("C0 freeze blob drifted")
    if json.loads(PHASE4C_RESULT.read_text(encoding="utf-8")).get("verdict") != PREMISE:
        errs.append("Phase 4C verdict rewritten")
    if json.loads(PHASE4A_PATH.read_text(encoding="utf-8")).get("verdict") != PHASE4A_VERDICT:
        errs.append("Phase 4A verdict rewritten")
    split = json.loads(SPLIT_PATH.read_text(encoding="utf-8"))
    if list(split.get("evaluation") or []) != list(EVAL_SOURCE_IDS):
        errs.append("split.json evaluation drifted")
    if json.loads(PHASE3T_PATH.read_text(encoding="utf-8")).get("verdict") != PHASE3T_VERDICT:
        errs.append("Phase 3T verdict rewritten")
    if json.loads(PHASE3S_PATH.read_text(encoding="utf-8")).get("verdict") != PHASE3S_VERDICT:
        errs.append("Phase 3S verdict rewritten")
    if json.loads(PHASE3Q_PATH.read_text(encoding="utf-8")).get("verdict") != PHASE3Q_VERDICT:
        errs.append("Phase 3Q verdict rewritten")
    for path, expected in {
        PHASE4C_FREEZE_PATH: C0_FREEZE_BLOB,
        PHASE4C_RESULT_PATH: PHASE4C_RESULT_BLOB,
        PHASE4C_REFERENCE_PATH: PHASE4C_REFERENCE_BLOB,
        PHASE4C_PROVENANCE_PATH: PHASE4C_PROVENANCE_BLOB,
        ADAPTER_PATH: ADAPTER_BLOB,
        PHASE4B_LOCK_PATH: PHASE4B_LOCK_BLOB,
        PHASE4B_EVAL_PATH: PHASE4B_EVAL_HARNESS_BLOB,
        "corpora/realstruct-1/annotations-v2.json": OVERLAY_V2_BLOB,
        **LOCKED_BITE_BLOBS,
        **LOCKED_PHASE4A_BLOBS,
    }.items():
        if _git_blob(path) != expected:
            errs.append(f"locked blob drifted: {path}")
    if overlay_v2_sha256() != OVERLAY_V2_SHA256:
        errs.append("annotations-v2 hash drifted")
    try:
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
        errs.append("p3f seal did not fire")
    except EvaluationSealError:
        pass
    return errs


def write_freeze() -> Path:
    FREEZE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FREEZE_PATH.write_bytes(
        (json.dumps(freeze_manifest(), indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    return FREEZE_PATH


if __name__ == "__main__":
    write_freeze()
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    print(freeze["verdict"])
    print("errors", validate_phase4d_freeze(freeze))
