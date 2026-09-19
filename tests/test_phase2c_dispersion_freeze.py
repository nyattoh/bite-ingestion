"""Phase 2C freeze invariants.

Registers confirmatory pairs before holdout is opened. Does not generate
evaluation surfaces, count tokens, or import bite_eval.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from bite_bench.phase2a import design_cells, design_manifest, surface_profiles
from bite_bench.phase2c import (
    PHASE2C_REVISION,
    PHASE2C_REVISION_V01,
    PHASE2D_ARMS,
    PHASE2D_VERDICTS,
    PRIMARY_AXIS,
    SCHEMA_ID,
    SCHEMA_ID_V01,
    SYSTEM_PROMPT,
    TOKENIZER_REFERENCE,
    USER_TEMPLATE,
    classify_dispersion_pair,
    confirmatory_pairs,
    decide_phase2d_verdict,
    freeze_manifest,
    load_v01_freeze,
    validate_freeze_doc,
)
from bite_bench.token_match import (
    TOKEN_MATCH_MAX_ABS_DELTA,
    TOKEN_MATCH_MAX_RELATIVE_DELTA,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE_V01 = ROOT / "benchmarks" / "spec" / "phase2c-dispersion-freeze.json"
FREEZE_V02 = ROOT / "benchmarks" / "spec" / "phase2c-dispersion-freeze-v0.2.json"
SCHEMA_V01 = ROOT / "spec" / "phase2c-dispersion-freeze.schema.json"
SCHEMA_V02 = ROOT / "spec" / "phase2c-dispersion-freeze-v0.2.schema.json"
PHASE1C = ROOT / "benchmarks" / "spec" / "phase1c-token-freeze.json"
PHASE2A = ROOT / "benchmarks" / "spec" / "phase2a-design.json"
PHASE2C_PY = ROOT / "src" / "bite_bench" / "phase2c.py"
FORBIDDEN = (
    "bite_eval",
    "generate_phase2a_bundle",
    "DeterministicMorphologyProfiler",
    "RulePolicy",
    "LengthOnlyPolicy",
    "UNTANGLE",
    "REDUCE",
    "INTEGRATE",
)


def _no_eval_measurements(pairs: object) -> None:
    blob = json.dumps(pairs)
    for key in (
        "prompt_tokens",
        "left_tokens",
        "right_tokens",
        "operator_sequence",
        "payload_sha256",
        "T_profiler",
        "T_router",
        "T_total",
        "abs_delta",
    ):
        assert key not in blob, key


def test_phase2c_source_does_not_open_evaluation_or_bite_eval() -> None:
    source = PHASE2C_PY.read_text(encoding="utf-8")
    for needle in FORBIDDEN:
        assert needle not in source, needle


def test_v01_is_retained_not_overwritten() -> None:
    v01 = json.loads(FREEZE_V01.read_text(encoding="utf-8"))
    assert v01["revision"] == PHASE2C_REVISION_V01
    assert v01["schema"] == SCHEMA_ID_V01
    assert validate_freeze_doc(v01) == []
    jsonschema.validate(v01, json.loads(SCHEMA_V01.read_text(encoding="utf-8")))
    assert v01 == load_v01_freeze()


def test_v02_supersedes_v01_and_matches_code() -> None:
    v02 = json.loads(FREEZE_V02.read_text(encoding="utf-8"))
    assert v02 == freeze_manifest()
    assert validate_freeze_doc(v02) == []
    jsonschema.validate(v02, json.loads(SCHEMA_V02.read_text(encoding="utf-8")))
    assert v02["schema"] == SCHEMA_ID
    assert v02["revision"] == PHASE2C_REVISION
    assert v02["supersedes"] == PHASE2C_REVISION_V01
    assert v02["supersession"]["v0_1_deleted"] is False
    assert v02["supersession"]["v0_1_overwritten"] is False
    assert v02["evaluation_sealed"] is True
    assert v02["arms_run"] is False


def test_v02_keeps_v01_pairs_and_contracts() -> None:
    v01 = load_v01_freeze()
    v02 = freeze_manifest()
    assert v02["confirmatory_pairs"] == v01["confirmatory_pairs"]
    assert v02["arms"] == v01["arms"]
    assert v02["primary_axis"] == v01["primary_axis"]
    assert v02["tokenizer_reference"] == v01["tokenizer_reference"]
    assert v02["prompt_contract"] == v01["prompt_contract"]
    assert v02["length_criterion"] == v01["length_criterion"]
    assert v02["case_ids"] == v01["case_ids"]
    assert v02["secondary_axes"] == v01["secondary_axes"]
    assert v02["primary_question"] == v01["primary_question"]
    assert v02["primary_offline_endpoints"] == v01["primary_offline_endpoints"]
    assert v02["exclusion_rule"] == v01["exclusion_rule"]
    assert v02["n_planned_pairs"] == v01["n_planned_pairs"] == 48
    assert v02["phase2d_verdicts"] != v01["phase2d_verdicts"]


def test_primary_axis_is_dispersion_with_48_pairs() -> None:
    pairs = confirmatory_pairs()
    assert PRIMARY_AXIS == "dispersion"
    assert len(pairs) == 48
    eval_ids = [c.case_id for c in design_cells("evaluation")]
    assert len(eval_ids) == 12
    assert {p["case_id"] for p in pairs} == set(eval_ids)
    by_case: dict[str, int] = {}
    for pair in pairs:
        by_case[pair["case_id"]] = by_case.get(pair["case_id"], 0) + 1
        assert pair["left"]["dispersion"] == "clustered"
        assert pair["right"]["dispersion"] == "dispersed"
        assert pair["structure"] in {"flat", "nested"}
        assert pair["redundancy"] in {"low", "high"}
        assert pair["varies"] == "dispersion"
        assert pair["left"]["family"].endswith(f"_{pair['redundancy']}")
        assert f"_{pair['structure']}_" in pair["left"]["family"]
        assert pair["left"]["family"] != pair["right"]["family"]
        assert pair["replica"] in {2, 3}
    assert set(by_case.values()) == {4}


def test_pairs_hold_structure_and_redundancy_grid() -> None:
    families = {p.family for p in surface_profiles()}
    triples = {
        (p["structure"], p["redundancy"])
        for p in confirmatory_pairs()
        if p["case_id"] == "p2a-small-direct-r2"
    }
    assert triples == {("flat", "low"), ("flat", "high"), ("nested", "low"), ("nested", "high")}
    for pair in confirmatory_pairs():
        assert pair["left"]["family"] in families
        assert pair["right"]["family"] in families


def test_freeze_has_no_evaluation_measurements() -> None:
    for path in (FREEZE_V01, FREEZE_V02):
        doc = json.loads(path.read_text(encoding="utf-8"))
        _no_eval_measurements(doc["confirmatory_pairs"])


def test_length_criterion_is_phase1c() -> None:
    freeze = freeze_manifest()
    phase1c = json.loads(PHASE1C.read_text(encoding="utf-8"))
    rule = freeze["length_criterion"]
    assert TOKEN_MATCH_MAX_ABS_DELTA == 3
    assert TOKEN_MATCH_MAX_RELATIVE_DELTA == 0.04
    assert rule["max_abs_delta"] == phase1c["frozen_match_rule"]["max_abs_delta"] == 3
    assert rule["max_relative_delta"] == phase1c["frozen_match_rule"]["max_relative_delta"] == 0.04
    assert rule["no_padding"] is True
    assert rule["widened_after_phase2b"] is False
    assert rule["calibration_observation"]["abs_delta"] == 0
    assert rule["calibration_observation"]["n_matched"] == 48
    tok = freeze["tokenizer_reference"]
    assert tok["revision"] == phase1c["tokenizer_reference"]["revision"]
    assert tok["tokenizer_json_sha256"] == phase1c["tokenizer_reference"]["tokenizer_json_sha256"]
    assert tok["exact_hosted_model_equivalence_asserted"] is False
    assert tok["repo"] == TOKENIZER_REFERENCE["repo"]
    prompt = freeze["prompt_contract"]
    assert prompt["system"] == SYSTEM_PROMPT == phase1c["prompt_contract"]["system"]
    assert prompt["user_template"] == USER_TEMPLATE
    assert prompt["thinking"] == "disabled"
    assert prompt["add_generation_prompt"] is True


def test_four_arms_and_phase2d_verdicts_are_pre_registered() -> None:
    freeze = freeze_manifest()
    assert tuple(freeze["arms"]) == PHASE2D_ARMS
    assert set(freeze["phase2d_verdicts"]) == set(PHASE2D_VERDICTS)
    assert freeze["paid_model_accuracy_is_primary_endpoint"] is False
    assert "BITE_wins" in freeze["not_an_endpoint"]
    assert "n_pairs_length_pi_neq_rule_pi" in freeze["primary_offline_endpoints"]
    assert freeze["exclusion_rule"]["if_pair_fails_length_criterion"].startswith("exclude")
    assert "widen max_abs_delta" in freeze["exclusion_rule"]["do_not"]
    assert freeze["eligible_pair"]["if_length_criterion_fails"].startswith("exclude")


def test_structure_and_redundancy_remain_secondary() -> None:
    freeze = freeze_manifest()
    for axis in ("structure", "redundancy"):
        row = freeze["secondary_axes"][axis]
        assert row["in_primary_confirmatory"] is False
        assert row["deleted"] is False
        assert row["new_matching_method_after_evaluation"] is False
        assert "confounded" in row["status"]


def test_phase2a_design_was_not_rewritten() -> None:
    committed = json.loads(PHASE2A.read_text(encoding="utf-8"))
    assert committed == design_manifest()
    assert committed["status"] == "DESIGN_READY_NOT_FROZEN"
    assert committed["locks"]["token_length_matching_frozen"] is False


def test_dispersion_specific_signal_definition() -> None:
    base = {
        "length_criterion_ok": True,
        "instrumentation_ok": True,
        "frozen_contract_ok": True,
        "length_pi_behavior_same": True,
        "rule_pi_sequence_differs": False,
        "rule_pi_noop_status_differs": False,
        "rule_pi_rebite_recovery_differs": False,
    }
    assert classify_dispersion_pair(**base)["dispersion_specific_signal"] is False
    assert classify_dispersion_pair(**{**base, "rule_pi_sequence_differs": True})[
        "dispersion_specific_signal"
    ]
    assert classify_dispersion_pair(**{**base, "rule_pi_noop_status_differs": True})[
        "dispersion_specific_signal"
    ]
    assert classify_dispersion_pair(**{**base, "rule_pi_rebite_recovery_differs": True})[
        "dispersion_specific_signal"
    ]
    noise = classify_dispersion_pair(
        **base,
        raw_payload_hash_differs=True,
        recall_differs=True,
        provenance_differs=True,
        t_total_differs=True,
        length_pi_neq_rule_pi=True,
    )
    assert noise["dispersion_specific_signal"] is False
    inconsistent = classify_dispersion_pair(
        **{**base, "length_pi_behavior_same": False, "rule_pi_sequence_differs": True}
    )
    assert inconsistent["eligible"] is True
    assert inconsistent["dispersion_specific_signal"] is False
    assert inconsistent["classification"] == "instrumentation_or_policy_consistency_issue"
    ineligible = classify_dispersion_pair(**{**base, "length_criterion_ok": False})
    assert ineligible["eligible"] is False
    assert ineligible["dispersion_specific_signal"] is False


def test_phase2d_verdict_rules() -> None:
    assert decide_phase2d_verdict(n_eligible=0, n_dispersion_specific_signal=0) == (
        "PHASE2D_BLOCKED"
    )
    assert decide_phase2d_verdict(
        n_eligible=12,
        n_dispersion_specific_signal=0,
        blocked_reasons=("self-check failed",),
    ) == "PHASE2D_BLOCKED"
    assert decide_phase2d_verdict(n_eligible=12, n_dispersion_specific_signal=1) == (
        "PHASE2D_OFFLINE_SIGNAL"
    )
    assert decide_phase2d_verdict(n_eligible=12, n_dispersion_specific_signal=0) == (
        "PHASE2D_OFFLINE_NO_SIGNAL"
    )
