"""Phase 4K K0 evidence-ledger freeze tests.

Documentation-only. Does not run experiments, tokenizer, arms, or sensors.
Does not open p3f. Does not rewrite Phase 4A-4J artifacts.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4k import (
    EVIDENCE_CATEGORIES,
    PHASE3Q_VERDICT,
    PHASE3S_VERDICT,
    PHASE4_CONCLUSION,
    PHASE4J_HEAD,
    PREMISE,
    PROTOCOL_FROZEN,
    UNSUPPORTED_CLAIMS,
    freeze_manifest,
    validate_phase4k_freeze,
)
from bite_bench.phase4k_ledger import (
    K0_COMMIT_SHA,
    K0_FREEZE_BLOB,
    RESULT_PATH,
    validate_phase4k_result,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase4k-evidence-ledger-freeze.json"
SCHEMA = ROOT / "spec" / "phase4k-evidence-ledger-freeze.schema.json"
RESULT_SCHEMA = ROOT / "spec" / "phase4k-evidence-ledger.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase4k.py"
LEDGER_PY = ROOT / "src" / "bite_bench" / "phase4k_ledger.py"


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


def test_k1_ledger_does_not_execute() -> None:
    imports = _import_lines(LEDGER_PY)
    assert "gold_triples_v2" not in imports
    assert "phase4j_audit" not in imports
    assert "phase4i_eval" not in imports
    assert "reference_tokenizer" not in imports
    assert "length_pi_v1" not in imports
    assert "conditional_texture_policy" not in imports
    assert "dependency_dispersion" not in imports
    assert "bite_ingestion.operators" not in imports
    assert "realstruct1_adapter" not in imports
    freeze_imports = _import_lines(GEN_PY)
    assert "phase4k_ledger" not in freeze_imports


def test_k1_evidence_ledger_frozen() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert validate_phase4k_result(result) == []
    jsonschema.validate(result, json.loads(RESULT_SCHEMA.read_text(encoding="utf-8")))
    assert result["verdict"] == "PHASE4K_EVIDENCE_LEDGER_FROZEN"
    assert result["protocol_commit_sha"] == K0_COMMIT_SHA
    assert result["k0_freeze_blob"] == K0_FREEZE_BLOB
    assert result["documentation_only"] is True
    assert result["no_new_experiment"] is True
    assert result["no_arm_rerun"] is True
    assert result["no_sensor_replay"] is True
    assert result["no_merge"] is True
    assert result["p3f_evaluation_holdout_used"] is False
    assert result["phase4_conclusion"] == PHASE4_CONCLUSION
    assert result["errors"] == []
    assert "overall_score" not in result
    assert "best_arm" not in result
    assert "win_rate" not in result

    ledger = json.loads(
        (ROOT / "artifacts" / "phase4k" / "evidence-ledger.json").read_text(encoding="utf-8")
    )
    assert ledger["do_not_pool_evidence_categories"] is True
    assert ledger["evidence_categories"] == list(EVIDENCE_CATEGORIES)
    for key in EVIDENCE_CATEGORIES:
        assert key in ledger
        assert ledger[key]["pooled_with_other_categories"] is False
    prospective = ledger["prospective_realstruct2_comparison_evidence"]
    assert prospective["n_primary_documents"] == 18
    assert prospective["n_arm_rows"] == 72
    assert prospective["bite_model_visible_reduction_incidence"]["n"] == 1
    assert prospective["bite_model_visible_reduction_incidence"]["not_a_win_rate"] is True
    ident = prospective["matched_budget_unique_identity"]
    assert ident["n"] == 1
    assert ident["n_prominence"] == "n=1"
    assert ident["source_id"] == "rs2-ini-genicam-harvesters_gui"
    hist = prospective["historical_reference_retention_phase4i"]
    assert hist["n"] == 0
    assert hist["status"] == "not_observed"
    retro = ledger["retrospective_measurement_corrections"]
    assert retro["phase4j_reference_retention"]["n"] == 1
    assert retro["phase4j_reference_retention"]["delta"] == 0.0
    assert retro["phase4j_reference_sensor"]["precision"] == 1.0
    assert retro["not_a_new_first_open"] is True
    mechanism = ledger["mechanism_evidence"]
    assert mechanism["phase4i_mechanism_incidence"]["route_empty"]["n"] == 17
    assert mechanism["phase4i_mechanism_incidence"]["gate_is_not_successful_transformation_incidence"] is True
    failures = {row["verdict"] for row in mechanism["historical_failures_preserved"]}
    assert PHASE3Q_VERDICT in failures
    assert PHASE3S_VERDICT in failures

    compare = json.loads(
        (ROOT / "artifacts" / "phase4k" / "prospective-vs-retrospective.json").read_text(
            encoding="utf-8"
        )
    )
    assert compare["reference_retention"]["prospective_phase4i"]["n"] == 0
    assert compare["reference_retention"]["retrospective_phase4j"]["n"] == 1
    assert compare["matched_budget_unique_identity"]["n"] == 1

    claims = json.loads(
        (ROOT / "artifacts" / "phase4k" / "claim-matrix.json").read_text(encoding="utf-8")
    )
    unsupported = {row["claim"] for row in claims["unsupported"]}
    assert unsupported == set(UNSUPPORTED_CLAIMS)
    assert all(row.get("n") is not None for row in claims["supported"])

    wording = json.loads(
        (ROOT / "artifacts" / "phase4k" / "publication-safe-wording.json").read_text(
            encoding="utf-8"
        )
    )
    assert wording["phase4_conclusion"] == PHASE4_CONCLUSION
    assert wording["do_not_add_winner_conclusion"] is True
    assert "BITE superiority" in wording["forbidden"]

    def blob(rel: str) -> str:
        return subprocess.check_output(["git", "hash-object", rel], cwd=ROOT, text=True).strip()

    assert blob("artifacts/phase4i/first-open.json") == "144a4ca3c2e44d8f0abbd32d0bb8b2f2b5b7b149"
    assert blob("artifacts/phase4j/reference-schema-audit.json") == (
        "b4ccdff3860c643630a292d16ea4428c6d480e06"
    )
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
