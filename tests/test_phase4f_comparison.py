"""Phase 4F prospective comparison protocol tests.

F0 freeze does not implement baselines. F1 tests cover length_pi_v1 and
the committed development artifact. Does not open p3f. Does not acquire
REALSTRUCT-2. Does not retune BITE.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4f import (
    ARMS,
    IDENTITY_V2_BLOB,
    PHASE4C_VERDICT,
    PHASE4D_VERDICT,
    PHASE4E_RESULT_BLOB,
    POLICY_V5_BLOB,
    PREMISE,
    PROTOCOL_FROZEN,
    TOKENIZER_JSON_SHA256,
    freeze_manifest,
    validate_phase4f_freeze,
)
from bite_eval.length_pi_v1 import apply_length_pi_v1
from bite_eval.phase4f_eval import RESULT_PATH, validate_phase4f_result
from bite_eval.phase4f_metrics import (
    complete_prefix_indices,
    unique_assignment_identity_retention,
    visible_reference_retention,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase4f-prospective-comparison-freeze.json"
SCHEMA = ROOT / "spec" / "phase4f-prospective-comparison-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase4f.py"
LENGTH_PI_PY = ROOT / "src" / "bite_eval" / "length_pi_v1.py"


def _import_lines(path: Path) -> str:
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            lines.append(stripped)
    return "\n".join(lines)


def test_f0_freeze_matches_generator() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_phase4f_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["premise"] == PREMISE
    assert committed["arm_order"] == list(ARMS)
    assert committed["tokenizer_reference"]["tokenizer_json_sha256"] == TOKENIZER_JSON_SHA256
    assert committed["tokenizer_reference"]["forbidden_cost_metric"] == "local_char4_proxy"
    assert committed["no_realstruct2_acquisition"] is True
    assert committed["no_bite_retune_after_f0"] is True
    assert committed["no_winner_score"] is True
    assert committed["t_high_reference"] == 4
    assert committed["p3f_evaluation_holdout_used"] is False


def test_f0_does_not_implement_or_open_p3f() -> None:
    imports = _import_lines(GEN_PY)
    assert "length_pi_v1" not in imports
    assert "reference_tokenizer" not in imports
    assert "conditional_texture_policy_v5" not in imports
    assert "huggingface" not in imports
    assert "transformers" not in imports
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
    phase4e = json.loads(
        (ROOT / "artifacts" / "phase4e" / "full-key-reference.json").read_text(encoding="utf-8")
    )
    phase4c = json.loads(
        (ROOT / "artifacts" / "phase4c" / "real-holdout.json").read_text(encoding="utf-8")
    )
    phase4d = json.loads(
        (ROOT / "artifacts" / "phase4d" / "measurement-semantics.json").read_text(encoding="utf-8")
    )
    assert phase4e["verdict"] == PREMISE
    assert phase4c["verdict"] == PHASE4C_VERDICT
    assert phase4d["verdict"] == PHASE4D_VERDICT
    assert not (ROOT / "corpora" / "realstruct-2").exists()


def _count(text: str) -> int:
    return len(text)


def _end(text: str, budget: int) -> int:
    return max(0, min(int(budget), len(text)))


def test_length_pi_v1_prefix_and_sidecar() -> None:
    row = apply_length_pi_v1("abcdef", 4, payload_tokens=_count, prefix_char_end=_end)
    assert row["visible"] == "abcd"
    assert row["sidecar"] == "ef"
    assert row["visible"] + row["sidecar"] == "abcdef"
    assert row["budget_match_applicable"] is True
    full = apply_length_pi_v1("abcdef", 9, payload_tokens=_count, prefix_char_end=_end)
    assert full["visible"] == "abcdef"
    assert full["sidecar"] == ""
    assert full["bite_expanded_or_no_reduction"] is True
    source = LENGTH_PI_PY.read_text(encoding="utf-8")
    assert "from bite_ingestion" not in source
    assert "identity_of_text" not in source
    assert "measure_v4" not in source
    assert "gold_triples" not in source


def test_retention_metrics_prefix_and_na() -> None:
    texts = ["alpha=1", "beta=2", "alpha=1"]
    visible = "alpha=1"
    kept = complete_prefix_indices(texts, visible)
    assert kept == [0]
    assert unique_assignment_identity_retention(texts, [texts[0]]) == 0.5
    assert visible_reference_retention([], {1, 2}) == "NA"
    assert visible_reference_retention([(1, "X", 2), (3, "Y", 4)], {1, 2}) == 0.5


def test_f1_protocol_ready_and_frozen_blobs() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert validate_phase4f_result(result) == []
    jsonschema.validate(
        result,
        json.loads(
            (ROOT / "spec" / "phase4f-prospective-comparison.schema.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    assert result["verdict"] == "PHASE4F_COMPARISON_PROTOCOL_READY"
    assert result["n_documents"] == 12
    assert result["tokenizer_hash_verified"] is True
    assert result["length_pi_reconstruct_ok"] is True
    assert result["not_holdout"] is True
    assert result["not_confirmatory"] is True
    assert result["no_winner_score"] is True
    assert result["p3f_evaluation_holdout_used"] is False
    token = json.loads(
        (ROOT / "artifacts" / "phase4f" / "token-accounting.json").read_text(encoding="utf-8")
    )
    assert token["tokenizer_json_sha256"] == TOKENIZER_JSON_SHA256
    assert token["hash_verified"] is True
    assert token["hosted_glm_45_flash_byte_identical"] is False
    assert token["forbidden_cost_metric"] == "local_char4_proxy"

    def blob(rel: str) -> str:
        return subprocess.check_output(["git", "hash-object", rel], cwd=ROOT, text=True).strip()

    assert blob("src/bite_ingestion/profilers/reference_identity_v2.py") == IDENTITY_V2_BLOB
    assert blob("src/bite_ingestion/policies/conditional_texture_policy_v5.py") == POLICY_V5_BLOB
    assert blob("artifacts/phase4e/full-key-reference.json") == PHASE4E_RESULT_BLOB
    assert not (ROOT / "corpora" / "realstruct-2").exists()
