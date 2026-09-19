"""Phase 3R R0 freeze and R1 channel-planner tests.

Does not change Phase 3Q/3O. Does not open p3f. Does not retune thresholds.
"""

from __future__ import annotations

import json
import subprocess
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
from bite_eval.phase3r_eval import (
    LOCKED_BLOBS,
    PROTOCOL_COMMIT_SHA,
    RESULT_PATH,
    run_evaluation,
    validate_phase3r_result,
)
from bite_ingestion.profilers.dependency_dispersion_v1 import measure as measure_v1
from bite_ingestion.profilers.dependency_dispersion_v2 import measure as measure_v2

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


def test_v2_fail_closed_and_does_not_rewrite_v1() -> None:
    nul = measure_v2({"payload": "src_pier_x=tide_lock_x\x00"})
    assert nul.fail_closed is True
    assert nul.features["n_reference_edges"] == 0.0
    bad = measure_v2({"payload": "{"})
    assert bad.fail_closed is True
    hop = "src_pier_ref=tide_lock_ref\ndst_tide_lock_ref=wake_ref\n"
    v1 = measure_v1({"payload": hop})
    v2 = measure_v2({"payload": hop})
    assert v1.fail_closed is False and v2.fail_closed is False
    assert v1.features["n_edges"] == v2.features["n_reference_edges"]
    assert v1.features["mean_edge_distance"] == v2.features["mean_reference_edge_distance"]
    for rel, expected in LOCKED_BLOBS.items():
        observed = subprocess.check_output(
            ["git", "hash-object", rel], cwd=ROOT, text=True
        ).strip()
        assert observed == expected, rel


def test_p1_matches_artifacts_and_keeps_seals() -> None:
    doc = run_evaluation()
    committed = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(doc, sort_keys=True)) == json.loads(
        json.dumps(committed, sort_keys=True)
    )
    assert validate_phase3r_result(committed) == []
    jsonschema.validate(
        committed,
        json.loads((ROOT / "spec" / "phase3r-channel-planner.schema.json").read_text(encoding="utf-8")),
    )
    for name in (
        "channel-separation.json",
        "planner-integrity.json",
        "composition-safety.json",
        "xfer2-regression.json",
    ):
        extra = json.loads((ROOT / "artifacts" / "phase3r" / name).read_text(encoding="utf-8"))
        schema = json.loads(
            (ROOT / "spec" / f"phase3r-{name.replace('.json', '')}.schema.json").read_text(
                encoding="utf-8"
            )
        )
        jsonschema.validate(extra, schema)
    assert committed["protocol_commit_sha"] == PROTOCOL_COMMIT_SHA
    assert committed["verdict"] == "PHASE3R_CHANNEL_PLANNER_VALIDATED"
    assert committed["n_track_a_ok"] == 56
    assert committed["n_track_a"] == 56
    assert committed["t_high_carry_forward"] is True
    assert committed["p3f_evaluation_holdout_used"] is False
    assert committed["calibration"] is False
    assert committed["no_threshold_grid"] is True
    assert committed["xfer2_regression"]["primary"] is False
    assert committed["phase3q_remains"] == "Phase3Q remains FAILED"
    assert json.loads(PHASE3Q.read_text(encoding="utf-8"))["verdict"] == PREMISE
    blob = RESULT_PATH.read_text(encoding="utf-8")
    assert "p3f-" not in blob
    eval_py = (ROOT / "src" / "bite_eval" / "phase3r_eval.py").read_text(encoding="utf-8")
    assert "bite_bench.xfer1_corpus" not in eval_py
    assert "bite_bench.phase3m" not in eval_py
    assert "bite_bench.phase3p" not in eval_py
    assert "RulePolicy(" not in eval_py
