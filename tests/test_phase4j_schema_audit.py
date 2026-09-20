"""Phase 4J reference-schema audit tests.

J0 freeze stays reader-free. Reader tests use synthetic fixtures only.
Does not rerun arms. Does not open p3f. Does not rewrite Phase 4I artifacts.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4i import PHASE4H2_RESULT_BLOB, PRIMARY_IDS
from bite_bench.phase4j import (
    ARM_ROWS_BLOB,
    HISTORICAL_GOLD_READER_BLOB,
    LEGACY_PAIRED_REF_BLOB,
    PHASE4I_HEAD,
    PHASE4I_RESULT_BLOB,
    PREMISE,
    PROTOCOL_FROZEN,
    freeze_manifest,
    validate_phase4j_freeze,
)
from bite_eval.atom_aware_reference import gold_triples
from bite_eval.gold_triples_v2 import GoldSchemaError, gold_triples_v2
from bite_eval.phase4j_audit import (
    J0_COMMIT_SHA,
    J0_FREEZE_BLOB,
    LEGACY_WHY,
    RESULT_PATH,
    validate_phase4j_result,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase4j-reference-schema-freeze.json"
SCHEMA = ROOT / "spec" / "phase4j-reference-schema-freeze.schema.json"
RESULT_SCHEMA = ROOT / "spec" / "phase4j-reference-schema-audit.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase4j.py"
AUDIT_PY = ROOT / "src" / "bite_eval" / "phase4j_audit.py"
FIXTURES = ROOT / "tests" / "fixtures" / "phase4j"


def _import_lines(path: Path) -> str:
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            lines.append(stripped)
    return "\n".join(lines)


def test_j0_freeze_matches_generator() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_phase4j_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["premise"] == PREMISE
    assert committed["phase4i_head_sha"] == PHASE4I_HEAD
    assert committed["no_arm_rerun"] is True
    assert committed["no_tokenizer_rerun"] is True
    assert committed["no_phase4i_rewrite"] is True
    assert committed["historical_gold_reader_blob"] == HISTORICAL_GOLD_READER_BLOB
    assert committed["gold_triples_v2"]["fail_closed_if_both_dest_fields"] is True
    assert committed["p3f_evaluation_holdout_used"] is False


def test_j0_does_not_rerun_or_rewrite_phase4i() -> None:
    imports = _import_lines(GEN_PY)
    assert "gold_triples_v2" not in imports
    assert "phase4j_audit" not in imports
    assert "reference_tokenizer" not in imports
    assert "length_pi_v1" not in imports
    assert "conditional_texture_policy_v5" not in imports
    phase4i = json.loads(
        (ROOT / "artifacts" / "phase4i" / "first-open.json").read_text(encoding="utf-8")
    )
    assert phase4i["verdict"] == PREMISE
    legacy = json.loads(
        (ROOT / "artifacts" / "phase4i" / "paired-reference-retention.json").read_text(
            encoding="utf-8"
        )
    )
    assert legacy["n"] == 0
    assert legacy["status"] == "not_observed"
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_gold_triples_v2_rs1_single_dest_lines() -> None:
    assert gold_triples_v2(_fixture("rs1_single.json")) == [(1, "HOST", 2)]


def test_gold_triples_v2_rs1_multiple_dest_lines() -> None:
    assert gold_triples_v2(_fixture("rs1_multi.json")) == [(4, "BASE", 1), (4, "BASE", 2)]


def test_gold_triples_v2_rs2_single_dest_line() -> None:
    assert gold_triples_v2(_fixture("rs2_single.json")) == [(17, "CT_ISO", 10)]


def test_gold_triples_v2_gold_identity_exact_match() -> None:
    assert gold_triples_v2(_fixture("gold_identity_match.json")) == [(17, "CT_ISO", 10)]


def test_gold_triples_v2_both_fields_fail_closed() -> None:
    with pytest.raises(GoldSchemaError, match="both dest_line and dest_lines"):
        gold_triples_v2(_fixture("both_fields.json"))


def test_gold_triples_v2_neither_field_fail_closed() -> None:
    with pytest.raises(GoldSchemaError, match="neither dest_line nor dest_lines"):
        gold_triples_v2(_fixture("neither_field.json"))


def test_gold_triples_v2_gold_identity_mismatch_fail_closed() -> None:
    with pytest.raises(GoldSchemaError, match="gold_identity"):
        gold_triples_v2(_fixture("gold_identity_mismatch.json"))


def test_gold_triples_v2_non_integer_destination_fail_closed() -> None:
    with pytest.raises(GoldSchemaError, match="dest_line must be integer"):
        gold_triples_v2(_fixture("non_integer_dest.json"))


def test_historical_reader_still_ignores_dest_line() -> None:
    doc = _fixture("rs2_single.json")
    assert gold_triples(doc) == []
    assert gold_triples_v2(doc) == [(17, "CT_ISO", 10)]


def test_j1_audit_does_not_rerun_arms_or_rewrite_phase4i() -> None:
    imports = _import_lines(AUDIT_PY)
    assert "reference_tokenizer" not in imports
    assert "length_pi_v1" not in imports
    assert "conditional_texture_policy" not in imports
    assert "phase4i_eval" not in imports
    assert "bite_ingestion.operators" not in imports
    historical = (ROOT / "src" / "bite_eval" / "atom_aware_reference.py").read_text(encoding="utf-8")
    assert "gold_triples_v2" not in historical
    assert 'edge.get("dest_lines")' in historical

    def blob(rel: str) -> str:
        return subprocess.check_output(["git", "hash-object", rel], cwd=ROOT, text=True).strip()

    assert blob("artifacts/phase4i/first-open.json") == PHASE4I_RESULT_BLOB
    assert blob("artifacts/phase4i/arm-rows.json") == ARM_ROWS_BLOB
    assert blob("artifacts/phase4i/paired-reference-retention.json") == LEGACY_PAIRED_REF_BLOB
    assert blob("artifacts/phase4h2/realstruct-2-augmented.json") == PHASE4H2_RESULT_BLOB
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")


def test_j1_reference_schema_audited() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert validate_phase4j_result(result) == []
    jsonschema.validate(result, json.loads(RESULT_SCHEMA.read_text(encoding="utf-8")))
    assert result["verdict"] == "PHASE4J_REFERENCE_SCHEMA_AUDITED"
    assert result["protocol_commit_sha"] == J0_COMMIT_SHA
    assert result["j0_freeze_blob"] == J0_FREEZE_BLOB
    assert result["track_a_rescored"] is True
    assert result["sensor_replay_exact"] is True
    assert result["atom_aware_corrected_produced"] is True
    assert result["phase4i_artifacts_unchanged"] is True
    assert result["p3f_evaluation_holdout_used"] is False
    assert result["no_arm_rerun"] is True
    assert result["errors"] == []
    assert "overall_score" not in result
    assert "best_arm" not in result

    paired = json.loads(
        (ROOT / "artifacts" / "phase4j" / "legacy-vs-corrected-paired-reference.json").read_text(
            encoding="utf-8"
        )
    )
    legacy = paired["phase4i_legacy_schema_reader_result"]
    assert legacy["n"] == 0
    assert legacy["status"] == "not_observed"
    assert paired["why"] == LEGACY_WHY
    assert paired["kind"] == "retrospective corrected reference-retention audit"
    corrected = paired["corrected"]
    assert corrected["n"] >= 1
    assert corrected["status"] == "observed"

    compat = json.loads(
        (ROOT / "artifacts" / "phase4j" / "annotation-compatibility.json").read_text(
            encoding="utf-8"
        )
    )
    assert compat["invariant_ok"] is True
    assert compat["n_documents"] == 18
    gold_docs = [row for row in compat["documents"] if int(row["n_canonical_triples"] or 0) > 0]
    assert gold_docs
    assert all(int(row["n_historical_gold_triples"] or 0) == 0 for row in gold_docs)

    sensor = json.loads(
        (ROOT / "artifacts" / "phase4j" / "sensor-replay.json").read_text(encoding="utf-8")
    )
    assert sensor["exact"] is True
    assert sensor["n_documents"] == 18
    assert [row["source_id"] for row in sensor["documents"]] == list(PRIMARY_IDS)

    atom = json.loads(
        (ROOT / "artifacts" / "phase4j" / "corrected-atom-aware.json").read_text(encoding="utf-8")
    )
    assert atom["produced"] is True
    assert atom["sensor_replay_exact"] is True
    assert len(atom["documents"]) == 18
