"""Phase 3S S0 freeze and S1 specificity-audit tests.

Does not change Phase 3R/3Q. Does not open p3f. Does not repair v2.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase3s import (
    LOCKED_BLOBS,
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
from bite_eval.phase3s_eval import (
    PROTOCOL_COMMIT_SHA,
    RESULT_PATH,
    run_evaluation,
    validate_phase3s_result,
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


def test_s1_matches_artifacts_and_does_not_repair() -> None:
    doc = run_evaluation()
    committed = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(doc, sort_keys=True)) == json.loads(
        json.dumps(committed, sort_keys=True)
    )
    assert validate_phase3s_result(committed) == []
    jsonschema.validate(
        committed,
        json.loads(
            (ROOT / "spec" / "phase3s-reference-specificity.schema.json").read_text(encoding="utf-8")
        ),
    )
    for name in (
        "edge-rows.json",
        "edge-precision.json",
        "gate.json",
        "policy-consequence.json",
        "cross-format.json",
    ):
        extra = json.loads((ROOT / "artifacts" / "phase3s" / name).read_text(encoding="utf-8"))
        schema = json.loads(
            (ROOT / "spec" / f"phase3s-{name.replace('.json', '')}.schema.json").read_text(
                encoding="utf-8"
            )
        )
        jsonschema.validate(extra, schema)
    assert committed["protocol_commit_sha"] == PROTOCOL_COMMIT_SHA
    assert committed["verdict"] in {
        "PHASE3S_REFERENCE_SPECIFICITY_CONFIRMED",
        "PHASE3S_REFERENCE_SPECIFICITY_FAILED",
        "PHASE3S_REFERENCE_SPECIFICITY_BLOCKED",
    }
    assert committed["n_surfaces"] == N_SURFACES
    assert committed["p3f_evaluation_holdout_used"] is False
    assert committed["no_repair"] is True
    assert committed["phase3q_remains"] == "Phase3Q remains FAILED"
    assert json.loads(PHASE3R.read_text(encoding="utf-8"))["verdict"] == PREMISE
    assert json.loads(PHASE3Q.read_text(encoding="utf-8"))["verdict"] == PHASE3Q_VERDICT
    if committed["verdict"] == "PHASE3S_REFERENCE_SPECIFICITY_FAILED":
        assert committed["edge_precision"]["n_extra"] > 0
        assert committed["by_family"]["true_reference_only"]["n_ok"] == 16
        assert committed["by_family"]["suffix_collision_only"]["n_ok"] == 0
    blob = RESULT_PATH.read_text(encoding="utf-8")
    assert "p3f-" not in blob
    eval_py = (ROOT / "src" / "bite_eval" / "phase3s_eval.py").read_text(encoding="utf-8")
    assert "bite_bench.xfer1_corpus" not in eval_py
    assert "RulePolicy(" not in eval_py
    for rel, expected in LOCKED_BLOBS.items():
        observed = subprocess.check_output(
            ["git", "hash-object", rel], cwd=ROOT, text=True
        ).strip()
        assert observed == expected, rel
