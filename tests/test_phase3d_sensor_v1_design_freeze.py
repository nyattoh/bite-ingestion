"""Phase 3D v1 design-freeze invariants.

Does not implement the sensor. Does not open Phase 2 evaluation.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from bite_eval.phase3d_v1_freeze import (
    COST_LINE_COUNTS,
    DIAGNOSTIC_FEATURES,
    PRIMARY_EDGE_RULE,
    REQUIRED_FORMATS,
    SCHEMA_ID,
    V0_LIMITS,
    V0_SENSOR,
    V1_SENSOR,
    freeze_manifest,
    validate_phase3d_doc,
)
from bite_ingestion.policies.thresholds import TBD_CALIBRATE
from bite_ingestion.profilers.dependency_dispersion import SENSOR_NAME, STOPWORDS

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase3d-sensor-v1-design-freeze.json"
SCHEMA = ROOT / "spec" / "phase3d-sensor-v1-design-freeze.schema.json"
FREEZE_PY = ROOT / "src" / "bite_eval" / "phase3d_v1_freeze.py"
SENSOR_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "dependency_dispersion.py"
V0_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "deterministic.py"
POLICY_PY = ROOT / "src" / "bite_ingestion" / "policies" / "rule_policy.py"


def test_committed_freeze_matches_code() -> None:
    assert FREEZE.is_file(), "write benchmarks/spec/phase3d-sensor-v1-design-freeze.json"
    doc = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert doc == freeze_manifest()
    assert validate_phase3d_doc(doc) == []
    jsonschema.validate(doc, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert doc["schema"] == SCHEMA_ID
    assert doc["verdict"] == "PHASE3D_V1_DESIGN_FROZEN"
    assert doc["blocked_reasons"] == []


def test_phase3d_source_excludes_holdout_and_does_not_implement_v1() -> None:
    text = FREEZE_PY.read_text(encoding="utf-8")
    for needle in (
        "confirmatory-offline",
        "confirmatory_pairs",
        "design_cells",
        "EVALUATION_REPLICAS",
        "generate_phase2a_bundle",
        "p2a-",
        "syn-case",
        "lookup_for_",
        "phase2d_confirmatory",
        "bite_bench.phase2a",
    ):
        assert needle not in text, needle
    assert "def measure(" not in text
    assert "class DependencyDispersionSensor" not in text


def test_v0_sensor_and_routing_untouched() -> None:
    assert SENSOR_NAME == V0_SENSOR
    assert V1_SENSOR != V0_SENSOR
    sensor = SENSOR_PY.read_text(encoding="utf-8")
    assert f'SENSOR_NAME = "{V0_SENSOR}"' in sensor
    assert V1_SENSOR not in sensor
    assert 'name = "deterministic_v0"' in V0_PY.read_text(encoding="utf-8")
    assert "ROUTING_FEATURES" in POLICY_PY.read_text(encoding="utf-8")
    assert TBD_CALIBRATE.HIGH == 0.66
    assert TBD_CALIBRATE.LOW == 0.34


def test_v0_limits_and_format_scope_are_frozen() -> None:
    doc = freeze_manifest()
    assert doc["v0_limits_retained"] == list(V0_LIMITS)
    assert doc["format_scope"]["required"] == list(REQUIRED_FORMATS)
    assert doc["format_scope"]["optional"] == ["csv", "yaml"]
    assert doc["format_scope"]["out_of_scope"] == ["prose"]
    assert doc["format_scope"]["do_not_promote_after_seeing_results"] is True
    assert doc["performance"]["wall_time_slo"] is None
    assert doc["performance"]["measure_after_impl_line_counts"] == list(COST_LINE_COUNTS)
    assert "per_value_atom_full_document_scan" in doc["performance"]["forbids"]
    assert doc["quantities"]["features"] == list(DIAGNOSTIC_FEATURES)
    assert doc["quantities"]["threshold"] == "not_in_this_phase"
    assert doc["routing_feature_choice"] == "not_decided"
    assert doc["integrate_threshold"] is None


def test_primary_edge_rule_rejects_mere_cooccurrence() -> None:
    doc = freeze_manifest()
    assert doc["edge_rule"]["primary"] == PRIMARY_EDGE_RULE
    assert doc["edge_rule"]["heuristic"] is True
    by_id = {row["id"]: row for row in doc["edge_rule"]["candidates"]}
    assert by_id["value_to_any_occurrence"]["v1_role"] == "rejected_as_primary"
    assert by_id["value_to_value_cooccurrence"]["v1_role"] == "rejected_as_primary"
    assert by_id[PRIMARY_EDGE_RULE]["shared_label_becomes_edge"] is False
    item = doc["fixture_identifiers"]
    ids = {
        item["shared_env"],
        item["shared_service"],
        item["shared_owner"],
        item["shared_label"],
        item["shared_case"],
    }
    for token in ids:
        assert token.casefold() not in STOPWORDS


def test_expected_relations_are_predeclared() -> None:
    doc = freeze_manifest()
    rel = {row["id"]: row for row in doc["expected_relations"]}
    assert rel["near_lt_medium_lt_far"]["order"] == [
        "true_dep_near_kv",
        "true_dep_medium_kv",
        "true_dep_far_kv",
    ]
    assert rel["pretty_eq_compact_logical"]["equal"] == [
        "true_dep_near_json_pretty",
        "true_dep_near_json_compact",
    ]
    assert "shared_env_only" in rel["cooccurrence_zero_edges"]["cases"]
    assert rel["pollution_matches_true_near"]["equal"] == [
        "true_dep_near_kv",
        "true_edge_plus_cooccurrence_pollution",
    ]
    by_id = {row["case_id"]: row for row in doc["fixtures"]}
    assert by_id["shared_env_only"]["expect"]["n_edges"] == 0.0
    assert by_id["true_dep_near_json_pretty"]["expect"]["n_logical_units"] == 2
    assert by_id["blank_line_kv"]["expect"]["mean_edge_distance"] == 1.0
    assert by_id["true_edge_plus_cooccurrence_pollution"]["expect"]["n_edges"] == 1.0


def test_committed_freeze_excludes_holdout_ids() -> None:
    blob = FREEZE.read_text(encoding="utf-8")
    for needle in ("syn-case", "p2a-", "lookup_for_", "confirmatory-offline"):
        assert needle not in blob
