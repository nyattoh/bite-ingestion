"""Phase 1D confirmatory offline comparison — instrument and freeze locks.

These tests do not retune profiler, routing, operators, or the token-match
rule. They check that the comparison still uses the frozen conditions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bite_bench.token_match import (
    TOKEN_MATCH_LEFT,
    TOKEN_MATCH_MAX_ABS_DELTA,
    TOKEN_MATCH_MAX_RELATIVE_DELTA,
    TOKEN_MATCH_RIGHT,
)
from bite_eval.arm_runtime import PHASE1_ARMS
from bite_eval.phase1_matrix import OFFLINE_WRAPPER
from bite_eval.phase1d_confirmatory import (
    CASE_KIND_CALIB,
    CASE_KIND_EVAL,
    FROZEN_TEXTURES,
    VERDICT_BLOCKED,
    VERDICTS,
    build_phase1d_doc,
    run_negative_control_self_check,
    validate_confirmatory_doc,
    verify_freeze_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "phase1d" / "confirmatory-offline.json"


@pytest.fixture(scope="module")
def phase1d_doc() -> dict:
    return build_phase1d_doc(
        tokenizer_remeasure=None,
        require_tokenizer_remeasure=False,
        include_calibration=True,
    )


def test_freeze_pair_and_tolerance_are_unchanged() -> None:
    assert FROZEN_TEXTURES == ("prose_narrative", "table_csv")
    assert (TOKEN_MATCH_LEFT, TOKEN_MATCH_RIGHT) == FROZEN_TEXTURES
    assert TOKEN_MATCH_MAX_ABS_DELTA == 3
    assert TOKEN_MATCH_MAX_RELATIVE_DELTA == 0.04


def test_committed_holdout_still_matches_frozen_rule() -> None:
    check = verify_freeze_manifest()
    assert check["ok"], check["mismatches"]
    assert check["n_holdout"] == 12
    assert check["n_matched"] == 12


def test_negative_controls_still_detect_failure() -> None:
    result = run_negative_control_self_check()
    assert result["ok"], result
    report = result["negative_control_report"]
    assert report["n_checked"] > 0
    assert report["violations"] == []


def test_confirmatory_uses_holdout_pair_and_four_arms(phase1d_doc: dict) -> None:
    if phase1d_doc["verdict"] == VERDICT_BLOCKED:
        pytest.fail(f"blocked: {phase1d_doc['blocked_reasons']}")
    rows = phase1d_doc["confirmatory"]["rows"]
    assert len(rows) == 96
    assert {r["benchmark_split"] for r in rows} == {"evaluation"}
    assert {r["case_kind"] for r in rows} == {CASE_KIND_EVAL}
    assert {r["texture"] for r in rows} == set(FROZEN_TEXTURES)
    assert {r["method"] for r in rows} == set(PHASE1_ARMS)
    assert {r["facts_id"] for r in rows} == {f"syn-case-{i:03d}" for i in range(12, 24)}
    assert all(r["wrapper"] == OFFLINE_WRAPPER for r in rows)


def test_calibration_is_not_mixed_into_confirmatory(phase1d_doc: dict) -> None:
    eval_ids = {r["facts_id"] for r in phase1d_doc["confirmatory"]["rows"]}
    calib_rows = phase1d_doc["development"]["rows"]
    assert calib_rows
    assert {r["case_kind"] for r in calib_rows} == {CASE_KIND_CALIB}
    assert {r["benchmark_split"] for r in calib_rows} == {"calibration"}
    calib_ids = {r["facts_id"] for r in calib_rows}
    assert eval_ids.isdisjoint(calib_ids)
    assert calib_ids == {f"syn-case-{i:03d}" for i in range(12)}


def test_four_arms_share_facts_query_and_budget(phase1d_doc: dict) -> None:
    by_case: dict[str, list[dict]] = {}
    for row in phase1d_doc["confirmatory"]["rows"]:
        by_case.setdefault(row["case_id"], []).append(row)
    for cid, rows in by_case.items():
        assert {r["method"] for r in rows} == set(PHASE1_ARMS), cid
        assert len({r["query"] for r in rows}) == 1, cid
        assert len({r["facts_id"] for r in rows}) == 1, cid
        assert len({json.dumps(r["budget"], sort_keys=True) for r in rows}) == 1, cid
        assert len({r["wrapper"] for r in rows}) == 1, cid


def test_required_comparison_lists_exist(phase1d_doc: dict) -> None:
    lists = phase1d_doc["confirmatory"]["comparisons"]
    for key in (
        "length_pi_ne_rule_pi",
        "operator_fired",
        "rebite_fired",
        "recall_lt_1",
        "no_op_cases",
        "no_diff_vs_raw",
        "profiler_differed_sequence_same",
    ):
        assert key in lists, key
    assert phase1d_doc["verdict"] in VERDICTS
    assert phase1d_doc["paid_api"] is False
    assert phase1d_doc["research_conclusion"] is False
    assert validate_confirmatory_doc(phase1d_doc) == []


def test_committed_artifact_validates() -> None:
    assert ARTIFACT.is_file(), "run scripts/run_phase1d_confirmatory.py to write the artifact"
    doc = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert validate_confirmatory_doc(doc) == []
    assert doc["paid_api"] is False
    assert doc["verdict"] in VERDICTS
