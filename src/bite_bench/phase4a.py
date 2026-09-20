"""Phase 4A REALSTRUCT-1 selection protocol (A0).

Freezes families, strata, eligibility, split, annotation grammar, and
claim boundary. Does not acquire sources. Does not import or run BITE
sensors, policies, planners, or operators. Does not open p3f.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA_ID = "bitebench-phase4a-realstruct1-freeze/v0.1"
REVISION = "phase4a-realstruct1-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE4A_REAL_CORPUS_PROTOCOL_FROZEN"
VERDICT_FROZEN = "PHASE4A_REAL_CORPUS_FROZEN"
VERDICT_PARTIAL = "PHASE4A_REAL_CORPUS_PARTIAL"
VERDICT_BLOCKED = "PHASE4A_REAL_CORPUS_BLOCKED"
A1_VERDICTS = (VERDICT_FROZEN, VERDICT_PARTIAL, VERDICT_BLOCKED)
PREMISE = "PHASE3T_EXACT_REFERENCE_VALIDATED"
PHASE3S_REMAINS = "Phase3S remains FAILED"
PHASE3Q_REMAINS = "Phase3Q remains FAILED"
PHASE3S_VERDICT = "PHASE3S_REFERENCE_SPECIFICITY_FAILED"
PHASE3Q_VERDICT = "PHASE3Q_XFER2_TRANSFER_FAILED"
PHASE3T_VERDICT = "PHASE3T_EXACT_REFERENCE_VALIDATED"
T0_SHA = "70a3f7792a5baee1382b890fb7021dc7fb234ce1"
T1_SHA = "c5dc9852bea5ab28edff9048ad79a6372191daa9"
CORPUS_NAME = "REALSTRUCT-1"
N_DOCUMENTS = 12
N_PER_FAMILY = 4
N_NATURAL_PER_FAMILY = 2
N_ENRICHED_PER_FAMILY = 2
N_DEV_PER_FAMILY = 1
N_DEV = 3
N_EVAL = 9
MIN_ASSIGNMENTS = 10
MAX_BYTES = 262144
MAX_LINES = 4000
FAMILIES = (
    "dotenv-like",
    "java_properties",
    "ini_cfg",
)
STRATA = ("natural", "explicit-reference-enriched")
ALLOWED_SPDX = (
    "MIT",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "0BSD",
    "Unlicense",
    "CC0-1.0",
)
CLAIM_BOUNDARY = "small convenience sample of public real-world key=value configuration artifacts"
LOCKED_BLOBS = {
    "artifacts/phase3t/exact-reference.json": "5892ad925152e8cac32319e243c2e85f67ae2a0c",
    "artifacts/phase3s/reference-specificity.json": (
        "f4bcaae86586c5f738954b78fda8427f3bb78694"
    ),
    "artifacts/phase3q/xfer2-transfer.json": "47ede9cab9619bc66dace5738e1f523b87a35f63",
    "benchmarks/spec/phase3t-exact-reference-freeze.json": (
        "7c03641aba310d6808480451e88624cbe7e1a2a2"
    ),
}

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase4a-realstruct1-freeze.json"
PHASE3T_PATH = _REPO / "artifacts" / "phase3t" / "exact-reference.json"
PHASE3S_PATH = _REPO / "artifacts" / "phase3s" / "reference-specificity.json"
PHASE3Q_PATH = _REPO / "artifacts" / "phase3q" / "xfer2-transfer.json"


class EvaluationSealError(RuntimeError):
    """p3f evaluation replicas 2/3 stay sealed."""


def refuse_p3f_evaluation(case_id: str) -> None:
    cid = str(case_id)
    if cid.startswith("p3f-") and ("-r2" in cid or "-r3" in cid):
        raise EvaluationSealError(f"p3f evaluation sealed: refused {cid}")


def freeze_manifest() -> dict[str, Any]:
    return {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "verdict": PROTOCOL_FROZEN,
        "paid_api": False,
        "offline_core_tests": True,
        "research_conclusion": False,
        "premise": PREMISE,
        "phase3t_t0_sha": T0_SHA,
        "phase3t_head_sha": T1_SHA,
        "phase3t_verdict": PHASE3T_VERDICT,
        "phase3s_remains": PHASE3S_REMAINS,
        "phase3s_verdict": PHASE3S_VERDICT,
        "phase3q_remains": PHASE3Q_REMAINS,
        "phase3q_verdict": PHASE3Q_VERDICT,
        "p3f_evaluation_holdout_used": False,
        "no_xfer3": True,
        "no_bite_execution": True,
        "no_bite_policy_import": True,
        "no_bite_profiler_import": True,
        "no_baseline_execution": True,
        "corpus_name": CORPUS_NAME,
        "primary_scope": "public real-world line-oriented key=value configuration documents",
        "one_document_one_uri": True,
        "no_cross_document_join": True,
        "one_repository_per_document": True,
        "no_synthetic_or_bite_authored_sources": True,
        "no_source_rewrite_after_bite": True,
        "families": list(FAMILIES),
        "n_documents": N_DOCUMENTS,
        "n_per_family": N_PER_FAMILY,
        "strata": list(STRATA),
        "n_natural_per_family": N_NATURAL_PER_FAMILY,
        "n_enriched_per_family": N_ENRICHED_PER_FAMILY,
        "stratum_rule": {
            "natural": "select real shipped config without conditioning on morphology",
            "explicit-reference-enriched": (
                "${NAME} in the same document whose NAME equals an assignment key; "
                "raw syntax only, never BITE sensor output"
            ),
        },
        "eligibility": {
            "immutable_repository_commit_path": True,
            "license_must_be_explicit_and_redistributable": True,
            "allowed_spdx": list(ALLOWED_SPDX),
            "min_assignments": MIN_ASSIGNMENTS,
            "max_bytes": MAX_BYTES,
            "max_lines": MAX_LINES,
            "exclude_credential_private_key_live_secret_values": True,
            "record_exclusion_reason_and_replace": True,
        },
        "acquisition": {
            "preserve_exact_bytes": True,
            "no_newline_rewrite": True,
            "no_encoding_transcode": True,
            "no_source_canonicalize": True,
            "skip_if_redistribution_unclear": True,
            "raw_dir": "corpora/realstruct-1/raw/",
        },
        "split": {
            "when": "after 12 sources accepted",
            "order": "within family, lexicographic sha256 of exact raw bytes",
            "development_per_family": N_DEV_PER_FAMILY,
            "n_development": N_DEV,
            "n_evaluation": N_EVAL,
            "no_swap_after_split": True,
            "evaluation_bytes_may_be_stored": True,
            "evaluation_may_not_be_measured_by_bite": True,
        },
        "annotation_grammar": {
            "independent_of_bite_implementation": True,
            "raw_syntax_only": True,
            "assignment": "first '=' separator records logical key/value",
            "unsupported": (
                "comments, section headers, blank, and other non-assignment lines; "
                "not negative examples"
            ),
            "explicit_reference_gold": "${NAME} only",
            "explicit_reference_edge": (
                "NAME case-sensitive exact match to an assignment key in the same document"
            ),
            "not_gold": ["$NAME", "substring", "semantic similarity", "default-value ${NAME:-x}"],
            "missing_annotation_is_not_non_reference": True,
            "allowed_scorer_fields": [
                "exact logical duplicate groups",
                "source line/span",
                "explicit reference source/destination",
            ],
            "forbidden_scorer_fields": [
                "expected BITE route",
                "expected operator sequence",
            ],
        },
        "synthetic_controls": {
            "phase3t_frozen_artifacts_secondary_only": True,
            "do_not_mix_real_and_synthetic_accuracy": True,
        },
        "future_comparison_preregistration": {
            "evaluation_documents": N_EVAL,
            "same_bytes_for_bite_and_baseline": True,
            "same_tokenizer_and_budget_conditions": True,
            "no_baseline_tuning_on_evaluation": True,
            "no_baseline_in_phase4a": True,
        },
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "representative sample",
            "real-world generalization",
            "BITE superiority",
        ],
        "token_reduction": "diagnostic_only",
        "no_winner_score": True,
        "locked_blobs": dict(LOCKED_BLOBS),
        "a1_verdicts": list(A1_VERDICTS),
        "verdict_rule": {
            VERDICT_FROZEN: (
                "12/12 provenance+hash+license; split frozen; scorer annotation frozen; "
                "raw bytes unchanged; no BITE execution/imports; p3f unopened"
            ),
            VERDICT_PARTIAL: "source/licensing/annotation conditions only partly met",
            VERDICT_BLOCKED: "reproducible acquisition or lawful redistribution not possible",
        },
    }


def validate_phase4a_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("revision") != REVISION:
        errs.append("revision mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("protocol not frozen")
    if doc.get("premise") != PREMISE:
        errs.append("Phase 3T premise drifted")
    if doc.get("no_bite_execution") is not True:
        errs.append("BITE execution must stay forbidden")
    if doc.get("no_bite_policy_import") is not True:
        errs.append("policy import must stay forbidden")
    if doc.get("no_bite_profiler_import") is not True:
        errs.append("profiler import must stay forbidden")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("no_xfer3") is not True:
        errs.append("XFER-3 must not be invented")
    if doc.get("n_documents") != N_DOCUMENTS:
        errs.append("n_documents drifted")
    if list(doc.get("families") or []) != list(FAMILIES):
        errs.append("families drifted")
    if not PHASE3T_PATH.is_file():
        errs.append("Phase 3T artifact missing")
    else:
        phase3t = json.loads(PHASE3T_PATH.read_text(encoding="utf-8"))
        if phase3t.get("verdict") != PHASE3T_VERDICT:
            errs.append("Phase 3T verdict rewritten")
    if not PHASE3S_PATH.is_file():
        errs.append("Phase 3S artifact missing")
    else:
        phase3s = json.loads(PHASE3S_PATH.read_text(encoding="utf-8"))
        if phase3s.get("verdict") != PHASE3S_VERDICT:
            errs.append("Phase 3S verdict rewritten")
    if not PHASE3Q_PATH.is_file():
        errs.append("Phase 3Q artifact missing")
    else:
        phase3q = json.loads(PHASE3Q_PATH.read_text(encoding="utf-8"))
        if phase3q.get("verdict") != PHASE3Q_VERDICT:
            errs.append("Phase 3Q verdict rewritten")
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
