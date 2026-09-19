"""Phase 3B gold-free dependency-dispersion sensor tests.

Expected inequalities are fixed in fixtures, not fitted after seeing numbers.
Does not open Phase 2 evaluation or retune deterministic_v0.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from bite_eval.phase3b_fixtures import (
    EXPECTED_DISTANCE_ORDER,
    FORBIDDEN_SENSOR_NEEDLES,
    development_cases,
    layout_one_hop,
)
from bite_eval.phase3b_sensor import SCHEMA_ID, validate_phase3b_doc
from bite_ingestion.profilers.dependency_dispersion import (
    PRIMARY_FEATURE,
    SENSOR_NAME,
    DependencyDispersionSensor,
    measure,
    query_identifier_span,
)
from bite_ingestion.profilers.deterministic import (
    FEATURE_KEYS,
    DeterministicMorphologyProfiler,
)

ROOT = Path(__file__).resolve().parents[1]
SENSOR_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "dependency_dispersion.py"
V0_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "deterministic.py"
ARTIFACT = ROOT / "artifacts" / "phase3b" / "sensor-evaluation.json"
SCHEMA = ROOT / "spec" / "phase3b-sensor-evaluation.schema.json"


def _unit(text: str, query: str = "What result is stored?") -> dict[str, str]:
    return {"payload": text, "text": text, "query": query}


def _d(text: str) -> float:
    return float(measure(_unit(text)).features[PRIMARY_FEATURE])


def test_sensor_source_is_gold_free_and_not_v0() -> None:
    source = SENSOR_PY.read_text(encoding="utf-8")
    for needle in FORBIDDEN_SENSOR_NEEDLES:
        assert needle not in source, needle
    v0 = V0_PY.read_text(encoding="utf-8")
    assert 'name = "deterministic_v0"' in v0
    assert DependencyDispersionSensor.name == SENSOR_NAME
    assert SENSOR_NAME != "deterministic_v0"


def test_expected_order_is_declared_before_use() -> None:
    assert EXPECTED_DISTANCE_ORDER == ("near", "medium", "far")


def test_one_hop_mean_distance_is_strictly_increasing() -> None:
    vals = [_d("\n".join(layout_one_hop(kind))) for kind in EXPECTED_DISTANCE_ORDER]
    assert vals[0] < vals[1] < vals[2]
    edges = [
        measure(_unit("\n".join(layout_one_hop(k)))).features["n_edges"]
        for k in EXPECTED_DISTANCE_ORDER
    ]
    assert edges == [1.0, 1.0, 1.0]


def test_v0_is_permutation_invariant_on_the_same_multiset() -> None:
    prof = DeterministicMorphologyProfiler()
    query = "What result is stored?"
    vectors = []
    for kind in EXPECTED_DISTANCE_ORDER:
        text = "\n".join(layout_one_hop(kind))
        vectors.append(tuple(prof.profile(_unit(text, query))[k] for k in FEATURE_KEYS))
    assert len(set(vectors)) == 1


def test_unrelated_noise_permutation_does_not_move_primary() -> None:
    near = _d("\n".join(layout_one_hop("near")))
    perm = next(c for c in development_cases() if c["case_id"] == "unrelated_perm")
    assert _d(perm["text"]) == near


def test_duplicate_noise_keeps_raw_distance_and_edge_count() -> None:
    near = measure(_unit("\n".join(layout_one_hop("near"))))
    dup = next(c for c in development_cases() if c["case_id"] == "duplicate_noise")
    got = measure(_unit(dup["text"]))
    assert got.features["n_edges"] == near.features["n_edges"] == 1.0
    assert got.features[PRIMARY_FEATURE] == near.features[PRIMARY_FEATURE]


def test_nested_surface_still_monotone() -> None:
    nested = {
        c["kind"]: c["text"]
        for c in development_cases()
        if c["family"] == "one_hop_nested"
    }
    vals = [_d(nested[kind]) for kind in EXPECTED_DISTANCE_ORDER]
    assert vals[0] < vals[1] < vals[2]


def test_two_hop_chain_span_increases() -> None:
    two = {c["kind"]: c["text"] for c in development_cases() if c["family"] == "two_hop"}
    spans = [measure(_unit(two[k])).features["chain_span"] for k in EXPECTED_DISTANCE_ORDER]
    assert spans[0] < spans[1] < spans[2]


def test_no_reference_and_false_positive() -> None:
    cases = {c["case_id"]: c for c in development_cases()}
    none = measure(_unit(cases["no_reference"]["text"]))
    fp = measure(_unit(cases["false_positive"]["text"]))
    assert none.features["n_edges"] == 0.0
    assert none.features[PRIMARY_FEATURE] == 0.0
    assert fp.features["n_edges"] == 0.0
    assert fp.features[PRIMARY_FEATURE] == 0.0


def test_malformed_nul_fail_closed() -> None:
    report = measure({"payload": "origin_bin=id_alpha_77\x00bin_id_alpha_77=id_result_99"})
    assert report.fail_closed is True
    assert report.features[PRIMARY_FEATURE] == 0.0


def test_ignores_gold_fields() -> None:
    text = "\n".join(layout_one_hop("near"))
    base = measure(_unit(text))
    leaked = measure(
        {
            **_unit(text),
            "gold_answer": "SHOULD_NOT_MATTER",
            "gold_route": "(INTEGRATE)",
            "required_evidence_ids": ["gold-1"],
        }
    )
    assert base.features == leaked.features


def test_deterministic_repeat() -> None:
    text = "\n".join(layout_one_hop("far"))
    assert measure(_unit(text)).features == measure(_unit(text)).features


def test_generic_query_span_is_idle_identifier_query_moves() -> None:
    far = next(c for c in development_cases() if c["case_id"] == "one_hop_far")
    generic = query_identifier_span(_unit(far["text"], far["query"]))
    specific = query_identifier_span(_unit(far["text"], far["query_with_identifier"]))
    assert generic["q_hits"] == 0.0
    assert specific["q_span"] > 0.0


def test_not_wired_to_rule_policy() -> None:
    source = SENSOR_PY.read_text(encoding="utf-8")
    assert "RulePolicy" not in source
    assert "TBD_CALIBRATE" not in source
    assert "propose(" not in source


def test_committed_artifact() -> None:
    assert ARTIFACT.is_file(), "run scripts/run_phase3b_sensor.py"
    doc = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert validate_phase3b_doc(doc) == []
    jsonschema.validate(doc, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert doc["schema"] == SCHEMA_ID
    assert doc["paid_api"] is False
    assert doc["routing_connected"] is False
    assert doc["evaluation_holdout_used"] is False
    assert doc["verdict"] in {
        "PHASE3B_SENSOR_READY",
        "PHASE3B_SENSOR_PARTIAL",
        "PHASE3B_SENSOR_NOT_READY",
    }
    assert doc["v0_overwritten"] is False
