"""Phase 3I composite provenance freeze (I0) and validation (I1) tests.

Does not open p3f evaluation. Does not rewrite Phase 3H. Does not connect routing.
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
    VERDICT_VALIDATED,
    freeze_manifest,
    planned_cases,
    validate_phase3i_freeze,
)
from bite_eval.phase3i_validate import (
    PROTOCOL_COMMIT_SHA,
    RESULT_PATH,
    malformed_unit,
    run_validation,
    validate_phase3i_result,
    well_formed_fixture,
)
from bite_ingestion.packet_contract import (
    PacketContractError,
    is_complete_provenance,
    provenance_kind,
    validate_unit,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase3i-composite-provenance-freeze.json"
SCHEMA = ROOT / "spec" / "phase3i-composite-provenance-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase3i.py"
V1_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "dependency_dispersion_v1.py"
POLICY_PY = ROOT / "src" / "bite_ingestion" / "policies" / "rule_policy.py"
PHASE3H = ROOT / "artifacts" / "phase3h" / "operator-map-experiment.json"
EXP_SCHEMA = ROOT / "spec" / "phase3i-composite-provenance.schema.json"
EXP_PY = ROOT / "src" / "bite_eval" / "phase3i_validate.py"


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


def test_i1_records_i0_sha_and_matches_artifacts() -> None:
    doc = run_validation()
    committed = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(doc, sort_keys=True)) == json.loads(
        json.dumps(committed, sort_keys=True)
    )
    assert validate_phase3i_result(committed) == []
    jsonschema.validate(committed, json.loads(EXP_SCHEMA.read_text(encoding="utf-8")))
    assert committed["protocol_commit_sha"] == PROTOCOL_COMMIT_SHA
    assert len(PROTOCOL_COMMIT_SHA) == 40
    assert committed["verdict"] == VERDICT_VALIDATED
    assert committed["rule_policy_implemented"] is False
    assert committed["p3f_evaluation_holdout_used"] is False
    assert committed["phase3h_verdict_unchanged"] == "PHASE3H_CONDITIONAL_MAP_REQUIRED"


def test_joined_from_is_not_complete_provenance() -> None:
    unit = malformed_unit("p3i-malformed-joined-from-only")
    assert provenance_kind(unit) == "malformed"
    assert is_complete_provenance(unit) is False
    with pytest.raises(PacketContractError, match="composite provenance"):
        validate_unit(unit)


def test_composite_cannot_wear_a_source_exact_span() -> None:
    unit = malformed_unit("p3i-malformed-fake-span")
    assert provenance_kind(unit) == KIND_COMPOSITE
    with pytest.raises(PacketContractError, match="envelope span"):
        validate_unit(unit)


def test_operator_packet_does_not_carry_gold() -> None:
    fixture = well_formed_fixture("p3i-same-uri-2way")
    assert "gold_evidence_ids" not in fixture["packet"]
    assert fixture["gold_unit_ids"]
    assert fixture["generation"] == GENERATION


def test_i1_does_not_import_routing_or_p3f_eval() -> None:
    blob = EXP_PY.read_text(encoding="utf-8")
    assert "from bite_ingestion.policies" not in blob
    assert "RulePolicy" not in blob
    assert "from bite_bench.phase3f" not in blob
