"""EVAL-01: Q_baseline gold-oracle leak tests.

Verifies that Q_baseline comes from actual raw_full model response,
not from gold answer.
"""

from __future__ import annotations

import pytest

from bite_eval.pilot.billed_runner import evaluate_billed_instance
from bite_eval.pilot.families import generate_family_instances


class _FakeResult:
    def __init__(self, text: str):
        self.text = text
        self.usage = {
            "prompt_tokens": 10,
            "completion_tokens": 2,
            "total_tokens": 12,
            "cached_tokens": 0,
        }
        self.model = "glm-4.5-flash"
        self.estimate_source = "z.ai_provider_usage"


class _FakeClientWithError:
    """Client that returns wrong answer (not gold)."""

    model = "glm-4.5-flash"

    def chat_completion(self, messages, **kwargs):
        return _FakeResult("WRONG_ANSWER")


def test_q_baseline_not_from_gold():
    """Q_baseline must come from raw_full response, not gold answer."""
    packets = generate_family_instances("clean_local", 1)
    packet = packets[0]
    gold = str(packet.get("gold_answer", ""))

    client = _FakeClientWithError()
    row = evaluate_billed_instance(packet, "raw_full", client)

    # The client returns WRONG_ANSWER, so Q should be 0.0
    assert row.Q == 0.0, "Model gave wrong answer, Q should be 0.0"

    # Q_baseline should NOT be 1.0 (which would mean it came from gold)
    # For raw_full, Q_baseline should equal Q (self-paired)
    assert row.Q_baseline == row.Q, (
        f"Q_baseline should equal Q for raw_full method. "
        f"Got Q_baseline={row.Q_baseline}, Q={row.Q}. "
        f"If Q_baseline=1.0, it means baseline was computed from gold={gold}, not model response."
    )


def test_compressed_method_pairs_with_raw_full():
    """Compressed method should use raw_full Q as baseline, not gold."""
    # This test will need raw_full to run first
    # For now, document the requirement
    pytest.skip("Requires paired raw_full evaluation - implement after billed_runner fix")


def test_baseline_status_field_exists():
    """Result should have baseline_status field tracking pair status."""
    packets = generate_family_instances("clean_local", 1)

    client = _FakeClientWithError()
    row = evaluate_billed_instance(packets[0], "raw_full", client)

    # Check that baseline_status field exists
    assert hasattr(row, "baseline_status"), "BilledInstanceResult should have baseline_status field"


def test_missing_raw_pair_has_missing_status():
    """When raw_full pair is missing, baseline_status should indicate it."""
    pytest.skip("Requires paired raw_full evaluation - implement after billed_runner fix")


def test_timeout_raw_pair_has_timeout_status():
    """When raw_full pair timed out, baseline_status should indicate it."""
    pytest.skip("Requires paired raw_full evaluation - implement after billed_runner fix")
