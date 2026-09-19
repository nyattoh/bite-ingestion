"""Phase 3O BITE-XFER-1 freeze (O0) tests.

Does not run policy. Does not import phase3m. Does not open p3f.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase3o import (
    N_SURFACES,
    PROTOCOL_FROZEN,
    EvaluationSealError,
    derive_expected_sequence,
    freeze_manifest,
    refuse_p3f_evaluation,
    validate_phase3o_freeze,
)
from bite_bench.xfer1_corpus import (
    ANNOTATIONS_PATH,
    CORPUS_DIR,
    FORMATS,
    N_CANONICAL,
    forbidden_hits,
)
from bite_ingestion.adapters.bite_xfer1 import unitize

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase3o-xfer1-freeze.json"
SCHEMA = ROOT / "spec" / "phase3o-xfer1-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase3o.py"
CORPUS_PY = ROOT / "src" / "bite_bench" / "xfer1_corpus.py"
PHASE3N = ROOT / "artifacts" / "phase3n" / "conditional-routing-first-open.json"


def test_committed_freeze_matches_manifest() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_phase3o_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["n_surfaces"] == N_SURFACES
    assert committed["no_phase3m_import"] is True
    assert committed["p3f_evaluation_holdout_used"] is False
    assert committed["cut_forbidden"] is True
    anns = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))["annotations"]
    assert len(anns) == N_CANONICAL
    for row in anns.values():
        assert "expected_sequence" not in row
        assert set(row) == {
            "required_evidence_ids",
            "intended_dispersion",
            "has_exact_duplicate",
            "has_quarantinable_anomaly",
            "has_explicit_join_cluster",
        }


def test_rendered_corpus_has_104_source_exact_units() -> None:
    rendered = list((CORPUS_DIR / "rendered").glob("*"))
    assert len(rendered) == N_SURFACES
    for path in rendered:
        stem, _ext = path.name.rsplit(".", 1)
        cid, fmt = stem.split(".", 1)
        body = path.read_text(encoding="utf-8")
        assert forbidden_hits(body) == []
        units = unitize(body, case_id=cid, fmt=fmt)
        assert units
        for unit in units:
            span = unit["span"]
            assert body[int(span["start"]) : int(span["end"])] == unit["text"]


def test_o0_does_not_run_policy_or_import_phase3m() -> None:
    for path in (GEN_PY, CORPUS_PY):
        blob = path.read_text(encoding="utf-8")
        assert "bite_bench.phase3m" not in blob
        assert "conditional_texture_policy_v1" not in blob
        assert "class RulePolicy" not in blob
        assert "from bite_ingestion.policies" not in blob
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
    assert json.loads(PHASE3N.read_text(encoding="utf-8"))["verdict"] == (
        "PHASE3N_CONDITIONAL_ROUTING_HOLDOUT_CONFIRMED"
    )
    anns = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))["annotations"]
    high = [row for row in anns.values() if row["intended_dispersion"] == "high"]
    assert any(derive_expected_sequence(row) == [] for row in anns.values())
    assert any(derive_expected_sequence(row) for row in high)
    assert FORMATS == (
        "key_value",
        "compact_json",
        "pretty_json",
        "mixed_order_json",
    )
