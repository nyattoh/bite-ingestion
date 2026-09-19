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
