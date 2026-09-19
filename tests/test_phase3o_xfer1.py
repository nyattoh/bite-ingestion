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
from bite_eval.phase3o_eval import (
    PROTOCOL_COMMIT_SHA,
    RESULT_PATH,
    run_evaluation,
    validate_phase3o_result,
)
from bite_ingestion.adapters.bite_xfer1 import packet_from_document, unitize
from bite_ingestion.policies.conditional_texture_policy_v1 import (
    ConditionalTexturePolicyV1,
    PolicyLeakError,
)
from bite_ingestion.policies.leak_guard import OracleLeakError

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "benchmarks" / "spec" / "phase3o-xfer1-freeze.json"
SCHEMA = ROOT / "spec" / "phase3o-xfer1-freeze.schema.json"
GEN_PY = ROOT / "src" / "bite_bench" / "phase3o.py"
CORPUS_PY = ROOT / "src" / "bite_bench" / "xfer1_corpus.py"
EVAL_PY = ROOT / "src" / "bite_eval" / "phase3o_eval.py"
EXP_SCHEMA = ROOT / "spec" / "phase3o-xfer1-transfer.schema.json"
PHASE3N = ROOT / "artifacts" / "phase3n" / "conditional-routing-first-open.json"
POLICY_PY = ROOT / "src" / "bite_ingestion" / "policies" / "rule_policy.py"


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


def test_o1_matches_artifacts_and_keeps_p3f_sealed() -> None:
    doc = run_evaluation()
    committed = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    assert json.loads(json.dumps(doc, sort_keys=True)) == json.loads(
        json.dumps(committed, sort_keys=True)
    )
    assert validate_phase3o_result(committed) == []
    jsonschema.validate(committed, json.loads(EXP_SCHEMA.read_text(encoding="utf-8")))
    for name in (
        "cross-format.json",
        "actionability.json",
        "composition-safety.json",
        "failure-classification.json",
    ):
        extra = json.loads((ROOT / "artifacts" / "phase3o" / name).read_text(encoding="utf-8"))
        schema = json.loads(
            (ROOT / "spec" / f"phase3o-{name.replace('.json', '')}.schema.json").read_text(
                encoding="utf-8"
            )
        )
        jsonschema.validate(extra, schema)
    assert committed["protocol_commit_sha"] == PROTOCOL_COMMIT_SHA
    assert committed["n_rows"] == N_SURFACES
    assert committed["n_sequence_ok"] == N_SURFACES
    assert committed["p3f_evaluation_holdout_used"] is False
    assert committed["calibration"] is False
    assert committed["rule_policy_executed"] is False
    assert committed["verdict"] in {
        "PHASE3O_XFER1_TRANSFER_CONFIRMED",
        "PHASE3O_XFER1_TRANSFER_FAILED",
        "PHASE3O_XFER1_TRANSFER_BLOCKED",
    }
    if committed["verdict"] == "PHASE3O_XFER1_TRANSFER_FAILED":
        assert committed["failure_classes"]
        assert set(committed["failure_classes"]) <= {
            "gate_format_dependence",
            "predicate_format_dependence",
            "sensor_operator_mismatch",
            "composition_safety",
            "other",
        }
    blob = RESULT_PATH.read_text(encoding="utf-8")
    assert "p3f-" not in blob
    assert "bite_bench.phase3m" not in EVAL_PY.read_text(encoding="utf-8")
    assert "class RulePolicy" in POLICY_PY.read_text(encoding="utf-8")
    assert "RulePolicy(" not in EVAL_PY.read_text(encoding="utf-8")


def test_o1_policy_packet_is_gold_free() -> None:
    path = CORPUS_DIR / "rendered" / "xfer1-c001.key_value.txt"
    packet = packet_from_document(
        path.read_text(encoding="utf-8"), case_id="xfer1-c001", fmt="key_value"
    )
    assert "gold_unit_ids" not in packet
    assert "texture" not in packet
    assert "expected_sequence" not in packet
    policy = ConditionalTexturePolicyV1()
    with pytest.raises(OracleLeakError):
        policy.propose({**packet, "gold_route": ["REDUCE"]})
    with pytest.raises(PolicyLeakError):
        policy.propose({**packet, "texture": "redundant"})
