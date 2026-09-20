"""Phase 4G G0 comparison-measurement amendment protocol.

Freezes recovery-bundle and visibility-v2 contracts before implementation.
Does not implement recovery_bundle_v1 or visibility metrics v2.
Does not rewrite Phase 4F artifacts. Does not retune BITE or length_pi_v1.
Does not open p3f. Does not acquire REALSTRUCT-2.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4b import DEV_SOURCE_IDS, EVAL_SOURCE_IDS
from bite_bench.phase4d import AUDIT_SOURCE_IDS
from bite_bench.phase4f import LOCKED_BLOBS as PHASE4F_LOCKED_BLOBS
from bite_bench.phase4f import LOCKED_T_HIGH

SCHEMA_ID = "bitebench-phase4g-comparison-accounting-freeze/v0.1"
REVISION = "phase4g-comparison-accounting-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE4G_COMPARISON_ACCOUNTING_PROTOCOL_FROZEN"
VERDICT_VALIDATED = "PHASE4G_COMPARISON_ACCOUNTING_VALIDATED"
VERDICT_PARTIAL = "PHASE4G_COMPARISON_ACCOUNTING_PARTIAL"
VERDICT_BLOCKED = "PHASE4G_COMPARISON_ACCOUNTING_BLOCKED"
G1_VERDICTS = (VERDICT_VALIDATED, VERDICT_PARTIAL, VERDICT_BLOCKED)
PREMISE = "PHASE4F_COMPARISON_PROTOCOL_READY"
PHASE4C_VERDICT = "PHASE4C_REAL_HOLDOUT_MEASURED"
PHASE4D_VERDICT = "PHASE4D_MEASUREMENT_SEMANTICS_AUDITED"
PHASE4E_VERDICT = "PHASE4E_FULL_KEY_REFERENCE_VALIDATED"
PHASE3S_VERDICT = "PHASE3S_REFERENCE_SPECIFICITY_FAILED"
PHASE3Q_VERDICT = "PHASE3Q_XFER2_TRANSFER_FAILED"
PHASE3T_VERDICT = "PHASE3T_EXACT_REFERENCE_VALIDATED"
PHASE4F_HEAD = "48eaba1a8f55363da3beccec726460b961199300"
F0_COMMIT_SHA = "ee8d190567e0ce055d7ffa2b7163cffa8d94912a"
F0_FREEZE_BLOB = "9f4e957af859432036e9d150c85b5066892dad8f"
PHASE4F_RESULT_BLOB = "28bfd7ea8b131b72ba55bb3f84a7126f99c96578"
LENGTH_PI_V1_BLOB = "2de74b1b21c466aaa20858a2066e011f14a0fe20"
TOKENIZER_BLOB = "6f95df67723fe8ee2e572e589f6ca3e864de37bc"
METRICS_V1_BLOB = "d58a2f3729423d79731cb081e8d64b0204fdfa6f"
ARMS = ("raw_full", "adapter_only", "length_pi_v1", "BITE_v5")
CLAIM_BOUNDARY = "comparison-measurement amendment before prospective corpus acquisition"
FIXTURE_FAMILIES = (
    "pass_through",
    "reduce_duplicate",
    "untangle_quarantine",
    "integrate_2way",
    "integrate_3way",
    "reduce_then_integrate",
    "untangle_then_integrate",
    "neg_partial_text",
    "neg_lineage_without_text",
    "neg_text_without_lineage",
)
LOCKED_PHASE4F = {
    "artifacts/phase4f/prospective-comparison.json": PHASE4F_RESULT_BLOB,
    "src/bite_eval/length_pi_v1.py": LENGTH_PI_V1_BLOB,
    "src/bite_eval/reference_tokenizer.py": TOKENIZER_BLOB,
    "src/bite_eval/phase4f_metrics.py": METRICS_V1_BLOB,
    "benchmarks/spec/phase4f-prospective-comparison-freeze.json": F0_FREEZE_BLOB,
}
LOCKED_BLOBS = {**PHASE4F_LOCKED_BLOBS, **LOCKED_PHASE4F}

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase4g-comparison-accounting-freeze.json"
PHASE4F_PATH = _REPO / "artifacts" / "phase4f" / "prospective-comparison.json"
PHASE4E_PATH = _REPO / "artifacts" / "phase4e" / "full-key-reference.json"
PHASE4C_PATH = _REPO / "artifacts" / "phase4c" / "real-holdout.json"
PHASE4D_PATH = _REPO / "artifacts" / "phase4d" / "measurement-semantics.json"
PHASE3T_PATH = _REPO / "artifacts" / "phase3t" / "exact-reference.json"
PHASE3S_PATH = _REPO / "artifacts" / "phase3s" / "reference-specificity.json"
PHASE3Q_PATH = _REPO / "artifacts" / "phase3q" / "xfer2-transfer.json"


def _git_blob(path: str) -> str:
    return subprocess.check_output(["git", "hash-object", path], cwd=_REPO, text=True).strip()


def planned_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "p4g-pass-through",
            "family": "pass_through",
            "mode": "operators",
            "sequence": [],
            "records": [["cairn_west", "ridge_alpha"], ["ridge_mark", "weft_beta"]],
            "expected_visible_indices": [0, 1],
        },
        {
            "case_id": "p4g-reduce-duplicate",
            "family": "reduce_duplicate",
            "mode": "operators",
            "sequence": ["REDUCE_v2"],
            "records": [["cairn_copy", "same_weft"], ["cairn_copy", "same_weft"]],
            "expected_visible_indices": [0],
        },
        {
            "case_id": "p4g-untangle-quarantine",
            "family": "untangle_quarantine",
            "mode": "operators",
            "sequence": ["UNTANGLE"],
            "records": [["cairn_ok", "plain_weft"], ["cairn_bad", "shuttle jam FATAL"]],
            "expected_visible_indices": [0],
        },
        {
            "case_id": "p4g-integrate-2way",
            "family": "integrate_2way",
            "mode": "operators",
            "sequence": ["INTEGRATE"],
            "records": [
                ["cairn_left", "ridge_one id=join_west"],
                ["cairn_right", "ridge_two id=join_west"],
            ],
            "expected_visible_indices": [0, 1],
        },
        {
            "case_id": "p4g-integrate-3way",
            "family": "integrate_3way",
            "mode": "operators",
            "sequence": ["INTEGRATE"],
            "records": [
                ["cairn_a", "one id=join_tri"],
                ["cairn_b", "two id=join_tri"],
                ["cairn_c", "three id=join_tri"],
            ],
            "expected_visible_indices": [0, 1, 2],
        },
        {
            "case_id": "p4g-reduce-then-integrate",
            "family": "reduce_then_integrate",
            "mode": "operators",
            "sequence": ["REDUCE_v2", "INTEGRATE"],
            "records": [
                ["cairn_dup", "same id=join_mix"],
                ["cairn_dup", "same id=join_mix"],
                ["cairn_mate", "other id=join_mix"],
            ],
            "expected_visible_indices": [0, 2],
        },
        {
            "case_id": "p4g-untangle-then-integrate",
            "family": "untangle_then_integrate",
            "mode": "operators",
            "sequence": ["UNTANGLE", "INTEGRATE"],
            "records": [
                ["cairn_keep", "ok id=join_iso"],
                ["cairn_iso", "bad FATAL"],
                ["cairn_mate", "pair id=join_iso"],
            ],
            "expected_visible_indices": [0, 2],
        },
        {
            "case_id": "p4g-neg-partial-text",
            "family": "neg_partial_text",
            "mode": "synthetic_visible",
            "records": [["cairn_full", "ridge_complete"]],
            "visible_text": "ridge_complete",
            "expected_visible_indices": [],
        },
        {
            "case_id": "p4g-neg-lineage-without-text",
            "family": "neg_lineage_without_text",
            "mode": "synthetic_visible",
            "records": [["cairn_left", "alpha_one"], ["cairn_right", "beta_two"]],
            "expected_visible_indices": [],
        },
        {
            "case_id": "p4g-neg-text-without-lineage",
            "family": "neg_text_without_lineage",
            "mode": "synthetic_visible",
            "records": [["cairn_left", "alpha_one"], ["cairn_right", "beta_two"]],
            "expected_visible_indices": [],
        },
    ]


def freeze_manifest() -> dict[str, Any]:
    return {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "verdict": PROTOCOL_FROZEN,
        "paid_api": False,
        "offline_core_tests": True,
        "research_conclusion": False,
        "premise": PREMISE,
        "phase4f_head_sha": PHASE4F_HEAD,
        "f0_commit_sha": F0_COMMIT_SHA,
        "f0_freeze_blob": F0_FREEZE_BLOB,
        "phase4f_result_blob": PHASE4F_RESULT_BLOB,
        "length_pi_v1_blob": LENGTH_PI_V1_BLOB,
        "tokenizer_blob": TOKENIZER_BLOB,
        "metrics_v1_blob": METRICS_V1_BLOB,
        "phase4c_verdict": PHASE4C_VERDICT,
        "phase4d_verdict": PHASE4D_VERDICT,
        "phase4e_verdict": PHASE4E_VERDICT,
        "phase4f_verdict": PREMISE,
        "phase3t_verdict": PHASE3T_VERDICT,
        "phase3s_verdict": PHASE3S_VERDICT,
        "phase3q_verdict": PHASE3Q_VERDICT,
        "p3f_evaluation_holdout_used": False,
        "no_realstruct2": True,
        "no_realstruct2_acquisition": True,
        "no_bite_retune": True,
        "no_length_pi_retune": True,
        "no_phase4f_rewrite": True,
        "no_winner_score": True,
        "t_high_reference": LOCKED_T_HIGH,
        "arms": list(ARMS),
        "locked_blobs": dict(LOCKED_BLOBS),
        "track_a": {
            "preserve_legacy_as": [
                "arm_local_sidecar_bytes_legacy",
                "arm_local_sidecar_tokens_legacy",
            ],
            "do_not_compare_legacy_across_arms": True,
            "canonical_recovery_bundle": True,
            "invariant": "raw_sha256 == sha256(reconstruct(visible, recovery_bundle))",
            "do_not_count_uncounted_original_source_copy": True,
            "metrics": [
                "recovery_bundle_bytes",
                "recovery_bundle_tokens",
                "recovery_metadata_bytes",
                "recovery_content_bytes",
            ],
            "raw_full_empty_iff_visible_bytes_equal_raw": True,
            "length_pi_bundle_includes_adapter_and_truncation_omissions": True,
        },
        "track_b": {
            "metric_id": "visible_source_record_ids_v2",
            "pass_through": "original unit_id + exact text",
            "integrate": "lineage AND exact newline-separated complete component",
            "lineage_alone_insufficient": True,
            "text_alone_insufficient": True,
            "substring_is_not_visibility": True,
            "recomputed": [
                "visible_reference_retention_v2",
                "unique_assignment_identity_retention_v2",
                "duplicate diagnostics v2",
            ],
            "do_not_change_bite_output": True,
        },
        "fixture_families": list(FIXTURE_FAMILIES),
        "planned_cases": planned_cases(),
        "realstruct1_retrospective": {
            "role": "development / retrospective diagnostic",
            "source_ids": list(AUDIT_SOURCE_IDS),
            "dev_source_ids": list(DEV_SOURCE_IDS),
            "eval_source_ids": list(EVAL_SOURCE_IDS),
            "not_holdout": True,
            "not_confirmatory": True,
            "not_generalization": True,
            "not_for_retuning": True,
            "integrate_absence_does_not_void_track_b": True,
        },
        "g1_verdicts": list(G1_VERDICTS),
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "new BITE evidence",
            "new baseline evidence",
            "holdout",
            "confirmatory comparison",
            "generalization",
            "BITE superiority",
        ],
    }


def validate_phase4g_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("G0 protocol not frozen")
    if doc.get("premise") != PREMISE:
        errs.append("Phase 4F premise drifted")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("no_realstruct2") is not True or doc.get("no_realstruct2_acquisition") is not True:
        errs.append("REALSTRUCT-2 must stay untouched")
    if doc.get("no_phase4f_rewrite") is not True:
        errs.append("Phase 4F rewrite must stay forbidden")
    if doc.get("no_bite_retune") is not True or doc.get("no_length_pi_retune") is not True:
        errs.append("arm retune must stay forbidden")
    if doc.get("t_high_reference") != LOCKED_T_HIGH:
        errs.append("T_high drifted")
    if list(doc.get("fixture_families") or []) != list(FIXTURE_FAMILIES):
        errs.append("fixture families drifted")
    if len(doc.get("planned_cases") or []) != len(FIXTURE_FAMILIES):
        errs.append("planned_cases count drifted")
    if json.loads(PHASE4F_PATH.read_text(encoding="utf-8")).get("verdict") != PREMISE:
        errs.append("Phase 4F verdict rewritten")
    if json.loads(PHASE4E_PATH.read_text(encoding="utf-8")).get("verdict") != PHASE4E_VERDICT:
        errs.append("Phase 4E verdict rewritten")
    if json.loads(PHASE4C_PATH.read_text(encoding="utf-8")).get("verdict") != PHASE4C_VERDICT:
        errs.append("Phase 4C verdict rewritten")
    if json.loads(PHASE4D_PATH.read_text(encoding="utf-8")).get("verdict") != PHASE4D_VERDICT:
        errs.append("Phase 4D verdict rewritten")
    if json.loads(PHASE3T_PATH.read_text(encoding="utf-8")).get("verdict") != PHASE3T_VERDICT:
        errs.append("Phase 3T verdict rewritten")
    if json.loads(PHASE3S_PATH.read_text(encoding="utf-8")).get("verdict") != PHASE3S_VERDICT:
        errs.append("Phase 3S verdict rewritten")
    if json.loads(PHASE3Q_PATH.read_text(encoding="utf-8")).get("verdict") != PHASE3Q_VERDICT:
        errs.append("Phase 3Q verdict rewritten")
    for path, expected in LOCKED_PHASE4F.items():
        if _git_blob(path) != expected:
            errs.append(f"Phase 4F blob drifted: {path}")
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
    print(freeze["verdict"], "n", len(freeze["planned_cases"]))
    print("errors", validate_phase4g_freeze(freeze))
