"""Phase 4D D0 measurement-semantics freeze tests.

Does not rewrite Phase 4C. Does not open p3f. Does not retune frozen BITE.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4b import EVAL_SOURCE_IDS
from bite_bench.phase4c import PROTOCOL_FROZEN as C0_PROTOCOL
from bite_bench.phase4d import (
    AUDIT_SOURCE_IDS,
    C0_FREEZE_BLOB,
    FORBIDDEN_PHASE4C_SAFETY_PHRASE,
    FREEZE_PATH,
    PHASE4C_HEAD,
    PHASE4C_PROVENANCE_BLOB,
    PHASE4C_REFERENCE_BLOB,
    PHASE4C_RESULT_BLOB,
    PHASE4C_SAFETY_PHRASE,
    PREMISE,
    PROTOCOL_FROZEN,
    freeze_manifest,
    validate_phase4d_freeze,
)
from bite_eval.phase4c_eval import RESULT_PATH as PHASE4C_RESULT

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "spec" / "phase4d-measurement-semantics-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase4d.py"


def _import_lines(path: Path) -> str:
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            lines.append(stripped)
    return "\n".join(lines)


def _git_blob(rel: str) -> str:
    return subprocess.check_output(["git", "hash-object", rel], cwd=ROOT, text=True).strip()


def test_d0_freeze_matches_generator() -> None:
    committed = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_phase4d_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["premise"] == PREMISE
    assert committed["phase4c_head_sha"] == PHASE4C_HEAD
    assert committed["audit_source_ids"] == list(AUDIT_SOURCE_IDS)
    assert committed["eval_source_ids"] == list(EVAL_SOURCE_IDS)
    assert committed["not_second_holdout_evaluation"] is True
    assert committed["not_confirmatory"] is True
    assert committed["phase4c_preservation"]["safety_phrasing"] == PHASE4C_SAFETY_PHRASE
    assert (
        committed["phase4c_preservation"]["forbidden_safety_phrasing"]
        == FORBIDDEN_PHASE4C_SAFETY_PHRASE
    )


def test_d0_does_not_open_p3f_or_retune() -> None:
    imports = _import_lines(GEN_PY)
    assert "bite_eval.phase4d_audit" not in imports
    assert "bite_ingestion.policies" not in imports
    assert "bite_ingestion.operators" not in imports
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")


def test_phase4c_artifacts_unchanged() -> None:
    result = json.loads(PHASE4C_RESULT.read_text(encoding="utf-8"))
    assert result["verdict"] == PREMISE
    freeze4c = json.loads(
        (ROOT / "benchmarks" / "spec" / "phase4c-holdout-first-open-freeze.json").read_text(
            encoding="utf-8"
        )
    )
    assert freeze4c["verdict"] == C0_PROTOCOL
    assert _git_blob("artifacts/phase4c/real-holdout.json") == PHASE4C_RESULT_BLOB
    assert _git_blob("artifacts/phase4c/reference-coverage.json") == PHASE4C_REFERENCE_BLOB
    assert _git_blob("artifacts/phase4c/full-source-provenance.json") == PHASE4C_PROVENANCE_BLOB
    assert _git_blob("benchmarks/spec/phase4c-holdout-first-open-freeze.json") == C0_FREEZE_BLOB
