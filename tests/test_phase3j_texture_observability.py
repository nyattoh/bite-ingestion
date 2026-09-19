"""Phase 3J texture observability freeze tests (J0).

Does not measure profiler values. Does not open p3f evaluation.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase3j import (
    FORMATS,
    GENERATION,
    PROTOCOL_FROZEN,
    TEXTURES,
    EvaluationSealError,
    design_surfaces,
    freeze_manifest,
    make_surface,
    profiler_source_unit,
    refuse_p3f_evaluation,
    validate_phase3j_freeze,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase3j-texture-observability-freeze.json"
SCHEMA = ROOT / "spec" / "phase3j-texture-observability-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase3j.py"
V0_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "deterministic.py"
V1_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "dependency_dispersion_v1.py"
POLICY_PY = ROOT / "src" / "bite_ingestion" / "policies" / "rule_policy.py"
PHASE3H = ROOT / "artifacts" / "phase3h" / "operator-map-experiment.json"
PHASE3I = ROOT / "artifacts" / "phase3i" / "composite-provenance.json"


def test_committed_freeze_matches_manifest() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_phase3j_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["generation"] == GENERATION
    assert committed["reuse_p3h_fixtures"] is False
    assert committed["no_new_absolute_threshold"] is True
    assert committed["routing"]["rule_policy_executed"] is False
    assert committed["routing"]["fix_profiler_on_revision"] is False
    assert set(committed["design"]["formats"]) == set(FORMATS)
    assert set(committed["design"]["textures"]) == set(TEXTURES)


def test_p3j_surfaces_are_fresh_and_sealed() -> None:
    surfaces = design_surfaces()
    assert len(surfaces) == 24
    assert [row["surface_id"] for row in surfaces] == freeze_manifest()["planned_surface_ids"]
    for row in surfaces:
        assert row["generation"] == "p3j"
        assert row["split"] == "development"
        assert row["dispersion"] == "far"
        assert not row["case_id"].startswith("p3h-")
        assert not row["case_id"].startswith("p3f-")
        assert "-r2-" not in row["surface_id"]
        assert "-r3-" not in row["surface_id"]
        src = profiler_source_unit(row["payload"])
        assert set(src) == {"payload", "text"}
        assert "texture" not in src
        assert "gold" not in src
        assert "query" not in src


def test_canonical_gold_is_shared_intervening_texture_varies() -> None:
    red = make_surface("redundant", 0, "key_value")
    neu = make_surface("neutral", 0, "key_value")
    uniq = make_surface("unique_reference", 0, "key_value")
    anom = make_surface("anomalous", 0, "key_value")
    assert red["gold_unit_ids"] == neu["gold_unit_ids"] == uniq["gold_unit_ids"]
    assert red["n_facts"] == neu["n_facts"] == uniq["n_facts"] == anom["n_facts"]
    red_lines = red["payload"].splitlines()
    neu_lines = neu["payload"].splitlines()
    assert red_lines[0] == neu_lines[0]
    assert red_lines[-1] == neu_lines[-1]
    assert red_lines[1] == red_lines[2]
    assert neu_lines[1] != neu_lines[2]
    assert "id=" in uniq["payload"]
    assert "ref:" in uniq["payload"]
    assert "EXCEPTION" in anom["payload"]
    assert "ERROR" in anom["payload"]
    assert "EXCEPTION" not in neu["payload"]


def test_j0_does_not_open_p3f_or_touch_profiler_routing() -> None:
    blob = GEN_PY.read_text(encoding="utf-8")
    assert "from bite_bench.phase3f" not in blob
    assert "from bite_ingestion.policies" not in blob
    assert "RulePolicy" not in blob
    assert "DeterministicMorphologyProfiler" not in blob
    with pytest.raises(EvaluationSealError, match="evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
    refuse_p3f_evaluation("p3j-core-r0")
    assert json.loads(PHASE3H.read_text(encoding="utf-8"))["verdict"] == (
        "PHASE3H_CONDITIONAL_MAP_REQUIRED"
    )
    assert json.loads(PHASE3I.read_text(encoding="utf-8"))["verdict"] == (
        "PHASE3I_COMPOSITE_PROVENANCE_VALIDATED"
    )
    assert "class DeterministicMorphologyProfiler" in V0_PY.read_text(encoding="utf-8")
    assert "def measure(" in V1_PY.read_text(encoding="utf-8")
    assert "class RulePolicy" in POLICY_PY.read_text(encoding="utf-8")
