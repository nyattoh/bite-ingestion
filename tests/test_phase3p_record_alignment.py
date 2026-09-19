"""Phase 3P P0 freeze tests.

Does not implement v2. Does not change Phase 3O. Does not open p3f.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase3p import (
    PHASE3O_VERDICT,
    PROTOCOL_FROZEN,
    REPRODUCTION_SURFACES,
    EvaluationSealError,
    freeze_manifest,
    refuse_p3f_evaluation,
    validate_phase3p_freeze,
)
from bite_eval.phase3p_eval import (
    PROTOCOL_COMMIT_SHA,
    RESULT_PATH,
    run_evaluation,
    validate_phase3p_result,
)
from bite_ingestion.interfaces.operator import OperatorId
from bite_ingestion.logical_record import identity_of_text
from bite_ingestion.operators import OPERATOR_REGISTRY
from bite_ingestion.operators.reduce_v2 import LogicalReduceOperatorV2
from bite_ingestion.packet_contract import make_unit
from bite_ingestion.profilers.structural_redundancy_v2 import measure

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase3p-record-alignment-freeze.json"
SCHEMA = ROOT / "spec" / "phase3p-record-alignment-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase3p.py"
PHASE3O = ROOT / "artifacts" / "phase3o" / "xfer1-transfer.json"
V1_POLICY = ROOT / "src" / "bite_ingestion" / "policies" / "conditional_texture_policy_v1.py"
V1_SENSOR = ROOT / "src" / "bite_ingestion" / "profilers" / "structural_redundancy_v1.py"
V1_REDUCE = ROOT / "src" / "bite_ingestion" / "operators" / "reduce.py"
V1_SAFETY = ROOT / "src" / "bite_eval" / "phase3m_eval.py"


def test_committed_freeze_matches_manifest() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_phase3p_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["premise"] == PHASE3O_VERDICT
    assert committed["copy_xfer1_cases"] is False
    assert committed["p3f_evaluation_holdout_used"] is False
    assert committed["no_new_threshold"] is True
    assert committed["reproduction_only_surfaces"] == list(REPRODUCTION_SURFACES)
    assert committed["reproduction_not_primary_evidence"] is True
    assert committed["phase3o_remains"] == (
        "Phase3O remains FAILED; known failures are repaired in development"
    )


def test_phase3o_stays_failed_and_p3f_sealed() -> None:
    phase3o = json.loads(PHASE3O.read_text(encoding="utf-8"))
    assert phase3o["verdict"] == PHASE3O_VERDICT
    blob = GEN_PY.read_text(encoding="utf-8")
    assert "from bite_ingestion.policies.conditional_texture_policy_v2" not in blob
    assert "class RulePolicy" not in blob
    assert "from bite_ingestion.operators.reduce_v2" not in blob
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
    for path in (V1_POLICY, V1_SENSOR, V1_REDUCE):
        assert path.is_file()
    assert "def composition_safety(" in V1_SAFETY.read_text(encoding="utf-8")


def test_logical_identity_ignores_json_order_and_rejects_extra_fields() -> None:
    compact = '{"k":"slot_lab_dadj","v":"same_lab_dadj"}'
    reversed_obj = '{"v":"same_lab_dadj","k":"slot_lab_dadj"}'
    extra = '{"k":"slot_lab_dadj","v":"same_lab_dadj","meta":"tag"}'
    assert identity_of_text(compact) == identity_of_text(reversed_obj)
    assert identity_of_text(extra) is None
    payload = f"[{compact},{reversed_obj}]"
    report = measure({"payload": payload})
    assert report.fail_closed is False
    assert report.features["duplicate_unit_ratio"] > 0.0
    doc = f"[{compact},{reversed_obj}]"
    units = [
        make_unit(unit_id="a", text=compact, start=1, end=1 + len(compact), source_uri="u"),
        make_unit(
            unit_id="b",
            text=reversed_obj,
            start=2 + len(compact),
            end=2 + len(compact) + len(reversed_obj),
            source_uri="u",
        ),
    ]
    packet = {"packet_id": "t", "document": doc, "units": units, "visible_evidence": []}
    after = LogicalReduceOperatorV2().apply(packet)
    assert len(after["units"]) == 1
    assert after["units"][0]["unit_id"] == "a"
    assert after["units"][0]["text"] == compact


def test_p1_matches_artifacts_and_keeps_phase3o_failed() -> None:
    doc = run_evaluation()
    committed = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(doc, sort_keys=True)) == json.loads(
        json.dumps(committed, sort_keys=True)
    )
    assert validate_phase3p_result(committed) == []
    jsonschema.validate(
        committed,
        json.loads((ROOT / "spec" / "phase3p-record-alignment.schema.json").read_text(encoding="utf-8")),
    )
    assert committed["protocol_commit_sha"] == PROTOCOL_COMMIT_SHA
    assert committed["verdict"] == "PHASE3P_RECORD_ALIGNMENT_VALIDATED"
    assert committed["phase3o_verdict_unchanged"] is True
    assert json.loads(PHASE3O.read_text(encoding="utf-8"))["verdict"] == PHASE3O_VERDICT
    assert committed["xfer1_reproduction"]["primary"] is False
    assert OperatorId.REDUCE_V2 not in OPERATOR_REGISTRY
    assert "class ReduceOperator" in V1_REDUCE.read_text(encoding="utf-8")
    blob = RESULT_PATH.read_text(encoding="utf-8")
    assert "p3f-" not in blob
