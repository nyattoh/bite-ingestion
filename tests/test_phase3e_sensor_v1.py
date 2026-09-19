"""Phase 3E v1 sensor validation tests.

Uses frozen Phase 3D expectations. Does not retune freeze values.
Does not open Phase 2 evaluation. Does not change v0.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from bite_eval.phase3d_v1_freeze import fixture_specs, freeze_manifest
from bite_eval.phase3e_validate import (
    SCHEMA_ID,
    fixture_payload,
    validate_phase3e_doc,
)
from bite_ingestion.policies.thresholds import TBD_CALIBRATE
from bite_ingestion.profilers.dependency_dispersion import SENSOR_NAME as V0_NAME
from bite_ingestion.profilers.dependency_dispersion import STOPWORDS
from bite_ingestion.profilers.dependency_dispersion_v1 import (
    SENSOR_NAME,
    measure,
)

ROOT = Path(__file__).resolve().parents[1]
V0_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "dependency_dispersion.py"
V1_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "dependency_dispersion_v1.py"
FREEZE_JSON = ROOT / "benchmarks" / "spec" / "phase3d-sensor-v1-design-freeze.json"
VALIDATE_PY = ROOT / "src" / "bite_eval" / "phase3e_validate.py"
ARTIFACT = ROOT / "artifacts" / "phase3e" / "sensor-v1-validation.json"
SCHEMA = ROOT / "spec" / "phase3e-sensor-v1-validation.schema.json"


def test_phase3d_freeze_is_unmodified() -> None:
    committed = json.loads(FREEZE_JSON.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()


def test_v0_and_routing_untouched() -> None:
    assert V0_NAME == "dependency_dispersion_v0"
    assert SENSOR_NAME == "dependency_dispersion_v1"
    v0 = V0_PY.read_text(encoding="utf-8")
    assert 'SENSOR_NAME = "dependency_dispersion_v0"' in v0
    assert TBD_CALIBRATE.HIGH == 0.66
    assert TBD_CALIBRATE.LOW == 0.34
    v1 = V1_PY.read_text(encoding="utf-8")
    assert "RulePolicy" not in v1
    assert "TBD_CALIBRATE" not in v1
    assert "lookup_for_" not in v1
    assert "required_evidence" not in v1


def test_v1_has_no_per_value_full_document_scan() -> None:
    source = V1_PY.read_text(encoding="utf-8")
    assert "_contains_atom" not in source
    assert "for j, other in enumerate" not in source
    assert "_build_target_index" in source
    assert "target_index.get(" in source


def test_holdout_not_used() -> None:
    for path in (V1_PY, VALIDATE_PY):
        text = path.read_text(encoding="utf-8")
        for needle in (
            "confirmatory-offline",
            "confirmatory_pairs",
            "design_cells",
            "generate_phase2a_bundle",
            "p2a-",
            "syn-case",
            "lookup_for_",
            "phase2d_confirmatory",
        ):
            assert needle not in text, f"{path.name}: {needle}"


def test_frozen_fixture_expects() -> None:
    for case in fixture_specs():
        report = measure({"payload": fixture_payload(case), "text": fixture_payload(case)})
        observed = {
            **report.features,
            "n_logical_units": report.diagnostics["n_logical_units"],
            "fail_closed": report.fail_closed,
        }
        for key, expected in dict(case["expect"]).items():
            assert observed[key] == expected, f"{case['case_id']} {key}"


def test_gold_fields_do_not_change_features() -> None:
    case = next(c for c in fixture_specs() if c["case_id"] == "true_dep_far_kv")
    payload = fixture_payload(case)
    base = measure({"payload": payload, "text": payload})
    leaked = measure(
        {
            "payload": payload,
            "text": payload,
            "gold_answer": "IGNORE",
            "gold_route": "(INTEGRATE)",
            "required_evidence_ids": ["gold-1"],
        }
    )
    assert base.features == leaked.features


def test_shared_labels_are_not_added_to_stopwords() -> None:
    ids = freeze_manifest()["fixture_identifiers"]
    for token in ids.values():
        assert str(token).casefold() not in STOPWORDS


def test_committed_artifact() -> None:
    assert ARTIFACT.is_file(), "run scripts/run_phase3e_validate.py"
    doc = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert validate_phase3e_doc(doc) == []
    jsonschema.validate(doc, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert doc["schema"] == SCHEMA_ID
    assert doc["verdict"] in {
        "PHASE3E_V1_VALIDATED",
        "PHASE3E_V1_PARTIAL",
        "PHASE3E_IMPLEMENTATION_BLOCKED",
    }
    assert doc["paid_api"] is False
    assert doc["routing_connected"] is False
    assert doc["evaluation_holdout_used"] is False
    assert doc["v0_overwritten"] is False
    assert doc["freeze_modified"] is False
    assert doc["n_fixtures_matched"] == doc["n_fixtures"]
