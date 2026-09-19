"""Phase 4A A0 REALSTRUCT-1 protocol freeze tests.

Does not acquire sources. Does not import or run BITE sensors/policies.
Does not change Phase 3T/3S/3Q. Does not open p3f.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase4a import (
    N_DOCUMENTS,
    PHASE3Q_VERDICT,
    PHASE3S_VERDICT,
    PHASE3T_VERDICT,
    PREMISE,
    PROTOCOL_FROZEN,
    EvaluationSealError,
    freeze_manifest,
    refuse_p3f_evaluation,
    validate_phase4a_freeze,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase4a-realstruct1-freeze.json"
SCHEMA = ROOT / "spec" / "phase4a-realstruct1-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase4a.py"
PHASE3T = ROOT / "artifacts" / "phase3t" / "exact-reference.json"
PHASE3S = ROOT / "artifacts" / "phase3s" / "reference-specificity.json"
PHASE3Q = ROOT / "artifacts" / "phase3q" / "xfer2-transfer.json"


def test_committed_freeze_matches_manifest() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_phase4a_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["premise"] == PREMISE
    assert committed["n_documents"] == N_DOCUMENTS
    assert committed["no_bite_execution"] is True
    assert committed["no_source_rewrite_after_bite"] is True
    assert committed["p3f_evaluation_holdout_used"] is False
    assert committed["no_xfer3"] is True
    assert "sources" not in committed
    assert committed["split"]["n_development"] == 3
    assert committed["split"]["n_evaluation"] == 9


def test_a0_does_not_import_bite_or_open_p3f() -> None:
    blob = GEN_PY.read_text(encoding="utf-8")
    assert "bite_ingestion.policies" not in blob
    assert "bite_ingestion.profilers" not in blob
    assert "dependency_dispersion_v3" not in blob
    assert "conditional_texture_policy_v4" not in blob
    assert "class RulePolicy" not in blob
    assert json.loads(PHASE3T.read_text(encoding="utf-8"))["verdict"] == PHASE3T_VERDICT
    assert json.loads(PHASE3S.read_text(encoding="utf-8"))["verdict"] == PHASE3S_VERDICT
    assert json.loads(PHASE3Q.read_text(encoding="utf-8"))["verdict"] == PHASE3Q_VERDICT
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
