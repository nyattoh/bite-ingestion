"""Phase 3H operator-map protocol freeze tests (H0).

Does not run operators. Does not open p3f evaluation. Does not change v1.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase3h import (
    ARMS,
    FORMATS,
    GENERATION,
    LOCKED_CANDIDATE,
    LOCKED_T_HIGH,
    LOCKED_T_LOW,
    MAP_VERDICTS,
    PROTOCOL_FROZEN,
    REPLICAS,
    TEXTURES,
    VERDICT_CONDITIONAL,
    VERDICT_M1,
    VERDICT_M2,
    VERDICT_UNRESOLVED,
    EvaluationSealError,
    consensus_signals,
    decide_verdict,
    design_surfaces,
    freeze_manifest,
    make_surface,
    refuse_p3f_evaluation,
    validate_phase3h_freeze,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase3h-operator-map-freeze.json"
SCHEMA = ROOT / "spec" / "phase3h-operator-map-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase3h.py"
V1_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "dependency_dispersion_v1.py"
POLICY_PY = ROOT / "src" / "bite_ingestion" / "policies" / "rule_policy.py"


def test_committed_freeze_matches_manifest() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_phase3h_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["generation"] == GENERATION
    assert committed["locked_from_phase3g"]["selected_candidate"] == LOCKED_CANDIDATE
    assert committed["locked_from_phase3g"]["T_low"] == LOCKED_T_LOW
    assert committed["locked_from_phase3g"]["T_high"] == LOCKED_T_HIGH
    assert committed["token_reduction_used_for_verdict"] is False
    assert committed["must_pick_m1_or_m2"] is False
    assert committed["map_verdicts"] == list(MAP_VERDICTS)


def test_p3f_evaluation_replicas_fail_closed() -> None:
    with pytest.raises(EvaluationSealError, match="evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
    with pytest.raises(EvaluationSealError, match="evaluation sealed"):
        refuse_p3f_evaluation("p3f-adv-shared_prefix-r3-json")
    refuse_p3f_evaluation("p3h-core-r0")
    refuse_p3f_evaluation("p3f-medium-one_hop-r0")


def test_generation_is_p3h_development_only() -> None:
    surfaces = design_surfaces()
    assert len(surfaces) == 12
    ids = [row["surface_id"] for row in surfaces]
    assert ids == freeze_manifest()["planned_surface_ids"]
    for row in surfaces:
        assert row["generation"] == "p3h"
        assert row["split"] == "development"
        assert row["dispersion"] == "far"
        assert row["replica"] in REPLICAS
        assert row["texture"] in TEXTURES
        assert row["format"] in FORMATS
        assert not row["case_id"].startswith("p3f-")
        assert "-r2-" not in row["surface_id"]
        assert "-r3-" not in row["surface_id"]
        gold = row["gold_unit_ids"]
        units = row["unit_ids"]
        assert units[0] == gold[0]
        assert units[-1] == gold[1]
        assert len(units) == 26


def test_textures_only_change_intervening_or_declared_overlay() -> None:
    red = make_surface("redundant", 0, "key_value")
    uniq = make_surface("unique", 0, "key_value")
    anom = make_surface("anomalous", 0, "key_value")
    assert red["question"] == uniq["question"] == anom["question"]
    assert red["answer"] == uniq["answer"] == anom["answer"]
    assert red["gold_unit_ids"] == uniq["gold_unit_ids"] == anom["gold_unit_ids"]
    assert red["unit_texts"][1] == red["unit_texts"][2]
    assert uniq["unit_texts"][1] != uniq["unit_texts"][2]
    assert "id=" in uniq["unit_texts"][0]
    assert "id=" in uniq["unit_texts"][-1]
    assert "id=" not in red["unit_texts"][0]
    assert any("ERROR" in text for text in anom["unit_texts"][1:-1])
    assert "ERROR" not in anom["unit_texts"][0]
    assert "ERROR" not in anom["unit_texts"][-1]


def test_verdict_rules_are_predeclared_and_ignore_tokens() -> None:
    def row(texture: str, arm: str, **extra: object) -> dict[str, object]:
        base: dict[str, object] = {
            "texture": texture,
            "arm": arm,
            "recall_visible": 1.0,
            "n_gold_removed": 0,
            "n_nongold_removed": 0,
            "n_gold_joined": 0,
            "n_quarantined": 0,
            "n_gold_quarantined": 0,
            "token_proxy": 9999,
        }
        base.update(extra)
        return base

    surfaces = product_rows(
        redundant_reduce=True,
        unique_integrate=True,
        anomalous_untangle=True,
        row=row,
    )
    consensus = consensus_signals(surfaces)
    assert decide_verdict(blocked=False, high_confirmed=True, consensus=consensus) == (
        VERDICT_CONDITIONAL
    )
    m1 = consensus_signals(
        product_rows(
            redundant_reduce=True,
            unique_integrate=False,
            anomalous_untangle=True,
            row=row,
        )
    )
    assert decide_verdict(blocked=False, high_confirmed=True, consensus=m1) == VERDICT_M1
    m2 = consensus_signals(
        product_rows(
            redundant_reduce=False,
            unique_integrate=True,
            anomalous_untangle=False,
            row=row,
        )
    )
    assert decide_verdict(blocked=False, high_confirmed=True, consensus=m2) == VERDICT_M2
    assert (
        decide_verdict(blocked=True, high_confirmed=True, consensus=consensus)
        == VERDICT_UNRESOLVED
    )
    assert (
        decide_verdict(blocked=False, high_confirmed=False, consensus=consensus)
        == VERDICT_UNRESOLVED
    )


def product_rows(
    *,
    redundant_reduce: bool,
    unique_integrate: bool,
    anomalous_untangle: bool,
    row: object,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for texture in TEXTURES:
        for arm in ARMS:
            for replica in REPLICAS:
                for fmt in FORMATS:
                    extra: dict[str, object] = {}
                    if texture == "redundant" and arm == "REDUCE" and redundant_reduce:
                        extra["n_nongold_removed"] = 12
                    if texture == "unique" and arm == "INTEGRATE" and unique_integrate:
                        extra["n_gold_joined"] = 1
                    if texture == "anomalous" and arm == "UNTANGLE" and anomalous_untangle:
                        extra["n_quarantined"] = 4
                    rows.append(row(texture, arm, replica=replica, format=fmt, **extra))
    return rows


def test_h0_does_not_import_routing_or_p3f_generator() -> None:
    blob = GEN_PY.read_text(encoding="utf-8")
    assert "from bite_bench.phase3f" not in blob
    assert "from bite_ingestion.policies" not in blob
    assert "RulePolicy" not in blob
    assert POLICY_PY.is_file()
    assert V1_PY.is_file()
    assert "HIGH" in POLICY_PY.read_text(encoding="utf-8")
