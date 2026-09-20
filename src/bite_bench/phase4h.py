"""Phase 4H H0 REALSTRUCT-2 acquisition and analysis protocol.

Freezes families, discovery queries, pool size, eligibility, selection
order, strata, annotation grammar, and the future Phase 4I analysis
contract. Does not search GitHub. Does not acquire sources. Does not
open file contents. Does not run comparison arms or tokenizers.
Does not open p3f. Does not rewrite Phase 4F/4G artifacts.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4g import LOCKED_BLOBS as PHASE4G_LOCKED_BLOBS

SCHEMA_ID = "bitebench-phase4h-realstruct2-freeze/v0.1"
REVISION = "phase4h-realstruct2-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE4H_REALSTRUCT2_PROTOCOL_FROZEN"
VERDICT_FROZEN = "PHASE4H_REALSTRUCT2_FROZEN"
VERDICT_PARTIAL = "PHASE4H_REALSTRUCT2_PARTIAL"
VERDICT_BLOCKED = "PHASE4H_REALSTRUCT2_BLOCKED"
H2_VERDICTS = (VERDICT_FROZEN, VERDICT_PARTIAL, VERDICT_BLOCKED)
PREMISE = "PHASE4G_COMPARISON_ACCOUNTING_VALIDATED"
PHASE4F_VERDICT = "PHASE4F_COMPARISON_PROTOCOL_READY"
PHASE4C_VERDICT = "PHASE4C_REAL_HOLDOUT_MEASURED"
PHASE4D_VERDICT = "PHASE4D_MEASUREMENT_SEMANTICS_AUDITED"
PHASE4E_VERDICT = "PHASE4E_FULL_KEY_REFERENCE_VALIDATED"
PHASE3S_VERDICT = "PHASE3S_REFERENCE_SPECIFICITY_FAILED"
PHASE3Q_VERDICT = "PHASE3Q_XFER2_TRANSFER_FAILED"
PHASE3T_VERDICT = "PHASE3T_EXACT_REFERENCE_VALIDATED"
PHASE4G_HEAD = "be0248c972d9136ae6c39c57bf7e6a756e815aa9"
G0_COMMIT_SHA = "df096829d7178e6d33094494e93712fde37580b5"
G0_FREEZE_BLOB = "b74b591f61a030134fb35272e20f01bceea295bf"
PHASE4G_RESULT_BLOB = "2635401558d27b2a2781ee53ff7465b877f39b37"
PHASE4F_HEAD = "48eaba1a8f55363da3beccec726460b961199300"
PHASE4F_RESULT_BLOB = "28bfd7ea8b131b72ba55bb3f84a7126f99c96578"
LENGTH_PI_V1_BLOB = "2de74b1b21c466aaa20858a2066e011f14a0fe20"
TOKENIZER_BLOB = "6f95df67723fe8ee2e572e589f6ca3e864de37bc"
METRICS_V1_BLOB = "d58a2f3729423d79731cb081e8d64b0204fdfa6f"
LOCKED_T_HIGH = 4
ARMS = ("raw_full", "adapter_only", "length_pi_v1", "BITE_v5")
CORPUS_NAME = "REALSTRUCT-2"
N_PRIMARY = 18
N_PRIMARY_PER_FAMILY = 6
N_SECONDARY_PER_FAMILY = 2
N_SECONDARY_MAX = 6
CANDIDATE_POOL_PER_FAMILY = 60
MIN_ASSIGNMENTS = 10
MAX_BYTES = 524288
FAMILIES = ("dotenv-like", "properties", "ini_cfg")
STRATA = ("primary", "secondary_reference_enriched")
ALLOWED_SPDX = ("MIT", "Apache-2.0")
CLAIM_BOUNDARY = (
    "prospectively acquired convenience sample for a later frozen comparison"
)
DISCOVERY_QUERIES: dict[str, tuple[str, ...]] = {
    "dotenv-like": (
        "filename:.env.example",
        "filename:.env.sample",
        "filename:example.env",
        "filename:sample.env",
    ),
    "properties": ("extension:properties",),
    "ini_cfg": (
        "extension:ini",
        "extension:cfg",
        "extension:conf",
    ),
}
FORBIDDEN_QUERY_TERMS = (
    "${",
    "id=",
    "FATAL",
    "duplicate",
    "BITE",
    "reference",
    "joinability",
    "dispersion",
)
TEST_PATH_MARKERS = (
    "/test/",
    "/tests/",
    "/testing/",
    "/__tests__/",
    "/testdata/",
    "/fixtures/",
    "/fixture/",
    "/benchmark/",
    "/benchmarks/",
)
RS1_REPOS = (
    "laravel/laravel",
    "koel/koel",
    "BookStackApp/BookStack",
    "sissbruecker/linkding",
    "apache/hadoop",
    "apache/ratis",
    "apache/kafka",
    "apache/tomcat",
    "gogs/gogs",
    "polybar/polybar",
    "openembedded/openembedded-core",
    "OE4T/meta-tegra",
)
LOCKED_PHASE4G = {
    "artifacts/phase4g/comparison-accounting.json": PHASE4G_RESULT_BLOB,
    "benchmarks/spec/phase4g-comparison-accounting-freeze.json": G0_FREEZE_BLOB,
    "artifacts/phase4f/prospective-comparison.json": PHASE4F_RESULT_BLOB,
    "src/bite_eval/length_pi_v1.py": LENGTH_PI_V1_BLOB,
    "src/bite_eval/reference_tokenizer.py": TOKENIZER_BLOB,
    "src/bite_eval/phase4f_metrics.py": METRICS_V1_BLOB,
}
LOCKED_BLOBS = {**PHASE4G_LOCKED_BLOBS, **LOCKED_PHASE4G}

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase4h-realstruct2-freeze.json"
PHASE4G_PATH = _REPO / "artifacts" / "phase4g" / "comparison-accounting.json"
PHASE4F_PATH = _REPO / "artifacts" / "phase4f" / "prospective-comparison.json"
PHASE4E_PATH = _REPO / "artifacts" / "phase4e" / "full-key-reference.json"
PHASE4C_PATH = _REPO / "artifacts" / "phase4c" / "real-holdout.json"
PHASE4D_PATH = _REPO / "artifacts" / "phase4d" / "measurement-semantics.json"
PHASE3T_PATH = _REPO / "artifacts" / "phase3t" / "exact-reference.json"
PHASE3S_PATH = _REPO / "artifacts" / "phase3s" / "reference-specificity.json"
PHASE3Q_PATH = _REPO / "artifacts" / "phase3q" / "xfer2-transfer.json"


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
        "phase4g_head_sha": PHASE4G_HEAD,
        "g0_commit_sha": G0_COMMIT_SHA,
        "g0_freeze_blob": G0_FREEZE_BLOB,
        "phase4g_result_blob": PHASE4G_RESULT_BLOB,
        "phase4f_head_sha": PHASE4F_HEAD,
        "phase4f_result_blob": PHASE4F_RESULT_BLOB,
        "phase4g_verdict": PREMISE,
        "phase4f_verdict": PHASE4F_VERDICT,
        "phase4e_verdict": PHASE4E_VERDICT,
        "phase4c_verdict": PHASE4C_VERDICT,
        "phase4d_verdict": PHASE4D_VERDICT,
        "phase3t_verdict": PHASE3T_VERDICT,
        "phase3s_verdict": PHASE3S_VERDICT,
        "phase3q_verdict": PHASE3Q_VERDICT,
        "p3f_evaluation_holdout_used": False,
        "no_xfer3": True,
        "no_bite_execution": True,
        "no_bite_policy_import": True,
        "no_bite_profiler_import": True,
        "no_baseline_execution": True,
        "no_tokenizer_execution": True,
        "no_arm_execution": True,
        "no_recovery_bundle_comparison": True,
        "no_visibility_metrics": True,
        "no_phase4f_rewrite": True,
        "no_phase4g_rewrite": True,
        "no_bite_retune": True,
        "no_length_pi_retune": True,
        "t_high_reference": LOCKED_T_HIGH,
        "arms_frozen_not_executed": list(ARMS),
        "corpus_name": CORPUS_NAME,
        "primary_scope": "public real-world line-oriented key=value configuration documents",
        "one_document_one_uri": True,
        "no_cross_document_join": True,
        "families": list(FAMILIES),
        "n_primary": N_PRIMARY,
        "n_primary_per_family": N_PRIMARY_PER_FAMILY,
        "n_secondary_per_family": N_SECONDARY_PER_FAMILY,
        "n_secondary_max": N_SECONDARY_MAX,
        "candidate_pool_per_family": CANDIDATE_POOL_PER_FAMILY,
        "strata": list(STRATA),
        "discovery": {
            "github_search_endpoint": "GET /search/code",
            "queries": {family: list(queries) for family, queries in DISCOVERY_QUERIES.items()},
            "query_dimensions": "filename / extension only",
            "forbidden_query_terms": list(FORBIDDEN_QUERY_TERMS),
            "ignore_code_search_snippets": True,
            "per_page": 100,
            "collection_order": (
                "queries in freeze order; paginate each query until the family "
                "has 60 unique repository_full_name+path or pages are exhausted"
            ),
            "unique_key": "repository_full_name + path",
            "repo_metadata_without_file_contents": True,
            "head_sha_source": "GET /repos/{owner}/{repo}/commits/{default_branch}",
            "no_additions_after_h1": True,
            "no_reordering_after_h1": True,
        },
        "selection_order": {
            "key": "SHA256(repository_full_name + '@' + frozen_commit_sha + ':' + path)",
            "direction": "ascending hex",
            "evaluate_eligibility_in_that_order": True,
            "no_hand_picking_after_content_inspection": True,
        },
        "primary_must_not_depend_on": [
            "BITE features",
            "BITE route",
            "token reduction",
            "reference dispersion",
            "duplicate count",
            "anomaly detection",
            "joinability",
            "length_pi result",
            "future comparison metrics",
        ],
        "primary_rule": "first 6 eligible documents per family under selection_order",
        "secondary_rule": (
            "after primary 18 fixed, up to 2 remaining eligible documents per family "
            "with at least one scorer-only exact same-document ${NAME} reference; "
            "never pool with primary; never replace primary"
        ),
        "eligibility": {
            "public": True,
            "not_archived": True,
            "not_fork": True,
            "allowed_spdx": list(ALLOWED_SPDX),
            "not_in_realstruct1_repos": list(RS1_REPOS),
            "no_repository_overlap_within_primary": True,
            "no_duplicate_raw_sha256": True,
            "no_nul_bytes": True,
            "utf8_or_ascii_compatible": True,
            "min_assignments": MIN_ASSIGNMENTS,
            "max_bytes": MAX_BYTES,
            "exclude_live_credentials_private_keys_obvious_secrets": True,
            "exclude_generated_benchmark_test_fixtures": True,
            "test_path_markers": list(TEST_PATH_MARKERS),
            "exclude_bite_artificial_inputs": True,
            "log_each_rejection_and_continue": True,
            "do_not_alter_h0_if_pool_cannot_fill_primary": True,
        },
        "acquisition": {
            "preserve_exact_bytes": True,
            "no_newline_rewrite": True,
            "no_encoding_transcode": True,
            "no_whitespace_rewrite": True,
            "no_comment_rewrite": True,
            "no_ordering_rewrite": True,
            "vendor_exact_bytes_only_when_redistribution_permitted": True,
            "raw_dir": "corpora/realstruct-2/raw/",
        },
        "annotation_grammar": {
            "independent_of_bite_implementation": True,
            "raw_syntax_only": True,
            "assignment": "first '=' separator records logical key/value",
            "unsupported": (
                "comments, blank, section headers, and other non-assignment lines"
            ),
            "explicit_reference_gold": "${NAME} only",
            "two_pass_whole_document_key_index": True,
            "name_case_sensitive_exact_key_match": True,
            "gold_identity": "(source_line, NAME, dest_line)",
            "exact_duplicate_identity": "(key, value)",
            "repeated_key_different_value_is_separate_diagnostic": True,
            "forbidden_scorer_fields": [
                "expected route",
                "expected operator sequence",
                "expected BITE edge",
                "expected arm winner",
            ],
        },
        "future_phase4i_analysis": {
            "primary_only_for_headline": True,
            "report_all_four_arms_per_document": True,
            "no_winner_score": True,
            "matched_budget_subset": (
                "primary documents where length_pi_v1.budget_match_applicable == true; "
                "do not redefine after results"
            ),
            "paired_A_visible_reference_retention_v2": (
                "documents with reference gold > 0; BITE_v5 - length_pi_v1 per document; "
                "n / mean / median / positive-tie-negative; n=0 => not_observed"
            ),
            "paired_B_unique_assignment_identity_retention_v2": "on matched_budget_subset",
            "paired_C_recovery_bundle_bytes_and_tokens": (
                "report separately; do not combine with visible token cost"
            ),
            "paired_D_model_visible_cost": (
                "raw_full / adapter_only / BITE_v5 / length_pi_v1 tokens; "
                "BITE reduction incidence = count of primary docs where "
                "BITE_v5 tokens < adapter_only tokens; not an overall score"
            ),
            "paired_E_safety": (
                "every arm: raw reconstruction exact; BITE additionally provenance "
                "completeness, lineage recall, silent loss, conservation_untraced, "
                "unsupported loss, no unrelated overmerge"
            ),
            "paired_F_bite_mechanism_diagnostic": (
                "route-sequence frequencies, atom-aware sensor precision/recall, "
                "unadjudicated edges; report separately from comparison outcome"
            ),
            "secondary_label": "mechanism-enriched diagnostic",
            "secondary_never_pooled_with_primary": True,
            "secondary_not_representative_evidence": True,
            "statistical_claim_boundary": (
                "fixed convenience sample; no population-generalization p-values"
            ),
            "allowed_claim_form": (
                "On the frozen REALSTRUCT-2 primary corpus, BITE retained X versus Y "
                "under the matched-budget protocol."
            ),
            "forbidden_claims": [
                "BITE is generally superior",
                "works better on real-world configuration files",
                "statistically proves superiority",
            ],
        },
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "BITE evidence",
            "baseline evidence",
            "comparison result",
            "generalization",
            "superiority",
        ],
        "locked_blobs": dict(LOCKED_BLOBS),
        "h2_verdicts": list(H2_VERDICTS),
        "verdict_rule": {
            VERDICT_FROZEN: (
                "H0 before discovery; H1 pool frozen before file-content selection; "
                "18/18 primary; provenance/hash/license valid; deterministic order; "
                "annotations frozen; secondary separate; no arm/tokenizer execution; "
                "BITE/baseline blobs unchanged; p3f unopened"
            ),
            VERDICT_PARTIAL: (
                "corpus cannot fill frozen quotas or licensing/source constraints fail"
            ),
            VERDICT_BLOCKED: (
                "protocol leakage, arm execution before H2, post-inspection cherry-picking, "
                "or frozen component drift"
            ),
        },
    }


def validate_phase4h_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("revision") != REVISION:
        errs.append("revision mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("H0 protocol not frozen")
    if doc.get("premise") != PREMISE:
        errs.append("Phase 4G premise drifted")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("no_arm_execution") is not True or doc.get("no_tokenizer_execution") is not True:
        errs.append("arm/tokenizer execution must stay forbidden")
    if doc.get("no_phase4f_rewrite") is not True or doc.get("no_phase4g_rewrite") is not True:
        errs.append("Phase 4F/4G rewrite must stay forbidden")
    if doc.get("n_primary") != N_PRIMARY:
        errs.append("n_primary drifted")
    if list(doc.get("families") or []) != list(FAMILIES):
        errs.append("families drifted")
    queries = (doc.get("discovery") or {}).get("queries") or {}
    if queries != {family: list(items) for family, items in DISCOVERY_QUERIES.items()}:
        errs.append("discovery queries drifted")
    joined = " ".join(term for items in DISCOVERY_QUERIES.values() for term in items)
    for term in FORBIDDEN_QUERY_TERMS:
        if term in joined:
            errs.append(f"forbidden discovery term: {term}")
    if json.loads(PHASE4G_PATH.read_text(encoding="utf-8")).get("verdict") != PREMISE:
        errs.append("Phase 4G verdict rewritten")
    if json.loads(PHASE4F_PATH.read_text(encoding="utf-8")).get("verdict") != PHASE4F_VERDICT:
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
    for path, expected in LOCKED_PHASE4G.items():
        if _git_blob(path) != expected:
            errs.append(f"Phase 4F/4G blob drifted: {path}")
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
    print(freeze["verdict"], "families", freeze["families"])
    print("errors", validate_phase4h_freeze(freeze))
