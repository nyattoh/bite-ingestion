"""Phase 4A REALSTRUCT-1 protocol freeze and corpus tests.

Does not import or run BITE sensors/policies. Does not open p3f.
Does not change Phase 3T/3S/3Q.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase4a import (
    N_DOCUMENTS,
    PHASE3Q_VERDICT,
    PHASE3S_VERDICT,
    PHASE3T_VERDICT,
    PREMISE,
    PROTOCOL_FROZEN,
    EvaluationSealError,
    freeze_manifest,
    refuse_p3f_evaluation,
    validate_phase4a_freeze,
)
from bite_bench.realstruct1 import (
    A0_FREEZE_BLOB,
    ANNOTATION_PATH,
    LICENSE_PATH,
    MANIFEST_PATH,
    PROTOCOL_COMMIT_SHA,
    RESULT_PATH,
    SOURCES,
    SPLIT_PATH,
    VERDICT_FROZEN,
    annotate_bytes,
    sha256_bytes,
    validate_phase4a_corpus,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase4a-realstruct1-freeze.json"
SCHEMA = ROOT / "spec" / "phase4a-realstruct1-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase4a.py"
ACQ_PY = ROOT / "src" / "bite_bench" / "realstruct1.py"
PHASE3T = ROOT / "artifacts" / "phase3t" / "exact-reference.json"
PHASE3S = ROOT / "artifacts" / "phase3s" / "reference-specificity.json"
PHASE3Q = ROOT / "artifacts" / "phase3q" / "xfer2-transfer.json"
RESULT_SCHEMA = ROOT / "spec" / "phase4a-realstruct1.schema.json"


def _import_lines(path: Path) -> str:
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            lines.append(stripped)
    return "\n".join(lines)


def test_committed_freeze_matches_manifest() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_phase4a_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["premise"] == PREMISE
    assert committed["n_documents"] == N_DOCUMENTS
    assert committed["no_bite_execution"] is True
    assert committed["no_source_rewrite_after_bite"] is True
    assert committed["p3f_evaluation_holdout_used"] is False
    assert committed["no_xfer3"] is True
    assert "sources" not in committed
    assert committed["split"]["n_development"] == 3
    assert committed["split"]["n_evaluation"] == 9
    blob = subprocess.check_output(["git", "hash-object", str(FREEZE)], text=True).strip()
    assert blob == A0_FREEZE_BLOB
    assert PROTOCOL_COMMIT_SHA == "3e5d2d7c9cd0a07346e90401496df042aa956bf7"


def test_a0_does_not_import_bite_or_open_p3f() -> None:
    blob = GEN_PY.read_text(encoding="utf-8")
    assert "bite_ingestion.policies" not in blob
    assert "bite_ingestion.profilers" not in blob
    assert "dependency_dispersion_v3" not in blob
    assert "conditional_texture_policy_v4" not in blob
    assert "class RulePolicy" not in blob
    imports = _import_lines(ACQ_PY)
    assert "bite_ingestion.policies" not in imports
    assert "bite_ingestion.profilers" not in imports
    assert json.loads(PHASE3T.read_text(encoding="utf-8"))["verdict"] == PHASE3T_VERDICT
    assert json.loads(PHASE3S.read_text(encoding="utf-8"))["verdict"] == PHASE3S_VERDICT
    assert json.loads(PHASE3Q.read_text(encoding="utf-8"))["verdict"] == PHASE3Q_VERDICT
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")


def test_annotation_grammar_from_raw_syntax_only() -> None:
    gold = annotate_bytes(b"A=1\nB=${A}\nC=$A\nD=${A:-x}\nE=${B}\nF=${missing}\n")
    names = [edge["name"] for edge in gold["explicit_reference_edges"]]
    assert names == ["A", "B"]
    assert gold["n_assignments"] == 6
    sectioned = annotate_bytes(b"[colors]\nbackground=1\nfoo=${colors.background}\n")
    assert sectioned["explicit_reference_edges"] == []
    mixed = annotate_bytes(b"# K=1\n\nK=1\n")
    assert [row["kind"] for row in mixed["records"]] == [
        "unsupported",
        "unsupported",
        "assignment",
    ]
    assert "non_reference" not in json.dumps(gold)


def test_realstruct1_corpus_frozen() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert validate_phase4a_corpus(result) == []
    jsonschema.validate(result, json.loads(RESULT_SCHEMA.read_text(encoding="utf-8")))
    assert result["verdict"] == VERDICT_FROZEN
    assert result["errors"] == []
    assert result["n_documents"] == 12
    assert result["n_development"] == 3
    assert result["n_evaluation"] == 9
    assert result["no_bite_execution"] is True
    assert result["p3f_evaluation_holdout_used"] is False
    corpus = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    split = json.loads(SPLIT_PATH.read_text(encoding="utf-8"))
    licenses = json.loads(LICENSE_PATH.read_text(encoding="utf-8"))
    annotations = json.loads(ANNOTATION_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(
        corpus, json.loads((ROOT / "spec" / "phase4a-realstruct1-corpus.schema.json").read_text())
    )
    jsonschema.validate(
        split, json.loads((ROOT / "spec" / "phase4a-realstruct1-split.schema.json").read_text())
    )
    jsonschema.validate(
        licenses,
        json.loads((ROOT / "spec" / "phase4a-realstruct1-licenses.schema.json").read_text()),
    )
    jsonschema.validate(
        annotations,
        json.loads((ROOT / "spec" / "phase4a-realstruct1-annotations.schema.json").read_text()),
    )
    assert len(SOURCES) == 12
    assert len({(spec.owner, spec.repo) for spec in SOURCES}) == 12
    by_id = {spec.source_id: spec for spec in SOURCES}
    for row in corpus["sources"]:
        spec = by_id[row["source_id"]]
        raw = (ROOT / row["raw_file"]).read_bytes()
        assert sha256_bytes(raw) == row["sha256"]
        assert spec.spdx == row["spdx"]
    assert split["no_swap_after_split"] is True
    assert len(split["development"]) == 3
    assert len(split["evaluation"]) == 9
    assert annotations["missing_annotation_is_not_non_reference"] is True
    assert "expected BITE route" not in json.dumps(
        [doc.get("records") for doc in annotations["documents"]]
    )
    for document in licenses["documents"]:
        assert document["redistributable"] is True
        assert document["spdx"] in {
            "MIT",
            "Apache-2.0",
            "BSD-2-Clause",
            "BSD-3-Clause",
            "ISC",
            "0BSD",
            "Unlicense",
            "CC0-1.0",
        }
