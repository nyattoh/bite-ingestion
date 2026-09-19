"""Phase 3K structural-redundancy freeze (K0) tests.

Does not implement or import the sensor. Does not open evaluation.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase3k import (
    CALIBRATION_REPLICAS,
    EVALUATION_REPLICAS,
    FAMILIES,
    FAMILY_EXPECT,
    FORMATS,
    GENERATION,
    PROTOCOL_FROZEN,
    EvaluationSealError,
    development_surfaces,
    freeze_manifest,
    planned_case_ids,
    records_for,
    refuse_evaluation,
    sensor_source_unit,
    split_manifest,
    validate_phase3k_freeze,
    validate_phase3k_split,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase3k-structural-redundancy-freeze.json"
SPLIT = ROOT / "benchmarks" / "spec" / "phase3k-split-manifest.json"
SCHEMA = ROOT / "spec" / "phase3k-structural-redundancy-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase3k.py"
V0_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "deterministic.py"
V1_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "dependency_dispersion_v1.py"
POLICY_PY = ROOT / "src" / "bite_ingestion" / "policies" / "rule_policy.py"
PHASE3J = ROOT / "artifacts" / "phase3j" / "texture-observability.json"


def test_committed_freeze_and_split_match_manifest() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert split == split_manifest()
    assert validate_phase3k_freeze(committed) == []
    assert validate_phase3k_split(split) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["generation"] == GENERATION
    assert committed["reuse_p3j_surfaces"] is False
    assert committed["no_threshold"] is True
    assert committed["routing"]["connect_on_ready"] is False
    assert split["evaluation_sealed"] is True
    assert split["calibration_replicas"] == list(CALIBRATION_REPLICAS)
    assert split["evaluation_replicas"] == list(EVALUATION_REPLICAS)


def test_family_expects_match_canonical_record_counts() -> None:
    for family in FAMILIES:
        recs = records_for(family, 0)
        n_records = len(recs)
        n_unique = len(set(recs))
        expect = FAMILY_EXPECT[family]
        assert expect["n_records"] == n_records
        assert expect["n_unique_records"] == n_unique
        assert expect["n_duplicate_records"] == n_records - n_unique
        assert expect["max_multiplicity"] == max(recs.count(item) for item in recs)
        assert expect["duplicate_unit_ratio"] == 1.0 - (n_unique / n_records)
        assert recs == records_for(family, 0)
        assert recs != records_for(family, 1)


def test_split_ids_are_p3k_and_evaluation_is_sealed() -> None:
    ids = planned_case_ids()
    assert len(ids) == len(set(ids))
    assert all(item.startswith("p3k-") for item in ids)
    assert not any(item.startswith("p3j-") for item in ids)
    assert not any(item.startswith("p3f-") for item in ids)
    assert any("-r2-" in item for item in ids)
    assert any("-r3-" in item for item in ids)
    with pytest.raises(EvaluationSealError, match="p3k evaluation sealed"):
        refuse_evaluation("p3k-exact_dup_pairs-r2-key_value")
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_evaluation("p3f-medium-one_hop-r2")
    refuse_evaluation("p3k-exact_dup_pairs-r0-key_value")
    assert all(row["split"] == "development" for row in development_surfaces())
    src = sensor_source_unit("a=b")
    assert set(src) == {"payload", "text"}


def test_k0_does_not_open_eval_or_touch_profiler_routing() -> None:
    blob = GEN_PY.read_text(encoding="utf-8")
    assert "from bite_bench.phase3j" not in blob
    assert "from bite_ingestion.policies" not in blob
    assert "RulePolicy" not in blob
    assert "DeterministicMorphologyProfiler" not in blob
    assert "structural_redundancy_v1 import" not in blob
    assert json.loads(PHASE3J.read_text(encoding="utf-8"))["verdict"] == (
        "PHASE3J_TEXTURE_SENSOR_REVISION_REQUIRED"
    )
    assert 'FEATURE_KEYS = ("b", "r", "s", "k", "a", "l", "p", "u")' in V0_PY.read_text(
        encoding="utf-8"
    )
    assert "def measure(" in V1_PY.read_text(encoding="utf-8")
    assert "class RulePolicy" in POLICY_PY.read_text(encoding="utf-8")
    assert FORMATS == ("key_value", "compact_json", "pretty_json")
