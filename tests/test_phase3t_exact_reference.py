"""Phase 3T T0 freeze and T1 exact-reference tests.

Does not change Phase 3S/3Q. Does not open p3f.
Does not change v2 sensor, policy v3, planner, or operators.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase3t import (
    LOCKED_BLOBS,
    N_CANONICAL,
    N_SURFACES,
    PHASE3Q_VERDICT,
    PREMISE,
    PROTOCOL_FROZEN,
    SECONDARY_SURFACES,
    EvaluationSealError,
    forbidden_hits,
    freeze_manifest,
    refuse_p3f_evaluation,
    validate_phase3t_freeze,
)
from bite_eval.phase3t_eval import (
    PROTOCOL_COMMIT_SHA,
    RESULT_PATH,
    run_evaluation,
    validate_phase3t_result,
)
from bite_ingestion.profilers.dependency_dispersion_v3 import measure as measure_v3
from bite_ingestion.profilers.reference_identity_v1 import source_tokens, target_tokens

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase3t-exact-reference-freeze.json"
SCHEMA = ROOT / "spec" / "phase3t-exact-reference-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase3t.py"
PHASE3S = ROOT / "artifacts" / "phase3s" / "reference-specificity.json"
PHASE3Q = ROOT / "artifacts" / "phase3q" / "xfer2-transfer.json"
V2_SENSOR = ROOT / "src" / "bite_ingestion" / "profilers" / "dependency_dispersion_v2.py"
V3_POLICY = ROOT / "src" / "bite_ingestion" / "policies" / "conditional_texture_policy_v3.py"


def test_committed_freeze_matches_manifest() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_phase3t_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["premise"] == PREMISE
    assert committed["copy_p3s_content"] is False
    assert committed["p3f_evaluation_holdout_used"] is False
    assert committed["no_threshold_grid"] is True
    assert committed["no_planner_change"] is True
    assert committed["n_surfaces"] == N_SURFACES
    assert len(committed["planned_cases"]) == N_CANONICAL
    assert committed["reproduction_only_surfaces"] == list(SECONDARY_SURFACES)
    assert len(SECONDARY_SURFACES) == 48
    for spec in committed["planned_cases"]:
        assert "intended_reference_edges" in spec
        assert "gate_expected" in spec
        assert forbidden_hits(json.dumps(spec["records"])) == []
        if spec["family"] == "exact_reference_only":
            assert spec["bridge"] is True
            assert spec["intended_reference_edges"] == [[0, spec["distance"]]]
            assert spec["gate_expected"] is (spec["distance"] >= 4)
        if spec["family"] == "exact_reference_plus_suffix_collision" and spec["distance"] == 4:
            assert spec["gate_expected"] is True
        if spec["family"] == "suffix_collision_plus_actionability":
            assert spec["intended_reference_edges"] == []
            assert spec["gate_expected"] is False
            assert spec["policy_sequence_expected"] == []


def test_phase3s_stays_failed_and_p3f_sealed() -> None:
    assert json.loads(PHASE3S.read_text(encoding="utf-8"))["verdict"] == PREMISE
    assert json.loads(PHASE3Q.read_text(encoding="utf-8"))["verdict"] == PHASE3Q_VERDICT
    blob = GEN_PY.read_text(encoding="utf-8")
    assert "from bite_ingestion.profilers.dependency_dispersion_v3" not in blob
    assert "from bite_ingestion.profilers.reference_identity_v1" not in blob
    assert "from bite_ingestion.policies.conditional_texture_policy_v4" not in blob
    assert "class RulePolicy" not in blob
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
    assert V2_SENSOR.is_file()
    assert V3_POLICY.is_file()


def test_target_identity_has_no_underscore_suffix_expansion() -> None:
    tokens = target_tokens("bin_grove_keg_77")
    assert tokens == ("bin_grove_keg_77",)
    assert "grove_keg_77" not in tokens
    assert "keg_77" not in tokens
    assert "spool_77" not in source_tokens("bobbin_a id=spool_77 extra")


def test_v3_exact_token_not_suffix() -> None:
    exact = "src_warp=loom_heddle_77\nloom_heddle_77=weft_77\n"
    exact_report = measure_v3({"payload": exact, "text": exact})
    assert exact_report.features["n_reference_edges"] == 1.0
    assert exact_report.features["mean_reference_edge_distance"] == 1.0
    collision = "src_warp=heddle_77\nbin_shed_heddle_77=yarn_77\n"
    collision_report = measure_v3({"payload": collision, "text": collision})
    assert collision_report.features["n_reference_edges"] == 0.0


def test_t1_matches_artifacts_and_does_not_open_p3f() -> None:
    doc = run_evaluation()
    committed = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(doc, sort_keys=True)) == json.loads(
        json.dumps(committed, sort_keys=True)
    )
    assert validate_phase3t_result(committed) == []
    jsonschema.validate(
        committed,
        json.loads(
            (ROOT / "spec" / "phase3t-exact-reference.schema.json").read_text(encoding="utf-8")
        ),
    )
    for name in (
        "exact-edge.json",
        "threshold-bridge.json",
        "gate.json",
        "policy-consequence.json",
        "phase3s-regression.json",
    ):
        extra = json.loads((ROOT / "artifacts" / "phase3t" / name).read_text(encoding="utf-8"))
        schema = json.loads(
            (ROOT / "spec" / f"phase3t-{name.replace('.json', '')}.schema.json").read_text(
                encoding="utf-8"
            )
        )
        jsonschema.validate(extra, schema)
    assert committed["protocol_commit_sha"] == PROTOCOL_COMMIT_SHA
    assert committed["verdict"] in {
        "PHASE3T_EXACT_REFERENCE_VALIDATED",
        "PHASE3T_EXACT_REFERENCE_PARTIAL",
        "PHASE3T_EXACT_REFERENCE_BLOCKED",
    }
    assert committed["n_surfaces"] == N_SURFACES
    assert committed["p3f_evaluation_holdout_used"] is False
    assert committed["calibration"] is False
    assert committed["no_threshold_grid"] is True
    assert committed["phase3s_remains"] == "Phase3S remains FAILED"
    assert committed["phase3q_remains"] == "Phase3Q remains FAILED"
    assert committed["phase3s_regression"]["primary"] is False
    assert json.loads(PHASE3S.read_text(encoding="utf-8"))["verdict"] == PREMISE
    assert json.loads(PHASE3Q.read_text(encoding="utf-8"))["verdict"] == PHASE3Q_VERDICT
    blob = RESULT_PATH.read_text(encoding="utf-8")
    assert "p3f-" not in blob
    eval_py = (ROOT / "src" / "bite_eval" / "phase3t_eval.py").read_text(encoding="utf-8")
    assert "bite_bench.xfer1_corpus" not in eval_py
    assert "RulePolicy(" not in eval_py
    for rel, expected in LOCKED_BLOBS.items():
        observed = subprocess.check_output(
            ["git", "hash-object", rel], cwd=ROOT, text=True
        ).strip()
        assert observed == expected, rel
