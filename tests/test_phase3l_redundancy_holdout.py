"""Phase 3L first-open evaluation freeze (L0) tests.

Does not measure evaluation. Does not change the sensor or p3k split.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase3k import (
    EvaluationSealError,
    refuse_p3f_evaluation,
    split_manifest,
)
from bite_bench.phase3l import (
    K0_COMMIT_SHA,
    N_EVAL_SURFACES,
    PROTOCOL_FROZEN,
    evaluation_case_ids,
    evaluation_surfaces,
    freeze_manifest,
    locked_hashes,
    split_evaluation_ids,
    validate_phase3l_freeze,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase3l-redundancy-first-open-freeze.json"
SCHEMA = ROOT / "spec" / "phase3l-redundancy-first-open-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase3l.py"
SENSOR_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "structural_redundancy_v1.py"
V0_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "deterministic.py"
V1_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "dependency_dispersion_v1.py"
POLICY_PY = ROOT / "src" / "bite_ingestion" / "policies" / "rule_policy.py"
SPLIT = ROOT / "benchmarks" / "spec" / "phase3k-split-manifest.json"
PHASE3K = ROOT / "artifacts" / "phase3k" / "structural-redundancy.json"


def test_committed_freeze_matches_manifest() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_phase3l_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["k0_commit_sha"] == K0_COMMIT_SHA
    assert committed["n_evaluation_surfaces"] == N_EVAL_SURFACES
    assert committed["locked_hashes"] == locked_hashes()
    assert committed["claim_boundary"] == "same frozen families / new replica values"
    assert committed["routing"]["routing_connected"] is False
    assert committed["routing"]["redundancy_threshold_set"] is False
    assert committed["p3f_evaluation_holdout_used"] is False
    assert committed["remeasure_development"] is False


def test_evaluation_ids_are_k0_replicas_2_and_3_only() -> None:
    ids = evaluation_case_ids()
    assert ids == split_evaluation_ids()
    assert len(ids) == N_EVAL_SURFACES == 60
    assert len(ids) == len(set(ids))
    assert all(item.startswith("p3k-") for item in ids)
    assert all("-r2-" in item or "-r3-" in item for item in ids)
    assert not any("-r0-" in item or "-r1-" in item for item in ids)
    assert not any(item.startswith("p3f-") for item in ids)
    split_ids = set(split_manifest()["case_ids"])
    assert set(ids) <= split_ids
    surfaces = evaluation_surfaces()
    assert [row["case_id"] for row in surfaces] == ids
    assert all(row["split"] == "evaluation" for row in surfaces)
    assert all(row["replica"] in (2, 3) for row in surfaces)


def test_l0_does_not_measure_or_touch_locked_blobs() -> None:
    blob = GEN_PY.read_text(encoding="utf-8")
    assert "from bite_ingestion.profilers.structural_redundancy_v1" not in blob
    assert "from bite_ingestion.policies" not in blob
    assert "RulePolicy" not in blob
    assert "measure(" not in blob
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
    assert json.loads(PHASE3K.read_text(encoding="utf-8"))["verdict"] == (
        "PHASE3K_REDUNDANCY_SENSOR_READY"
    )
    assert json.loads(SPLIT.read_text(encoding="utf-8")) == split_manifest()
    assert "Counter(" in SENSOR_PY.read_text(encoding="utf-8")
    assert 'FEATURE_KEYS = ("b", "r", "s", "k", "a", "l", "p", "u")' in V0_PY.read_text(
        encoding="utf-8"
    )
    assert "def measure(" in V1_PY.read_text(encoding="utf-8")
    assert "class RulePolicy" in POLICY_PY.read_text(encoding="utf-8")
