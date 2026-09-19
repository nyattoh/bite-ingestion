"""Phase 3L first-open evaluation freeze (L0) and holdout (L1) tests.

Does not change the sensor, p3k split, or routing. Does not open p3f.
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
    VERDICT_CONFIRMED,
    evaluation_case_ids,
    evaluation_surfaces,
    freeze_manifest,
    locked_hashes,
    split_evaluation_ids,
    validate_phase3l_freeze,
)
from bite_eval.phase3l_eval import (
    PROTOCOL_COMMIT_SHA,
    RESULT_PATH,
    run_evaluation,
    validate_phase3l_result,
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
EXP_SCHEMA = ROOT / "spec" / "phase3l-redundancy-first-open.schema.json"
EXP_PY = ROOT / "src" / "bite_eval" / "phase3l_eval.py"


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


def test_l1_records_l0_sha_and_matches_artifacts() -> None:
    doc = run_evaluation()
    committed = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(doc, sort_keys=True)) == json.loads(
        json.dumps(committed, sort_keys=True)
    )
    assert validate_phase3l_result(committed) == []
    jsonschema.validate(committed, json.loads(EXP_SCHEMA.read_text(encoding="utf-8")))
    assert committed["protocol_commit_sha"] == PROTOCOL_COMMIT_SHA
    assert len(PROTOCOL_COMMIT_SHA) == 40
    assert committed["k0_commit_sha"] == K0_COMMIT_SHA
    assert committed["verdict"] == VERDICT_CONFIRMED
    assert committed["n_rows"] == N_EVAL_SURFACES
    assert committed["n_matched"] == N_EVAL_SURFACES
    assert committed["routing_connected"] is False
    assert committed["redundancy_threshold_set"] is False
    assert committed["rule_policy_changed"] is False
    assert committed["p3f_evaluation_holdout_used"] is False
    assert committed["claim_boundary"] == "same frozen families / new replica values"


def test_l1_evaluation_set_is_r2_r3_only() -> None:
    blob = RESULT_PATH.read_text(encoding="utf-8")
    assert "p3f-" not in blob
    doc = json.loads(blob)
    assert [row["case_id"] for row in doc["rows"]] == evaluation_case_ids()
    for row in doc["rows"]:
        assert row["split"] == "evaluation"
        assert row["replica"] in (2, 3)
        assert "-r0-" not in row["case_id"]
        assert "-r1-" not in row["case_id"]
        assert row["match"] is True
        assert row["mismatches"] == {}
    assert all(item["ok"] is True for item in doc["format_invariance"])
    assert doc["checks"]["negative_controls"] is True
    assert doc["checks"]["reorder_invariance"] is True


def test_l1_does_not_patch_locked_code() -> None:
    blob = EXP_PY.read_text(encoding="utf-8")
    assert "from bite_ingestion.policies" not in blob
    assert "class RulePolicy" not in blob
    assert "from bite_bench.phase3f" not in blob
    assert json.loads(PHASE3K.read_text(encoding="utf-8"))["verdict"] == (
        "PHASE3K_REDUNDANCY_SENSOR_READY"
    )
    assert json.loads(SPLIT.read_text(encoding="utf-8")) == split_manifest()
    assert freeze_manifest()["locked_hashes"] == locked_hashes()
    assert 'FEATURE_KEYS = ("b", "r", "s", "k", "a", "l", "p", "u")' in V0_PY.read_text(
        encoding="utf-8"
    )
    assert "class RulePolicy" in POLICY_PY.read_text(encoding="utf-8")
    assert "Counter(" in SENSOR_PY.read_text(encoding="utf-8")
