"""Phase 3K structural-redundancy freeze (K0) and calibration (K1) tests.

Does not open p3k/p3f evaluation. Does not change deterministic_v0 or routing.
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
    VERDICT_READY,
    EvaluationSealError,
    contract_payload,
    development_surfaces,
    freeze_manifest,
    planned_case_ids,
    records_for,
    refuse_evaluation,
    render_payload,
    sensor_source_unit,
    split_manifest,
    validate_phase3k_freeze,
    validate_phase3k_split,
)
from bite_eval.phase3k_validate import (
    PROTOCOL_COMMIT_SHA,
    RESULT_PATH,
    run_validation,
    validate_phase3k_result,
)
from bite_ingestion.profilers.structural_redundancy_v1 import measure

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase3k-structural-redundancy-freeze.json"
SPLIT = ROOT / "benchmarks" / "spec" / "phase3k-split-manifest.json"
SCHEMA = ROOT / "spec" / "phase3k-structural-redundancy-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase3k.py"
V0_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "deterministic.py"
V1_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "dependency_dispersion_v1.py"
POLICY_PY = ROOT / "src" / "bite_ingestion" / "policies" / "rule_policy.py"
PHASE3J = ROOT / "artifacts" / "phase3j" / "texture-observability.json"
EXP_SCHEMA = ROOT / "spec" / "phase3k-structural-redundancy.schema.json"
EXP_PY = ROOT / "src" / "bite_eval" / "phase3k_validate.py"
SENSOR_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "structural_redundancy_v1.py"


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


def _ratio(payload: str) -> tuple[float, bool]:
    report = measure(sensor_source_unit(payload))
    return float(report.features["duplicate_unit_ratio"]), report.fail_closed


def test_k1_records_k0_sha_and_matches_artifacts() -> None:
    doc = run_validation()
    committed = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(doc, sort_keys=True)) == json.loads(
        json.dumps(committed, sort_keys=True)
    )
    assert validate_phase3k_result(committed) == []
    jsonschema.validate(committed, json.loads(EXP_SCHEMA.read_text(encoding="utf-8")))
    assert committed["protocol_commit_sha"] == PROTOCOL_COMMIT_SHA
    assert len(PROTOCOL_COMMIT_SHA) == 40
    assert committed["verdict"] == VERDICT_READY
    assert committed["v0_overwritten"] is False
    assert committed["rule_policy_executed"] is False
    assert committed["no_threshold"] is True
    assert committed["p3f_evaluation_holdout_used"] is False
    assert committed["checks"]["format_invariance"] is True


def test_compact_pretty_and_kv_json_are_equal() -> None:
    recs = records_for("exact_dup_pairs", 0)
    reports = {
        fmt: measure(sensor_source_unit(render_payload(recs, fmt))) for fmt in FORMATS
    }
    keys = ("n_records", "n_unique_records", "n_duplicate_records")
    compact = reports["compact_json"]
    pretty = reports["pretty_json"]
    kv = reports["key_value"]
    assert compact.fail_closed is pretty.fail_closed is kv.fail_closed is False
    assert compact.features == pretty.features == kv.features
    for key in keys:
        assert compact.diagnostics[key] == pretty.diagnostics[key] == kv.diagnostics[key]
    assert compact.diagnostics["parsed_format"] == pretty.diagnostics["parsed_format"] == "json"
    assert kv.diagnostics["parsed_format"] == "key_value"
    assert compact.features["duplicate_unit_ratio"] == 0.5


def test_negative_controls_and_reorder() -> None:
    sk = render_payload(records_for("same_key_diff_value", 0), "key_value")
    sv = render_payload(records_for("same_value_diff_key", 0), "compact_json")
    assert _ratio(sk) == (0.0, False)
    assert _ratio(sv) == (0.0, False)
    ordered = measure(
        sensor_source_unit(render_payload(records_for("exact_dup_pairs", 1), "pretty_json"))
    )
    reordered = measure(
        sensor_source_unit(render_payload(records_for("reordered_duplicates", 1), "pretty_json"))
    )
    assert ordered.features == reordered.features
    assert ordered.diagnostics["n_unique_records"] == reordered.diagnostics["n_unique_records"]


def test_malformed_nul_and_json_object_fail_closed() -> None:
    for kind in ("malformed_json", "nul", "json_object"):
        report = measure(sensor_source_unit(contract_payload(kind)))
        assert report.fail_closed is True
        assert report.features["duplicate_unit_ratio"] == 0.0
        assert report.diagnostics["n_records"] == 0


def test_k1_does_not_open_eval_or_patch_routing() -> None:
    blob = RESULT_PATH.read_text(encoding="utf-8")
    assert "p3f-" not in blob
    doc = json.loads(blob)
    for row in doc["rows"]:
        assert row["generation"] == "p3k"
        assert row["split"] == "development"
        assert "-r2-" not in row["case_id"]
        assert "-r3-" not in row["case_id"]
    sensor = SENSOR_PY.read_text(encoding="utf-8")
    eval_py = EXP_PY.read_text(encoding="utf-8")
    assert "Counter(" in sensor
    assert "for j," not in sensor
    assert "exact_dup_pairs" not in sensor
    assert "RulePolicy" not in eval_py
    assert "from bite_ingestion.policies" not in eval_py
    assert "from bite_bench.phase3f" not in eval_py
    assert 'FEATURE_KEYS = ("b", "r", "s", "k", "a", "l", "p", "u")' in V0_PY.read_text(
        encoding="utf-8"
    )
    assert "class RulePolicy" in POLICY_PY.read_text(encoding="utf-8")
