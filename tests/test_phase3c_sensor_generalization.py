"""Phase 3C generalization audit tests.

Expectations live in fixtures, not in post-hoc numbers.
Phase 2 evaluation is not an input. The v0 sensor is not rewritten here.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from bite_eval.phase3c_audit import SCHEMA_ID, validate_phase3c_doc
from bite_eval.phase3c_fixtures import (
    ABS_EDGE_DISTANCE,
    ABS_TAILS,
    COST_LINE_COUNTS,
    DIAGNOSTIC_FEATURES,
    EXPECTED_FORMAT_STATUS,
    QUANTITY_MEANING,
    REL_N_LINES,
    SHARED_CAT,
    SHARED_ENV,
    SHARED_OWNER,
    SHARED_SVC,
    abs_scale_lines,
    blank_lines_doc,
    compact_json_one_line,
    csv_doc,
    false_positive_docs,
    format_docs,
    kv_pair,
    oneline_json_pair,
    pollution_doc,
    pretty_json_doc,
    prose_doc,
    rel_scale_lines,
    yaml_doc,
)
from bite_ingestion.profilers.dependency_dispersion import (
    PRIMARY_FEATURE,
    SENSOR_NAME,
    STOPWORDS,
    measure,
)

ROOT = Path(__file__).resolve().parents[1]
SENSOR_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "dependency_dispersion.py"
V0_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "deterministic.py"
POLICY_PY = ROOT / "src" / "bite_ingestion" / "policies" / "rule_policy.py"
THRESH_PY = ROOT / "src" / "bite_ingestion" / "policies" / "thresholds.py"
AUDIT_PY = ROOT / "src" / "bite_eval" / "phase3c_audit.py"
FIXTURES_PY = ROOT / "src" / "bite_eval" / "phase3c_fixtures.py"
SCRIPT_PY = ROOT / "scripts" / "run_phase3c_audit.py"
ARTIFACT = ROOT / "artifacts" / "phase3c" / "sensor-generalization.json"
SCHEMA = ROOT / "spec" / "phase3c-sensor-generalization.schema.json"


def _unit(text: str) -> dict[str, str]:
    return {"payload": text, "text": text}


def test_phase3c_source_excludes_phase2_holdout() -> None:
    needles = (
        "confirmatory-offline",
        "confirmatory_pairs",
        "design_cells",
        "EVALUATION_REPLICAS",
        "generate_phase2a_bundle",
        "p2a-",
        "syn-case",
        "lookup_for_",
        "next_for_",
        "value_for_",
        "phase2d_confirmatory",
        "bite_bench.phase2a",
    )
    for path in (AUDIT_PY, FIXTURES_PY, SCRIPT_PY):
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            assert needle not in text, f"{path.name}: {needle}"


def test_phase3c_does_not_read_spent_eval_artifact() -> None:
    src = AUDIT_PY.read_text(encoding="utf-8") + FIXTURES_PY.read_text(encoding="utf-8")
    assert "artifacts/phase2d" not in src
    assert "artifacts/phase2c" not in src
    assert "artifacts/phase2b" not in src


def test_sensor_and_routing_untouched() -> None:
    assert SENSOR_NAME == "dependency_dispersion_v0"
    v0 = V0_PY.read_text(encoding="utf-8")
    assert 'name = "deterministic_v0"' in v0
    policy = POLICY_PY.read_text(encoding="utf-8")
    thresh = THRESH_PY.read_text(encoding="utf-8")
    assert "HIGH: float = 0.66" in thresh
    assert "LOW: float = 0.34" in thresh
    assert "ROUTING_FEATURES" in policy
    sensor = SENSOR_PY.read_text(encoding="utf-8")
    assert "RulePolicy" not in sensor
    assert "TBD_CALIBRATE" not in sensor
    assert "propose(" not in sensor
    audit = AUDIT_PY.read_text(encoding="utf-8")
    assert "from bite_ingestion.profilers.dependency_dispersion import" in audit
    assert "STOPWORDS =" not in audit
    assert "STOPWORDS =" not in FIXTURES_PY.read_text(encoding="utf-8")


def test_false_positive_labels_are_not_added_to_stopwords() -> None:
    for token in (SHARED_ENV, SHARED_SVC, SHARED_OWNER, SHARED_CAT):
        assert token.casefold() not in STOPWORDS


def test_predeclared_quantity_meaning() -> None:
    assert QUANTITY_MEANING["mean_edge_distance"] == "absolute_dependency_separation"
    assert QUANTITY_MEANING["mean_edge_distance_norm"] == "relative_dependency_separation"
    assert DIAGNOSTIC_FEATURES == (
        "mean_edge_distance",
        "mean_edge_distance_norm",
        "median_edge_distance",
        "component_span",
        "chain_span",
    )


def test_abs_scale_raw_stable_norm_falls() -> None:
    snaps = [measure(_unit("\n".join(abs_scale_lines(tail)))) for _, tail in ABS_TAILS]
    raw = [float(s.features["mean_edge_distance"]) for s in snaps]
    norms = [float(s.features["mean_edge_distance_norm"]) for s in snaps]
    assert raw == [float(ABS_EDGE_DISTANCE)] * 3
    assert norms[0] > norms[1] > norms[2]


def test_rel_scale_raw_grows_norm_is_one() -> None:
    snaps = [measure(_unit("\n".join(rel_scale_lines(n)))) for n in REL_N_LINES]
    raw = [float(s.features["mean_edge_distance"]) for s in snaps]
    norms = [float(s.features["mean_edge_distance_norm"]) for s in snaps]
    assert raw[0] < raw[1] < raw[2]
    assert norms == [1.0, 1.0, 1.0]


def test_line_granularity_blank_and_pretty() -> None:
    kv = measure(_unit(kv_pair()))
    blank = measure(_unit(blank_lines_doc()))
    pretty = measure(_unit(pretty_json_doc()))
    compact = measure(_unit(compact_json_one_line()))
    nested = measure(_unit(oneline_json_pair()))
    assert kv.features["n_edges"] == 1.0
    assert nested.features["n_edges"] == 1.0
    assert nested.features[PRIMARY_FEATURE] == kv.features[PRIMARY_FEATURE]
    assert blank.features[PRIMARY_FEATURE] > kv.features[PRIMARY_FEATURE]
    assert pretty.features["n_edges"] == 0.0
    assert compact.features["n_edges"] == 0.0


def test_false_positive_cooccurrence_becomes_edges() -> None:
    docs = false_positive_docs()
    for key in (
        "shared_env",
        "shared_service",
        "shared_owner",
        "shared_category",
        "unrelated_records_same_identifier",
    ):
        got = measure(_unit(docs[key]))
        assert got.features["n_edges"] >= 1.0, key
    pollute = measure(_unit(pollution_doc()))
    assert pollute.features["n_edges"] > 1.0
    assert pollute.features[PRIMARY_FEATURE] > 1.0


def test_format_coverage_matches_predeclaration() -> None:
    for name, text in format_docs().items():
        n_edges = measure(_unit(text)).features["n_edges"]
        observed = "supported" if n_edges > 0.0 else "unsupported"
        assert observed == EXPECTED_FORMAT_STATUS[name], name
    assert measure(_unit(csv_doc())).features["n_edges"] == 0.0
    assert measure(_unit(yaml_doc())).features["n_edges"] == 0.0
    assert measure(_unit(prose_doc())).features["n_edges"] == 0.0


def test_committed_artifact() -> None:
    assert ARTIFACT.is_file(), "run scripts/run_phase3c_audit.py"
    doc = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert validate_phase3c_doc(doc) == []
    jsonschema.validate(doc, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert doc["schema"] == SCHEMA_ID
    assert doc["paid_api"] is False
    assert doc["routing_connected"] is False
    assert doc["evaluation_holdout_used"] is False
    assert doc["sensor_behavior_changed"] is False
    assert doc["routing_feature_choice"] == "not_decided"
    assert doc["verdict"] in {
        "PHASE3C_SENSOR_GENERALIZES",
        "PHASE3C_SENSOR_SCOPED",
        "PHASE3C_SENSOR_REVISE",
    }
    assert [row["n_lines_requested"] for row in doc["cost"]] == list(COST_LINE_COUNTS)
    artifact_text = ARTIFACT.read_text(encoding="utf-8")
    for needle in ("syn-case", "p2a-", "lookup_for_"):
        assert needle not in artifact_text
