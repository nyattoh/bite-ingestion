"""Phase 3A post-hoc profiler mechanism tests.

Do not retune profiler features or thresholds. Permutation invariance of
current `l` is the claim under test.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from bite_bench.phase2a import design_cells, generate_phase2a_bundle
from bite_bench.phase2c import confirmatory_pairs
from bite_eval.phase3a_audit import (
    FEATURE_KEYS,
    ROUTING_FEATURES,
    SCHEMA_ID,
    VERDICT_OBSERVABLE_UNUSED,
    VERDICT_UNOBSERVABLE,
    abs_delta,
    decide_phase3a_verdict,
    permute_lines,
    profile_payload,
    query_hit_line_index_span,
    required_span_spread,
    validate_phase3a_doc,
)
from bite_ingestion.policies.thresholds import TBD_CALIBRATE
from bite_ingestion.profilers.deterministic import FEATURE_KEYS as PROFILER_KEYS

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "phase3a" / "profiler-mechanism-audit.json"
SCHEMA = ROOT / "spec" / "phase3a-profiler-mechanism-audit.schema.json"
PROFILER_PY = ROOT / "src" / "bite_ingestion" / "profilers" / "deterministic.py"


def test_phase3a_does_not_rewrite_profiler_or_thresholds() -> None:
    assert FEATURE_KEYS == PROFILER_KEYS
    assert TBD_CALIBRATE.HIGH == 0.66
    assert TBD_CALIBRATE.LOW == 0.34
    assert "sorted(hits, reverse=True)" in PROFILER_PY.read_text(encoding="utf-8")


def test_line_permutation_preserves_all_profiler_features() -> None:
    text = "gold_a=zzz_unique\ngold_b=zzz_unique\nn1=x\nn2=y\nn3=z"
    query = "zzz_unique"
    flipped = permute_lines(text, [0, 2, 3, 4, 1])
    left = profile_payload(text, query)
    right = profile_payload(flipped, query)
    assert left == right
    assert abs_delta(left, right) == {k: 0.0 for k in FEATURE_KEYS}
    assert query_hit_line_index_span(text, query) == 1
    assert query_hit_line_index_span(flipped, query) == 4


def test_l_discards_line_order_and_distance() -> None:
    clustered = "hit_token_alpha=1\nhit_token_beta=2\nn1=x\nn2=y\nn3=z\nn4=w"
    dispersed = "hit_token_alpha=1\nn1=x\nn2=y\nn3=z\nn4=w\nhit_token_beta=2"
    query = "hit_token_alpha hit_token_beta"
    left = profile_payload(clustered, query)
    right = profile_payload(dispersed, query)
    assert left["l"] == right["l"]
    assert left == right
    assert required_span_spread(
        [
            {"span": {"start": 0}, "is_required_evidence": True},
            {"span": {"start": 10}, "is_required_evidence": True},
        ]
    ) != required_span_spread(
        [
            {"span": {"start": 0}, "is_required_evidence": True},
            {"span": {"start": 400}, "is_required_evidence": True},
        ]
    )


def test_phase2a_dispersion_moves_spans_not_profiler() -> None:
    pair = confirmatory_pairs()[0]
    cell = next(c for c in design_cells("evaluation") if c.case_id == pair["case_id"])
    bundle = generate_phase2a_bundle(cell)
    query = str(bundle["canonical"]["question"])
    left = bundle["surfaces"][pair["left"]["family"]]
    right = bundle["surfaces"][pair["right"]["family"]]
    assert profile_payload(str(left["text"]), query) == profile_payload(
        str(right["text"]), query
    )
    assert required_span_spread(left["units"]) != required_span_spread(right["units"])


def test_verdict_predicates() -> None:
    assert decide_phase3a_verdict(
        n_pairs=48, n_routing_feature_nonzero=0, phase2d_n_signal=0
    ) == VERDICT_UNOBSERVABLE
    assert decide_phase3a_verdict(
        n_pairs=48, n_routing_feature_nonzero=3, phase2d_n_signal=0
    ) == VERDICT_OBSERVABLE_UNUSED
    assert list(ROUTING_FEATURES) == ["b", "a", "r", "k", "l", "u"]


def test_committed_artifact_is_post_hoc_unobservable() -> None:
    assert ARTIFACT.is_file(), "run scripts/run_phase3a_audit.py"
    doc = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert validate_phase3a_doc(doc) == []
    jsonschema.validate(doc, json.loads(SCHEMA.read_text(encoding="utf-8")))
    assert doc["schema"] == SCHEMA_ID
    assert doc["confirmatory"] is False
    assert doc["post_hoc"] is True
    assert doc["paid_api"] is False
    assert doc["verdict"] == VERDICT_UNOBSERVABLE
    assert doc["n_pairs"] == 48
    assert doc["n_profiler_vectors_identical"] == 48
    assert doc["n_required_span_spread_differs"] == 48
    assert doc["n_routing_feature_nonzero"] == 0
    assert doc["l_definition"]["permutation_invariant"] is True
    for key in ROUTING_FEATURES:
        assert doc["feature_deltas"][key]["n_nonzero"] == 0
        assert doc["feature_deltas"][key]["max_abs"] == 0.0
