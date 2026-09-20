"""Phase 4E E0 full-key reference freeze tests.

Does not implement v2/v4/v5. Does not rewrite Phase 4C/4D. Does not open p3f.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4e import (
    N_CANONICAL,
    N_SURFACES,
    PHASE4C_PROVENANCE_BLOB,
    PHASE4C_REFERENCE_BLOB,
    PHASE4C_RESULT_BLOB,
    PHASE4C_VERDICT,
    PHASE4D_ATOM_BLOB,
    PREMISE,
    PROTOCOL_FROZEN,
    forbidden_hits,
    freeze_manifest,
    validate_phase4e_freeze,
)
from bite_eval.phase4e_eval import RESULT_PATH, validate_phase4e_result
from bite_ingestion.profilers.dependency_dispersion_v3 import measure as measure_v3
from bite_ingestion.profilers.dependency_dispersion_v4 import measure as measure_v4
from bite_ingestion.profilers.reference_identity_v2 import source_tokens, target_tokens

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase4e-full-key-reference-freeze.json"
SCHEMA = ROOT / "spec" / "phase4e-full-key-reference-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase4e.py"


def _import_lines(path: Path) -> str:
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            lines.append(stripped)
    return "\n".join(lines)


def test_e0_freeze_matches_generator() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_phase4e_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["premise"] == PREMISE
    assert committed["n_canonical"] == N_CANONICAL == 20
    assert committed["n_surfaces"] == N_SURFACES == 80
    assert len(committed["planned_cases"]) == 20
    assert committed["copy_realstruct1_identifiers"] is False
    assert committed["no_realstruct2"] is True
    assert committed["no_baseline_added"] is True
    assert committed["p3f_evaluation_holdout_used"] is False
    assert committed["locked_t_high"] == 4.0
    assert committed["bridge"]["family"] == "simple_exact"
    for spec in committed["planned_cases"]:
        assert forbidden_hits(json.dumps(spec["records"])) == []
        if spec["family"] == "simple_exact":
            assert spec["bridge"] is True
            assert spec["intended_reference_edges"] == [[0, spec["distance"]]]
            assert spec["gate_expected"] is (spec["distance"] >= 4)


def test_e0_does_not_implement_or_open_p3f() -> None:
    imports = _import_lines(GEN_PY)
    assert "reference_identity_v2" not in imports
    assert "dependency_dispersion_v4" not in imports
    assert "conditional_texture_policy_v5" not in imports
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
    phase4c = json.loads(
        (ROOT / "artifacts" / "phase4c" / "real-holdout.json").read_text(encoding="utf-8")
    )
    phase4d = json.loads(
        (ROOT / "artifacts" / "phase4d" / "measurement-semantics.json").read_text(encoding="utf-8")
    )
    assert phase4c["verdict"] == PHASE4C_VERDICT
    assert phase4d["verdict"] == PREMISE


def test_v2_keeps_full_key_and_rejects_components() -> None:
    assert target_tokens("ridge.cairn.atlas") == ("ridge.cairn.atlas",)
    assert target_tokens("ware-kiln") == ("ware-kiln",)
    assert target_tokens("ridge.mark-west") == ("ridge.mark-west",)
    assert "ridge" not in target_tokens("ridge.cairn.atlas")
    assert "cairn.atlas" not in target_tokens("ridge.cairn.atlas")
    assert source_tokens("${ridge.cairn.atlas}") == ("ridge.cairn.atlas",)
    assert "spool_zz" not in source_tokens("bobbin id=spool_zz extra")


def test_v4_negatives_and_v3_bridge_on_simple() -> None:
    simple = "src_ridge=cairn_mark_x\ncairn_mark_x=weft_x\n"
    v3 = measure_v3({"payload": simple, "text": simple})
    v4 = measure_v4({"payload": simple, "text": simple})
    assert v3.features["n_reference_edges"] == v4.features["n_reference_edges"] == 1.0
    assert v3.features["mean_reference_edge_distance"] == v4.features["mean_reference_edge_distance"]
    prefix = "src=ridge.cairn\nridge.cairn.atlas=weft\n"
    assert measure_v4({"payload": prefix, "text": prefix}).features["n_reference_edges"] == 0.0
    suffix = "src=cairn.atlas\nridge.cairn.atlas=weft\n"
    assert measure_v4({"payload": suffix, "text": suffix}).features["n_reference_edges"] == 0.0
    sub = "src=cairn\nridge.cairn.atlas=weft\n"
    assert measure_v4({"payload": sub, "text": sub}).features["n_reference_edges"] == 0.0


def test_e1_primary_validated_and_secondary_retrospective() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert validate_phase4e_result(result) == []
    jsonschema.validate(
        result,
        json.loads(
            (ROOT / "spec" / "phase4e-full-key-reference.schema.json").read_text(encoding="utf-8")
        ),
    )
    assert result["verdict"] == "PHASE4E_FULL_KEY_REFERENCE_VALIDATED"
    assert result["n_ok"] == 80
    assert result["t_high_carry_forward"] is True
    assert result["p3f_evaluation_holdout_used"] is False
    secondary = json.loads(
        (ROOT / "artifacts" / "phase4e" / "realstruct1-retrospective.json").read_text(encoding="utf-8")
    )
    assert secondary["not_holdout"] is True
    assert secondary["not_confirmatory"] is True
    assert secondary["not_primary_pass_criterion"] is True
    assert len(secondary["documents"]) == 12

    def blob(rel: str) -> str:
        return subprocess.check_output(["git", "hash-object", rel], cwd=ROOT, text=True).strip()

    assert blob("artifacts/phase4c/real-holdout.json") == PHASE4C_RESULT_BLOB
    assert blob("artifacts/phase4c/reference-coverage.json") == PHASE4C_REFERENCE_BLOB
    assert blob("artifacts/phase4c/full-source-provenance.json") == PHASE4C_PROVENANCE_BLOB
    assert blob("artifacts/phase4d/atom-aware-reference.json") == PHASE4D_ATOM_BLOB
    assert blob("src/bite_ingestion/profilers/reference_identity_v1.py") == (
        "49dcd367eccdece7a1bd90df0a3f44f0c24ded65"
    )
    assert blob("src/bite_ingestion/profilers/dependency_dispersion_v3.py") == (
        "9ec1c46a68d685210898552c879098bf0416e56d"
    )
    assert blob("src/bite_ingestion/policies/conditional_texture_policy_v4.py") == (
        "04d46b15424ccbaf02694d7e7ae056b0b6715686"
    )
