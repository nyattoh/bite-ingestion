"""Phase 4B B0 scorer addendum tests.

Does not run BITE. Does not open eval 9 or p3f. Does not rewrite Phase 4A.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4b import (
    DEV_SOURCE_IDS,
    EVAL_SOURCE_IDS,
    FREEZE_PATH,
    LOCKED_PHASE4A_BLOBS,
    PREMISE,
    PROTOCOL_FROZEN,
    V2_PATH,
    freeze_manifest,
    validate_phase4b_freeze,
)
from bite_bench.realstruct1_v2 import annotate_bytes_v2

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "spec" / "phase4b-scorer-addendum-freeze.schema.json"
V2_SCHEMA = ROOT / "spec" / "phase4a-realstruct1-annotations-v2.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase4b.py"
V2_PY = ROOT / "src" / "bite_bench" / "realstruct1_v2.py"
PHASE4A = ROOT / "artifacts" / "phase4a" / "realstruct-1.json"


def _import_lines(path: Path) -> str:
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            lines.append(stripped)
    return "\n".join(lines)


def _git_blob(rel: str) -> str:
    return subprocess.check_output(["git", "hash-object", rel], cwd=ROOT, text=True).strip()


def test_b0_freeze_matches_generator() -> None:
    committed = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_phase4b_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["premise"] == PREMISE
    assert committed["dev_source_ids"] == list(DEV_SOURCE_IDS)
    assert committed["eval_source_ids"] == list(EVAL_SOURCE_IDS)
    assert committed["no_eval_execution"] is True
    assert committed["no_bite_execution_in_b0"] is True
    assert json.loads(PHASE4A.read_text(encoding="utf-8"))["verdict"] == PREMISE


def test_b0_does_not_import_bite_or_rewrite_phase4a() -> None:
    for path in (GEN_PY, V2_PY):
        imports = _import_lines(path)
        assert "bite_ingestion.policies" not in imports
        assert "bite_ingestion.profilers" not in imports
        assert "bite_eval" not in imports
    for rel, expected in LOCKED_PHASE4A_BLOBS.items():
        assert _git_blob(rel) == expected
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")


def test_overlay_v2_two_pass_and_exact_duplicates() -> None:
    forward = annotate_bytes_v2(b"B=${A}\nA=1\n")
    names = [edge["name"] for edge in forward["explicit_reference_edges"]]
    assert names == ["A"]
    assert forward["explicit_reference_edges"][0]["dest_lines"] == [2]
    gold = annotate_bytes_v2(b"A=1\nB=${A}\nC=$A\nD=${A:-x}\nE=${missing}\n")
    assert [edge["name"] for edge in gold["explicit_reference_edges"]] == ["A"]
    assert "non_reference" not in json.dumps(gold)
    dups = annotate_bytes_v2(b"A=1\nA=1\nA=2\n")
    assert dups["n_exact_duplicate_groups"] == 1
    assert dups["exact_duplicate_groups"][0]["lines"] == [1, 2]
    assert len(dups["repeated_key_groups"]) == 1
    overlay = json.loads(V2_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(overlay, json.loads(V2_SCHEMA.read_text(encoding="utf-8")))
    assert overlay["key_index"] == "two-pass document-wide"
    assert len(overlay["documents"]) == 12
    blob = json.dumps(overlay)
    assert '"non_reference"' not in blob
    assert "expected BITE route" not in json.dumps(
        [doc.get("records") for doc in overlay["documents"]]
    )
