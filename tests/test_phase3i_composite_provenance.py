"""Phase 3I composite provenance freeze tests (I0).

Does not change INTEGRATE. Does not open p3f evaluation. Does not rewrite 3H.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase3i import (
    GENERATION,
    KIND_COMPOSITE,
    KIND_SOURCE,
    PROTOCOL_FROZEN,
    SPAN_ENVELOPE,
    freeze_manifest,
    planned_cases,
    validate_phase3i_freeze,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase3i-composite-provenance-freeze.json"
SCHEMA = ROOT / "spec" / "phase3i-composite-provenance-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase3i.py"
V1_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "dependency_dispersion_v1.py"
POLICY_PY = ROOT / "src" / "bite_ingestion" / "policies" / "rule_policy.py"
PHASE3H = ROOT / "artifacts" / "phase3h" / "operator-map-experiment.json"


def test_committed_freeze_matches_manifest() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_phase3i_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["generation"] == GENERATION
    assert committed["fields"]["provenance.kind"] == [KIND_SOURCE, KIND_COMPOSITE]
    assert committed["fields"]["composite_span"] == SPAN_ENVELOPE
    assert committed["completeness"]["joined_from_alone"] is False
    assert committed["routing"]["implement_conditional_map"] is False


def test_planned_cases_cover_required_shapes() -> None:
    ids = {row["case_id"] for row in planned_cases()}
    assert "p3i-same-uri-2way" in ids
    assert "p3i-three-way" in ids
    assert "p3i-mixed-uri" in ids
    assert "p3i-passthrough" in ids
    assert "p3i-dep-edge" in ids
    assert "p3i-explicit-key" in ids
    assert "p3i-malformed-joined-from-only" in ids
    assert "p3i-malformed-fake-span" in ids
    for row in planned_cases():
        assert str(row["case_id"]).startswith("p3i-")
        assert not str(row["case_id"]).startswith("p3h-")
        assert not str(row["case_id"]).startswith("p3f-")


def test_phase3h_artifact_is_not_rewritten() -> None:
    doc = json.loads(PHASE3H.read_text(encoding="utf-8"))
    assert doc["verdict"] == "PHASE3H_CONDITIONAL_MAP_REQUIRED"
    assert doc["rule_policy_implemented"] is False
    assert doc["token_reduction_used_for_verdict"] is False


def test_i0_does_not_open_p3f_or_touch_routing_sensor() -> None:
    blob = GEN_PY.read_text(encoding="utf-8")
    freeze = FREEZE.read_text(encoding="utf-8")
    assert "from bite_bench.phase3f" not in blob
    assert "from bite_ingestion.policies" not in blob
    assert "from bite_ingestion.operators" not in blob
    assert "RulePolicy" not in blob
    assert '"p3f_evaluation_holdout_used": false' in freeze
    assert POLICY_PY.is_file()
    assert "class RulePolicy" in POLICY_PY.read_text(encoding="utf-8")
    assert "def measure(" in V1_PY.read_text(encoding="utf-8")
    from bite_bench.phase3h import EvaluationSealError, refuse_p3f_evaluation

    with pytest.raises(EvaluationSealError):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
