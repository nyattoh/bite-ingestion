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
from bite_eval.atom_aware_reference import (
    atom_aware_predictions,
    gold_triples,
    score_triples,
)
from bite_eval.phase4c_eval import RESULT_PATH as PHASE4C_RESULT
from bite_eval.phase4d_audit import RESULT_PATH, validate_phase4d_result

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


def test_atom_aware_triple_contract() -> None:
    gold = gold_triples(
        {
            "explicit_reference_edges": [
                {"name": "FOO", "source_line": 1, "dest_lines": [2]},
            ]
        }
    )
    assert gold == [(1, "FOO", 2)]
    units = [
        {"line_no": 1, "text": "SRC=${FOO}"},
        {"line_no": 2, "text": "FOO=kept"},
        {"line_no": 3, "text": "BAR=other"},
    ]
    pred, extra = atom_aware_predictions(
        [
            {"src": 0, "dst": 1, "atom": "FOO"},
            {"src": 0, "dst": 2, "atom": "FOO"},
            {"src": 0, "dst": 1, "atom": "nope"},
        ],
        units,
    )
    assert pred == [(1, "FOO", 2)]
    assert extra == 2
    scores = score_triples(gold, pred)
    assert scores["tp"] == 1
    assert scores["fp"] == 0
    assert scores["fn"] == 0
    fp_scores = score_triples(gold, [(1, "FOO", 3)])
    assert fp_scores["tp"] == 0
    assert fp_scores["fp"] == 1
    assert fp_scores["fn"] == 1
    empty = score_triples([], [])
    assert empty["atom_aware_recall"] == "NA"
    assert empty["atom_aware_precision"] == "NA"


def test_d1_audit_twelve_reconstructed() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert validate_phase4d_result(result) == []
    jsonschema.validate(
        result,
        json.loads(
            (ROOT / "spec" / "phase4d-measurement-semantics.schema.json").read_text(encoding="utf-8")
        ),
    )
    atom = json.loads((ROOT / "artifacts" / "phase4d" / "atom-aware-reference.json").read_text(encoding="utf-8"))
    jsonschema.validate(
        atom,
        json.loads(
            (ROOT / "spec" / "phase4d-atom-aware-reference.schema.json").read_text(encoding="utf-8")
        ),
    )
    assert result["verdict"] == "PHASE4D_MEASUREMENT_SEMANTICS_AUDITED"
    assert result["n_ok"] == 12
    assert result["n_audit"] == 12
    assert result["p3f_evaluation_holdout_used"] is False
    assert result["not_second_holdout_evaluation"] is True
    assert result["not_confirmatory"] is True
    assert result["phase4c_safety_phrasing"] == PHASE4C_SAFETY_PHRASE
    assert result["eval_conservation_safety_9_of_9"] is True
    ids = [row["source_id"] for row in result["rows"]]
    assert ids == list(AUDIT_SOURCE_IDS)


def test_legacy_eval_matches_phase4c_and_ratis_not_assumed() -> None:
    cov = json.loads(
        (ROOT / "artifacts" / "phase4c" / "reference-coverage.json").read_text(encoding="utf-8")
    )
    cmp = json.loads(
        (ROOT / "artifacts" / "phase4d" / "legacy-vs-atom-aware.json").read_text(encoding="utf-8")
    )
    by_id = {row["source_id"]: row for row in cmp["documents"]}
    for row in cov["documents"]:
        got = by_id[row["source_id"]]
        assert got["line_pair_recall_legacy"] == row["gold_reference_recall"]
        assert got["gold_n_pairs"] == row["gold_n"]
    ratis = by_id["rs1-props-ratis-log4j"]
    assert ratis["line_pair_recall_legacy"] == 1.0
    assert ratis["atom_aware_recall"] != 1.0
    assert ratis["recalls_differ"] is True


def test_polybar_gogs_reduce_check_classified() -> None:
    safe = json.loads(
        (ROOT / "artifacts" / "phase4d" / "safety-check-decomposition.json").read_text(encoding="utf-8")
    )
    route = json.loads(
        (ROOT / "artifacts" / "phase4d" / "routing-vs-full-source-safety.json").read_text(encoding="utf-8")
    )
    by_safe = {row["source_id"]: row for row in safe["documents"]}
    by_route = {row["source_id"]: row for row in route["documents"]}
    for source_id in ("rs1-ini-polybar", "rs1-ini-gogs"):
        row = by_safe[source_id]
        diag = by_route[source_id]
        assert row["full_source_conservation_safety"] is True
        assert row["composition_safety_v2_ok"] is False
        assert row["failed_composition_checks"] == ["reduce_only_logical_duplicates"]
        assert row["failure_class"] == "full_source_merge_interaction"
        assert diag["routing_post_checks"]["reduce_only_logical_duplicates"] is True
        assert diag["routing_post_ok"] is True
        assert diag["passthrough_in_duplicate_idents"] is True
