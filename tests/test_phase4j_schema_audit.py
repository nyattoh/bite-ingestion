"""Phase 4J J0 reference-schema audit freeze tests.

Does not implement gold_triples_v2. Does not rerun arms. Does not open p3f.
Does not rewrite Phase 4I artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4j import (
    HISTORICAL_GOLD_READER_BLOB,
    PHASE4I_HEAD,
    PREMISE,
    PROTOCOL_FROZEN,
    freeze_manifest,
    validate_phase4j_freeze,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase4j-reference-schema-freeze.json"
SCHEMA = ROOT / "spec" / "phase4j-reference-schema-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase4j.py"


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
