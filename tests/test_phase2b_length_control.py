"""Phase 2B calibration-only length control tests.

No BITE profiler/routing/operator imports. Evaluation surfaces are not
generated. Tokenizer download is not required for these tests.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase2a import design_cells, generate_phase2a_bundle
from bite_bench.phase2b import (
    AXIS_LEVELS,
    SCHEMA_ID,
    calibration_cells,
    evaluation_case_ids,
    morphology_coverage,
    paired_contrasts,
    require_calibration,
    validate_phase2b_doc,
)
from bite_bench.token_match import (
    TOKEN_MATCH_MAX_ABS_DELTA,
    TOKEN_MATCH_MAX_RELATIVE_DELTA,
)

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "phase2b" / "calibration-token-matrix.json"
DRAFT = ROOT / "benchmarks" / "spec" / "phase2b-length-control-draft.json"
SCHEMA = ROOT / "spec" / "phase2b-length-control.schema.json"
PHASE2B_PY = ROOT / "src" / "bite_bench" / "phase2b.py"
SCRIPT = ROOT / "scripts" / "measure_phase2b_calibration_lengths.py"
FORBIDDEN = (
    "bite_eval",
    "DeterministicMorphologyProfiler",
    "RulePolicy",
    "LengthOnlyPolicy",
    "UNTANGLE",
    "REDUCE",
    "INTEGRATE",
    "re-bite",
    "rebite",
)


def _calibration_cell():
    return next(c for c in design_cells("calibration") if c.replica == 0)


def test_evaluation_split_is_fail_closed() -> None:
    with pytest.raises(ValueError, match="sealed"):
        require_calibration("evaluation")
    with pytest.raises(ValueError, match="sealed"):
        require_calibration("all")


def test_runner_fail_closes_before_evaluation_generation(tmp_path: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--split",
            "evaluation",
            "--artifact-dir",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert proc.returncode != 0
    assert "BLOCKED" in (proc.stderr + proc.stdout)
    assert list(tmp_path.iterdir()) == []


def test_phase2b_source_does_not_import_bite_eval_or_operators() -> None:
    source = PHASE2B_PY.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")
    for blob in (source, script):
        for needle in FORBIDDEN:
            assert needle not in blob, needle


def test_phase1c_tolerance_was_not_widened() -> None:
    assert TOKEN_MATCH_MAX_ABS_DELTA == 3
    assert TOKEN_MATCH_MAX_RELATIVE_DELTA == 0.04


def test_calibration_cells_are_replicas_0_and_1() -> None:
    cells = calibration_cells()
    assert len(cells) == 12
    assert {c.replica for c in cells} == {0, 1}
    assert all(c.split == "calibration" for c in cells)
    assert not ({c.case_id for c in cells} & evaluation_case_ids())


def test_pairs_are_within_one_calibration_case() -> None:
    cell = _calibration_cell()
    bundle = generate_phase2a_bundle(cell)
    for axis in AXIS_LEVELS:
        rows = paired_contrasts(bundle["surfaces"], axis)
        assert len(rows) == 4
        for row in rows:
            assert row["left_family"] in bundle["surfaces"]
            assert row["right_family"] in bundle["surfaces"]
            assert row["left_family"] != row["right_family"]


def test_morphology_coverage_on_calibration_only() -> None:
    for cell in design_cells("calibration"):
        bundle = generate_phase2a_bundle(cell)
        report = morphology_coverage(bundle)
        assert report["ok"], report["violations"]
        assert report["identity_stable"] is True
        assert report["structure_hash_diffs"] == 4
        assert report["dispersion_spread_diffs"] == 4
        assert report["redundancy_count_diffs"] == 4


def test_measurement_script_iterates_calibration_cells_only() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "calibration_cells()" in source
    assert "generate_phase2a_bundle(cell)" in source
    assert "require_calibration" in source


def test_validator_rejects_evaluation_leak() -> None:
    leaked = next(iter(sorted(evaluation_case_ids())))
    doc = {
        "schema": SCHEMA_ID,
        "paid_api": False,
        "research_conclusion": False,
        "split": "calibration",
        "evaluation_sealed": True,
        "padding": False,
        "verdict": "PHASE2B_LENGTH_CONTROL_PARTIAL",
        "n_canonical_cases": 12,
        "n_surfaces": 96,
        "surfaces": [{"case_id": leaked, "replica": 2}],
        "contrasts": [],
    }
    errs = validate_phase2b_doc(doc)
    assert any("evaluation" in err for err in errs)


def test_committed_artifact_has_no_evaluation_cases() -> None:
    assert ARTIFACT.is_file(), "run scripts/measure_phase2b_calibration_lengths.py"
    doc = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert validate_phase2b_doc(doc) == []
    jsonschema.validate(doc, json.loads(SCHEMA.read_text(encoding="utf-8")))
    eval_ids = evaluation_case_ids()
    blob = ARTIFACT.read_text(encoding="utf-8")
    for case_id in eval_ids:
        assert case_id not in blob
    assert doc["split"] == "calibration"
    assert doc["n_canonical_cases"] == 12
    assert doc["n_surfaces"] == 96
    assert doc["padding"] is False
    assert doc["paid_api"] is False
    assert doc["tokenizer_reference"]["exact_hosted_model_equivalence_asserted"] is False
    assert doc["phase1c_match_rule"]["max_abs_delta"] == 3
    assert doc["phase1c_match_rule"]["max_relative_delta"] == 0.04
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    assert draft["evaluation_sealed"] is True
    assert draft["official_match_rule"]["widened_after_seeing_results"] is False
    for case_id in eval_ids:
        assert case_id not in DRAFT.read_text(encoding="utf-8")
