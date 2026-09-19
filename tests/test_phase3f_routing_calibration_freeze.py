"""Phase 3F routing-calibration protocol freeze tests.

v0.2 supersedes v0.1. Does not measure v1 or RulePolicy. Does not open holdout.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from bite_bench.phase3f import (
    ADVERSARIAL_KINDS,
    CALIBRATION_REPLICAS,
    DISPERSIONS,
    EVALUATION_REPLICAS,
    FORMATS,
    REVISION,
    REVISION_V01,
    REVISION_V02,
    SCHEMA_ID,
    SCHEMA_ID_V01,
    SCHEMA_ID_V02,
    adversarial_case,
    adversarial_surface,
    bin_ordering_holds,
    candidate_ordering_holds,
    design_cells,
    freeze_manifest,
    is_negative_adversarial_case,
    load_v01_freeze,
    load_v02_freeze,
    make_surface,
    scale_stability_holds,
    select_best_candidate,
    select_best_grid_point,
    sensor_source_unit,
    split_manifest,
    validate_phase3f_doc,
)
from bite_ingestion.policies.thresholds import TBD_CALIBRATE
from bite_ingestion.profilers.dependency_dispersion import SENSOR_NAME as V0_NAME
from bite_ingestion.profilers.dependency_dispersion_v1 import SENSOR_NAME as V1_NAME

ROOT = Path(__file__).resolve().parents[1]
FREEZE_V01 = ROOT / "benchmarks" / "spec" / "phase3f-routing-calibration-freeze.json"
FREEZE_V02 = ROOT / "benchmarks" / "spec" / "phase3f-routing-calibration-freeze-v0.2.json"
FREEZE_V03 = ROOT / "benchmarks" / "spec" / "phase3f-routing-calibration-freeze-v0.3.json"
SPLIT = ROOT / "benchmarks" / "spec" / "phase3f-split-manifest.json"
SCHEMA_V01 = ROOT / "spec" / "phase3f-routing-calibration-freeze.schema.json"
SCHEMA_V02 = ROOT / "spec" / "phase3f-routing-calibration-freeze-v0.2.schema.json"
SCHEMA_V03 = ROOT / "spec" / "phase3f-routing-calibration-freeze-v0.3.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase3f.py"
V1_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "dependency_dispersion_v1.py"
POLICY_PY = ROOT / "src" / "bite_ingestion" / "policies" / "rule_policy.py"


def test_v01_is_retained_not_overwritten() -> None:
    v01 = json.loads(FREEZE_V01.read_text(encoding="utf-8"))
    assert v01["revision"] == REVISION_V01
    assert v01["schema"] == SCHEMA_ID_V01
    assert validate_phase3f_doc(v01) == []
    jsonschema.validate(v01, json.loads(SCHEMA_V01.read_text(encoding="utf-8")))
    assert v01 == load_v01_freeze()
    names = [row["name"] for row in v01["candidates"]["selection_priority"]]
    assert names[0] == "adversarial_false_positive_rate"
    assert "bin_ordering_coverage" not in str(v01["threshold_search"]["objective"])


def test_v02_is_retained_not_overwritten() -> None:
    v02 = json.loads(FREEZE_V02.read_text(encoding="utf-8"))
    assert v02["revision"] == REVISION_V02
    assert v02["schema"] == SCHEMA_ID_V02
    assert validate_phase3f_doc(v02) == []
    jsonschema.validate(v02, json.loads(SCHEMA_V02.read_text(encoding="utf-8")))
    assert v02 == load_v02_freeze()
    assert v02["supersedes"] == REVISION_V01
    assert json.loads(SPLIT.read_text(encoding="utf-8")) == split_manifest()


def test_v03_supersedes_v02_and_matches_code() -> None:
    v03 = json.loads(FREEZE_V03.read_text(encoding="utf-8"))
    assert v03 == freeze_manifest()
    assert validate_phase3f_doc(v03) == []
    jsonschema.validate(v03, json.loads(SCHEMA_V03.read_text(encoding="utf-8")))
    assert v03["schema"] == SCHEMA_ID
    assert v03["revision"] == REVISION
    assert v03["supersedes"] == REVISION_V02
    assert v03["supersession"]["v0_1_deleted"] is False
    assert v03["supersession"]["v0_2_deleted"] is False
    assert v03["supersession"]["v0_2_overwritten"] is False
    assert v03["verdict"] == "PHASE3F_ROUTING_CALIBRATION_PROTOCOL_FROZEN"


def test_v03_keeps_v02_generation_split_candidates_grids_objective() -> None:
    v01 = load_v01_freeze()
    v02 = load_v02_freeze()
    v03 = freeze_manifest()
    assert v02["adversarial"] == v01["adversarial"]
    assert v03["adversarial"] == v02["adversarial"]
    assert v03["canonical_case_ids"] == v02["canonical_case_ids"]
    assert v03["required_formats"] == v02["required_formats"]
    assert v03["candidates"] == v02["candidates"]
    assert v03["threshold_search"]["grids"] == v02["threshold_search"]["grids"]
    assert v03["threshold_search"]["objective"] == v02["threshold_search"]["objective"]
    assert v03["operator_maps"]["candidates"] == v02["operator_maps"]["candidates"]
    assert v03["n_primary_surfaces"] == v02["n_primary_surfaces"] == 216
    assert v03["n_adversarial_surfaces"] == v02["n_adversarial_surfaces"] == 48
    assert v03["generation"] == "p3f"
    assert split_manifest()["revision"] == REVISION_V01


def test_generator_source_does_not_measure_or_open_holdout() -> None:
    text = GEN_PY.read_text(encoding="utf-8")
    for needle in (
        "bite_bench.phase2a",
        "generate_phase2a_bundle",
        "from bite_ingestion.policies",
        "from bite_ingestion.profilers",
        "RulePolicy",
        "TBD_CALIBRATE",
    ):
        assert needle not in text, needle


def test_sensor_and_policy_untouched() -> None:
    assert V0_NAME == "dependency_dispersion_v0"
    assert V1_NAME == "dependency_dispersion_v1"
    assert TBD_CALIBRATE.HIGH == 0.66
    assert TBD_CALIBRATE.LOW == 0.34
    assert "ROUTING_FEATURES" in POLICY_PY.read_text(encoding="utf-8")
    v1 = V1_PY.read_text(encoding="utf-8")
    assert "def _key_side_atoms(" in v1


def test_split_is_frozen_and_disjoint() -> None:
    cal = {c.case_id for c in design_cells("calibration")}
    ev = {c.case_id for c in design_cells("evaluation")}
    assert cal.isdisjoint(ev)
    assert all(c.replica in CALIBRATION_REPLICAS for c in design_cells("calibration"))
    assert all(c.replica in EVALUATION_REPLICAS for c in design_cells("evaluation"))
    split = split_manifest()
    assert split["evaluation_outcomes_open"] is False
    assert split["calibration_measured"] is False
    assert split["n_calibration"] + split["n_evaluation"] == len(split["surfaces"])


def test_near_medium_far_are_permutations_no_padding() -> None:
    cell = design_cells("calibration")[0]
    payloads = []
    for disp in DISPERSIONS:
        surf = make_surface(cell, disp, "key_value")
        payloads.append(tuple(sorted(surf["payload"].splitlines())))
    assert payloads[0] == payloads[1] == payloads[2]
    unit = sensor_source_unit(make_surface(cell, "far", "json")["payload"])
    assert set(unit) == {"payload", "text"}
    assert "required_evidence_ids" not in unit
    assert "gold_answer" not in unit


def test_required_formats_only_kv_and_json() -> None:
    assert FORMATS == ("key_value", "json")
    cell = next(c for c in design_cells() if c.shape == "one_hop" and c.scale == "small")
    kv = make_surface(cell, "near", "key_value")["payload"]
    js = make_surface(cell, "near", "json")["payload"]
    assert kv.startswith("origin_")
    assert js.startswith("[{")
    assert ":" not in kv.split("=", 1)[0]


def test_adversarial_kinds_are_specified() -> None:
    assert ADVERSARIAL_KINDS[0] == "key_suffix_matches_value"
    spec = freeze_manifest()["adversarial"]
    kinds = {row["kind"] for row in spec}
    assert set(ADVERSARIAL_KINDS) <= kinds
    trap = adversarial_surface("true_dep_plus_misleading_suffix", 0, "key_value")
    assert "trap_hop_mu_r0" in trap["payload"]
    unit = sensor_source_unit(trap["payload"])
    assert "intended_edges" not in unit
    empty = [k for k in ADVERSARIAL_KINDS if is_negative_adversarial_case(adversarial_case(k, 0)["intended_edges"])]
    assert "true_dep_plus_misleading_suffix" not in empty
    assert len(empty) == 5


def test_v03_metric_roles_and_selection_rules() -> None:
    doc = freeze_manifest()
    fp = doc["metric_roles"]["sensor_level_diagnostic"]["edge_false_positive_rate"]
    assert fp["used_in_threshold_grid_objective"] is False
    assert fp["used_in_candidate_selection"] is False
    cand = doc["metric_roles"]["candidate_level"]
    assert cand["used_in_threshold_grid_point_comparison"] is False
    assert cand["no_new_scalar_for_C"] is True
    assert cand["no_weighted_sum_of_raw_and_norm"] is True
    assert cand["continuous_dispersion_ordering_coverage"]["C_raw_and_norm"]["continuous_score"] is None
    names = [row["name"] for row in doc["candidates"]["selection_priority"]]
    assert names == [
        "continuous_dispersion_ordering_coverage",
        "scale_stability",
        "format_consistency",
        "non_collapse",
        "simplicity",
    ]
    order = [row["name"] for row in doc["threshold_search"]["objective"]["selection_order"]]
    assert order[:3] == [
        "negative_adversarial_elevated_bin_rate",
        "bin_ordering_coverage",
        "format_consistency",
    ]
    assert doc["threshold_search"]["objective"]["eligibility"] == "non_collapse"
    assert doc["threshold_search"]["values_not_set_in_phase3f"] is True
    assert doc["operator_maps"]["dispersion_feature_does_not_auto_integrate"] is True
    assert doc["operator_maps"]["adoption"] == "phase3h_routing_semantics_freeze"
    assert doc["operator_maps"]["phase3g_selects"] == [
        "feature_candidate_A_B_C",
        "threshold_values",
    ]
    assert "M1_locality_for_integrate" in doc["operator_maps"]["phase3g_does_not_select"]
    assert doc["thresholds_set"] is False
    assert bin_ordering_holds("low", "mid", "high")
    assert bin_ordering_holds("low", "low", "high")
    assert not bin_ordering_holds("mid", "mid", "mid")
    assert not bin_ordering_holds("high", "mid", "low")
    assert candidate_ordering_holds(
        "A_mean_edge_distance",
        raw_near=1,
        raw_medium=2,
        raw_far=4,
        norm_near=0.9,
        norm_medium=0.5,
        norm_far=0.1,
    )
    assert not candidate_ordering_holds(
        "C_raw_and_norm",
        raw_near=1,
        raw_medium=2,
        raw_far=4,
        norm_near=0.9,
        norm_medium=0.5,
        norm_far=0.1,
    )
    assert candidate_ordering_holds(
        "C_raw_and_norm",
        raw_near=1,
        raw_medium=2,
        raw_far=4,
        norm_near=0.1,
        norm_medium=0.2,
        norm_far=0.4,
    )
    assert scale_stability_holds(
        "A_mean_edge_distance",
        raw_one_hop_medium={"small": 4, "medium": 4, "large": 4},
        norm_one_hop_far={"small": 0.9, "medium": 0.5, "large": 0.3},
    )
    assert not scale_stability_holds(
        "C_raw_and_norm",
        raw_one_hop_medium={"small": 4, "medium": 4, "large": 4},
        norm_one_hop_far={"small": 0.9, "medium": 0.5, "large": 0.3},
    )
    winner = select_best_grid_point(
        [
            {
                "non_collapse": True,
                "negative_adversarial_elevated_bin_rate": 0.2,
                "bin_ordering_coverage": 0.9,
                "format_consistency": 1.0,
                "T_high": 8,
                "T_low": 2,
            },
            {
                "non_collapse": True,
                "negative_adversarial_elevated_bin_rate": 0.1,
                "bin_ordering_coverage": 0.1,
                "format_consistency": 0.0,
                "T_high": 9,
                "T_low": 1,
            },
            {
                "non_collapse": False,
                "negative_adversarial_elevated_bin_rate": 0.0,
                "bin_ordering_coverage": 1.0,
                "format_consistency": 1.0,
                "T_high": 4,
                "T_low": 1,
            },
        ]
    )
    assert winner is not None
    assert winner["T_high"] == 9
    tied = select_best_grid_point(
        [
            {
                "non_collapse": True,
                "negative_adversarial_elevated_bin_rate": 0.0,
                "bin_ordering_coverage": 1.0,
                "format_consistency": 1.0,
                "T_high": 6,
                "T_low": 2,
            },
            {
                "non_collapse": True,
                "negative_adversarial_elevated_bin_rate": 0.0,
                "bin_ordering_coverage": 1.0,
                "format_consistency": 1.0,
                "T_high": 6,
                "T_low": 1,
            },
        ]
    )
    assert tied is not None
    assert tied["T_low"] == 1
    cand = select_best_candidate(
        [
            {
                "id": "C_raw_and_norm",
                "non_collapse": True,
                "continuous_dispersion_ordering_coverage": 1.0,
                "scale_stability": 1.0,
                "format_consistency": 1.0,
            },
            {
                "id": "A_mean_edge_distance",
                "non_collapse": True,
                "continuous_dispersion_ordering_coverage": 1.0,
                "scale_stability": 1.0,
                "format_consistency": 1.0,
            },
        ]
    )
    assert cand is not None
    assert cand["id"] == "A_mean_edge_distance"


def test_freeze_has_no_evaluation_outcomes() -> None:
    blob = (
        FREEZE_V01.read_text(encoding="utf-8")
        + FREEZE_V02.read_text(encoding="utf-8")
        + FREEZE_V03.read_text(encoding="utf-8")
        + SPLIT.read_text(encoding="utf-8")
    )
    for needle in ("operator_sequence", "T_profiler", "T_router"):
        assert needle not in blob
    assert "p2a-" not in blob
    assert "lookup_for_" not in blob
    assert "syn-case" not in blob
