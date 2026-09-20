"""Phase 4I I0 first-open execution freeze tests.

Does not execute REALSTRUCT-2 tokenizer or arms. Does not open p3f.
Does not retune BITE. Does not rewrite Phase 4H/4H2 artifacts.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4h import freeze_manifest as phase4h_freeze
from bite_bench.phase4i import (
    AUGMENTED_MANIFEST_BLOB,
    N_PRIMARY,
    PHASE4H2_RESULT_BLOB,
    PREMISE,
    PRIMARY_IDS,
    PROTOCOL_FROZEN,
    freeze_manifest,
    planned_preflight_cases,
    validate_phase4i_freeze,
)
from bite_bench.realstruct1 import sha256_bytes
from bite_eval.phase4i_eval import (
    I0_FREEZE_BLOB,
    RESULT_PATH,
    _document_row,
    i0_commit_sha,
    paired_summary,
    validate_phase4i_result,
)
from bite_ingestion.policies.conditional_texture_policy_v5 import ConditionalTexturePolicyV5

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase4i-first-open-freeze.json"
SCHEMA = ROOT / "spec" / "phase4i-first-open-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase4i.py"
RS2_RAW = ROOT / "corpora" / "realstruct-2" / "raw"


class _CharTok:
    def payload_tokens(self, text: str) -> int:
        return len(text)

    def prefix_char_end(self, text: str, budget: int) -> int:
        if budget <= 0:
            return 0
        return min(int(budget), len(text))


def _import_lines(path: Path) -> str:
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            lines.append(stripped)
    return "\n".join(lines)


def test_i0_freeze_matches_generator() -> None:
    committed = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert committed == freeze_manifest()
    assert validate_phase4i_freeze(committed) == []
    jsonschema.validate(committed, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert committed["verdict"] == PROTOCOL_FROZEN
    assert committed["premise"] == PREMISE
    assert committed["primary_ids"] == list(PRIMARY_IDS)
    assert committed["n_primary"] == N_PRIMARY
    assert committed["no_realstruct2_tokenizer_before_i0"] is True
    assert committed["no_realstruct2_arm_before_i0"] is True
    assert committed["no_winner_score"] is True
    assert committed["no_wave1_vs_wave2_outcome"] is True
    assert committed["do_not_use_historical_10_document_manifest"] is True
    assert committed["analysis_contract"] == phase4h_freeze()["future_phase4i_analysis"]
    assert committed["p3f_evaluation_holdout_used"] is False
    assert len(committed["planned_preflight_cases"]) == 5


def test_i0_does_not_execute_rs2_or_open_p3f() -> None:
    imports = _import_lines(GEN_PY)
    assert "phase4i_eval" not in imports
    assert "reference_tokenizer" not in imports
    assert "length_pi_v1" not in imports
    assert "recovery_bundle" not in imports
    assert "visibility_metrics_v2" not in imports
    assert "conditional_texture_policy_v5" not in imports
    text = GEN_PY.read_text(encoding="utf-8")
    assert "run_first_open" not in text
    historical = json.loads(
        (ROOT / "corpora" / "realstruct-2" / "manifest.json").read_text(encoding="utf-8")
    )
    assert historical["n_primary"] == 10
    phase4h2 = json.loads(
        (ROOT / "artifacts" / "phase4h2" / "realstruct-2-augmented.json").read_text(
            encoding="utf-8"
        )
    )
    assert phase4h2["verdict"] == PREMISE
    assert phase4h2["n_primary"] == 18
    with pytest.raises(EvaluationSealError, match="p3f evaluation sealed"):
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")


def test_preflight_fixtures_four_arm_offline() -> None:
    policy = ConditionalTexturePolicyV5()
    tokenizer = _CharTok()
    for spec in planned_preflight_cases():
        raw = "".join(f"{key}={value}\n" for key, value in spec["records"]).encode("utf-8")
        row = _document_row(
            source_id=str(spec["case_id"]),
            raw=raw,
            gold={
                "source_id": spec["case_id"],
                "explicit_reference_edges": list(spec.get("gold_edges") or []),
            },
            policy=policy,
            tokenizer=tokenizer,
            family=str(spec["family"]),
            wave=None,
            expected_sha=sha256_bytes(raw),
        )
        assert len(row["arms"]) == 4
        assert [arm["arm"] for arm in row["arms"]] == [
            "raw_full",
            "adapter_only",
            "length_pi_v1",
            "BITE_v5",
        ]
        assert row["reconstruct_ok"] is True
        assert row["bite_conservation_ok"] is True
        assert row["planner_integrity"] is True
        bite = next(arm for arm in row["arms"] if arm["arm"] == "BITE_v5")
        assert bite["actual_sequence"] == bite["projected_sequence"]
        assert "recovery_bundle_bytes" in bite
        assert "visible_reference_retention_v2" in bite
        assert "unique_assignment_identity_retention_v2" in bite
    executed = {str(spec["case_id"]) for spec in planned_preflight_cases()}
    assert all(not case_id.startswith("rs2-") for case_id in executed)
    assert not any((RS2_RAW / case_id).is_file() for case_id in executed)


def test_paired_summary_n1_and_empty() -> None:
    empty = paired_summary([])
    assert empty["n"] == 0
    assert empty["status"] == "not_observed"
    one = paired_summary([0.25])
    assert one["n"] == 1
    assert one["mean"] == 0.25
    assert one["median"] == 0.25
    assert one["positive"] == 1
    assert one["tie"] == 0
    assert one["negative"] == 0


def test_i1_first_open_measured() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert validate_phase4i_result(result) == []
    jsonschema.validate(
        result,
        json.loads((ROOT / "spec" / "phase4i-first-open.schema.json").read_text(encoding="utf-8")),
    )
    assert result["verdict"] == "PHASE4I_PROSPECTIVE_COMPARISON_MEASURED"
    assert result["n_documents"] == 18
    assert result["n_arm_rows"] == 72
    assert result["errors"] == []
    assert result["tokenizer_hash_verified"] is True
    assert result["raw_reconstruction_exact"] is True
    assert result["bite_safety_ok"] is True
    assert result["planner_integrity_ok"] is True
    assert result["no_winner_score"] is True
    assert result["no_wave1_vs_wave2_outcome"] is True
    assert result["p3f_evaluation_holdout_used"] is False
    assert result["protocol_commit_sha"] == i0_commit_sha()
    assert result["i0_freeze_blob"] == I0_FREEZE_BLOB
    assert "overall_score" not in result
    assert "best_arm" not in result
    rows = json.loads((ROOT / "artifacts" / "phase4i" / "arm-rows.json").read_text(encoding="utf-8"))
    assert [doc["source_id"] for doc in rows["documents"]] == list(PRIMARY_IDS)
    historical = json.loads(
        (ROOT / "corpora" / "realstruct-2" / "manifest.json").read_text(encoding="utf-8")
    )
    assert historical["n_primary"] == 10
    ref = json.loads(
        (ROOT / "artifacts" / "phase4i" / "paired-reference-retention.json").read_text(
            encoding="utf-8"
        )
    )
    assert ref["n"] == 0
    assert ref["status"] == "not_observed"
    ident = json.loads(
        (ROOT / "artifacts" / "phase4i" / "paired-unique-identity.json").read_text(encoding="utf-8")
    )
    assert ident["n"] == 1
    cost = json.loads(
        (ROOT / "artifacts" / "phase4i" / "model-visible-cost.json").read_text(encoding="utf-8")
    )
    assert cost["bite_reduction_incidence"] == 1
    assert cost["not_a_win_rate"] is True
    safety = json.loads((ROOT / "artifacts" / "phase4i" / "safety.json").read_text(encoding="utf-8"))
    assert safety["n_arm_reconstruction_exact"] == 72
    assert safety["not_a_weighted_score"] is True
    failure = json.loads(
        (ROOT / "artifacts" / "phase4i" / "failure-classification.json").read_text(encoding="utf-8")
    )
    assert failure["classification"] == "none"

    def blob(rel: str) -> str:
        return subprocess.check_output(["git", "hash-object", rel], cwd=ROOT, text=True).strip()

    assert blob("benchmarks/spec/phase4i-first-open-freeze.json") == I0_FREEZE_BLOB
    assert blob("artifacts/phase4h2/realstruct-2-augmented.json") == PHASE4H2_RESULT_BLOB
    assert blob("corpora/realstruct-2/augmented-manifest.json") == AUGMENTED_MANIFEST_BLOB
