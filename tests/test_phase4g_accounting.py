"""Phase 4G G0 comparison-accounting freeze tests.

Does not implement recovery_bundle_v1 or visibility v2. Does not open p3f.
Does not rewrite Phase 4F. Does not acquire REALSTRUCT-2.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4g import (
    FIXTURE_FAMILIES,
    PHASE4C_VERDICT,
    PHASE4D_VERDICT,
    PHASE4E_VERDICT,
    PREMISE,
    PROTOCOL_FROZEN,
    freeze_manifest,
    validate_phase4g_freeze,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase4g-comparison-accounting-freeze.json"
SCHEMA = ROOT / "spec" / "phase4g-comparison-accounting-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase4g.py"


def _import_lines(path: Path) -> str:
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            lines.append(stripped)
    return "\n".join(lines)


def test_g0_freeze_matches_generator() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_phase4g_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["premise"] == PREMISE
    assert committed["fixture_families"] == list(FIXTURE_FAMILIES)
    assert len(committed["planned_cases"]) == 10
    assert committed["no_phase4f_rewrite"] is True
    assert committed["track_a"]["do_not_count_uncounted_original_source_copy"] is True
    assert committed["track_b"]["lineage_alone_insufficient"] is True
    assert committed["p3f_evaluation_holdout_used"] is False


def test_g0_does_not_implement_or_open_p3f() -> None:
    imports = _import_lines(GEN_PY)
    assert "recovery_bundle" not in imports
    assert "visibility_metrics_v2" not in imports
    assert "phase4g_eval" not in imports
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
    phase4f = json.loads(
        (ROOT / "artifacts" / "phase4f" / "prospective-comparison.json").read_text(encoding="utf-8")
    )
    phase4e = json.loads(
        (ROOT / "artifacts" / "phase4e" / "full-key-reference.json").read_text(encoding="utf-8")
    )
    phase4c = json.loads(
        (ROOT / "artifacts" / "phase4c" / "real-holdout.json").read_text(encoding="utf-8")
    )
    phase4d = json.loads(
        (ROOT / "artifacts" / "phase4d" / "measurement-semantics.json").read_text(encoding="utf-8")
    )
    assert phase4f["verdict"] == PREMISE
    assert phase4e["verdict"] == PHASE4E_VERDICT
    assert phase4c["verdict"] == PHASE4C_VERDICT
    assert phase4d["verdict"] == PHASE4D_VERDICT
    assert not (ROOT / "corpora" / "realstruct-2").exists()
