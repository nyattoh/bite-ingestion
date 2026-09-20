"""Phase 4K K0 evidence-ledger freeze tests.

Documentation-only. Does not run experiments, tokenizer, arms, or sensors.
Does not open p3f. Does not rewrite Phase 4A-4J artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4k import (
    EVIDENCE_CATEGORIES,
    PHASE3Q_VERDICT,
    PHASE3S_VERDICT,
    PHASE4J_HEAD,
    PREMISE,
    PROTOCOL_FROZEN,
    UNSUPPORTED_CLAIMS,
    freeze_manifest,
    validate_phase4k_freeze,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase4k-evidence-ledger-freeze.json"
SCHEMA = ROOT / "spec" / "phase4k-evidence-ledger-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase4k.py"


def _import_lines(path: Path) -> str:
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            lines.append(stripped)
    return "\n".join(lines)


def test_k0_freeze_matches_generator() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_phase4k_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["premise"] == PREMISE
    assert committed["phase4j_head_sha"] == PHASE4J_HEAD
    assert committed["documentation_only"] is True
    assert committed["no_new_experiment"] is True
    assert committed["no_arm_rerun"] is True
    assert committed["no_tokenizer_execution"] is True
    assert committed["no_sensor_replay"] is True
    assert committed["no_phase4a_to_4j_rewrite"] is True
    assert committed["no_merge"] is True
    assert committed["do_not_pool_evidence_categories"] is True
    assert committed["evidence_categories"] == list(EVIDENCE_CATEGORIES)
    assert committed["phase3q_remains"] == PHASE3Q_VERDICT
    assert committed["phase3s_remains"] == PHASE3S_VERDICT
    assert committed["prospective_realstruct2_facts"]["matched_budget_unique_identity"]["n"] == 1
    assert committed["prospective_realstruct2_facts"]["historical_reference_retention"]["n"] == 0
    assert committed["retrospective_corrections"]["reference_retention"]["n"] == 1
    assert committed["unsupported_claims"] == list(UNSUPPORTED_CLAIMS)
    assert committed["p3f_evaluation_holdout_used"] is False
    assert committed["no_p3f_result_statement"] is True


def test_k0_does_not_execute_or_rewrite() -> None:
    imports = _import_lines(GEN_PY)
    assert "gold_triples_v2" not in imports
    assert "phase4j_audit" not in imports
    assert "phase4i_eval" not in imports
    assert "reference_tokenizer" not in imports
    assert "length_pi_v1" not in imports
    assert "conditional_texture_policy" not in imports
    assert "dependency_dispersion" not in imports
    assert "bite_ingestion.operators" not in imports
    assert "realstruct1_adapter" not in imports
    phase4j = json.loads(
        (ROOT / "artifacts" / "phase4j" / "reference-schema-audit.json").read_text(
            encoding="utf-8"
        )
    )
    assert phase4j["verdict"] == PREMISE
    phase4i = json.loads(
        (ROOT / "artifacts" / "phase4i" / "first-open.json").read_text(encoding="utf-8")
    )
    assert phase4i["verdict"] == "PHASE4I_PROSPECTIVE_COMPARISON_MEASURED"
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
