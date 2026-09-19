"""Phase 3R R0 freeze tests.

Does not implement v2 sensor, planner, or policy v3.
Does not change Phase 3Q/3O. Does not open p3f.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase3r import (
    PHASE3O_VERDICT,
    PREMISE,
    PROTOCOL_FROZEN,
    REPRODUCTION_SURFACES,
    EvaluationSealError,
    freeze_manifest,
    refuse_p3f_evaluation,
    validate_phase3r_freeze,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase3r-channel-planner-freeze.json"
SCHEMA = ROOT / "spec" / "phase3r-channel-planner-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase3r.py"
PHASE3Q = ROOT / "artifacts" / "phase3q" / "xfer2-transfer.json"
PHASE3O = ROOT / "artifacts" / "phase3o" / "xfer1-transfer.json"
V1_SENSOR = ROOT / "src" / "bite_ingestion" / "profilers" / "dependency_dispersion_v1.py"
V2_POLICY = ROOT / "src" / "bite_ingestion" / "policies" / "conditional_texture_policy_v2.py"
V2_SAFETY = ROOT / "src" / "bite_eval" / "composition_safety_v2.py"


def test_committed_freeze_matches_manifest() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_phase3r_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["premise"] == PREMISE
    assert committed["copy_xfer2_cases"] is False
    assert committed["p3f_evaluation_holdout_used"] is False
    assert committed["no_threshold_grid"] is True
    assert committed["no_operator_semantic_change"] is True
    assert committed["reproduction_only_surfaces"] == list(REPRODUCTION_SURFACES)
    assert committed["reproduction_not_primary_evidence"] is True
    assert committed["track_a"]["n_surfaces"] == 56
    assert committed["phase3q_remains"] == "Phase3Q remains FAILED"


def test_phase3q_stays_failed_and_p3f_sealed() -> None:
    assert json.loads(PHASE3Q.read_text(encoding="utf-8"))["verdict"] == PREMISE
    assert json.loads(PHASE3O.read_text(encoding="utf-8"))["verdict"] == PHASE3O_VERDICT
    blob = GEN_PY.read_text(encoding="utf-8")
    assert "from bite_ingestion.profilers.dependency_dispersion_v2" not in blob
    assert "from bite_ingestion.policies.projected_actionability_plan_v1" not in blob
    assert "from bite_ingestion.policies.conditional_texture_policy_v3" not in blob
    assert "class RulePolicy" not in blob
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
    assert V1_SENSOR.is_file()
    assert V2_POLICY.is_file()
    assert "def composition_safety_v2(" in V2_SAFETY.read_text(encoding="utf-8")
