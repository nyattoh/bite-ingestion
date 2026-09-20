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
    DISCOVERY_QUERIES,
    FAMILIES,
    FORBIDDEN_QUERY_TERMS,
    N_PRIMARY,
    PREMISE,
    PROTOCOL_FROZEN,
    freeze_manifest,
    validate_phase4h_freeze,
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
