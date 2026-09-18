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
    PHASE2D_ARMS,
    PHASE2D_VERDICTS,
    PRIMARY_AXIS,
    SCHEMA_ID,
    SYSTEM_PROMPT,
    TOKENIZER_REFERENCE,
    USER_TEMPLATE,
    confirmatory_pairs,
    freeze_manifest,
    validate_freeze_doc,
)
from bite_bench.token_match import (
    TOKEN_MATCH_MAX_ABS_DELTA,
    TOKEN_MATCH_MAX_RELATIVE_DELTA,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase2c-dispersion-freeze.json"
SCHEMA = ROOT / "spec" / "phase2c-dispersion-freeze.schema.json"
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


def test_phase2c_source_does_not_open_evaluation_or_bite_eval() -> None:
    source = PHASE2C_PY.read_text(encoding="utf-8")
    for needle in FORBIDDEN:
        assert needle not in source, needle


def test_committed_freeze_matches_code() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_freeze_doc(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["schema"] == SCHEMA_ID
    assert committed["revision"] == PHASE2C_REVISION
    assert committed["status"] == "FROZEN_PRE_HOLDOUT"
    assert committed["evaluation_sealed"] is True
    assert committed["arms_run"] is False


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
    blob = FREEZE.read_text(encoding="utf-8")
    for key in (
        "prompt_tokens",
        "left_tokens",
        "right_tokens",
        "operator_sequence",
        "payload_sha256",
        "T_profiler",
        "T_router",
    ):
        assert key not in blob
    pairs = json.dumps(json.loads(blob)["confirmatory_pairs"])
    assert "T_total" not in pairs
    assert "abs_delta" not in pairs


def test_length_criterion_is_phase1c() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
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
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert tuple(freeze["arms"]) == PHASE2D_ARMS
    assert set(freeze["phase2d_verdicts"]) == set(PHASE2D_VERDICTS)
    assert freeze["paid_model_accuracy_is_primary_endpoint"] is False
    assert "BITE_wins" in freeze["not_an_endpoint"]
    assert "n_pairs_length_pi_neq_rule_pi" in freeze["primary_offline_endpoints"]
    assert freeze["exclusion_rule"]["if_pair_fails_length_criterion"].startswith("exclude")
    assert "widen max_abs_delta" in freeze["exclusion_rule"]["do_not"]


def test_structure_and_redundancy_remain_secondary() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
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
