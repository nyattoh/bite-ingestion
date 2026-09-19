"""Phase 3N conditional routing first-open freeze (N0) tests.

Does not run the policy. Does not open p3f. Does not remeasure development.
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
    evaluation_case_ids,
    evaluation_surfaces,
    freeze_manifest,
    git_blob_sha,
    locked_blob_manifest,
    split_evaluation_ids,
    validate_phase3n_freeze,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase3n-conditional-routing-first-open-freeze.json"
LOCKED = ROOT / "benchmarks" / "spec" / "phase3n-locked-blobs.json"
SCHEMA = ROOT / "spec" / "phase3n-conditional-routing-first-open-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase3n.py"
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
