"""Phase 4C C0 holdout protocol and reachability-equivalence tests.

Does not open eval 9 or p3f. Does not rewrite Phase 4A/4B or frozen BITE files.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4b import DEV_SOURCE_IDS, EVAL_SOURCE_IDS, LOCKED_T_HIGH
from bite_bench.phase4c import (
    ADAPTER_BLOB,
    EQ_PATH,
    FREEZE_PATH,
    OVERLAY_V2_BLOB,
    PHASE4B_EVAL_HARNESS_BLOB,
    PHASE4B_HEAD,
    PHASE4B_LOCK_BLOB,
    PREMISE,
    PROTOCOL_FROZEN,
    freeze_manifest,
    validate_phase4c_freeze,
)
from bite_bench.realstruct1 import RAW_DIR
from bite_eval.chain_span_reachable import (
    all_directed_graphs,
    chain_span_reachable,
    chain_span_simple_path,
)
from bite_eval.phase4c_eval import RESULT_PATH, validate_phase4c_result
from bite_ingestion.adapters.realstruct1_adapter_v1 import adapt
from bite_ingestion.profilers import dependency_dispersion_v3 as v3mod
from bite_ingestion.profilers.dependency_dispersion_v3 import measure as measure_v3

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "spec" / "phase4c-holdout-first-open-freeze.schema.json"
EQ_SCHEMA = ROOT / "spec" / "phase4c-reachability-equivalence.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase4c.py"


def _import_lines(path: Path) -> str:
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            lines.append(stripped)
    return "\n".join(lines)


def _git_blob(rel: str) -> str:
    return subprocess.check_output(["git", "hash-object", rel], cwd=ROOT, text=True).strip()


def _gate(report: object) -> bool:
    n_ref = float(report.features["n_reference_edges"])  # type: ignore[attr-defined]
    mean = float(report.features["mean_reference_edge_distance"])  # type: ignore[attr-defined]
    return (not report.fail_closed) and n_ref > 0.0 and mean >= float(LOCKED_T_HIGH)  # type: ignore[attr-defined]


def test_c0_freeze_matches_generator() -> None:
    committed = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_phase4c_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["premise"] == PREMISE
    assert committed["eval_source_ids"] == list(EVAL_SOURCE_IDS)
    assert committed["no_eval_execution_in_c0"] is True
    assert committed["phase4b_head_sha"] == PHASE4B_HEAD
    assert committed["adapter_blob"] == ADAPTER_BLOB
    assert committed["overlay_v2_blob"] == OVERLAY_V2_BLOB
    assert committed["phase4b_evaluation_lock_blob"] == PHASE4B_LOCK_BLOB
    assert committed["phase4b_eval_harness_blob"] == PHASE4B_EVAL_HARNESS_BLOB
    assert _git_blob("src/bite_eval/phase4b_eval.py") == PHASE4B_EVAL_HARNESS_BLOB


def test_c0_does_not_open_eval_or_p3f() -> None:
    imports = _import_lines(GEN_PY)
    assert "bite_eval.phase4c_eval" not in imports
    assert "bite_ingestion.policies" not in imports
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")


def test_reachability_matches_original_chain_span_n_le_4() -> None:
    frozen = (
        ROOT / "src" / "bite_ingestion" / "profilers" / "dependency_dispersion.py"
    ).read_text(encoding="utf-8")
    assert "best = max(best, node - start)" in frozen
    for n in range(5):
        for graph in all_directed_graphs(n):
            assert chain_span_simple_path(n, graph) == chain_span_reachable(n, graph)
    eq = json.loads(EQ_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(eq, json.loads(EQ_SCHEMA.read_text(encoding="utf-8")))
    assert eq["exact"] is True
    assert eq["n_mismatches"] == 0
    assert eq["n_max"] == 4


def test_dev3_gate_features_match_under_chain_span_replacement() -> None:
    saved = v3mod._chain_span
    try:
        for source_id in DEV_SOURCE_IDS:
            raw = (RAW_DIR / source_id).read_bytes()
            adapted = adapt(raw, source_id=source_id)
            payload = "\n".join(str(unit["text"]) for unit in adapted["routing_packet"]["units"])
            packet = {"payload": payload, "text": payload}
            v3mod._chain_span = chain_span_reachable  # type: ignore[misc]
            with_rep = measure_v3(packet)
            v3mod._chain_span = lambda *_args: 0  # type: ignore[misc]
            dummy = measure_v3(packet)
            assert with_rep.features["n_reference_edges"] == dummy.features["n_reference_edges"]
            assert (
                with_rep.features["mean_reference_edge_distance"]
                == dummy.features["mean_reference_edge_distance"]
            )
            assert _gate(with_rep) == _gate(dummy)
    finally:
        v3mod._chain_span = saved


def test_c1_holdout_measured_eval_nine() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert validate_phase4c_result(result) == []
    jsonschema.validate(
        result,
        json.loads((ROOT / "spec" / "phase4c-real-holdout.schema.json").read_text(encoding="utf-8")),
    )
    assert result["verdict"] == "PHASE4C_REAL_HOLDOUT_MEASURED"
    assert result["n_ok"] == 9
    assert result["n_eval"] == 9
    assert result["eval_opened"] is True
    assert result["p3f_evaluation_holdout_used"] is False
    assert result["errors"] == []
    assert [row["source_id"] for row in result["rows"]] == list(EVAL_SOURCE_IDS)
    assert "rs1-dotenv-linkding" not in [row["source_id"] for row in result["rows"]]
