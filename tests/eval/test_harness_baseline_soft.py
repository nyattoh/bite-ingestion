"""Soft-import baseline path when bite12 is on PYTHONPATH."""

from __future__ import annotations

from pathlib import Path

import pytest

from bite_eval.harness import EvalHarness


def test_optional_raw_full_when_baselines_present(tmp_path: Path):
    try:
        from bite_eval.baselines import get_baseline
    except ImportError:
        pytest.skip("bite12 baselines not on PYTHONPATH")
    assert get_baseline("raw_full") is not None
    h = EvalHarness(artifact_root=tmp_path, persist=True)
    packet = {
        "document": "Baseline soft path. ALPHA=1.",
        "query": "ALPHA?",
        "domain": "prose",
    }
    m = h.run_smoke("raw_full", packet, {"domain": "prose"})
    assert m["status"] in {"ok", "overflow", "failed", "not_applicable"}
    assert m["paid_api"] is False
    assert "T_total" in m
    assert "token_buckets" in m
