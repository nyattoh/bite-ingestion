"""Phase 3S S0 freeze tests.

Does not run v2 sensor, planner, or policy v3.
Does not change Phase 3R/3Q. Does not open p3f.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase3s import (
    N_CANONICAL,
    N_SURFACES,
    PHASE3Q_VERDICT,
    PREMISE,
    PROTOCOL_FROZEN,
    EvaluationSealError,
    forbidden_hits,
    freeze_manifest,
    refuse_p3f_evaluation,
    validate_phase3s_freeze,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase3s-reference-specificity-freeze.json"
SCHEMA = ROOT / "spec" / "phase3s-reference-specificity-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase3s.py"
PHASE3R = ROOT / "artifacts" / "phase3r" / "channel-planner.json"
PHASE3Q = ROOT / "artifacts" / "phase3q" / "xfer2-transfer.json"
V2_SENSOR = ROOT / "src" / "bite_ingestion" / "profilers" / "dependency_dispersion_v2.py"
V3_POLICY = ROOT / "src" / "bite_ingestion" / "policies" / "conditional_texture_policy_v3.py"
PLANNER = ROOT / "src" / "bite_ingestion" / "policies" / "projected_actionability_plan_v1.py"


def test_committed_freeze_matches_manifest() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_phase3s_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["premise"] == PREMISE
    assert committed["copy_p3f_cases"] is False
    assert committed["copy_p3r_cases"] is False
    assert committed["p3f_evaluation_holdout_used"] is False
    assert committed["no_repair"] is True
    assert committed["no_key_side_atoms_change"] is True
    assert committed["n_surfaces"] == N_SURFACES
    assert len(committed["planned_cases"]) == N_CANONICAL
    for spec in committed["planned_cases"]:
        assert "intended_reference_edges" in spec
        assert "gate_expected" in spec
        assert "records" in spec
        assert forbidden_hits(json.dumps(spec["records"])) == []
        if spec["family"] == "suffix_collision_plus_actionability":
            assert spec["intended_reference_edges"] == []
            assert spec["gate_expected"] is False
            assert spec["policy_sequence_expected"] == []
        if spec["family"] == "true_reference_only":
            assert spec["intended_reference_edges"] == [[0, spec["distance"]]]
            assert spec["gate_expected"] is (spec["distance"] >= 4)


def test_phase3r_stays_validated_and_p3f_sealed() -> None:
    assert json.loads(PHASE3R.read_text(encoding="utf-8"))["verdict"] == PREMISE
    assert json.loads(PHASE3Q.read_text(encoding="utf-8"))["verdict"] == PHASE3Q_VERDICT
    blob = GEN_PY.read_text(encoding="utf-8")
    assert "from bite_ingestion.profilers.dependency_dispersion_v2" not in blob
    assert "from bite_ingestion.policies.projected_actionability_plan_v1" not in blob
    assert "from bite_ingestion.policies.conditional_texture_policy_v3" not in blob
    assert "measure(" not in blob
    assert "class RulePolicy" not in blob
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
    assert V2_SENSOR.is_file()
    assert V3_POLICY.is_file()
    assert PLANNER.is_file()
