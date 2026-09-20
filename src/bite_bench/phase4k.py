"""Phase 4K K0 evidence-ledger freeze.

Documentation-only contract. Does not run experiments, tokenizer, arms,
sensors, policies, or operators. Does not rewrite Phase 4A-4J artifacts.
Does not open p3f. Does not merge.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation

SCHEMA_ID = "bitebench-phase4k-evidence-ledger-freeze/v0.1"
REVISION = "phase4k-evidence-ledger-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE4K_EVIDENCE_LEDGER_PROTOCOL_FROZEN"
VERDICT_FROZEN = "PHASE4K_EVIDENCE_LEDGER_FROZEN"
VERDICT_BLOCKED = "PHASE4K_EVIDENCE_LEDGER_BLOCKED"
K1_VERDICTS = (VERDICT_FROZEN, VERDICT_BLOCKED)
PREMISE = "PHASE4J_REFERENCE_SCHEMA_AUDITED"
PHASE4J_HEAD = "7616c89542895a88726762069ef482d897b25335"
J0_FREEZE_BLOB = "731ffbc7db9652ad03928c3defdb775ca0b83c8e"
PHASE4J_RESULT_BLOB = "b4ccdff3860c643630a292d16ea4428c6d480e06"
PHASE3Q_VERDICT = "PHASE3Q_XFER2_TRANSFER_FAILED"
PHASE3S_VERDICT = "PHASE3S_REFERENCE_SPECIFICITY_FAILED"
PHASE3T_VERDICT = "PHASE3T_EXACT_REFERENCE_VALIDATED"
CLAIM_BOUNDARY = (
    "Phase-4 documentation-only evidence ledger; no new experiment"
)
PHASE4_CONCLUSION = (
    "Phase 4 established a reproducible real-structured evaluation path, "
    "full-source safety under the frozen protocol, and one prospective "
    "four-arm convenience-sample measurement. The sample provided limited "
    "opportunity to evaluate BITE transformations because operator "
    "activation was sparse."
)
EVIDENCE_CATEGORIES = (
    "mechanism_evidence",
    "real_corpus_safety_evidence",
    "prospective_realstruct2_comparison_evidence",
    "retrospective_measurement_corrections",
)
UNSUPPORTED_CLAIMS = (
    "BITE superiority",
    "general real-world effectiveness",
    "population-level frequency",
    "answer-quality improvement",
    "RAG superiority",
    "production-readiness",
    "statistical superiority",
    "reference-retention advantage",
)
SUPPORTED_CLAIMS = (
    (
        "On the frozen 18-document REALSTRUCT-2 convenience sample, "
        "BITE preserved the frozen safety invariants on all documents."
    ),
    (
        "BITE reduced model-visible tokens relative to adapter_only "
        "on 1 of 18 documents."
    ),
    (
        "On the single matched-budget document, "
        "BITE retained all unique assignment identities while prefix truncation "
        "retained 84.6%."
    ),
    (
        "On the single reference-gold document, "
        "retrospectively corrected reference retention was 1.0 for both BITE and "
        "the matched length arm."
    ),
)
HISTORICAL_VERDICTS = (
    {
        "phase": "3Q",
        "path": "artifacts/phase3q/xfer2-transfer.json",
        "verdict": PHASE3Q_VERDICT,
        "blob": "47ede9cab9619bc66dace5738e1f523b87a35f63",
        "label": "historical failure; later versions repaired mechanisms without erasing this verdict",
    },
    {
        "phase": "3S",
        "path": "artifacts/phase3s/reference-specificity.json",
        "verdict": PHASE3S_VERDICT,
        "blob": "f4bcaae86586c5f738954b78fda8427f3bb78694",
        "label": "historical failure; later versions repaired mechanisms without erasing this verdict",
    },
    {
        "phase": "3T",
        "path": "artifacts/phase3t/exact-reference.json",
        "verdict": PHASE3T_VERDICT,
        "blob": "5892ad925152e8cac32319e243c2e85f67ae2a0c",
        "label": "v3 exact-reference repair; does not erase Phase3S FAILED",
    },
    {
        "phase": "4A",
        "path": "artifacts/phase4a/realstruct-1.json",
        "verdict": "PHASE4A_REAL_CORPUS_FROZEN",
        "blob": "7a7b0834e9b66c599492a06dbe116e773eca6320",
        "label": "REALSTRUCT-1 corpus freeze",
    },
    {
        "phase": "4B",
        "path": "artifacts/phase4b/real-adapter.json",
        "verdict": "PHASE4B_REAL_ADAPTER_READY",
        "blob": "137312ddb8b19396cc48c992ebd75bfc1ed8f585",
        "label": "REALSTRUCT-1 development adapter",
    },
    {
        "phase": "4C",
        "path": "artifacts/phase4c/real-holdout.json",
        "verdict": "PHASE4C_REAL_HOLDOUT_MEASURED",
        "blob": "f344bde69d7f963bb78780e967bc59bf639d2942",
        "label": "REALSTRUCT-1 holdout first-open",
    },
    {
        "phase": "4D",
        "path": "artifacts/phase4d/measurement-semantics.json",
        "verdict": "PHASE4D_MEASUREMENT_SEMANTICS_AUDITED",
        "blob": "5a0060138866ed28fca9cb54b5916b03edebea5c",
        "label": "retrospective measurement-semantics audit",
    },
    {
        "phase": "4E",
        "path": "artifacts/phase4e/full-key-reference.json",
        "verdict": "PHASE4E_FULL_KEY_REFERENCE_VALIDATED",
        "blob": "5f3681439d37dd44df2e74299b3c1ad7fc95bce2",
        "label": "v2 full-key / v4 sensor repair; does not erase Phase3S FAILED",
    },
    {
        "phase": "4F",
        "path": "artifacts/phase4f/prospective-comparison.json",
        "verdict": "PHASE4F_COMPARISON_PROTOCOL_READY",
        "blob": "28bfd7ea8b131b72ba55bb3f84a7126f99c96578",
        "label": "prospective comparison protocol",
    },
    {
        "phase": "4G",
        "path": "artifacts/phase4g/comparison-accounting.json",
        "verdict": "PHASE4G_COMPARISON_ACCOUNTING_VALIDATED",
        "blob": "2635401558d27b2a2781ee53ff7465b877f39b37",
        "label": "comparison accounting v2",
    },
    {
        "phase": "4H",
        "path": "artifacts/phase4h/realstruct-2.json",
        "verdict": "PHASE4H_REALSTRUCT2_PARTIAL",
        "blob": "666eed454c3dba6dd2cfa2a73e5989004380f177",
        "label": "REALSTRUCT-2 corpus freeze PARTIAL",
    },
    {
        "phase": "4H2",
        "path": "artifacts/phase4h2/realstruct-2-augmented.json",
        "verdict": "PHASE4H2_REALSTRUCT2_AUGMENTED_FROZEN",
        "blob": "095bb18a206842c813e8f47c165528743c9f6210",
        "label": "REALSTRUCT-2 two-wave fill to 18/18",
    },
    {
        "phase": "4I",
        "path": "artifacts/phase4i/first-open.json",
        "verdict": "PHASE4I_PROSPECTIVE_COMPARISON_MEASURED",
        "blob": "144a4ca3c2e44d8f0abbd32d0bb8b2f2b5b7b149",
        "label": "prospective four-arm first-open",
    },
    {
        "phase": "4J",
        "path": "artifacts/phase4j/reference-schema-audit.json",
        "verdict": PREMISE,
        "blob": PHASE4J_RESULT_BLOB,
        "label": "retrospective reference-schema compatibility audit",
    },
)
CITED_BLOBS = {
    "artifacts/phase3q/xfer2-transfer.json": "47ede9cab9619bc66dace5738e1f523b87a35f63",
    "artifacts/phase3s/reference-specificity.json": "f4bcaae86586c5f738954b78fda8427f3bb78694",
    "artifacts/phase3t/exact-reference.json": "5892ad925152e8cac32319e243c2e85f67ae2a0c",
    "artifacts/phase4a/realstruct-1.json": "7a7b0834e9b66c599492a06dbe116e773eca6320",
    "artifacts/phase4b/real-adapter.json": "137312ddb8b19396cc48c992ebd75bfc1ed8f585",
    "artifacts/phase4c/real-holdout.json": "f344bde69d7f963bb78780e967bc59bf639d2942",
    "artifacts/phase4d/measurement-semantics.json": "5a0060138866ed28fca9cb54b5916b03edebea5c",
    "artifacts/phase4e/full-key-reference.json": "5f3681439d37dd44df2e74299b3c1ad7fc95bce2",
    "artifacts/phase4f/prospective-comparison.json": "28bfd7ea8b131b72ba55bb3f84a7126f99c96578",
    "artifacts/phase4g/comparison-accounting.json": "2635401558d27b2a2781ee53ff7465b877f39b37",
    "artifacts/phase4h/realstruct-2.json": "666eed454c3dba6dd2cfa2a73e5989004380f177",
    "artifacts/phase4h2/realstruct-2-augmented.json": "095bb18a206842c813e8f47c165528743c9f6210",
    "benchmarks/spec/phase4i-first-open-freeze.json": "260c5ae4847776c33d27ea6718466d1dd814abdf",
    "artifacts/phase4i/first-open.json": "144a4ca3c2e44d8f0abbd32d0bb8b2f2b5b7b149",
    "artifacts/phase4i/arm-rows.json": "d8d43669fa00f94b86e3cd5d26feb6d8072eb99f",
    "artifacts/phase4i/safety.json": "8d3da7283799e291412c177eba339f50bd72f3e7",
    "artifacts/phase4i/model-visible-cost.json": "044325494109fcb0910ec1195bd7836a77d253cf",
    "artifacts/phase4i/paired-unique-identity.json": "eeb2941399d11817bd0d4c16b2737b43d4344d0b",
    "artifacts/phase4i/paired-reference-retention.json": "455b8d3e95ced9c17e9d096f7dc334fe480d14c3",
    "artifacts/phase4i/mechanism-diagnostic.json": "3500b26b1f0fe2c61301b97656e5628c4dae7004",
    "benchmarks/spec/phase4j-reference-schema-freeze.json": J0_FREEZE_BLOB,
    "artifacts/phase4j/reference-schema-audit.json": PHASE4J_RESULT_BLOB,
    "artifacts/phase4j/legacy-vs-corrected-paired-reference.json": (
        "9f01369f8542155afc65eee31dfcaa74c9506349"
    ),
    "artifacts/phase4j/corrected-atom-aware.json": "bf6054588f36b97e3d823112a54ac129be4e94d1",
    "artifacts/phase4j/sensor-replay.json": "e948e468b8c74ea38543a23462f91812e33c5e84",
    "artifacts/phase4j/annotation-compatibility.json": (
        "018c591efcbcac2ba0d76d733dd319508c98a629"
    ),
    "src/bite_eval/atom_aware_reference.py": "1c24b419cba83adb205eb1bce16d60ad451ffa17",
}

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase4k-evidence-ledger-freeze.json"


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
        "documentation_only": True,
        "no_new_experiment": True,
        "premise": PREMISE,
        "phase4j_head_sha": PHASE4J_HEAD,
        "j0_freeze_blob": J0_FREEZE_BLOB,
        "phase4j_result_blob": PHASE4J_RESULT_BLOB,
        "p3f_evaluation_holdout_used": False,
        "no_p3f_result_statement": True,
        "no_xfer3": True,
        "no_arm_rerun": True,
        "no_tokenizer_execution": True,
        "no_sensor_replay": True,
        "no_bite_retune": True,
        "no_threshold_change": True,
        "no_sensor_change": True,
        "no_policy_change": True,
        "no_operator_change": True,
        "no_baseline_change": True,
        "no_corpus_acquisition": True,
        "no_phase4a_to_4j_rewrite": True,
        "no_merge": True,
        "no_winner_score": True,
        "do_not_pool_evidence_categories": True,
        "evidence_categories": list(EVIDENCE_CATEGORIES),
        "historical_verdicts": [dict(row) for row in HISTORICAL_VERDICTS],
        "phase3q_remains": PHASE3Q_VERDICT,
        "phase3s_remains": PHASE3S_VERDICT,
        "prospective_realstruct2_facts": {
            "primary_documents": 18,
            "four_arms_rows": 72,
            "raw_reconstruction_exact": "72/72",
            "bite_safety": "18/18",
            "planner_integrity": "18/18",
            "bite_model_visible_reduction_incidence": "1/18",
            "not_a_win_rate": True,
            "matched_budget_unique_identity": {
                "n": 1,
                "n_prominence": "n=1",
                "source_id": "rs2-ini-genicam-harvesters_gui",
                "BITE_v5": 1.0,
                "length_pi_v1": 0.8461538461538461,
                "delta": 0.15384615384615385,
            },
            "historical_reference_retention": {
                "n": 0,
                "status": "not_observed",
                "reason": "legacy reader schema incompatibility",
            },
            "mechanism": {
                "route_empty": "17/18",
                "reduce_v2": "1/18",
                "gate_incidence": "4/18",
                "gate_is_not_successful_transformation_incidence": True,
            },
        },
        "retrospective_corrections": {
            "not_a_new_first_open": True,
            "reference_retention": {
                "n": 1,
                "source_id": "rs2-ini-ahuacate-pve-medialab",
                "BITE_v5": 1.0,
                "length_pi_v1": 1.0,
                "delta": 0.0,
                "tie": 1,
            },
            "reference_sensor_ahuacate": {
                "precision": 1.0,
                "recall": 1.0,
                "unadjudicated": 0,
                "do_not_generalize_from_one_gold_document": True,
            },
        },
        "supported_claims": list(SUPPORTED_CLAIMS),
        "unsupported_claims": list(UNSUPPORTED_CLAIMS),
        "negative_null_evidence": [
            "Natural convenience sample produced sparse transformation: 17/18 documents had no BITE operator sequence.",
            "Reference-retention comparison was effectively n=1.",
            "Matched-budget evidence comparison was effectively n=1.",
            "These are results, not protocol failures.",
        ],
        "phase4_conclusion": PHASE4_CONCLUSION,
        "claim_boundary": CLAIM_BOUNDARY,
        "cited_blobs": dict(CITED_BLOBS),
        "k1_verdicts": list(K1_VERDICTS),
        "verdict_rule": {
            VERDICT_FROZEN: (
                "Phase4A-4J historical verdicts preserved; all cited blob SHAs "
                "verified; prospective and retrospective evidence clearly "
                "separated; n values shown beside every comparative result; "
                "no new execution; no retune; no merge; p3f unopened; no "
                "superiority/generalization claim"
            ),
            VERDICT_BLOCKED: (
                "historical verdict drifted, cited blob SHA drifted, evidence "
                "categories pooled, or a forbidden claim/execution flag is set"
            ),
        },
    }


def validate_phase4k_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("K0 protocol not frozen")
    if doc.get("premise") != PREMISE:
        errs.append("Phase 4J premise drifted")
    if doc.get("documentation_only") is not True or doc.get("no_new_experiment") is not True:
        errs.append("ledger must stay documentation-only")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("no_p3f_result_statement") is not True:
        errs.append("p3f result statement must stay forbidden")
    if doc.get("no_arm_rerun") is not True or doc.get("no_tokenizer_execution") is not True:
        errs.append("arm/tokenizer execution must stay forbidden")
    if doc.get("no_sensor_replay") is not True:
        errs.append("sensor replay must stay forbidden")
    if doc.get("no_bite_retune") is not True or doc.get("no_threshold_change") is not True:
        errs.append("BITE/threshold change must stay forbidden")
    if doc.get("no_phase4a_to_4j_rewrite") is not True:
        errs.append("Phase 4A-4J rewrite must stay forbidden")
    if doc.get("no_merge") is not True:
        errs.append("merge must stay forbidden")
    if doc.get("no_winner_score") is not True:
        errs.append("winner score must stay forbidden")
    if list(doc.get("evidence_categories") or []) != list(EVIDENCE_CATEGORIES):
        errs.append("evidence categories drifted")
    if doc.get("do_not_pool_evidence_categories") is not True:
        errs.append("evidence categories must stay unpooled")
    if doc.get("phase3q_remains") != PHASE3Q_VERDICT:
        errs.append("Phase3Q FAILED verdict erased")
    if doc.get("phase3s_remains") != PHASE3S_VERDICT:
        errs.append("Phase3S FAILED verdict erased")
    if doc.get("phase4_conclusion") != PHASE4_CONCLUSION:
        errs.append("Phase 4 conclusion drifted")
    if list(doc.get("unsupported_claims") or []) != list(UNSUPPORTED_CLAIMS):
        errs.append("unsupported claims drifted")
    facts = doc.get("prospective_realstruct2_facts") or {}
    if not isinstance(facts, Mapping):
        errs.append("prospective facts missing")
    else:
        ident = facts.get("matched_budget_unique_identity") or {}
        if not isinstance(ident, Mapping) or ident.get("n") != 1:
            errs.append("matched-budget n=1 not locked")
        hist = facts.get("historical_reference_retention") or {}
        if not isinstance(hist, Mapping) or hist.get("n") != 0:
            errs.append("Phase4I historical reference n=0 not locked")
        if facts.get("not_a_win_rate") is not True:
            errs.append("reduction incidence must not be called win rate")
    retro = doc.get("retrospective_corrections") or {}
    if not isinstance(retro, Mapping) or retro.get("not_a_new_first_open") is not True:
        errs.append("retrospective corrections must not be a new first-open")
    for row in HISTORICAL_VERDICTS:
        path = str(row["path"])
        payload = json.loads((_REPO / path).read_text(encoding="utf-8"))
        if payload.get("verdict") != row["verdict"]:
            errs.append(f"historical verdict drifted: {row['phase']}")
        if _git_blob(path) != row["blob"]:
            errs.append(f"historical result blob drifted: {path}")
    for path, expected in CITED_BLOBS.items():
        if _git_blob(path) != expected:
            errs.append(f"cited blob drifted: {path}")
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
    print(freeze["verdict"], "premise", freeze["premise"])
    print("errors", validate_phase4k_freeze(freeze))
