"""Phase 4H H0 REALSTRUCT-2 protocol freeze tests.

Does not discover candidates. Does not acquire sources. Does not open p3f.
Does not execute comparison arms or tokenizers. Does not rewrite Phase 4F/4G.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4h import (
    CANDIDATE_POOL_PER_FAMILY,
    DISCOVERY_QUERIES,
    FAMILIES,
    FORBIDDEN_QUERY_TERMS,
    N_PRIMARY,
    PREMISE,
    PROTOCOL_FROZEN,
    freeze_manifest,
    validate_phase4h_freeze,
)
from bite_bench.realstruct2 import (
    ANNOTATION_PATH,
    MANIFEST_PATH,
    POOL_PATH,
    RESULT_PATH,
    annotate_source,
    validate_candidate_pool,
    validate_phase4h_corpus,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase4h-realstruct2-freeze.json"
SCHEMA = ROOT / "spec" / "phase4h-realstruct2-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase4h.py"


def _import_lines(path: Path) -> str:
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            lines.append(stripped)
    return "\n".join(lines)


def test_h0_freeze_matches_generator() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_phase4h_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["premise"] == PREMISE
    assert committed["n_primary"] == N_PRIMARY
    assert committed["families"] == list(FAMILIES)
    assert committed["no_arm_execution"] is True
    assert committed["no_tokenizer_execution"] is True
    assert committed["discovery"]["ignore_code_search_snippets"] is True
    assert committed["annotation_grammar"]["two_pass_whole_document_key_index"] is True
    joined = " ".join(term for items in DISCOVERY_QUERIES.values() for term in items)
    for term in FORBIDDEN_QUERY_TERMS:
        assert term not in joined
    assert "sources" not in committed
    assert committed["p3f_evaluation_holdout_used"] is False


def test_h0_does_not_discover_or_open_p3f() -> None:
    imports = _import_lines(GEN_PY)
    assert "realstruct2" not in imports
    assert "reference_tokenizer" not in imports
    assert "length_pi_v1" not in imports
    assert "recovery_bundle" not in imports
    assert "visibility_metrics_v2" not in imports
    assert "bite_ingestion.policies" not in imports
    assert "bite_ingestion.profilers" not in imports
    text = GEN_PY.read_text(encoding="utf-8")
    assert "gh api" not in text
    assert "/search/code" in json.dumps(freeze_manifest()["discovery"])
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")


def test_h1_candidate_pool_frozen_without_file_contents() -> None:
    pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))
    assert validate_candidate_pool(pool) == []
    jsonschema.validate(
        pool,
        json.loads((ROOT / "spec" / "phase4h-candidate-pool.schema.json").read_text(encoding="utf-8")),
    )
    assert pool["file_contents_opened"] is False
    assert pool["no_arm_execution"] is True
    assert pool["no_tokenizer_execution"] is True
    for family in FAMILIES:
        rows = pool["families"][family]
        assert 1 <= len(rows) <= CANDIDATE_POOL_PER_FAMILY
        for row in rows:
            assert "raw" not in row
            assert "text" not in row
            assert "content" not in row
            assert row["head_commit_sha"]
            assert row["selection_key"]


def test_annotation_two_pass_and_negative_gold() -> None:
    gold = annotate_source(b"B=${A}\nA=1\nC=${A:-x}\nD=$A\nE=${missing}\n")
    identities = [tuple(edge["gold_identity"]) for edge in gold["explicit_reference_edges"]]
    assert identities == [(1, "A", 2)]
    assert gold["n_assignments"] == 5
    sectioned = annotate_source(b"[colors]\nbackground=1\nfoo=${colors.background}\n")
    assert sectioned["explicit_reference_edges"] == []
    mixed = annotate_source(b"# K=1\n\nK=1\n")
    assert [row["kind"] for row in mixed["records"]] == [
        "unsupported",
        "unsupported",
        "assignment",
    ]
    dups = annotate_source(b"K=1\nK=1\nK=2\n")
    assert dups["exact_duplicate_groups"] == [
        {"assignment_key": "K", "assignment_value": "1", "lines": [1, 2]}
    ]
    assert dups["repeated_key_different_value"] == [{"assignment_key": "K", "n_values": 2}]


def test_h2_corpus_partial_or_frozen() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert validate_phase4h_corpus(result) == []
    jsonschema.validate(
        result,
        json.loads((ROOT / "spec" / "phase4h-realstruct2.schema.json").read_text(encoding="utf-8")),
    )
    assert result["verdict"] in {
        "PHASE4H_REALSTRUCT2_FROZEN",
        "PHASE4H_REALSTRUCT2_PARTIAL",
        "PHASE4H_REALSTRUCT2_BLOCKED",
    }
    assert result["no_arm_execution"] is True
    assert result["no_tokenizer_execution"] is True
    assert result["p3f_evaluation_holdout_used"] is False
    corpus = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    annotations = json.loads(ANNOTATION_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(
        corpus,
        json.loads((ROOT / "spec" / "phase4h-realstruct2-corpus.schema.json").read_text()),
    )
    jsonschema.validate(
        annotations,
        json.loads((ROOT / "spec" / "phase4h-realstruct2-annotations.schema.json").read_text()),
    )
    dumped = json.dumps([doc.get("records") for doc in annotations["documents"]])
    assert "expected route" not in dumped
    assert "expected operator sequence" not in dumped
    assert "expected BITE edge" not in dumped
    assert "expected arm winner" not in dumped
    imports = _import_lines(ROOT / "src" / "bite_bench" / "realstruct2.py")
    assert "reference_tokenizer" not in imports
    assert "length_pi_v1" not in imports
    assert "recovery_bundle" not in imports
    assert "visibility_metrics_v2" not in imports
    assert "bite_ingestion.policies" not in imports
    assert "bite_ingestion.profilers" not in imports
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
    if result["verdict"] == "PHASE4H_REALSTRUCT2_FROZEN":
        assert result["n_primary"] == 18
        assert result["errors"] == []
    else:
        assert result["errors"]
