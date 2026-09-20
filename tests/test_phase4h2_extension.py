"""Phase 4H2 H3 acquisition-extension freeze tests.

Does not discover new candidates. Does not open p3f. Does not rewrite Phase 4H.
Does not execute comparison arms or tokenizers.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4h import DISCOVERY_QUERIES, FORBIDDEN_QUERY_TERMS
from bite_bench.phase4h2 import (
    H2_RESULT_BLOB,
    PREMISE,
    PROTOCOL_FROZEN,
    REMAINING_PRIMARY,
    WAVE1_PRIMARY_IDS,
    freeze_manifest,
    validate_phase4h2_freeze,
)
from bite_bench.realstruct2_ext import (
    EXT_POOL_PATH,
    RESULT_PATH,
    WAVE_PROVENANCE,
    validate_augmented,
    validate_extension_pool,
)

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase4h2-acquisition-extension-freeze.json"
SCHEMA = ROOT / "spec" / "phase4h2-acquisition-extension-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase4h2.py"


def _import_lines(path: Path) -> str:
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            lines.append(stripped)
    return "\n".join(lines)


def test_h3_freeze_matches_generator() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_phase4h2_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["premise"] == PREMISE
    assert committed["wave1_primary_ids"] == list(WAVE1_PRIMARY_IDS)
    assert committed["remaining_primary"] == dict(REMAINING_PRIMARY)
    assert committed["discovery"]["queries"] == {
        family: list(items) for family, items in DISCOVERY_QUERIES.items()
    }
    assert committed["no_license_inference"] is True
    assert committed["no_h1_pool_rewrite"] is True
    joined = " ".join(term for items in DISCOVERY_QUERIES.values() for term in items)
    for term in FORBIDDEN_QUERY_TERMS:
        assert term not in joined
    assert "sources" not in committed


def test_h3_does_not_discover_or_rewrite_phase4h() -> None:
    imports = _import_lines(GEN_PY)
    assert "realstruct2_ext" not in imports
    assert "reference_tokenizer" not in imports
    assert "length_pi_v1" not in imports
    text = GEN_PY.read_text(encoding="utf-8")
    assert "gh api" not in text
    phase4h = json.loads(
        (ROOT / "artifacts" / "phase4h" / "realstruct-2.json").read_text(encoding="utf-8")
    )
    assert phase4h["verdict"] == PREMISE
    assert phase4h["n_primary"] == 10
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
    assert H2_RESULT_BLOB == "666eed454c3dba6dd2cfa2a73e5989004380f177"


def test_h4_extension_pool_frozen_without_file_contents() -> None:
    pool = json.loads(EXT_POOL_PATH.read_text(encoding="utf-8"))
    assert validate_extension_pool(pool) == []
    jsonschema.validate(
        pool,
        json.loads((ROOT / "spec" / "phase4h2-extension-pool.schema.json").read_text(encoding="utf-8")),
    )
    assert pool["file_contents_opened"] is False
    assert pool["exclude_h1_repo_path"] is True
    for rows in pool["families"].values():
        assert 1 <= len(rows) <= 180
        for row in rows:
            assert "raw" not in row
            assert "content" not in row
            assert row["selection_key"]


def test_h5_augmented_corpus_preserves_wave1() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert validate_augmented(result) == []
    jsonschema.validate(
        result,
        json.loads(
            (ROOT / "spec" / "phase4h2-realstruct2-augmented.schema.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    assert result["verdict"] == "PHASE4H2_REALSTRUCT2_AUGMENTED_FROZEN"
    assert result["n_primary"] == 18
    assert result["errors"] == []
    assert result["no_arm_execution"] is True
    assert result["no_license_inference"] is True
    assert result["p3f_evaluation_holdout_used"] is False
    prov = json.loads(WAVE_PROVENANCE.read_text(encoding="utf-8"))
    assert prov["wave1_source_ids"] == list(WAVE1_PRIMARY_IDS)
    assert len(prov["final_primary_source_ids"]) == 18
    assert set(WAVE1_PRIMARY_IDS).issubset(set(prov["final_primary_source_ids"]))
    hist = json.loads(
        (ROOT / "artifacts" / "phase4h" / "realstruct-2.json").read_text(encoding="utf-8")
    )
    assert hist["verdict"] == PREMISE
    assert hist["n_primary"] == 10
    imports = _import_lines(ROOT / "src" / "bite_bench" / "realstruct2_ext.py")
    assert "reference_tokenizer" not in imports
    assert "length_pi_v1" not in imports
    assert "recovery_bundle" not in imports
    assert "bite_ingestion.policies" not in imports
