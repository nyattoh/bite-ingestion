"""Phase 3D design freeze for dependency_dispersion_v1.

Spec only. Does not implement the sensor. Does not open Phase 2 evaluation.
Does not connect routing.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bite_eval.phase3b_fixtures import (
    LINE_DST,
    LINE_MID,
    LINE_ONE,
    LINE_SRC,
    NOISE,
    REF_A,
    REF_B,
    REF_OUT,
)
from bite_eval.phase3c_fixtures import (
    SHARED_CASE,
    SHARED_CAT,
    SHARED_ENV,
    SHARED_OWNER,
    SHARED_SVC,
)

SCHEMA_ID = "bitebench-phase3d-sensor-v1-design-freeze/v0.1"
REVISION = "phase3d-sensor-v1-design-freeze-v0.1"
VERDICT_FROZEN = "PHASE3D_V1_DESIGN_FROZEN"
VERDICT_BLOCKED = "PHASE3D_V1_DESIGN_BLOCKED"
VERDICTS = (VERDICT_FROZEN, VERDICT_BLOCKED)
V0_SENSOR = "dependency_dispersion_v0"
V1_SENSOR = "dependency_dispersion_v1"
COST_LINE_COUNTS = (100, 500, 1000, 5000, 10000)
PRIMARY_EDGE_RULE = "value_to_key_or_record_id"
DISTANCE_UNIT = "logical_unit_index"
RECORD_ID_FIELDS = ("id", "k")
REQUIRED_FORMATS = ("key_value", "json")
OPTIONAL_FORMATS = ("csv", "yaml")
OUT_OF_SCOPE_FORMATS = ("prose",)
DIAGNOSTIC_FEATURES = (
    "n_edges",
    "mean_edge_distance",
    "mean_edge_distance_norm",
    "component_span",
    "chain_span",
)
V0_LIMITS = (
    "supported_only_key_value_and_oneline_json",
    "pretty_json_csv_yaml_prose_unsupported",
    "blank_line_and_wrapping_distort_physical_line_distance",
    "identifier_reappearance_is_treated_as_reference",
    "value_atom_times_all_lines_scan_about_41s_at_5000_lines",
    "raw_vs_normalized_routing_choice_not_decided",
)

FREEZE_PATH = (
    Path(__file__).resolve().parents[2]
    / "benchmarks"
    / "spec"
    / "phase3d-sensor-v1-design-freeze.json"
)


def _pad(i: int) -> str:
    return f"pad_k{i}=pad_v{i}"


def _kv_json(line: str) -> dict[str, str]:
    left, _, right = line.partition("=")
    return {"k": left, "v": right}


def _json_docs(records: list[dict[str, str]]) -> dict[str, str]:
    return {
        "compact": json.dumps(records, separators=(",", ":")),
        "pretty": json.dumps(records, indent=2),
    }


def _one_hop_lines(kind: str) -> list[str]:
    src, dst = LINE_SRC, LINE_ONE
    if kind == "near":
        return [src, dst]
    if kind == "medium":
        return [src, _pad(0), _pad(1), _pad(2), dst]
    if kind == "far":
        return [src, *[_pad(i) for i in range(8)], dst]
    raise ValueError(kind)


def fixture_specs() -> list[dict[str, Any]]:
    hop_near = _one_hop_lines("near")
    hop_medium = _one_hop_lines("medium")
    hop_far = _one_hop_lines("far")
    json_near = _json_docs([_kv_json(LINE_SRC), _kv_json(LINE_ONE)])
    scale = {
        "short": [LINE_SRC, _pad(0), _pad(1), _pad(2), LINE_ONE, *[_pad(10 + i) for i in range(4)]],
        "medium": [LINE_SRC, _pad(0), _pad(1), _pad(2), LINE_ONE, *[_pad(10 + i) for i in range(20)]],
        "long": [LINE_SRC, _pad(0), _pad(1), _pad(2), LINE_ONE, *[_pad(10 + i) for i in range(80)]],
    }
    two_hop = [LINE_SRC, LINE_MID, LINE_DST]
    branch = [LINE_SRC, f"left_{REF_A}=id_left_01", f"right_{REF_A}=id_right_02"]
    pollution = [
        LINE_SRC,
        LINE_ONE,
        f"label_a={SHARED_ENV}",
        _pad(0),
        _pad(1),
        _pad(2),
        _pad(3),
        _pad(4),
        f"label_b={SHARED_ENV}",
    ]
    return [
        {
            "case_id": "true_dep_near_kv",
            "family": "true_dependency",
            "kind": "near",
            "surface": "key_value",
            "required": True,
            "lines": hop_near,
            "expect": {"n_edges": 1.0, "mean_edge_distance": 1.0, "n_logical_units": 2},
        },
        {
            "case_id": "true_dep_medium_kv",
            "family": "true_dependency",
            "kind": "medium",
            "surface": "key_value",
            "required": True,
            "lines": hop_medium,
            "expect": {"n_edges": 1.0, "mean_edge_distance": 4.0, "n_logical_units": 5},
        },
        {
            "case_id": "true_dep_far_kv",
            "family": "true_dependency",
            "kind": "far",
            "surface": "key_value",
            "required": True,
            "lines": hop_far,
            "expect": {"n_edges": 1.0, "mean_edge_distance": 9.0, "n_logical_units": 10},
        },
        {
            "case_id": "true_dep_near_json_compact",
            "family": "true_dependency",
            "kind": "near",
            "surface": "json_compact",
            "required": True,
            "text": json_near["compact"],
            "expect": {"n_edges": 1.0, "mean_edge_distance": 1.0, "n_logical_units": 2},
        },
        {
            "case_id": "true_dep_near_json_pretty",
            "family": "true_dependency",
            "kind": "near",
            "surface": "json_pretty",
            "required": True,
            "text": json_near["pretty"],
            "expect": {"n_edges": 1.0, "mean_edge_distance": 1.0, "n_logical_units": 2},
        },
        {
            "case_id": "scale_short",
            "family": "scale",
            "kind": "short",
            "surface": "key_value",
            "required": True,
            "lines": scale["short"],
            "expect": {"n_edges": 1.0, "mean_edge_distance": 4.0},
        },
        {
            "case_id": "scale_medium",
            "family": "scale",
            "kind": "medium",
            "surface": "key_value",
            "required": True,
            "lines": scale["medium"],
            "expect": {"n_edges": 1.0, "mean_edge_distance": 4.0},
        },
        {
            "case_id": "scale_long",
            "family": "scale",
            "kind": "long",
            "surface": "key_value",
            "required": True,
            "lines": scale["long"],
            "expect": {"n_edges": 1.0, "mean_edge_distance": 4.0},
        },
        {
            "case_id": "blank_line_kv",
            "family": "line_invariance",
            "kind": "blank_lines",
            "surface": "key_value",
            "required": True,
            "lines": [LINE_SRC, "", "", LINE_ONE],
            "expect": {"n_edges": 1.0, "mean_edge_distance": 1.0, "n_logical_units": 2},
        },
        {
            "case_id": "wrap_pretty_json",
            "family": "line_invariance",
            "kind": "wrap",
            "surface": "json_pretty",
            "required": True,
            "text": json_near["pretty"],
            "expect": {"n_edges": 1.0, "mean_edge_distance": 1.0, "n_logical_units": 2},
            "note": "pretty-print newlines are not logical units",
        },
        {
            "case_id": "shared_env_only",
            "family": "cooccurrence",
            "kind": "shared_env",
            "surface": "key_value",
            "required": True,
            "lines": [f"row_alpha={SHARED_ENV}", f"row_beta={SHARED_ENV}"],
            "expect": {"n_edges": 0.0},
        },
        {
            "case_id": "shared_service_only",
            "family": "cooccurrence",
            "kind": "shared_service",
            "surface": "key_value",
            "required": True,
            "lines": [f"row_alpha={SHARED_SVC}", f"row_beta={SHARED_SVC}"],
            "expect": {"n_edges": 0.0},
        },
        {
            "case_id": "shared_owner_only",
            "family": "cooccurrence",
            "kind": "shared_owner",
            "surface": "key_value",
            "required": True,
            "lines": [f"row_alpha={SHARED_OWNER}", f"row_beta={SHARED_OWNER}"],
            "expect": {"n_edges": 0.0},
        },
        {
            "case_id": "shared_label_only",
            "family": "cooccurrence",
            "kind": "shared_label",
            "surface": "key_value",
            "required": True,
            "lines": [f"row_alpha={SHARED_CAT}", f"row_beta={SHARED_CAT}"],
            "expect": {"n_edges": 0.0},
        },
        {
            "case_id": "multiple_unrelated_same_identifiers",
            "family": "cooccurrence",
            "kind": "unrelated_same_ids",
            "surface": "key_value",
            "required": True,
            "lines": [f"ticket_a={SHARED_CASE}", f"ticket_b={SHARED_CASE}"],
            "expect": {"n_edges": 0.0},
        },
        {
            "case_id": "true_edge_plus_cooccurrence_pollution",
            "family": "cooccurrence",
            "kind": "pollution",
            "surface": "key_value",
            "required": True,
            "lines": pollution,
            "expect": {"n_edges": 1.0, "mean_edge_distance": 1.0},
        },
        {
            "case_id": "one_hop_kv",
            "family": "graph_shape",
            "kind": "one_hop",
            "surface": "key_value",
            "required": True,
            "lines": hop_near,
            "expect": {"n_edges": 1.0, "chain_span": 1.0},
        },
        {
            "case_id": "two_hop_kv",
            "family": "graph_shape",
            "kind": "two_hop",
            "surface": "key_value",
            "required": True,
            "lines": two_hop,
            "expect": {"n_edges": 2.0, "chain_span": 2.0, "n_logical_units": 3},
        },
        {
            "case_id": "branch_kv",
            "family": "graph_shape",
            "kind": "branch",
            "surface": "key_value",
            "required": True,
            "lines": branch,
            "expect": {"n_edges": 2.0, "n_logical_units": 3, "component_span": 2.0},
        },
        {
            "case_id": "no_reference",
            "family": "negative",
            "kind": "no_reference",
            "surface": "key_value",
            "required": True,
            "lines": list(NOISE),
            "expect": {"n_edges": 0.0, "mean_edge_distance": 0.0},
        },
        {
            "case_id": "malformed_nul",
            "family": "negative",
            "kind": "malformed",
            "surface": "payload",
            "required": True,
            "payload_encoding": "nul",
            "expect": {"fail_closed": True, "n_edges": 0.0},
        },
    ]


def expected_relations() -> list[dict[str, Any]]:
    return [
        {
            "id": "near_lt_medium_lt_far",
            "metric": "mean_edge_distance",
            "order": ["true_dep_near_kv", "true_dep_medium_kv", "true_dep_far_kv"],
        },
        {
            "id": "scale_abs_raw_equal",
            "metric": "mean_edge_distance",
            "equal": ["scale_short", "scale_medium", "scale_long"],
        },
        {
            "id": "scale_norm_decreases",
            "metric": "mean_edge_distance_norm",
            "strict_decrease": ["scale_short", "scale_medium", "scale_long"],
        },
        {
            "id": "pretty_eq_compact_logical",
            "metrics": ["n_edges", "mean_edge_distance", "n_logical_units"],
            "equal": ["true_dep_near_json_pretty", "true_dep_near_json_compact"],
        },
        {
            "id": "blank_eq_near_logical",
            "metrics": ["n_edges", "mean_edge_distance", "n_logical_units"],
            "equal": ["true_dep_near_kv", "blank_line_kv"],
        },
        {
            "id": "wrap_pretty_eq_compact",
            "metrics": ["n_edges", "mean_edge_distance", "n_logical_units"],
            "equal": ["wrap_pretty_json", "true_dep_near_json_compact"],
        },
        {
            "id": "cooccurrence_zero_edges",
            "metric": "n_edges",
            "equal_to": 0.0,
            "cases": [
                "shared_env_only",
                "shared_service_only",
                "shared_owner_only",
                "shared_label_only",
                "multiple_unrelated_same_identifiers",
            ],
        },
        {
            "id": "pollution_matches_true_near",
            "metrics": ["n_edges", "mean_edge_distance"],
            "equal": ["true_dep_near_kv", "true_edge_plus_cooccurrence_pollution"],
        },
        {
            "id": "two_hop_chain_gt_one_hop",
            "metric": "chain_span",
            "order": ["one_hop_kv", "two_hop_kv"],
        },
    ]


def edge_candidates() -> list[dict[str, Any]]:
    return [
        {
            "id": "value_to_any_occurrence",
            "equals_v0": True,
            "shared_label_becomes_edge": True,
            "one_hop_kv": True,
            "v1_role": "rejected_as_primary",
        },
        {
            "id": "value_to_value_cooccurrence",
            "shared_label_becomes_edge": True,
            "one_hop_kv": False,
            "v1_role": "rejected_as_primary",
        },
        {
            "id": "value_to_foreign_key_side",
            "shared_label_becomes_edge": False,
            "one_hop_kv": True,
            "json_id_field_parent_pointer": False,
            "v1_role": "part_of_primary",
        },
        {
            "id": "value_to_record_identifier",
            "shared_label_becomes_edge": False,
            "one_hop_kv": True,
            "json_id_field_parent_pointer": True,
            "v1_role": "part_of_primary",
            "record_id_fields": list(RECORD_ID_FIELDS),
        },
        {
            "id": PRIMARY_EDGE_RULE,
            "heuristic": True,
            "shared_label_becomes_edge": False,
            "one_hop_kv": True,
            "json_id_field_parent_pointer": True,
            "v1_role": "primary",
            "note": (
                "value-side identifier on unit i edges to unit j iff j exposes "
                "that identifier on key-side or as a closed record-id field value"
            ),
        },
    ]


def freeze_manifest() -> dict[str, Any]:
    fixtures = fixture_specs()
    relations = expected_relations()
    candidates = edge_candidates()
    blocked_reasons: list[str] = []
    if PRIMARY_EDGE_RULE == "value_to_any_occurrence":
        blocked_reasons.append("primary_edge_still_v0")
    if "prose" in REQUIRED_FORMATS:
        blocked_reasons.append("prose_cannot_be_required")
    if not all(item["expect"] for item in fixtures):
        blocked_reasons.append("fixture_missing_expect")
    verdict = VERDICT_BLOCKED if blocked_reasons else VERDICT_FROZEN
    return {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "status": verdict,
        "verdict": verdict,
        "blocked_reasons": blocked_reasons,
        "offline": True,
        "paid_api": False,
        "synthetic": True,
        "research_conclusion": False,
        "confirmatory": False,
        "implementation": "not_started",
        "sensor_code_changed": False,
        "v0_overwritten": False,
        "routing_connected": False,
        "evaluation_holdout_used": False,
        "routing_feature_choice": "not_decided",
        "integrate_threshold": None,
        "premise": "PHASE3C_SENSOR_SCOPED",
        "predecessor_sensor": V0_SENSOR,
        "v1_sensor_name": V1_SENSOR,
        "v0_limits_retained": list(V0_LIMITS),
        "stopword_expansion_is_not_primary_control": True,
        "gold_inputs": False,
        "phase2_key_prefixes_as_oracle": False,
        "performance": {
            "v0_algorithm": "value_atom_times_all_lines",
            "v1_algorithm": "single_pass_identifier_occurrence_index_then_lookup",
            "forbids": ["per_value_atom_full_document_scan"],
            "success_criterion": "algorithm_has_no_full_line_rescan_per_value_atom",
            "not_success_criterion": "faster_wall_time",
            "wall_time_slo": None,
            "measure_after_impl_line_counts": list(COST_LINE_COUNTS),
        },
        "logical_unit": {
            "distance_unit": DISTANCE_UNIT,
            "physical_line_index": "diagnostic_only",
            "key_value": "non_empty_line_with_equals_is_one_unit; blank_lines_are_not_units",
            "json": (
                "parse document; array-of-objects → one unit per object; "
                "object with k and v → one kv-encoded unit; "
                "pretty and compact that parse equal have equal unit sequences"
            ),
            "wrap_invariance": "pretty_print_and_blank_lines_only; mid_identifier_split_is_malformed",
        },
        "edge_rule": {
            "primary": PRIMARY_EDGE_RULE,
            "heuristic": True,
            "record_id_fields": list(RECORD_ID_FIELDS),
            "copies_are_not_edges": True,
            "accepted_false_negative": (
                "value-to-value pointer whose target has no matching key-side "
                "or record-id field"
            ),
            "candidates": candidates,
        },
        "format_scope": {
            "required": list(REQUIRED_FORMATS),
            "json_pretty_and_compact_same_logical_structure": True,
            "optional": list(OPTIONAL_FORMATS),
            "out_of_scope": list(OUT_OF_SCOPE_FORMATS),
            "do_not_promote_after_seeing_results": True,
        },
        "quantities": {
            "features": list(DIAGNOSTIC_FEATURES),
            "mean_edge_distance_means": "absolute_logical_unit_separation",
            "mean_edge_distance_norm_means": "relative_logical_unit_separation",
            "not_comparable_to_v0_line_distance_without_conversion": True,
            "threshold": "not_in_this_phase",
            "routing_choice": "not_decided",
        },
        "fixtures": fixtures,
        "expected_relations": relations,
        "fixture_identifiers": {
            "ref_a": REF_A,
            "ref_b": REF_B,
            "ref_out": REF_OUT,
            "shared_env": SHARED_ENV,
            "shared_service": SHARED_SVC,
            "shared_owner": SHARED_OWNER,
            "shared_label": SHARED_CAT,
            "shared_case": SHARED_CASE,
        },
        "purpose": (
            "freeze v1 sensor design from Phase 3C limits before any v1 code; "
            "not a routing rule and not a Phase 2 rescore"
        ),
    }


def validate_phase3d_doc(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append(f"bad schema: {doc.get('schema')!r}")
    if doc.get("paid_api") is not False:
        errs.append("paid_api must be false")
    if doc.get("routing_connected") is not False:
        errs.append("must not connect routing")
    if doc.get("evaluation_holdout_used") is not False:
        errs.append("must not use holdout")
    if doc.get("sensor_code_changed") is not False:
        errs.append("this phase must not change sensor code")
    if doc.get("v0_overwritten") is not False:
        errs.append("v0 must not be overwritten")
    if doc.get("implementation") != "not_started":
        errs.append("v1 must not be implemented in this phase")
    if doc.get("verdict") not in VERDICTS:
        errs.append(f"bad verdict: {doc.get('verdict')!r}")
    if doc.get("integrate_threshold") is not None:
        errs.append("must not set INTEGRATE threshold")
    if doc.get("routing_feature_choice") != "not_decided":
        errs.append("must not pick a routing feature")
    scope = doc.get("format_scope") or {}
    if list(scope.get("required") or []) != list(REQUIRED_FORMATS):
        errs.append("required formats drifted")
    if "prose" in list(scope.get("required") or []):
        errs.append("prose must not be required")
    if scope.get("do_not_promote_after_seeing_results") is not True:
        errs.append("format scope must stay frozen")
    perf = doc.get("performance") or {}
    if perf.get("wall_time_slo") is not None:
        errs.append("must not set a wall-time SLO")
    if list(perf.get("measure_after_impl_line_counts") or []) != list(COST_LINE_COUNTS):
        errs.append("cost sizes drifted")
    edge = doc.get("edge_rule") or {}
    if edge.get("primary") != PRIMARY_EDGE_RULE:
        errs.append("primary edge rule drifted")
    if edge.get("heuristic") is not True:
        errs.append("edge rule must be marked heuristic")
    if list(doc.get("v0_limits_retained") or []) != list(V0_LIMITS):
        errs.append("v0 limits must stay listed")
    cases = [str(item.get("case_id")) for item in list(doc.get("fixtures") or [])]
    needed = (
        "true_dep_near_kv",
        "true_dep_medium_kv",
        "true_dep_far_kv",
        "true_dep_near_json_pretty",
        "true_dep_near_json_compact",
        "scale_short",
        "scale_medium",
        "scale_long",
        "blank_line_kv",
        "wrap_pretty_json",
        "shared_env_only",
        "shared_service_only",
        "shared_owner_only",
        "shared_label_only",
        "multiple_unrelated_same_identifiers",
        "true_edge_plus_cooccurrence_pollution",
        "one_hop_kv",
        "two_hop_kv",
        "branch_kv",
        "no_reference",
        "malformed_nul",
    )
    for case_id in needed:
        if case_id not in cases:
            errs.append(f"missing fixture {case_id}")
    rel_ids = [str(item.get("id")) for item in list(doc.get("expected_relations") or [])]
    if "near_lt_medium_lt_far" not in rel_ids:
        errs.append("missing predeclared near<medium<far")
    if doc.get("stopword_expansion_is_not_primary_control") is not True:
        errs.append("stopword expansion must not be the primary control")
    return errs


def write_freeze(path: Path | None = None) -> Path:
    target = path or FREEZE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(freeze_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target
