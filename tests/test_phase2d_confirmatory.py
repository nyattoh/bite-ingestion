"""Phase 2D confirmatory offline evaluation tests.

Do not retune profiler, routing, operators, or Phase 2C v0.2 rules.
Tokenizer download is not required; the committed artifact is the evaluation record.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from bite_bench.phase2c import (
    PHASE2C_REVISION,
    classify_dispersion_pair,
    confirmatory_pairs,
    decide_phase2d_verdict,
)
from bite_bench.token_match import (
    TOKEN_MATCH_MAX_ABS_DELTA,
    TOKEN_MATCH_MAX_RELATIVE_DELTA,
)
from bite_eval.phase1d_confirmatory import run_negative_control_self_check
from bite_eval.phase2d_confirmatory import (
    SCHEMA_ID,
    build_phase2d_doc,
    classify_measured_pair,
    validate_phase2d_doc,
    verify_phase2c_v02,
)

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "phase2d" / "confirmatory-offline.json"
SCHEMA = ROOT / "spec" / "phase2d-confirmatory-offline.schema.json"
PHASE2D_PY = ROOT / "src" / "bite_eval" / "phase2d_confirmatory.py"
PHASE2C_PY = ROOT / "src" / "bite_bench" / "phase2c.py"


def test_phase2c_v02_is_the_only_verdict_rule() -> None:
    check = verify_phase2c_v02()
    assert check["ok"], check["mismatches"]
    assert check["revision"] == PHASE2C_REVISION == "phase2c-dispersion-freeze-v0.2"
    source = PHASE2D_PY.read_text(encoding="utf-8")
    assert "classify_dispersion_pair" in source
    assert "decide_phase2d_verdict" in source


def test_phase1c_length_criterion_unchanged() -> None:
    assert TOKEN_MATCH_MAX_ABS_DELTA == 3
    assert TOKEN_MATCH_MAX_RELATIVE_DELTA == 0.04


def test_negative_controls_still_detect_failure() -> None:
    result = run_negative_control_self_check()
    assert result["ok"], result
    assert result["negative_control_report"]["violations"] == []


def test_missing_tokenizer_blocks_without_opening_eval() -> None:
    doc = build_phase2d_doc(prompt_tokens=None)
    assert doc["verdict"] == "PHASE2D_BLOCKED"
    assert doc["evaluation_opened"] is False
    assert doc["n_rows"] == 0
    assert doc["pairs"] == []
    assert doc["n_eligible"] == 0
    assert doc["n_signal"] == 0


def test_length_mismatch_is_not_rescued() -> None:
    pair = confirmatory_pairs()[0]
    row = classify_measured_pair(
        pair=pair,
        left_tokens=10,
        right_tokens=100,
        clustered_rows=[],
        dispersed_rows=[],
        frozen_contract_ok=True,
        instrumentation_ok=True,
    )
    assert row["length_matched"] is False
    assert row["eligible"] is False
    assert row["dispersion_specific_signal"] is False
    assert row["classification"] == "ineligible"


def test_v02_signal_definition_is_not_reimplemented() -> None:
    assert "dispersion_specific_signal" in PHASE2C_PY.read_text(encoding="utf-8")
    row = classify_dispersion_pair(
        length_criterion_ok=True,
        instrumentation_ok=True,
        frozen_contract_ok=True,
        length_pi_behavior_same=True,
        rule_pi_sequence_differs=False,
        rule_pi_noop_status_differs=False,
        rule_pi_rebite_recovery_differs=False,
        raw_payload_hash_differs=True,
        recall_differs=True,
        t_total_differs=True,
        length_pi_neq_rule_pi=True,
    )
    assert row["dispersion_specific_signal"] is False
    assert decide_phase2d_verdict(n_eligible=12, n_dispersion_specific_signal=0) == (
        "PHASE2D_OFFLINE_NO_SIGNAL"
    )


def test_committed_artifact_follows_v02() -> None:
    assert ARTIFACT.is_file(), "run scripts/run_phase2d_confirmatory.py"
    doc = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert validate_phase2d_doc(doc) == []
    jsonschema.validate(doc, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert doc["schema"] == SCHEMA_ID
    assert doc["phase2c_revision"] == "phase2c-dispersion-freeze-v0.2"
    assert doc["paid_api"] is False
    assert doc["research_conclusion"] is False
    assert doc["n_planned_pairs"] == 48
    assert doc["n_rows"] <= 384
    assert {r["benchmark_split"] for r in doc["rows"]} <= {"evaluation"}
    assert {r["replica"] for r in doc["rows"]} <= {2, 3}
    assert doc["n_signal"] == sum(1 for p in doc["pairs"] if p.get("dispersion_specific_signal"))
    assert doc["n_eligible"] == sum(1 for p in doc["pairs"] if p.get("eligible"))
    for pair in doc["pairs"]:
        if pair.get("dispersion_specific_signal"):
            assert pair.get("length_pi_behavior_same") is True
            assert pair.get("eligible") is True
            assert (
                pair.get("rule_pi_sequence_differs")
                or pair.get("rule_pi_noop_status_differs")
                or pair.get("rule_pi_rebite_recovery_differs")
            )
        if not pair.get("length_matched"):
            assert pair.get("eligible") is False
            assert pair.get("dispersion_specific_signal") is False
    if doc["verdict"] == "PHASE2D_OFFLINE_SIGNAL":
        assert doc["n_eligible"] >= 1 and doc["n_signal"] >= 1
    if doc["verdict"] == "PHASE2D_OFFLINE_NO_SIGNAL":
        assert doc["n_eligible"] >= 1 and doc["n_signal"] == 0
    assert doc["verdict"] == "PHASE2D_OFFLINE_NO_SIGNAL"
    assert doc["n_signal"] == 0
    assert doc["n_eligible"] == 48
    assert doc["n_rows"] == 384
    assert doc["evaluation_opened"] is True
    assert "scale" in doc["breakdowns"]
    assert "dependency" in doc["breakdowns"]
    assert "structure" in doc["breakdowns"]
    assert "redundancy" in doc["breakdowns"]
