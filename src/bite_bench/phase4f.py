"""Phase 4F F0 prospective comparison protocol.

Freezes arms, tokenizer identity, planes, serializer, and metrics before
any baseline implementation or comparison run. Does not implement
length_pi_v1, token counting, or REALSTRUCT-2. Does not retune BITE.
Does not open p3f.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4b import DEV_SOURCE_IDS, EVAL_SOURCE_IDS
from bite_bench.phase4d import AUDIT_SOURCE_IDS

SCHEMA_ID = "bitebench-phase4f-prospective-comparison-freeze/v0.1"
REVISION = "phase4f-prospective-comparison-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE4F_COMPARISON_PROTOCOL_FROZEN"
VERDICT_READY = "PHASE4F_COMPARISON_PROTOCOL_READY"
VERDICT_PARTIAL = "PHASE4F_COMPARISON_PROTOCOL_PARTIAL"
VERDICT_BLOCKED = "PHASE4F_COMPARISON_PROTOCOL_BLOCKED"
F1_VERDICTS = (VERDICT_READY, VERDICT_PARTIAL, VERDICT_BLOCKED)
PREMISE = "PHASE4E_FULL_KEY_REFERENCE_VALIDATED"
PHASE4C_VERDICT = "PHASE4C_REAL_HOLDOUT_MEASURED"
PHASE4D_VERDICT = "PHASE4D_MEASUREMENT_SEMANTICS_AUDITED"
PHASE3S_VERDICT = "PHASE3S_REFERENCE_SPECIFICITY_FAILED"
PHASE3Q_VERDICT = "PHASE3Q_XFER2_TRANSFER_FAILED"
PHASE3T_VERDICT = "PHASE3T_EXACT_REFERENCE_VALIDATED"
PHASE4E_HEAD = "03bc883b1e3ef0d1ab0c0332f544ce8c82613bfd"
E0_COMMIT_SHA = "9349087ab4fd5bb095a4904646243665c4464b52"
E0_FREEZE_BLOB = "911a22ff9d210de05ae799fce5c90f09c65c1029"
PHASE4E_RESULT_BLOB = "5f3681439d37dd44df2e74299b3c1ad7fc95bce2"
IDENTITY_V2_BLOB = "3524097e33a123ad4180ee4818dbf8d4ab980627"
DISPERSION_V4_BLOB = "e2dffa51e07af160ff64ab1d2b3983fac69f07be"
POLICY_V5_BLOB = "50180c1254efcc0d082c2cb36d2738200af9f8f5"
ADAPTER_BLOB = "2ef34b0486efb4badcdc29402ef5a9c4dc359565"
LOCKED_T_HIGH = 4
ARMS = ("raw_full", "adapter_only", "length_pi_v1", "BITE_v5")
CLAIM_BOUNDARY = "prospective comparison protocol development only"
TOKENIZER_REPO = "zai-org/GLM-4.5"
TOKENIZER_REVISION = "cbb2c7cfb52fa128a9660cb1a7a78e017899e115"
TOKENIZER_LIBRARY = "transformers==4.54.0"
TOKENIZER_JSON_SHA256 = "9340665016419c825c4bdabbcc9acc43b7ca2c68ce142724afa829abb1be5efd"
BITE_CANDIDATE = {
    "src/bite_ingestion/profilers/reference_identity_v2.py": IDENTITY_V2_BLOB,
    "src/bite_ingestion/profilers/dependency_dispersion_v4.py": DISPERSION_V4_BLOB,
    "src/bite_ingestion/policies/conditional_texture_policy_v5.py": POLICY_V5_BLOB,
    "artifacts/phase4e/full-key-reference.json": PHASE4E_RESULT_BLOB,
    "benchmarks/spec/phase4e-full-key-reference-freeze.json": E0_FREEZE_BLOB,
    "src/bite_ingestion/adapters/realstruct1_adapter_v1.py": ADAPTER_BLOB,
}
LOCKED_BLOBS = {
    **BITE_CANDIDATE,
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
    "src/bite_ingestion/operators/reduce_v2.py": "d4bafba7dfdd048a0ccad404a8f706202e2157b5",
    "src/bite_ingestion/operators/untangle.py": "2951b7542f96674930e750e438891ca772b46896",
    "src/bite_ingestion/operators/integrate.py": "68e34becd80e7e803f511ec57ea7a23c2aaa1240",
    "src/bite_eval/composition_safety_v2.py": "85560279375b30f737eb3825cce72373be70488e",
    "artifacts/phase4c/real-holdout.json": "f344bde69d7f963bb78780e967bc59bf639d2942",
    "artifacts/phase4c/reference-coverage.json": "9d0fd974d72d923f97f7c9dc6f325d7ea1e8a032",
    "artifacts/phase4c/full-source-provenance.json": "b22d290d1d8f89276c923439b62f5ae1102a9fbb",
    "artifacts/phase4d/atom-aware-reference.json": "8092ad6a61c9407b892fcb42fec5dc89f6fe7348",
    "artifacts/phase4d/measurement-semantics.json": "5a0060138866ed28fca9cb54b5916b03edebea5c",
}

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase4f-prospective-comparison-freeze.json"
PHASE4E_PATH = _REPO / "artifacts" / "phase4e" / "full-key-reference.json"
PHASE4C_PATH = _REPO / "artifacts" / "phase4c" / "real-holdout.json"
PHASE4D_PATH = _REPO / "artifacts" / "phase4d" / "measurement-semantics.json"
PHASE3T_PATH = _REPO / "artifacts" / "phase3t" / "exact-reference.json"
PHASE3S_PATH = _REPO / "artifacts" / "phase3s" / "reference-specificity.json"
PHASE3Q_PATH = _REPO / "artifacts" / "phase3q" / "xfer2-transfer.json"


def freeze_manifest() -> dict[str, Any]:
    return {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "verdict": PROTOCOL_FROZEN,
        "paid_api": False,
        "offline_core_tests": True,
        "research_conclusion": False,
        "premise": PREMISE,
        "phase4e_head_sha": PHASE4E_HEAD,
        "e0_commit_sha": E0_COMMIT_SHA,
        "e0_freeze_blob": E0_FREEZE_BLOB,
        "phase4e_result_blob": PHASE4E_RESULT_BLOB,
        "phase4c_verdict": PHASE4C_VERDICT,
        "phase4d_verdict": PHASE4D_VERDICT,
        "phase4e_verdict": PREMISE,
        "phase3t_verdict": PHASE3T_VERDICT,
        "phase3s_verdict": PHASE3S_VERDICT,
        "phase3q_verdict": PHASE3Q_VERDICT,
        "p3f_evaluation_holdout_used": False,
        "no_xfer3": True,
        "no_realstruct2": True,
        "no_realstruct2_acquisition": True,
        "no_bite_retune_after_f0": True,
        "no_winner_score": True,
        "no_threshold_search": True,
        "t_high_reference": LOCKED_T_HIGH,
        "adapter_id": "realstruct1_adapter_v1",
        "adapter_blob": ADAPTER_BLOB,
        "bite_candidate": {
            "reference_identity_v2": IDENTITY_V2_BLOB,
            "dependency_dispersion_v4": DISPERSION_V4_BLOB,
            "conditional_texture_policy_v5": POLICY_V5_BLOB,
            "planner": "projected_actionability_plan_v1",
            "operators": ["UNTANGLE", "REDUCE_v2", "INTEGRATE"],
            "t_high_reference": LOCKED_T_HIGH,
        },
        "locked_blobs": dict(LOCKED_BLOBS),
        "tokenizer_reference": {
            "repo": TOKENIZER_REPO,
            "revision": TOKENIZER_REVISION,
            "library": TOKENIZER_LIBRARY,
            "tokenizer_json_sha256": TOKENIZER_JSON_SHA256,
            "relationship_to_provider_model": (
                "GLM-4.5 family reference tokenizer. Exact hosted "
                "glm-4.5-flash tokenizer equivalence is not asserted here."
            ),
            "primary_cost_unit": "reference-tokenizer payload tokens",
            "forbidden_cost_metric": "local_char4_proxy",
        },
        "planes": {
            "model_visible": "text that would actually be supplied downstream",
            "audit_recovery": "source document, provenance, R, recoverable omitted material",
            "do_not_count_audit_as_model_visible": True,
            "report_audit_overhead_separately": True,
        },
        "serializer": {
            "structured_arms": "source-exact routing unit texts in adapter order, joined by newline",
            "adapter_routing_contract": "Phase4B source-exact routing units",
            "bite_visible": "post-policy routing visible units only",
            "do_not_merge_passthrough_into_bite_visible": True,
            "full_source_reconstruction": "audit/safety only",
        },
        "arms": {
            "raw_full": {
                "role": "identity reference, not a competitor winner",
                "model_visible": "entire original decoded source document",
                "transformation": False,
            },
            "adapter_only": {
                "model_visible": "all routing assignment units",
                "policy": False,
                "planner": False,
                "operator": False,
            },
            "length_pi_v1": {
                "input": "exact adapter_only model-visible payload",
                "inspects": ["token length", "position"],
                "forbidden_inspect": [
                    "keys",
                    "values",
                    "reference identities",
                    "duplicates",
                    "anomalies",
                    "joinability",
                    "BITE features",
                    "gold annotations",
                ],
                "budget": "BITE model-visible payload tokens for the same document",
                "budget_matching_is_not_tuning": True,
                "if_bite_tokens_ge_adapter_only": "return full adapter_only; do not pad",
                "selection": "longest source-exact prefix that fits the token budget",
                "offset_mapping": True,
                "never_rewrite_retained_text": True,
                "sidecar": "omitted source-exact suffix; not model-visible",
            },
            "BITE_v5": {
                "model_visible": "post-policy routing visible units",
                "audit_recovery": "R / provenance / original source plane",
            },
        },
        "arm_order": list(ARMS),
        "metrics": {
            "primary_for_future_realstruct2": [
                "model_visible_tokens",
                "model_visible_chars",
                "audit_sidecar_bytes",
                "audit_sidecar_tokens",
                "full_source_recoverable",
                "provenance completeness / traceability where applicable",
            ],
            "visible_reference_retention": {
                "not_sensor_accuracy": True,
                "gold": "(source_line, NAME, dest_line)",
                "retained_iff": "both source and destination assignment records completely model-visible",
                "gold_zero": "NA",
            },
            "unique_assignment_identity_retention": {
                "identity": "(key, value)",
                "collapse_source_duplicates_in_denominator": True,
                "retained_iff": "at least one complete visible representative",
            },
            "duplicate_diagnostic": [
                "source_exact_duplicate_groups",
                "visible_duplicate_excess",
                "duplicate_groups_collapsed",
            ],
            "bite_sensor_capability_separate": [
                "atom-aware reference precision",
                "atom-aware reference recall",
                "unadjudicated extra edges",
            ],
        },
        "safety": {
            "BITE_v5": [
                "full source recoverability",
                "provenance_completeness == 1",
                "lineage_recall == 1",
                "silent_loss == 0",
                "conservation_untraced == []",
                "unsupported loss == 0",
                "no unrelated overmerge",
            ],
            "length_pi_v1": [
                "visible prefix traceable to source",
                "dropped suffix recoverable exactly",
                "visible + sidecar reconstruct original adapter payload exactly",
            ],
            "do_not_declare_bite_better_for_different_safety_mechanisms": True,
        },
        "realstruct1_development": {
            "role": "post-open implementation/test of tokenizer, serializer, length_pi_v1, sidecar, metrics",
            "not_holdout": True,
            "not_confirmatory": True,
            "not_generalization": True,
            "not_for_retuning": True,
            "source_ids": list(AUDIT_SOURCE_IDS),
            "dev_source_ids": list(DEV_SOURCE_IDS),
            "eval_source_ids": list(EVAL_SOURCE_IDS),
        },
        "forbidden": [
            "single aggregate score",
            "weighted overall ranking",
            "post-hoc best arm",
            "BITE superiority verdict",
            "REALSTRUCT-2 acquisition",
            "BITE sensor/policy/operator/threshold tuning after F0",
        ],
        "f1_verdicts": list(F1_VERDICTS),
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "REALSTRUCT-2 evidence",
            "confirmatory comparison",
            "real-world generalization",
            "BITE superiority",
        ],
    }


def validate_phase4f_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("F0 protocol not frozen")
    if doc.get("premise") != PREMISE:
        errs.append("Phase 4E premise drifted")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("no_realstruct2") is not True or doc.get("no_realstruct2_acquisition") is not True:
        errs.append("REALSTRUCT-2 must stay untouched")
    if doc.get("no_bite_retune_after_f0") is not True:
        errs.append("BITE retune after F0 must stay forbidden")
    if doc.get("no_winner_score") is not True:
        errs.append("winner score must stay forbidden")
    if doc.get("t_high_reference") != LOCKED_T_HIGH:
        errs.append("T_high drifted")
    if list(doc.get("arm_order") or []) != list(ARMS):
        errs.append("arm order drifted")
    raw_tok = doc.get("tokenizer_reference")
    tok: Mapping[str, Any] = raw_tok if isinstance(raw_tok, Mapping) else {}
    if tok.get("tokenizer_json_sha256") != TOKENIZER_JSON_SHA256:
        errs.append("tokenizer hash drifted")
    if tok.get("primary_cost_unit") != "reference-tokenizer payload tokens":
        errs.append("primary cost unit drifted")
    if tok.get("forbidden_cost_metric") != "local_char4_proxy":
        errs.append("char4 proxy must stay forbidden as prospective cost")
    if (doc.get("planes") or {}).get("do_not_count_audit_as_model_visible") is not True:
        errs.append("plane separation drifted")
    if json.loads(PHASE4E_PATH.read_text(encoding="utf-8")).get("verdict") != PREMISE:
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
    if (_REPO / "corpora" / "realstruct-2").exists() or (_REPO / "artifacts" / "phase4f-realstruct2").exists():
        errs.append("REALSTRUCT-2 material present")
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
    print("errors", validate_phase4f_freeze(freeze))
