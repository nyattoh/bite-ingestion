"""Phase 3F routing-calibration protocol freeze tests.

Does not measure v1 or RulePolicy. Does not open Phase 2 holdout.
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
    SCHEMA_ID,
    adversarial_surface,
    design_cells,
    freeze_manifest,
    make_surface,
    sensor_source_unit,
    split_manifest,
    validate_phase3f_doc,
)
from bite_ingestion.policies.thresholds import TBD_CALIBRATE
from bite_ingestion.profilers.dependency_dispersion import SENSOR_NAME as V0_NAME
from bite_ingestion.profilers.dependency_dispersion_v1 import SENSOR_NAME as V1_NAME

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase3f-routing-calibration-freeze.json"
SPLIT = ROOT / "benchmarks" / "spec" / "phase3f-split-manifest.json"
SCHEMA = ROOT / "spec" / "phase3f-routing-calibration-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase3f.py"
V1_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "dependency_dispersion_v1.py"
POLICY_PY = ROOT / "src" / "bite_ingestion" / "policies" / "rule_policy.py"


def test_committed_freeze_matches_code() -> None:
    assert FREEZE.is_file()
    assert SPLIT.is_file()
    doc = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert doc == freeze_manifest()
    assert json.loads(SPLIT.read_text(encoding="utf-8")) == split_manifest()
    assert validate_phase3f_doc(doc) == []
    jsonschema.validate(doc, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert doc["schema"] == SCHEMA_ID
    assert doc["verdict"] == "PHASE3F_ROUTING_CALIBRATION_PROTOCOL_FROZEN"


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


def test_candidate_and_threshold_protocol_frozen() -> None:
    doc = freeze_manifest()
    ids = [row["id"] for row in doc["candidates"]["candidates"]]
    assert ids == [
        "A_mean_edge_distance",
        "B_mean_edge_distance_norm",
        "C_raw_and_norm",
    ]
    assert doc["candidates"]["do_not_pick_by_n_signal"] is True
    assert doc["candidates"]["selection_priority"][0]["name"] == "adversarial_false_positive_rate"
    assert doc["threshold_search"]["values_not_set_in_phase3f"] is True
    assert doc["threshold_search"]["evaluation_sealed_until_locked"] is True
    assert doc["operator_maps"]["dispersion_feature_does_not_auto_integrate"] is True
    assert doc["thresholds_set"] is False


def test_freeze_has_no_evaluation_outcomes() -> None:
    blob = FREEZE.read_text(encoding="utf-8") + SPLIT.read_text(encoding="utf-8")
    for needle in ("operator_sequence", "T_profiler", "T_router"):
        assert needle not in blob
    assert "p2a-" not in blob
    assert "lookup_for_" not in blob
    assert "syn-case" not in blob
