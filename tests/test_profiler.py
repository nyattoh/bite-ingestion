from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from bite_bench.generator import generate_texture_bundle
from bite_ingestion.interfaces import MorphologyProfiler
from bite_ingestion.profilers import DeterministicMorphologyProfiler


def test_protocol_and_feature_keys() -> None:
    prof = DeterministicMorphologyProfiler()
    assert isinstance(prof, MorphologyProfiler)
    feats = prof.profile({"payload": "a,b,c\n1,2,3\n1,2,3\n"})
    assert set(feats) == {"b", "r", "s", "k", "a", "l", "p", "u"}
    assert all(0.0 <= float(v) <= 1.0 for v in feats.values())


def test_redundancy_monotonic_with_duplicates() -> None:
    prof = DeterministicMorphologyProfiler()
    low = prof.profile({"payload": "alpha\nbeta\ngamma\n"})
    high = prof.profile({"payload": "alpha\nalpha\nalpha\nalpha\n"})
    assert high["r"] > low["r"]


def test_structure_higher_for_json_than_free_prose() -> None:
    prof = DeterministicMorphologyProfiler()
    prose = prof.profile({"payload": "Once upon a time the service failed softly."})
    js = prof.profile({"payload": json.dumps({"service": "alpha", "error_code": "E42"})})
    assert js["s"] > prose["s"]


def test_fail_closed_on_nul() -> None:
    prof = DeterministicMorphologyProfiler()
    report = prof.profile_report({"payload": "ok\x00bad"})
    assert report.fail_closed is True
    assert report.features["u"] >= 0.6
    assert report.cpu_ms >= 0.0
    assert report.peak_memory_kb >= 0.0


def test_ignores_answer_and_route_fields() -> None:
    prof = DeterministicMorphologyProfiler()
    base = {"payload": "service=alpha error_code=E42\n"}
    a = prof.profile(base)
    b = prof.profile({**base, "answer": "SHOULD_NOT_MATTER", "gold_route": "(CUT)", "route": "INTEGRATE"})
    assert a == b


def test_texture_pair_identity_does_not_force_equal_profiles() -> None:
    """Same facts / different texture may change morphology; identity is separate."""
    bundle = generate_texture_bundle(seed=0)
    prof = DeterministicMorphologyProfiler()
    profiles = {
        fam: prof.profile({"payload": payload["text"], "query": bundle["canonical"]["question"]})
        for fam, payload in bundle["textures"].items()
    }
    # At least one feature should vary across textures for this synthetic case
    feature_vectors = [tuple(round(profiles[f][k], 4) for k in ("b", "r", "s")) for f in profiles]
    assert len(set(feature_vectors)) >= 2


def test_schema_and_calibration_artifact() -> None:
    schema = json.loads(Path("spec/morphology.schema.json").read_text(encoding="utf-8"))
    prof = DeterministicMorphologyProfiler()
    feats = dict(prof.profile({"payload": "x=1\n"}))
    jsonschema.validate(feats, schema)
    cal = Path("output/calibration/profiler-baseline.json")
    assert cal.is_file()
    data = json.loads(cal.read_text(encoding="utf-8"))
    assert data["profiler"] == "deterministic_v0"
