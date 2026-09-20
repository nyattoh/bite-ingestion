"""Phase 4H2 H3 REALSTRUCT-2 acquisition-extension protocol.

Freezes extension-pool coverage only. Does not change Phase 4H queries,
eligibility, annotation, quotas, or the Phase 4I analysis contract.
Does not search GitHub. Does not open new file contents. Does not run
arms or tokenizers. Does not rewrite Phase 4H artifacts. Does not open p3f.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4h import (
    ALLOWED_SPDX,
    DISCOVERY_QUERIES,
    FAMILIES,
    FORBIDDEN_QUERY_TERMS,
    MIN_ASSIGNMENTS,
    N_PRIMARY,
    N_PRIMARY_PER_FAMILY,
    N_SECONDARY_PER_FAMILY,
    PHASE4F_RESULT_BLOB,
    PHASE4G_RESULT_BLOB,
)
from bite_bench.phase4h import (
    LOCKED_BLOBS as PHASE4H_LOCKED_BLOBS,
)

SCHEMA_ID = "bitebench-phase4h2-acquisition-extension-freeze/v0.1"
REVISION = "phase4h2-acquisition-extension-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE4H2_ACQUISITION_EXTENSION_PROTOCOL_FROZEN"
VERDICT_FROZEN = "PHASE4H2_REALSTRUCT2_AUGMENTED_FROZEN"
VERDICT_PARTIAL = "PHASE4H2_REALSTRUCT2_AUGMENTED_PARTIAL"
VERDICT_BLOCKED = "PHASE4H2_REALSTRUCT2_AUGMENTED_BLOCKED"
H5_VERDICTS = (VERDICT_FROZEN, VERDICT_PARTIAL, VERDICT_BLOCKED)
PREMISE = "PHASE4H_REALSTRUCT2_PARTIAL"
H0_COMMIT_SHA = "29dd6c91d02edcca6b486e74bac9bdf50259b149"
H0_FREEZE_BLOB = "4c48c198456babe2f5d0e652aefe831f8dacd3bc"
H1_COMMIT_SHA = "b50e36d2916ff8de7eaae37055fef6bf114d2008"
H1_POOL_BLOB = "7f45295f0ffe2880516f9f8ccbfa2c20b942a002"
H2_COMMIT_SHA = "5acaa887725325098c24b637aa09716de464425f"
H2_RESULT_BLOB = "666eed454c3dba6dd2cfa2a73e5989004380f177"
H1_REJECTIONS_BLOB = "a93f49ca54fdae11ddde58d25adaae9ed8db1af5"
H2_MANIFEST_BLOB = "e7c2d2291cdd62c1d6feff59c7d7870db6878350"
EXTENSION_POOL_PER_FAMILY = 180
H1_POOL_PER_FAMILY = 60
MAX_COVERAGE_PER_FAMILY = 240
WAVE1_PRIMARY_IDS = (
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
)
REMAINING_PRIMARY = {
    "dotenv-like": 2,
    "properties": 3,
    "ini_cfg": 3,
}
CLAIM_BOUNDARY = (
    "acquisition-amended, prospectively frozen convenience sample before comparison execution"
)
LOCKED_PHASE4H = {
    "benchmarks/spec/phase4h-realstruct2-freeze.json": H0_FREEZE_BLOB,
    "artifacts/phase4h/candidate-pool.json": H1_POOL_BLOB,
    "artifacts/phase4h/realstruct-2.json": H2_RESULT_BLOB,
    "corpora/realstruct-2/rejections.json": H1_REJECTIONS_BLOB,
    "corpora/realstruct-2/manifest.json": H2_MANIFEST_BLOB,
    "artifacts/phase4g/comparison-accounting.json": PHASE4G_RESULT_BLOB,
    "artifacts/phase4f/prospective-comparison.json": PHASE4F_RESULT_BLOB,
}
LOCKED_BLOBS = {**PHASE4H_LOCKED_BLOBS, **LOCKED_PHASE4H}

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase4h2-acquisition-extension-freeze.json"
PHASE4H_RESULT = _REPO / "artifacts" / "phase4h" / "realstruct-2.json"
PHASE4H_POOL = _REPO / "artifacts" / "phase4h" / "candidate-pool.json"


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
        "h0_commit_sha": H0_COMMIT_SHA,
        "h0_freeze_blob": H0_FREEZE_BLOB,
        "h1_commit_sha": H1_COMMIT_SHA,
        "h1_pool_blob": H1_POOL_BLOB,
        "h2_commit_sha": H2_COMMIT_SHA,
        "h2_result_blob": H2_RESULT_BLOB,
        "p3f_evaluation_holdout_used": False,
        "no_xfer3": True,
        "no_arm_execution": True,
        "no_tokenizer_execution": True,
        "no_bite_execution": True,
        "no_phase4h_rewrite": True,
        "no_h1_pool_rewrite": True,
        "no_license_inference": True,
        "no_license_file_rescue": True,
        "do_not_reconsider_h1_rejections": True,
        "wave1_primary_ids": list(WAVE1_PRIMARY_IDS),
        "n_wave1_primary": len(WAVE1_PRIMARY_IDS),
        "remaining_primary": dict(REMAINING_PRIMARY),
        "n_primary": N_PRIMARY,
        "n_primary_per_family": N_PRIMARY_PER_FAMILY,
        "n_secondary_per_family": N_SECONDARY_PER_FAMILY,
        "families": list(FAMILIES),
        "allowed_spdx": list(ALLOWED_SPDX),
        "min_assignments": MIN_ASSIGNMENTS,
        "changed_dimension": "candidate-pool coverage",
        "unchanged": [
            "discovery query strings",
            "license eligibility",
            "minimum assignments",
            "secret rejection",
            "family definitions",
            "selection-key formula",
            "annotation grammar",
            "primary quota",
            "secondary semantics",
            "future Phase4I analysis contract",
        ],
        "discovery": {
            "queries": {family: list(items) for family, items in DISCOVERY_QUERIES.items()},
            "query_order": "Phase4H freeze order, unchanged",
            "forbidden_query_terms": list(FORBIDDEN_QUERY_TERMS),
            "extension_pool_per_family": EXTENSION_POOL_PER_FAMILY,
            "h1_pool_per_family": H1_POOL_PER_FAMILY,
            "max_coverage_per_family": MAX_COVERAGE_PER_FAMILY,
            "exclude": "every repository_full_name+path in original H1",
            "ignore_code_search_snippets": True,
        },
        "selection": {
            "key": "SHA256(repository_full_name + '@' + frozen_commit_sha + ':' + path)",
            "wave1_documents_immutable": True,
            "sort_extension_candidates_only": True,
            "do_not_replace_wave1_even_if_lower_global_key": True,
            "acquisition_design": (
                "two-wave prospective acquisition; wave 2 added after quota shortfall, "
                "before any comparison-arm or tokenizer execution"
            ),
        },
        "secondary_after_family_primary_reaches_6": True,
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "comparison evidence",
            "confirmatory result",
            "generalization",
            "BITE superiority",
        ],
        "locked_blobs": dict(LOCKED_BLOBS),
        "h5_verdicts": list(H5_VERDICTS),
        "verdict_rule": {
            VERDICT_FROZEN: (
                "H3 before discovery; H4 pool before new content; wave1 10 preserved; "
                "final primary 18 with 6/family; same eligibility; secondary separate; "
                "no arms/tokenizer; blobs unchanged; p3f unopened"
            ),
            VERDICT_PARTIAL: "extension pool exhausted or cannot fill original quotas",
            VERDICT_BLOCKED: (
                "protocol leakage, old corpus rewritten, content before H4, "
                "arm/tokenizer execution, hand-picking, or frozen drift"
            ),
        },
    }


def validate_phase4h2_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("H3 protocol not frozen")
    if doc.get("premise") != PREMISE:
        errs.append("Phase 4H PARTIAL premise drifted")
    if doc.get("no_h1_pool_rewrite") is not True or doc.get("no_phase4h_rewrite") is not True:
        errs.append("Phase 4H rewrite must stay forbidden")
    if doc.get("no_license_inference") is not True:
        errs.append("license inference must stay forbidden")
    if doc.get("no_arm_execution") is not True or doc.get("no_tokenizer_execution") is not True:
        errs.append("arm/tokenizer execution must stay forbidden")
    if list(doc.get("wave1_primary_ids") or []) != list(WAVE1_PRIMARY_IDS):
        errs.append("wave1 primary IDs drifted")
    if doc.get("remaining_primary") != dict(REMAINING_PRIMARY):
        errs.append("remaining quotas drifted")
    queries = (doc.get("discovery") or {}).get("queries") or {}
    if queries != {family: list(items) for family, items in DISCOVERY_QUERIES.items()}:
        errs.append("discovery queries drifted from Phase 4H")
    joined = " ".join(term for items in DISCOVERY_QUERIES.values() for term in items)
    for term in FORBIDDEN_QUERY_TERMS:
        if term in joined:
            errs.append(f"forbidden discovery term: {term}")
    phase4h = json.loads(PHASE4H_RESULT.read_text(encoding="utf-8"))
    if phase4h.get("verdict") != PREMISE:
        errs.append("Phase 4H result rewritten")
    if phase4h.get("n_primary") != 10:
        errs.append("wave1 primary count drifted")
    pool = json.loads(PHASE4H_POOL.read_text(encoding="utf-8"))
    if pool.get("file_contents_opened") is not False:
        errs.append("H1 pool contents flag rewritten")
    for path, expected in LOCKED_PHASE4H.items():
        if _git_blob(path) != expected:
            errs.append(f"Phase 4H blob drifted: {path}")
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
    print(freeze["verdict"], "remaining", freeze["remaining_primary"])
    print("errors", validate_phase4h2_freeze(freeze))
