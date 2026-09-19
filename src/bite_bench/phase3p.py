"""Phase 3P record-alignment v2 protocol (P0).

Freezes the repair contract before implementation. Does not implement
sensors, operators, or evaluators. Does not change Phase 3O artifacts.
Does not open p3f. Does not retune thresholds.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA_ID = "bitebench-phase3p-record-alignment-freeze/v0.1"
REVISION = "phase3p-record-alignment-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE3P_RECORD_ALIGNMENT_PROTOCOL_FROZEN"
VERDICT_VALIDATED = "PHASE3P_RECORD_ALIGNMENT_VALIDATED"
VERDICT_PARTIAL = "PHASE3P_RECORD_ALIGNMENT_PARTIAL"
VERDICT_BLOCKED = "PHASE3P_RECORD_ALIGNMENT_BLOCKED"
P1_VERDICTS = (VERDICT_VALIDATED, VERDICT_PARTIAL, VERDICT_BLOCKED)
O0_SHA = "76998156d3cbf67fc0a53e151688e46bd3c26dc7"
O1_SHA = "d3b44c9c4f0d44b26b6c7074c48e76706eba918f"
PHASE3O_VERDICT = "PHASE3O_XFER1_TRANSFER_FAILED"
PHASE3O_REMAINS = "Phase3O remains FAILED; known failures are repaired in development"
GENERATION = "p3p"
LOCKED_T_HIGH = 4.0
LOCKED_FEATURE = "mean_edge_distance"
FORMATS = ("key_value", "compact_json", "pretty_json", "reversed_order_json")
OPERATOR_ORDER = ("UNTANGLE", "REDUCE_v2", "INTEGRATE")
REPRODUCTION_SURFACES = (
    "xfer1-c018-mixed_order_json",
    "xfer1-c021-mixed_order_json",
    "xfer1-c022-pretty_json",
    "xfer1-c022-mixed_order_json",
    "xfer1-c024-pretty_json",
)
CLAIM_BOUNDARY = "development repair of logical-record alignment and lineage-aware safety"
V1_UNCHANGED = (
    "conditional_texture_policy_v1",
    "structural_redundancy_v1",
    "ReduceOperator",
    "composition_safety",
    "RulePolicy",
    "preflight",
    "UNTANGLE",
    "INTEGRATE",
    "dependency_dispersion_v1",
)

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase3p-record-alignment-freeze.json"
PHASE3O_PATH = _REPO / "artifacts" / "phase3o" / "xfer1-transfer.json"


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
        "offline": True,
        "synthetic": True,
        "research_conclusion": False,
        "premise": PHASE3O_VERDICT,
        "phase3o_o0_sha": O0_SHA,
        "phase3o_head_sha": O1_SHA,
        "phase3o_artifact_unchanged": True,
        "phase3o_verdict_unchanged": True,
        "phase3o_remains": PHASE3O_REMAINS,
        "bite_xfer1_role": "development_evidence_not_confirmatory_holdout",
        "generation": GENERATION,
        "copy_xfer1_cases": False,
        "p3f_evaluation_holdout_used": False,
        "calibration": False,
        "no_new_threshold": True,
        "no_predicate_retune": True,
        "locked_from_phase3g": {
            "feature": LOCKED_FEATURE,
            "T_high": LOCKED_T_HIGH,
            "gate": "n_edges>0 AND mean_edge_distance>=4",
        },
        "v1_unchanged": list(V1_UNCHANGED),
        "track_a": {
            "logical_record_identity_v2": {
                "gold_free": True,
                "kv": "one unit key=value; strip only around separator",
                "json": "object schema exactly {k,v} both string; whitespace and field order ignored",
                "extra_field": "not a logical duplicate candidate",
                "fail_closed": ["malformed", "nul"],
                "forbidden": ["fuzzy", "lowercase", "semantic_similarity"],
            },
            "structural_redundancy_v2": {
                "does_not_change_v1": True,
                "identity": "logical_record_identity_v2",
                "feature": "duplicate_unit_ratio",
                "actionability": "ratio>0 AND not fail_closed",
                "no_threshold": True,
            },
            "LogicalReduceOperatorV2": {
                "does_not_change_ReduceOperator": True,
                "identity": "logical_record_identity_v2",
                "keep": "first source-exact representative",
                "omitted_recoverable": [
                    "original_text",
                    "source_span",
                    "provenance",
                    "duplicate_of",
                ],
                "no_whitespace_id_rewrite": True,
                "no_dedupe": [
                    "same_key_different_value",
                    "same_value_different_key",
                    "extra_field_object",
                ],
            },
            "conditional_texture_policy_v2": {
                "does_not_change_v1": True,
                "gate_unchanged": True,
                "untangle_predicate_unchanged": True,
                "integrate_predicate_unchanged": True,
                "reduce_sensor": "structural_redundancy_v2",
                "operator_order": list(OPERATOR_ORDER),
                "cut_forbidden": True,
            },
        },
        "track_b": {
            "composition_safety_v2": {
                "does_not_change_v1": True,
                "join_compare": "root_lineage_sets",
                "lineage_fields": [
                    "provenance.sources",
                    "joined_from",
                    "derived_from",
                    "parent_unit_id",
                    "R",
                ],
                "overmerge_uses_root_source_text": True,
                "dependency_edge_not_explicit_success": True,
            }
        },
        "formats": list(FORMATS),
        "reproduction_only_surfaces": list(REPRODUCTION_SURFACES),
        "reproduction_not_primary_evidence": True,
        "planned_cases": [
            {
                "case_id": "p3p-dadj",
                "role": "adjacent_logical_duplicate",
                "expect_duplicate": True,
                "formats": list(FORMATS),
            },
            {
                "case_id": "p3p-drev",
                "role": "reversed_field_order_duplicate",
                "expect_duplicate": True,
                "formats": ["compact_json", "pretty_json", "reversed_order_json"],
            },
            {
                "case_id": "p3p-dnon",
                "role": "nonadjacent_logical_duplicate",
                "expect_duplicate": True,
                "formats": list(FORMATS),
            },
            {
                "case_id": "p3p-nkey",
                "role": "same_key_different_value_negative",
                "expect_duplicate": False,
                "formats": list(FORMATS),
            },
            {
                "case_id": "p3p-nval",
                "role": "same_value_different_key_negative",
                "expect_duplicate": False,
                "formats": list(FORMATS),
            },
            {
                "case_id": "p3p-nextra",
                "role": "extra_field_object_negative",
                "expect_duplicate": False,
                "formats": ["compact_json", "pretty_json", "reversed_order_json"],
            },
            {
                "case_id": "p3p-kvdup",
                "role": "kv_exact_duplicate",
                "expect_duplicate": True,
                "formats": ["key_value"],
            },
            {
                "case_id": "p3p-rjoin",
                "role": "reduce_v2_then_integrate",
                "expect_duplicate": True,
                "formats": list(FORMATS),
            },
            {
                "case_id": "p3p-uri",
                "role": "untangle_reduce_v2_integrate",
                "expect_duplicate": True,
                "formats": list(FORMATS),
            },
            {
                "case_id": "p3p-derj",
                "role": "prior_derived_id_then_integrate",
                "expect_duplicate": False,
                "formats": ["pretty_json"],
            },
            {
                "case_id": "p3p-tjoin",
                "role": "true_shared_join_key",
                "expect_duplicate": False,
                "formats": list(FORMATS),
            },
            {
                "case_id": "p3p-nroot",
                "role": "unrelated_derived_roots_negative",
                "expect_duplicate": False,
                "formats": ["pretty_json"],
            },
        ],
        "invariants": {
            "sensor_operator_biconditional": True,
            "four_rendering_invariance": True,
            "reduce_after_multiplicity_le_1": True,
            "lineage_recall": 1.0,
            "provenance_completeness": 1.0,
            "conservation_untraced": [],
            "silent_loss": 0,
            "r_recoverable": True,
            "reduce_only_logical_duplicates": True,
            "integrate_only_explicit_join": True,
            "no_unrelated_root_overmerge": True,
        },
        "p1_verdicts": list(P1_VERDICTS),
        "verdict_rule": {
            VERDICT_VALIDATED: (
                "fresh p3p: sensor/operator biconditional; four-rendering invariance; "
                "lineage-aware safety; negatives; v1 unchanged"
            ),
            VERDICT_PARTIAL: "some invariants only",
            VERDICT_BLOCKED: "contract drift / provenance failure / fair validation cannot run",
        },
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "Phase3O TRANSFER_CONFIRMED",
            "real-world corpus generalization",
            "BITE superiority",
            "confirmatory holdout on BITE-XFER-1",
        ],
        "token_reduction": "diagnostic_only",
        "no_winner_score": True,
        "cut_forbidden": True,
        "rule_policy_unchanged": True,
    }


def validate_phase3p_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("revision") != REVISION:
        errs.append("revision mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("protocol not frozen")
    if doc.get("premise") != PHASE3O_VERDICT:
        errs.append("Phase 3O premise drifted")
    if doc.get("phase3o_verdict_unchanged") is not True:
        errs.append("Phase 3O verdict must stay unchanged")
    if doc.get("copy_xfer1_cases") is not False:
        errs.append("must not copy XFER-1 cases")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("no_new_threshold") is not True:
        errs.append("new threshold forbidden")
    if list(doc.get("reproduction_only_surfaces") or []) != list(REPRODUCTION_SURFACES):
        errs.append("reproduction surfaces drifted")
    if not PHASE3O_PATH.is_file():
        errs.append("Phase 3O artifact missing")
    else:
        phase3o = json.loads(PHASE3O_PATH.read_text(encoding="utf-8"))
        if phase3o.get("verdict") != PHASE3O_VERDICT:
            errs.append("Phase 3O verdict rewritten")
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
