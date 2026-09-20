"""Phase 4I I0 REALSTRUCT-2 prospective four-arm first-open protocol.

Freezes the execution harness, locked corpus, tokenizer identity, arms,
and the Phase 4H H0 analysis contract before any REALSTRUCT-2 tokenizer
or arm execution. Does not run arms. Does not open p3f. Does not retune
BITE or length_pi_v1. Does not acquire more documents.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4f import (
    TOKENIZER_JSON_SHA256,
    TOKENIZER_LIBRARY,
    TOKENIZER_REPO,
    TOKENIZER_REVISION,
)
from bite_bench.phase4h import freeze_manifest as phase4h_freeze_manifest
from bite_bench.phase4h2 import LOCKED_BLOBS as PHASE4H2_LOCKED_BLOBS
from bite_bench.phase4h2 import WAVE1_PRIMARY_IDS

SCHEMA_ID = "bitebench-phase4i-first-open-freeze/v0.1"
REVISION = "phase4i-first-open-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE4I_EXECUTION_PROTOCOL_FROZEN"
VERDICT_MEASURED = "PHASE4I_PROSPECTIVE_COMPARISON_MEASURED"
VERDICT_FAILED = "PHASE4I_PROSPECTIVE_COMPARISON_FAILED"
VERDICT_BLOCKED = "PHASE4I_PROSPECTIVE_COMPARISON_BLOCKED"
I1_VERDICTS = (VERDICT_MEASURED, VERDICT_FAILED, VERDICT_BLOCKED)
PREMISE = "PHASE4H2_REALSTRUCT2_AUGMENTED_FROZEN"
PHASE4H2_HEAD = "461ae71e646728018890e87e5d0cada5af25906e"
H3_FREEZE_BLOB = "b3823492dc987b0c2489fa8785cd0b8d813f4b53"
EXTENSION_POOL_BLOB = "b8e41a93ba38baabced1b62b5cb8f4a041a54e53"
PHASE4H2_RESULT_BLOB = "095bb18a206842c813e8f47c165528743c9f6210"
AUGMENTED_MANIFEST_BLOB = "0180ebf385beb6870a8c5a7ae860deedc0b107f4"
AUGMENTED_ANNOTATIONS_BLOB = "dbb0f20bef4d76dd1d8bfc8b3edee946ad088eb7"
AUGMENTED_LICENSES_BLOB = "6fb39a036501f54dea137d54d274ce5ea28b0701"
WAVE_PROVENANCE_BLOB = "f3f2743035480abf36c4f872ff1327b139676f5c"
TOKENIZER_BLOB = "6f95df67723fe8ee2e572e589f6ca3e864de37bc"
LENGTH_PI_V1_BLOB = "2de74b1b21c466aaa20858a2066e011f14a0fe20"
RECOVERY_BUNDLE_BLOB = "d0e974bcb2cbedd22ba3c6396daa345a178aa208"
VISIBILITY_V2_BLOB = "32c3c84ce14fa2add582145b0069b58328e4caf1"
IDENTITY_V2_BLOB = "3524097e33a123ad4180ee4818dbf8d4ab980627"
DISPERSION_V4_BLOB = "e2dffa51e07af160ff64ab1d2b3983fac69f07be"
POLICY_V5_BLOB = "50180c1254efcc0d082c2cb36d2738200af9f8f5"
LOCKED_T_HIGH = 4
ARMS = ("raw_full", "adapter_only", "length_pi_v1", "BITE_v5")
N_PRIMARY = 18
CLAIM_BOUNDARY = (
    "prospective four-arm measurement on the frozen two-wave "
    "REALSTRUCT-2 convenience sample"
)
PRIMARY_IDS = (
    "rs2-dotenv-ronakmaheshwari-capital",
    "rs2-dotenv-theafroofdoom-omegaflowey-minecraft-remastered",
    "rs2-dotenv-luizomf-dockerswarmp1",
    "rs2-dotenv-tradermonty-hermes-trading-research-agent-work-package",
    "rs2-props-edson-a-soares-poco_restful_webservice",
    "rs2-props-aterai-java-swing-tips",
    "rs2-props-oraopensource-apexbackup",
    "rs2-ini-ahuacate-pve-medialab",
    "rs2-ini-genicam-harvesters_gui",
    "rs2-ini-beluganos-beluganos",
    "rs2-dotenv-s1nro-granatapfel",
    "rs2-dotenv-johnsonchin1009-pulse",
    "rs2-props-redpill-linpro-alfresco-jobs",
    "rs2-props-xzel23-utility",
    "rs2-props-aterai-kotlin-swing-tips",
    "rs2-ini-jphutchins-pyavreceiver",
    "rs2-ini-astrarium-astrarium",
    "rs2-ini-waltenne-ubuntu-post-install",
)
LOCKED_PHASE4H2 = {
    "benchmarks/spec/phase4h2-acquisition-extension-freeze.json": H3_FREEZE_BLOB,
    "artifacts/phase4h2/extension-pool.json": EXTENSION_POOL_BLOB,
    "artifacts/phase4h2/realstruct-2-augmented.json": PHASE4H2_RESULT_BLOB,
    "corpora/realstruct-2/augmented-manifest.json": AUGMENTED_MANIFEST_BLOB,
    "corpora/realstruct-2/augmented-annotations.json": AUGMENTED_ANNOTATIONS_BLOB,
    "corpora/realstruct-2/augmented-licenses.json": AUGMENTED_LICENSES_BLOB,
    "corpora/realstruct-2/wave-provenance.json": WAVE_PROVENANCE_BLOB,
    "src/bite_eval/reference_tokenizer.py": TOKENIZER_BLOB,
    "src/bite_eval/length_pi_v1.py": LENGTH_PI_V1_BLOB,
    "src/bite_eval/recovery_bundle_v1.py": RECOVERY_BUNDLE_BLOB,
    "src/bite_eval/visibility_metrics_v2.py": VISIBILITY_V2_BLOB,
    "src/bite_ingestion/profilers/reference_identity_v2.py": IDENTITY_V2_BLOB,
    "src/bite_ingestion/profilers/dependency_dispersion_v4.py": DISPERSION_V4_BLOB,
    "src/bite_ingestion/policies/conditional_texture_policy_v5.py": POLICY_V5_BLOB,
}
LOCKED_BLOBS = {**PHASE4H2_LOCKED_BLOBS, **LOCKED_PHASE4H2}

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase4i-first-open-freeze.json"
PHASE4H2_RESULT = _REPO / "artifacts" / "phase4h2" / "realstruct-2-augmented.json"
AUGMENTED_MANIFEST = _REPO / "corpora" / "realstruct-2" / "augmented-manifest.json"
HISTORICAL_MANIFEST = _REPO / "corpora" / "realstruct-2" / "manifest.json"
PHASE4H_PATH = _REPO / "benchmarks" / "spec" / "phase4h-realstruct2-freeze.json"


def _git_blob(path: str) -> str:
    return subprocess.check_output(["git", "hash-object", path], cwd=_REPO, text=True).strip()


def analysis_contract() -> dict[str, Any]:
    return dict(phase4h_freeze_manifest()["future_phase4i_analysis"])


def planned_preflight_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "p4i-pass-through",
            "family": "pass_through",
            "mode": "operators",
            "records": [["west_alpha", "ridge_one"], ["east_beta", "ridge_two"]],
            "gold_edges": [],
        },
        {
            "case_id": "p4i-reduce-duplicate",
            "family": "reduce_duplicate",
            "mode": "operators",
            "records": [["copy_key", "same_val"], ["copy_key", "same_val"]],
            "gold_edges": [],
        },
        {
            "case_id": "p4i-integrate-2way",
            "family": "integrate_2way",
            "mode": "operators",
            "records": [
                ["join_left", "one id=join_p4i"],
                ["join_right", "two id=join_p4i"],
            ],
            "gold_edges": [],
        },
        {
            "case_id": "p4i-ref-gold",
            "family": "reference_gold",
            "mode": "operators",
            "records": [["ORIGIN", "plain_origin"], ["USE", "${ORIGIN}"]],
            "gold_edges": [{"name": "ORIGIN", "source_line": 1, "dest_lines": [2]}],
        },
        {
            "case_id": "p4i-untangle-quarantine",
            "family": "untangle_quarantine",
            "mode": "operators",
            "records": [["keep_ok", "plain_weft"], ["drop_bad", "shuttle jam FATAL"]],
            "gold_edges": [],
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
        "phase4h2_head_sha": PHASE4H2_HEAD,
        "h3_freeze_blob": H3_FREEZE_BLOB,
        "extension_pool_blob": EXTENSION_POOL_BLOB,
        "phase4h2_result_blob": PHASE4H2_RESULT_BLOB,
        "augmented_manifest_blob": AUGMENTED_MANIFEST_BLOB,
        "augmented_annotations_blob": AUGMENTED_ANNOTATIONS_BLOB,
        "augmented_licenses_blob": AUGMENTED_LICENSES_BLOB,
        "wave_provenance_blob": WAVE_PROVENANCE_BLOB,
        "p3f_evaluation_holdout_used": False,
        "no_xfer3": True,
        "no_more_acquisition": True,
        "no_license_change": True,
        "no_source_replacement": True,
        "no_secondary_corpus_addition": True,
        "no_bite_retune": True,
        "no_length_pi_retune": True,
        "no_harness_modification_after_i0": True,
        "no_realstruct2_tokenizer_before_i0": True,
        "no_realstruct2_arm_before_i0": True,
        "no_winner_score": True,
        "no_wave1_vs_wave2_outcome": True,
        "do_not_use_historical_10_document_manifest": True,
        "t_high_reference": LOCKED_T_HIGH,
        "arms": list(ARMS),
        "n_primary": N_PRIMARY,
        "primary_ids": list(PRIMARY_IDS),
        "wave1_primary_ids": list(WAVE1_PRIMARY_IDS),
        "primary_source": "corpora/realstruct-2/augmented-manifest.json",
        "tokenizer_reference": {
            "repo": TOKENIZER_REPO,
            "revision": TOKENIZER_REVISION,
            "library": TOKENIZER_LIBRARY,
            "tokenizer_json_sha256": TOKENIZER_JSON_SHA256,
            "primary_cost_unit": "reference-tokenizer payload tokens",
            "forbidden_cost_metric": "local_char4_proxy",
        },
        "comparison_implementation": {
            "reference_tokenizer.py": TOKENIZER_BLOB,
            "length_pi_v1.py": LENGTH_PI_V1_BLOB,
            "recovery_bundle_v1.py": RECOVERY_BUNDLE_BLOB,
            "visibility_metrics_v2.py": VISIBILITY_V2_BLOB,
            "reference_identity_v2": IDENTITY_V2_BLOB,
            "dependency_dispersion_v4": DISPERSION_V4_BLOB,
            "conditional_texture_policy_v5": POLICY_V5_BLOB,
            "adapter_planner_operators_t_high": "inherit exact Phase4F/H2 locked values",
        },
        "preflight_allowed": ["fresh synthetic unit fixtures", "REALSTRUCT-1"],
        "preflight_forbidden": ["REALSTRUCT-2 tokenizer", "REALSTRUCT-2 arms"],
        "planned_preflight_cases": planned_preflight_cases(),
        "first_open": {
            "documents": "all 18 frozen primary documents exactly once",
            "no_source_exclusion_after_start": True,
            "no_per_document_rerun_to_replace_result": True,
            "no_same_pr_arm_policy_metric_repair_after_results": True,
        },
        "analysis_contract": analysis_contract(),
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "representative real-world sample",
            "population generalization",
            "downstream answer-quality evidence",
            "BITE superiority",
        ],
        "locked_blobs": dict(LOCKED_BLOBS),
        "i1_verdicts": list(I1_VERDICTS),
        "verdict_rule": {
            VERDICT_MEASURED: (
                "18/18 frozen primary executed; four arms completed; tokenizer lock "
                "verified; raw reconstruction exact; BITE safety invariants pass; "
                "planner integrity passes; frozen summaries emitted; locked corpus/"
                "components unchanged; no same-PR retune; p3f unopened. Performance "
                "does not determine this verdict."
            ),
            VERDICT_FAILED: (
                "execution completes but a frozen safety / reconstruction / planner "
                "invariant fails, or an arm cannot complete. Do not repair in this PR."
            ),
            VERDICT_BLOCKED: (
                "pre-first-open lock drift, corpus mutation, tokenizer mismatch, "
                "arm/metric mutation, REALSTRUCT-2 leakage before I0, or protocol "
                "violation"
            ),
        },
    }


def validate_phase4i_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("I0 protocol not frozen")
    if doc.get("premise") != PREMISE:
        errs.append("Phase 4H2 premise drifted")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("no_realstruct2_tokenizer_before_i0") is not True:
        errs.append("REALSTRUCT-2 tokenizer must stay forbidden before I0")
    if doc.get("no_realstruct2_arm_before_i0") is not True:
        errs.append("REALSTRUCT-2 arms must stay forbidden before I0")
    if doc.get("no_winner_score") is not True:
        errs.append("winner score must stay forbidden")
    if doc.get("no_wave1_vs_wave2_outcome") is not True:
        errs.append("wave outcome comparison must stay forbidden")
    if doc.get("do_not_use_historical_10_document_manifest") is not True:
        errs.append("historical 10-document manifest fallback must stay forbidden")
    if doc.get("no_harness_modification_after_i0") is not True:
        errs.append("post-I0 harness modification must stay forbidden")
    if doc.get("t_high_reference") != LOCKED_T_HIGH:
        errs.append("T_high drifted")
    if list(doc.get("arms") or []) != list(ARMS):
        errs.append("arm order drifted")
    if list(doc.get("primary_ids") or []) != list(PRIMARY_IDS):
        errs.append("primary IDs drifted")
    if int(doc.get("n_primary") or 0) != N_PRIMARY:
        errs.append("n_primary drifted")
    raw_tok = doc.get("tokenizer_reference")
    tok: Mapping[str, Any] = raw_tok if isinstance(raw_tok, Mapping) else {}
    if tok.get("tokenizer_json_sha256") != TOKENIZER_JSON_SHA256:
        errs.append("tokenizer hash drifted")
    if tok.get("forbidden_cost_metric") != "local_char4_proxy":
        errs.append("char4 proxy must stay forbidden")
    if doc.get("analysis_contract") != analysis_contract():
        errs.append("Phase 4H H0 analysis contract drifted")
    h2 = json.loads(PHASE4H2_RESULT.read_text(encoding="utf-8"))
    if h2.get("verdict") != PREMISE:
        errs.append("Phase 4H2 result rewritten")
    if int(h2.get("n_primary") or 0) != N_PRIMARY:
        errs.append("Phase 4H2 primary count drifted")
    aug = json.loads(AUGMENTED_MANIFEST.read_text(encoding="utf-8"))
    aug_ids = [
        str(row["source_id"])
        for row in aug.get("sources") or []
        if isinstance(row, Mapping) and row.get("stratum") == "primary"
    ]
    if aug_ids != list(PRIMARY_IDS):
        errs.append("augmented-manifest primary IDs drifted")
    historical = json.loads(HISTORICAL_MANIFEST.read_text(encoding="utf-8"))
    if int(historical.get("n_primary") or len(historical.get("sources") or [])) != 10:
        errs.append("historical Phase4H 10-document manifest rewritten")
    h0 = json.loads(PHASE4H_PATH.read_text(encoding="utf-8"))
    if h0.get("future_phase4i_analysis") != analysis_contract():
        errs.append("committed H0 analysis contract drifted")
    for path, expected in LOCKED_PHASE4H2.items():
        if _git_blob(path) != expected:
            errs.append(f"frozen blob drifted: {path}")
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
    print(freeze["verdict"], "n_primary", freeze["n_primary"])
    print("errors", validate_phase4i_freeze(freeze))
