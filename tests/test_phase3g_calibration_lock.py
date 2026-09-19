"""Phase 3G calibration-only lock tests.

Does not open evaluation. Does not change v1 or RulePolicy.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase3f import CANDIDATES, Phase3FCell, freeze_manifest
from bite_eval.phase3g_calibrate import (
    GRID_PATH,
    LOCK_PATH,
    MEASURE_PATH,
    SCHEMA_ID,
    EvaluationSealError,
    enumerate_frozen_grid,
    measure_calibration_adversarial,
    measure_calibration_primary,
    refuse_if_evaluation,
    run_calibration,
    validate_phase3g_lock,
    validate_phase3g_measurements,
)
from bite_ingestion.policies.thresholds import TBD_CALIBRATE
from bite_ingestion.profilers.dependency_dispersion import SENSOR_NAME as V0_NAME
from bite_ingestion.profilers.dependency_dispersion_v1 import SENSOR_NAME as V1_NAME

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "spec" / "phase3g-calibration-lock.schema.json"
CALIBRATE_PY = ROOT / "src" / "bite_eval" / "phase3g_calibrate.py"
V1_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "dependency_dispersion_v1.py"
POLICY_PY = ROOT / "src" / "bite_ingestion" / "policies" / "rule_policy.py"
FREEZE_V03 = ROOT / "benchmarks" / "spec" / "phase3f-routing-calibration-freeze-v0.3.json"


def test_evaluation_replica_fails_closed_before_payload() -> None:
    with pytest.raises(EvaluationSealError, match="evaluation sealed"):
        refuse_if_evaluation(split="evaluation", replica=2)
    with pytest.raises(EvaluationSealError, match="evaluation sealed"):
        measure_calibration_adversarial("key_suffix_matches_value", 2, "key_value")
    cell = Phase3FCell("small", "one_hop", 2, "evaluation")
    with pytest.raises(EvaluationSealError, match="evaluation sealed"):
        measure_calibration_primary(cell, "near", "key_value")


def test_committed_artifacts_match_run() -> None:
    measurements, grid, lock = run_calibration()
    assert json.loads(json.dumps(measurements, sort_keys=True)) == json.loads(
        MEASURE_PATH.read_text(encoding="utf-8")
    )
    assert json.loads(json.dumps(grid, sort_keys=True)) == json.loads(
        GRID_PATH.read_text(encoding="utf-8")
    )
    assert json.loads(json.dumps(lock, sort_keys=True)) == json.loads(
        LOCK_PATH.read_text(encoding="utf-8")
    )
    assert validate_phase3g_lock(lock) == []
    assert validate_phase3g_measurements(measurements) == []
    jsonschema.validate(lock, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert lock["schema"] == SCHEMA_ID
    assert lock["freeze_revision"] == "phase3f-routing-calibration-freeze-v0.3"
    assert freeze_manifest() == json.loads(FREEZE_V03.read_text(encoding="utf-8"))
    assert lock["verdict"] in {
        "PHASE3G_CALIBRATION_LOCKED",
        "PHASE3G_CALIBRATION_BLOCKED",
    }


def test_artifacts_have_no_evaluation_replicas() -> None:
    blob = (
        MEASURE_PATH.read_text(encoding="utf-8")
        + GRID_PATH.read_text(encoding="utf-8")
        + LOCK_PATH.read_text(encoding="utf-8")
    )
    rows = json.loads(MEASURE_PATH.read_text(encoding="utf-8"))["rows"]
    assert len(rows) == 132
    for row in rows:
        assert row["replica"] in {0, 1}
        assert row["split"] == "calibration"
        assert "-r2-" not in row["surface_id"]
        assert "-r3-" not in row["surface_id"]
    assert '"replica": 2' not in blob
    assert '"replica": 3' not in blob
    for needle in ("operator_sequence", "T_profiler", "T_router", "p2a-", "syn-case"):
        assert needle not in blob


def test_only_frozen_grid_points_are_evaluated() -> None:
    freeze = freeze_manifest()
    grids = freeze["threshold_search"]["grids"]
    grid = json.loads(GRID_PATH.read_text(encoding="utf-8"))
    for cid in CANDIDATES:
        frozen = enumerate_frozen_grid(cid, grids)
        evaluated = [
            {key: point[key] for key in frozen[0]}
            for point in grid["candidates"][cid]["points"]
        ]
        assert evaluated == frozen
        assert grid["grids_extended"] is False
        assert grid["tolerance_added"] is False


def test_candidate_c_has_no_scalar_score() -> None:
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    c_row = lock["pre_threshold_metrics"]["C_raw_and_norm"]
    assert c_row["continuous_score"] is None
    assert c_row["weighted_sum"] is False
    blob = json.dumps(lock["pre_threshold_metrics"])
    assert "weighted_mean" not in blob
    assert "alpha_raw" not in blob


def test_m1_m2_not_selected_and_policy_untouched() -> None:
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    assert lock["operator_map_selected"] is False
    assert lock["selected_operator_map"] is None
    assert lock["high_bin_mapped_to_operator"] is False
    assert lock["routing_connected"] is False
    assert lock["rule_policy_changed"] is False
    assert V0_NAME == "dependency_dispersion_v0"
    assert V1_NAME == "dependency_dispersion_v1"
    assert TBD_CALIBRATE.HIGH == 0.66
    assert TBD_CALIBRATE.LOW == 0.34
    assert "ROUTING_FEATURES" in POLICY_PY.read_text(encoding="utf-8")
    src = CALIBRATE_PY.read_text(encoding="utf-8")
    for needle in (
        "bite_ingestion.policies",
        "TBD_CALIBRATE",
        "bite_bench.phase2a",
        "generate_phase2a_bundle",
        "confirmatory-offline",
    ):
        assert needle not in src
    assert "def _key_side_atoms(" in V1_PY.read_text(encoding="utf-8")
