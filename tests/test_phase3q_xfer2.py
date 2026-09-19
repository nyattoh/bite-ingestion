"""Phase 3Q BITE-XFER-2 freeze (Q0) tests.

Does not run policy. Does not import XFER-1/p3p/p3m generators. Does not open p3f.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase3q import (
    ANNOTATION_KEYS,
    LOCKED_BLOBS,
    N_SURFACES,
    PHASE3O_VERDICT,
    PREMISE,
    PROTOCOL_FROZEN,
    EvaluationSealError,
    derive_expected_sequence,
    freeze_manifest,
    refuse_p3f_evaluation,
    validate_phase3q_freeze,
)
from bite_bench.xfer2_corpus import (
    ANNOTATIONS_PATH,
    CORPUS_DIR,
    FORMATS,
    N_CANONICAL,
    forbidden_hits,
)
from bite_ingestion.adapters.bite_xfer2 import packet_from_document, unitize

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase3q-xfer2-freeze.json"
SCHEMA = ROOT / "spec" / "phase3q-xfer2-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase3q.py"
CORPUS_PY = ROOT / "src" / "bite_bench" / "xfer2_corpus.py"
PHASE3O = ROOT / "artifacts" / "phase3o" / "xfer1-transfer.json"
PHASE3P = ROOT / "artifacts" / "phase3p" / "record-alignment.json"


def test_committed_freeze_matches_manifest() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_phase3q_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["n_surfaces"] == N_SURFACES
    assert committed["premise"] == PREMISE
    assert committed["no_xfer1_generator_import"] is True
    assert committed["p3f_evaluation_holdout_used"] is False
    assert committed["cut_forbidden"] is True
    assert committed["locked_blobs"] == LOCKED_BLOBS
    anns = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))["annotations"]
    assert len(anns) == N_CANONICAL
    for row in anns.values():
        assert "expected_sequence" not in row
        assert set(row) == set(ANNOTATION_KEYS)


def test_rendered_corpus_has_112_source_exact_units() -> None:
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


def test_q0_does_not_run_policy_or_import_prior_generators() -> None:
    for path in (GEN_PY, CORPUS_PY):
        blob = path.read_text(encoding="utf-8")
        assert "bite_bench.xfer1_corpus" not in blob
        assert "bite_bench.phase3m" not in blob
        assert "bite_bench.phase3p" not in blob
        assert "from bite_ingestion.policies" not in blob
        assert "class RulePolicy" not in blob
        assert "ConditionalTexturePolicy" not in blob
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
    assert json.loads(PHASE3O.read_text(encoding="utf-8"))["verdict"] == PHASE3O_VERDICT
    assert json.loads(PHASE3P.read_text(encoding="utf-8"))["verdict"] == PREMISE
    anns = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))["annotations"]
    high = [row for row in anns.values() if row["intended_dispersion"] == "high"]
    assert any(derive_expected_sequence(row) == [] for row in anns.values())
    assert any(derive_expected_sequence(row) for row in high)
    assert FORMATS == (
        "key_value",
        "compact_json",
        "pretty_json",
        "reversed_order_json",
    )


def test_q0_packet_is_gold_free() -> None:
    path = CORPUS_DIR / "rendered" / "xfer2-q001.key_value.txt"
    packet = packet_from_document(
        path.read_text(encoding="utf-8"), case_id="xfer2-q001", fmt="key_value"
    )
    assert "gold_unit_ids" not in packet
    assert "texture" not in packet
    assert "expected_sequence" not in packet
    assert "duplicate_groups" not in packet
