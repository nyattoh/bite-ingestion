"""Phase 4E E0 full-key reference freeze tests.

Does not implement v2/v4/v5. Does not rewrite Phase 4C/4D. Does not open p3f.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4e import (
    N_CANONICAL,
    N_SURFACES,
    PHASE4C_VERDICT,
    PREMISE,
    PROTOCOL_FROZEN,
    forbidden_hits,
    freeze_manifest,
    validate_phase4e_freeze,
)

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
