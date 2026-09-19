"""Phase 3M conditional routing freeze (M0) tests.

Does not implement or run the policy. Does not open evaluation.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase3m import (
    CALIBRATION_REPLICAS,
    EVALUATION_REPLICAS,
    GENERATION,
    HIGH_SEQUENCES,
    PROTOCOL_FROZEN,
    EvaluationSealError,
    development_surfaces,
    expected_sequence,
    freeze_manifest,
    planned_case_ids,
    refuse_evaluation,
    split_manifest,
    validate_phase3m_freeze,
    validate_phase3m_split,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase3m-conditional-routing-freeze.json"
SPLIT = ROOT / "benchmarks" / "spec" / "phase3m-split-manifest.json"
SCHEMA = ROOT / "spec" / "phase3m-conditional-routing-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase3m.py"
POLICY_PY = ROOT / "src" / "bite_ingestion" / "policies" / "rule_policy.py"
PHASE3L = ROOT / "artifacts" / "phase3l" / "redundancy-first-open.json"


def test_committed_freeze_and_split_match_manifest() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert split == split_manifest()
    assert validate_phase3m_freeze(committed) == []
    assert validate_phase3m_split(split) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["generation"] == GENERATION
    assert committed["cut_in_conditional_map"] is False
    assert committed["rule_policy_unchanged"] is True
    assert committed["high_sequences"]["all_three"] == ["UNTANGLE", "REDUCE", "INTEGRATE"]
    assert committed["high_sequences"]["neutral"] == []
    assert split["evaluation_sealed"] is True
    assert split["calibration_replicas"] == list(CALIBRATION_REPLICAS)
    assert split["evaluation_replicas"] == list(EVALUATION_REPLICAS)


def test_development_ids_are_p3m_and_evaluation_is_sealed() -> None:
    ids = planned_case_ids()
    assert len(ids) == 96
    assert all(item.startswith("p3m-") for item in ids)
    assert not any(item.startswith(("p3h-", "p3j-", "p3k-", "p3f-")) for item in ids)
    with pytest.raises(EvaluationSealError, match="p3m evaluation sealed"):
        refuse_evaluation("p3m-redundant-high-r2")
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_evaluation("p3f-medium-one_hop-r2")
    refuse_evaluation("p3m-redundant-high-r0")
    surfaces = development_surfaces()
    assert len(surfaces) == 48
    assert all(row["split"] == "development" for row in surfaces)
    assert all(row["replica"] in (0, 1) for row in surfaces)
    high = [row for row in surfaces if row["dispersion"] == "high"]
    assert {tuple(row["expected_sequence"]) for row in high} == {
        tuple(seq) for seq in HIGH_SEQUENCES.values()
    }
    assert all(
        row["expected_sequence"] == [] for row in surfaces if row["dispersion"] != "high"
    )
    assert expected_sequence("anomaly_join", "high") == ("UNTANGLE", "INTEGRATE")


def test_m0_does_not_run_policy_or_open_eval() -> None:
    blob = GEN_PY.read_text(encoding="utf-8")
    assert "from bite_ingestion.policies.rule_policy" not in blob
    assert "class RulePolicy" not in blob
    assert "ConditionalTexturePolicy" not in blob
    assert "from bite_bench.phase3h" not in blob
    assert json.loads(PHASE3L.read_text(encoding="utf-8"))["verdict"] == (
        "PHASE3L_REDUNDANCY_HOLDOUT_CONFIRMED"
    )
    assert "class RulePolicy" in POLICY_PY.read_text(encoding="utf-8")
