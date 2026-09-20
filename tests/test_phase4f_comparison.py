"""Phase 4F F0 prospective comparison freeze tests.

Does not implement length_pi_v1 or token accounting. Does not open p3f.
Does not acquire REALSTRUCT-2. Does not retune BITE.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4f import (
    ARMS,
    PHASE4C_VERDICT,
    PHASE4D_VERDICT,
    PREMISE,
    PROTOCOL_FROZEN,
    TOKENIZER_JSON_SHA256,
    freeze_manifest,
    validate_phase4f_freeze,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase4f-prospective-comparison-freeze.json"
SCHEMA = ROOT / "spec" / "phase4f-prospective-comparison-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase4f.py"


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
