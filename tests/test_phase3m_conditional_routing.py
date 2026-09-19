"""Phase 3M conditional routing freeze (M0) and development (M1) tests.

Does not open p3m/p3f evaluation. Does not rewrite RulePolicy.
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
    POLICY_NAME,
    PROTOCOL_FROZEN,
    VERDICT_READY,
    EvaluationSealError,
    development_surfaces,
    expected_sequence,
    freeze_manifest,
    make_surface,
    planned_case_ids,
    refuse_evaluation,
    split_manifest,
    validate_phase3m_freeze,
    validate_phase3m_split,
)
from bite_eval.phase3m_eval import (
    PROTOCOL_COMMIT_SHA,
    RESULT_PATH,
    SAFETY_PATH,
    packet_from_surface,
    run_experiment,
    validate_phase3m_result,
)
from bite_ingestion.packet_contract import make_unit
from bite_ingestion.policies.conditional_texture_policy_v1 import (
    ConditionalTexturePolicyV1,
    PolicyLeakError,
)
from bite_ingestion.policies.leak_guard import OracleLeakError

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase3m-conditional-routing-freeze.json"
SPLIT = ROOT / "benchmarks" / "spec" / "phase3m-split-manifest.json"
SCHEMA = ROOT / "spec" / "phase3m-conditional-routing-freeze.schema.json"
SPLIT_SCHEMA = ROOT / "spec" / "phase3m-split-manifest.schema.json"
EXP_SCHEMA = ROOT / "spec" / "phase3m-conditional-routing.schema.json"
SAFETY_SCHEMA = ROOT / "spec" / "phase3m-composition-safety.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase3m.py"
EXP_PY = ROOT / "src" / "bite_eval" / "phase3m_eval.py"
POLICY_PY = ROOT / "src" / "bite_ingestion" / "policies" / "rule_policy.py"
NEW_POLICY_PY = ROOT / "src" / "bite_ingestion" / "policies" / "conditional_texture_policy_v1.py"
PHASE3L = ROOT / "artifacts" / "phase3l" / "redundancy-first-open.json"


def test_committed_freeze_and_split_match_manifest() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert split == split_manifest()
    assert validate_phase3m_freeze(committed) == []
    assert validate_phase3m_split(split) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    jsonschema.validate(split, json.loads(SPLIT_SCHEMA.read_text(encoding="utf-8")))
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


def test_n_edges_zero_is_not_low_and_does_not_route() -> None:
    units = []
    start = 0
    texts = ["dupk=dupv EXCEPTION", "dupk=dupv EXCEPTION"]
    document = "\n".join(texts)
    for index, text in enumerate(texts):
        end = start + len(text)
        units.append(
            make_unit(
                unit_id=f"z{index}",
                text=text,
                start=start,
                end=end,
                source_uri="bitebench://p3m-zero",
            )
        )
        start = end + 1
    packet = {"document": document, "units": units}
    decision = ConditionalTexturePolicyV1().explain_propose(packet)
    assert decision.sequence == ()
    assert "no_dependency_dispersion_contribution" in decision.notes
    assert "low" not in " ".join(decision.notes)


def test_policy_rejects_gold_and_texture_labels() -> None:
    surface = make_surface("redundant", "high", 0)
    packet = packet_from_surface(surface)
    assert "gold_unit_ids" not in packet
    assert "texture" not in packet
    assert "expected_sequence" not in packet
    policy = ConditionalTexturePolicyV1()
    with pytest.raises(OracleLeakError):
        policy.propose({**packet, "gold_route": ["REDUCE"]})
    with pytest.raises(PolicyLeakError):
        policy.propose({**packet, "texture": "redundant"})
    with pytest.raises(PolicyLeakError):
        policy.propose(packet, context={"dependency_edges": [("a", "b")]})


def test_m1_development_matches_committed_artifacts() -> None:
    doc = run_experiment()
    committed = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(doc, sort_keys=True)) == json.loads(
        json.dumps(committed, sort_keys=True)
    )
    assert validate_phase3m_result(committed) == []
    jsonschema.validate(committed, json.loads(EXP_SCHEMA.read_text(encoding="utf-8")))
    safety = json.loads(SAFETY_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(safety, json.loads(SAFETY_SCHEMA.read_text(encoding="utf-8")))
    assert committed["protocol_commit_sha"] == PROTOCOL_COMMIT_SHA
    assert committed["verdict"] == VERDICT_READY
    assert committed["n_rows"] == 48
    assert committed["n_ok"] == 48
    assert committed["p3m_evaluation_opened"] is False
    assert committed["rule_policy_changed"] is False
    assert committed["cut_in_conditional_map"] is False
    assert all(row["replica"] in CALIBRATION_REPLICAS for row in committed["rows"])
    assert not any("CUT" in row["sequence"] for row in committed["rows"])
    high = [row for row in committed["rows"] if row["dispersion"] == "high"]
    assert {tuple(row["sequence"]) for row in high} == {
        tuple(seq) for seq in HIGH_SEQUENCES.values()
    }
    assert all(
        row["sequence"] == [] for row in committed["rows"] if row["dispersion"] != "high"
    )
    blob = EXP_PY.read_text(encoding="utf-8")
    assert "RulePolicy(" not in blob
    assert POLICY_NAME in NEW_POLICY_PY.read_text(encoding="utf-8")
    assert json.loads(PHASE3L.read_text(encoding="utf-8"))["verdict"] == (
        "PHASE3L_REDUNDANCY_HOLDOUT_CONFIRMED"
    )
