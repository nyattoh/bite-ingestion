"""Phase 3N conditional routing first-open freeze (N0) and holdout (N1) tests.

Does not change predicates, fixtures, or RulePolicy. Does not open p3f.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase3m import (
    EVALUATION_REPLICAS,
    HIGH_SEQUENCES,
    EvaluationSealError,
    planned_case_ids,
    refuse_p3f_evaluation,
    split_manifest,
)
from bite_bench.phase3n import (
    CLAIM_BOUNDARY,
    LOCKED_GIT_BLOBS,
    M0_COMMIT_SHA,
    M1_COMMIT_SHA,
    N_EVAL_SURFACES,
    PROTOCOL_FROZEN,
    VERDICT_CONFIRMED,
    evaluation_case_ids,
    evaluation_surfaces,
    freeze_manifest,
    git_blob_sha,
    locked_blob_manifest,
    split_evaluation_ids,
    validate_phase3n_freeze,
)
from bite_eval.phase3n_eval import (
    PROTOCOL_COMMIT_SHA,
    RESULT_PATH,
    ROUTING_PATH,
    SAFETY_PATH,
    packet_from_surface,
    run_evaluation,
    validate_phase3n_result,
)
from bite_ingestion.policies.conditional_texture_policy_v1 import (
    ConditionalTexturePolicyV1,
    PolicyLeakError,
)
from bite_ingestion.policies.leak_guard import OracleLeakError

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase3n-conditional-routing-first-open-freeze.json"
LOCKED = ROOT / "benchmarks" / "spec" / "phase3n-locked-blobs.json"
SCHEMA = ROOT / "spec" / "phase3n-conditional-routing-first-open-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase3n.py"
EXP_PY = ROOT / "src" / "bite_eval" / "phase3n_eval.py"
EXP_SCHEMA = ROOT / "spec" / "phase3n-conditional-routing-first-open.schema.json"
ROUTING_SCHEMA = ROOT / "spec" / "phase3n-routing-comparison.schema.json"
SAFETY_SCHEMA = ROOT / "spec" / "phase3n-composition-safety.schema.json"
POLICY_PY = ROOT / "src" / "bite_ingestion" / "policies" / "rule_policy.py"
PHASE3M = ROOT / "artifacts" / "phase3m" / "conditional-routing.json"


def test_committed_freeze_matches_manifest() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    locked = json.loads(LOCKED.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert locked == locked_blob_manifest()
    assert validate_phase3n_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["m0_commit_sha"] == M0_COMMIT_SHA
    assert committed["m1_commit_sha"] == M1_COMMIT_SHA
    assert committed["n_evaluation_surfaces"] == N_EVAL_SURFACES
    assert committed["locked_git_blobs"] == LOCKED_GIT_BLOBS
    assert committed["claim_boundary"] == CLAIM_BOUNDARY
    assert committed["p3f_evaluation_holdout_used"] is False
    assert committed["remeasure_development"] is False
    assert committed["cut_in_conditional_map"] is False
    assert committed["high_sequences"]["all_three"] == ["UNTANGLE", "REDUCE", "INTEGRATE"]


def test_evaluation_ids_are_m0_replicas_2_and_3_only() -> None:
    ids = evaluation_case_ids()
    assert ids == split_evaluation_ids()
    assert len(ids) == N_EVAL_SURFACES == 48
    assert len(ids) == len(set(ids))
    assert all(item.startswith("p3m-") for item in ids)
    assert all(item.endswith(("-r2", "-r3")) for item in ids)
    assert not any(item.endswith(("-r0", "-r1")) for item in ids)
    assert not any(item.startswith("p3f-") for item in ids)
    assert set(ids) <= set(planned_case_ids())
    surfaces = evaluation_surfaces()
    assert [row["case_id"] for row in surfaces] == ids
    assert all(row["split"] == "evaluation" for row in surfaces)
    assert all(row["replica"] in EVALUATION_REPLICAS for row in surfaces)
    high = [row for row in surfaces if row["dispersion"] == "high"]
    assert {tuple(row["expected_sequence"]) for row in high} == {
        tuple(seq) for seq in HIGH_SEQUENCES.values()
    }
    assert all(
        row["expected_sequence"] == [] for row in surfaces if row["dispersion"] != "high"
    )


def test_n0_does_not_measure_or_open_p3f() -> None:
    blob = GEN_PY.read_text(encoding="utf-8")
    assert "from bite_ingestion.policies.conditional_texture_policy_v1" not in blob
    assert "from bite_ingestion.policies.rule_policy" not in blob
    assert "class RulePolicy" not in blob
    assert "ConditionalTexturePolicy" not in blob
    assert "measure(" not in blob
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
    assert json.loads(PHASE3M.read_text(encoding="utf-8"))["verdict"] == (
        "PHASE3M_CONDITIONAL_ROUTING_READY"
    )
    assert json.loads(
        (ROOT / "benchmarks" / "spec" / "phase3m-split-manifest.json").read_text(
            encoding="utf-8"
        )
    ) == split_manifest()
    assert "class RulePolicy" in POLICY_PY.read_text(encoding="utf-8")
    for path, expected in LOCKED_GIT_BLOBS.items():
        assert git_blob_sha(path) == expected


def test_n1_records_n0_sha_and_matches_artifacts() -> None:
    doc = run_evaluation()
    committed = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(doc, sort_keys=True)) == json.loads(
        json.dumps(committed, sort_keys=True)
    )
    assert validate_phase3n_result(committed) == []
    jsonschema.validate(committed, json.loads(EXP_SCHEMA.read_text(encoding="utf-8")))
    jsonschema.validate(
        json.loads(ROUTING_PATH.read_text(encoding="utf-8")),
        json.loads(ROUTING_SCHEMA.read_text(encoding="utf-8")),
    )
    jsonschema.validate(
        json.loads(SAFETY_PATH.read_text(encoding="utf-8")),
        json.loads(SAFETY_SCHEMA.read_text(encoding="utf-8")),
    )
    assert committed["protocol_commit_sha"] == PROTOCOL_COMMIT_SHA
    assert committed["m0_commit_sha"] == M0_COMMIT_SHA
    assert committed["m1_commit_sha"] == M1_COMMIT_SHA
    assert committed["verdict"] == VERDICT_CONFIRMED
    assert committed["n_rows"] == N_EVAL_SURFACES
    assert committed["n_ok"] == N_EVAL_SURFACES
    assert committed["n_sequence_ok"] == N_EVAL_SURFACES
    assert committed["n_safety_ok"] == N_EVAL_SURFACES
    assert committed["rule_policy_executed"] is False
    assert committed["p3f_evaluation_holdout_used"] is False
    assert committed["claim_boundary"] == CLAIM_BOUNDARY
    assert committed["no_winner_score"] is True


def test_n1_evaluation_set_is_r2_r3_only() -> None:
    blob = RESULT_PATH.read_text(encoding="utf-8")
    assert "p3f-" not in blob
    doc = json.loads(blob)
    assert [row["case_id"] for row in doc["rows"]] == evaluation_case_ids()
    for row in doc["rows"]:
        assert row["split"] == "evaluation"
        assert row["replica"] in (2, 3)
        assert not str(row["case_id"]).endswith(("-r0", "-r1"))
        assert row["ok"] is True
        assert row["cut_present"] is False
        assert row["n_edges_eq_0_as_low"] is False
        if row["dispersion"] == "high":
            assert row["gated"] is True
            assert row["sequence"] == list(HIGH_SEQUENCES[row["texture"]])
        else:
            assert row["gated"] is False
            assert row["sequence"] == []


def test_n1_policy_packet_is_gold_free() -> None:
    surface = evaluation_surfaces()[0]
    packet = packet_from_surface(surface)
    assert "gold_unit_ids" not in packet
    assert "texture" not in packet
    assert "expected_sequence" not in packet
    policy = ConditionalTexturePolicyV1()
    with pytest.raises(OracleLeakError):
        policy.propose({**packet, "gold_route": ["REDUCE"]})
    with pytest.raises(PolicyLeakError):
        policy.propose({**packet, "texture": "redundant"})
    blob = EXP_PY.read_text(encoding="utf-8")
    assert "RulePolicy(" not in blob
    assert json.loads(PHASE3M.read_text(encoding="utf-8"))["verdict"] == (
        "PHASE3M_CONDITIONAL_ROUTING_READY"
    )
    for path, expected in LOCKED_GIT_BLOBS.items():
        assert git_blob_sha(path) == expected
