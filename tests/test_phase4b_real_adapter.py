"""Phase 4B B0 freeze and development-adapter tests.

Does not open eval 9 or p3f. Does not rewrite Phase 4A or frozen BITE files.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4b import (
    B0_COMMIT_SHA,
    B0_FREEZE_BLOB,
    DEV_SOURCE_IDS,
    EVAL_SOURCE_IDS,
    FREEZE_PATH,
    LOCKED_BITE_BLOBS,
    LOCKED_PHASE4A_BLOBS,
    OVERLAY_V2_BLOB,
    PREMISE,
    PROTOCOL_FROZEN,
    V2_PATH,
    freeze_manifest,
    validate_phase4b_freeze,
)
from bite_bench.realstruct1 import SOURCES, load_raw
from bite_bench.realstruct1_v2 import annotate_bytes_v2
from bite_eval.phase4b_eval import (
    ADAPTER_PATH,
    LOCK_PATH,
    RESULT_PATH,
    EvalSealError,
    refuse_eval_source,
    validate_phase4b_result,
)
from bite_ingestion.adapters.realstruct1_adapter_v1 import (
    adapt,
    source_units_from_bytes,
)

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
    assert _git_blob("benchmarks/spec/phase4b-scorer-addendum-freeze.json") == B0_FREEZE_BLOB
    assert B0_COMMIT_SHA == "70fa0ce678611db122a74a5fbe730fccf5bf12fb"
    assert _git_blob("corpora/realstruct-1/annotations-v2.json") == OVERLAY_V2_BLOB


def test_b0_does_not_import_bite_or_rewrite_phase4a() -> None:
    for path in (GEN_PY, V2_PY):
        imports = _import_lines(path)
        assert "bite_ingestion.policies" not in imports
        assert "bite_ingestion.profilers" not in imports
        assert "bite_eval" not in imports
    for rel, expected in {**LOCKED_PHASE4A_BLOBS, **LOCKED_BITE_BLOBS}.items():
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


def test_adapter_reconstructs_raw_bytes_without_opening_eval() -> None:
    for spec in SOURCES:
        raw = load_raw(spec)
        source = source_units_from_bytes(raw, source_id=spec.source_id)
        joined = "".join(str(unit["text"]) for unit in source["units"])
        assert joined.encode(str(source["encoding"])) == raw
        assert source["n_assignments"] + source["n_unsupported"] == source["n_source_units"]
    raw = b"# c\nA=1\n\nB=2\n"
    adapted = adapt(raw, source_id="rs1-dotenv-linkding")
    packet = adapted["routing_packet"]
    assert "document" not in packet
    assert [unit["text"] for unit in packet["units"]] == ["A=1", "B=2"]
    assert adapted["n_unsupported_passthrough"] == 2
    with pytest.raises(EvalSealError, match="evaluation sealed"):
        refuse_eval_source(EVAL_SOURCE_IDS[0])


def test_dev_adapter_ready_eval_sealed() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert validate_phase4b_result(result) == []
    jsonschema.validate(
        result,
        json.loads((ROOT / "spec" / "phase4b-real-adapter.schema.json").read_text(encoding="utf-8")),
    )
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(
        lock,
        json.loads((ROOT / "spec" / "phase4b-evaluation-lock.schema.json").read_text(encoding="utf-8")),
    )
    assert result["verdict"] == "PHASE4B_REAL_ADAPTER_READY"
    assert result["n_ok"] == 3
    assert result["eval_unopened"] is True
    assert result["p3f_evaluation_holdout_used"] is False
    assert result["errors"] == []
    assert lock["eval_unopened"] is True
    assert lock["adapter_blob"] == _git_blob(ADAPTER_PATH)
    routing_src = (ROOT / "src" / "bite_eval" / "phase4b_eval.py").read_text(encoding="utf-8")
    for eval_id in EVAL_SOURCE_IDS:
        assert f'adapt(raw, source_id="{eval_id}")' not in routing_src

