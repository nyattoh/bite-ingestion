"""Regression tests for Bugbot findings on PR #11 baseline handling.

Bug 1: Stale baseline after resume retry
Bug 2: Rate-limit skip unpaired compressed
Bug 3: Provider errors marked baseline ok
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bite_eval.pilot.billed_runner import (
    append_checkpoint,
    evaluate_billed_instance,
    run_billed_pilot,
)
from bite_eval.pilot.families import generate_family_instances
from bite_eval.providers.zai_client import (
    BILLED_USAGE_LABEL,
    ProviderTimeoutError,
    RateLimitError,
    ZaiClientError,
)


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
        self.estimate_source = BILLED_USAGE_LABEL


class _TimeoutClient:
    """Client that times out."""

    model = "glm-4.5-flash"

    def chat_completion(self, messages, **kwargs):
        raise ProviderTimeoutError("Provider timeout")


class _ErrorClient:
    """Client that raises non-timeout ZaiClientError."""

    model = "glm-4.5-flash"

    def chat_completion(self, messages, **kwargs):
        raise ZaiClientError("Provider error: invalid request")


class _SuccessClient:
    """Client that succeeds and returns correct answer."""

    model = "glm-4.5-flash"
    calls = 0

    def chat_completion(self, messages, **kwargs):
        self.calls += 1
        # Extract gold from synthetic packet (more robust)
        user = messages[-1]["content"]
        import re

        # Try multiple patterns to match synthetic family formats
        patterns = [
            r"equals\s+(\d+)",
            r"maps to\s+(\d+)",
            r"HIDDEN:\s*K\d+=(\d+)",
            r"codeword\s+K\d+\s+is\s+(\d+)",
            r"value=K\d+:(\d+)",
            r"fact=K\d+=(\d+)",
            r"K\d+=(\d+)",
            r":\s*(\d+)\s*[}.]",
        ]
        for pattern in patterns:
            m = re.search(pattern, user)
            if m:
                return _FakeResult(m.group(1))
        # Fallback: last number
        nums = re.findall(r"\b(\d{2,4})\b", user)
        answer = nums[-1] if nums else "0"
        return _FakeResult(answer)


class _RateLimitClient:
    """Client that rate limits on first raw_full, succeeds on compressed."""

    model = "glm-4.5-flash"
    calls = 0

    def chat_completion(self, messages, **kwargs):
        self.calls += 1
        user = messages[-1]["content"]
        # Rate limit on raw_full (full document), succeed on compressed
        if "truncated" not in user:
            raise RateLimitError("HTTP 429 rate limit from provider")
        import re

        m = re.search(r"K\d+=(\d+)", user)
        answer = m.group(1) if m else "0"
        return _FakeResult(answer)


# ---------------------------------------------------------------------------
# Bug 3: Provider errors marked baseline ok
# ---------------------------------------------------------------------------


def test_bug3_provider_error_not_baseline_ok():
    """Bug 3: Non-timeout ZaiClientError on raw_full must not set baseline_status=ok."""
    packets = generate_family_instances("clean_local", 1)
    client = _ErrorClient()

    row = evaluate_billed_instance(packets[0], "raw_full", client)

    assert row.error is not None
    assert row.Q == 0.0
    assert row.baseline_status != "ok", (
        "Bug 3: Provider error on raw_full must NOT set baseline_status=ok. "
        f"Got baseline_status={row.baseline_status}"
    )
    assert row.baseline_status == "error", (
        f"Expected baseline_status='error' for provider error, got '{row.baseline_status}'"
    )
    assert "provider_error" in row.failures


def test_bug3_timeout_still_marked_timeout():
    """Bug 3 regression: Timeout should still set baseline_status=timeout."""
    packets = generate_family_instances("clean_local", 1)
    client = _TimeoutClient()

    row = evaluate_billed_instance(packets[0], "raw_full", client)

    assert row.error is not None
    assert row.Q == 0.0
    assert row.baseline_status == "timeout"
    assert "provider_timeout" in row.failures


# ---------------------------------------------------------------------------
# Bug 2: Rate-limit skip unpaired compressed
# ---------------------------------------------------------------------------


def test_bug2_rate_limit_records_baseline_status():
    """Bug 2: RateLimitError on raw_full must record baseline_status=rate_limit."""
    client = _RateLimitClient()
    summary = run_billed_pilot(
        client=client,
        minimal=True,
        families=["clean_local"],
        n_per_family=1,
        methods=["raw_full", "compressed_passthrough"],
        paid_api=True,
        resume=False,
    )

    # Should have stopped on rate limit
    assert summary["rate_limited"] is True
    # Should have 1 row for the rate-limited raw_full
    assert summary["n_instance_rows"] >= 1

    # Find the rate-limited raw_full row
    raw_rows = [r for r in summary["results"] if r["method_id"] == "raw_full"]
    assert len(raw_rows) == 1
    raw_row = raw_rows[0]

    assert raw_row["baseline_status"] == "rate_limit", (
        "Bug 2: Rate-limited raw_full must record baseline_status='rate_limit'. "
        f"Got baseline_status={raw_row['baseline_status']}"
    )
    assert raw_row["error"] is not None
    assert "rate_limit" in raw_row["failures"]


def test_bug2_compressed_skipped_when_raw_rate_limited(tmp_path: Path):
    """Bug 2: Compressed method should skip when paired raw_full was rate-limited."""
    ckpt = tmp_path / "ckpt.jsonl"
    partial = tmp_path / "partial.json"

    # First run: raw_full hits rate limit
    client1 = _RateLimitClient()
    summary1 = run_billed_pilot(
        client=client1,
        minimal=True,
        families=["clean_local"],
        n_per_family=1,
        methods=["raw_full", "compressed_passthrough"],
        paid_api=True,
        checkpoint_path=ckpt,
        partial_path=partial,
        resume=False,
    )

    assert summary1["rate_limited"] is True
    # Only raw_full attempted (hit rate limit before compressed)
    raw_rows = [r for r in summary1["results"] if r["method_id"] == "raw_full"]
    assert len(raw_rows) == 1
    assert raw_rows[0]["baseline_status"] == "rate_limit"

    # Second run: resume with success client
    # Compressed should skip because paired raw_full is rate_limit status
    client2 = _SuccessClient()
    summary2 = run_billed_pilot(
        client=client2,
        minimal=True,
        families=["clean_local"],
        n_per_family=1,
        methods=["raw_full", "compressed_passthrough"],
        paid_api=True,
        checkpoint_path=ckpt,
        partial_path=partial,
        resume=True,
    )

    # raw_full should be skipped (already has rate_limit status)
    # compressed should also be skipped (paired raw_full is rate_limit)
    compressed_rows = [r for r in summary2["results"] if r["method_id"] == "compressed_passthrough"]
    
    # Bug 2 fix: compressed should NOT run with missing_pair when raw was rate-limited
    # It should either be skipped entirely or not have baseline_status='missing_pair' with Q_baseline=0.0
    for comp_row in compressed_rows:
        if comp_row["baseline_status"] == "missing_pair" and comp_row["Q_baseline"] == 0.0:
            pytest.fail(
                "Bug 2: Compressed method ran with missing_pair/Q_baseline=0.0 "
                "when paired raw_full was rate-limited"
            )


# ---------------------------------------------------------------------------
# Bug 1: Stale baseline after resume retry
# ---------------------------------------------------------------------------


def test_bug1_stale_baseline_refreshed_after_resume(tmp_path: Path):
    """Bug 1: After raw_full timeout→success retry, compressed baseline must refresh."""
    ckpt = tmp_path / "ckpt.jsonl"
    partial = tmp_path / "partial.json"
    packets = generate_family_instances("clean_local", 1)
    pkt = packets[0]
    instance_id = str(pkt["instance_id"])

    # Simulate initial run: raw_full times out, compressed runs with timeout baseline
    # 1. Write checkpoint for timed-out raw_full
    append_checkpoint(
        ckpt,
        {
            "family": pkt["family"],
            "instance_id": instance_id,
            "method": "raw_full",
            "status": "timeout",
            "error_type": "ProviderTimeoutError",
            "usage": None,
            "ts": "2026-09-16T00:00:00Z",
        },
    )

    # 2. Write checkpoint for compressed that ran with stale baseline
    # (Q_baseline=0.0, baseline_status=timeout because paired raw_full timed out)
    compressed_row_data = {
        "instance_id": instance_id,
        "family": pkt["family"],
        "method_id": "compressed_passthrough",
        "Q": 1.0,  # Compressed succeeded
        "Q_baseline": 0.0,  # Stale! Should be updated after raw_full succeeds
        "recall_vis": 1.0,
        "recall_rec": 1.0,
        "provenance": 1.0,
        "constraints_ok": False,  # False because Q_baseline=0.0 (stale)
        "T_total": 50,
        "T_prompt": 40,
        "T_completion": 10,
        "T_cached": 0,
        "estimate_source": BILLED_USAGE_LABEL,
        "model": "glm-4.5-flash",
        "failures": [],
        "answer_text": "correct",
        "error": None,
        "baseline_status": "timeout",  # Inherited from timed-out raw_full
    }
    append_checkpoint(
        ckpt,
        {
            "family": pkt["family"],
            "instance_id": instance_id,
            "method": "compressed_passthrough",
            "status": "ok",
            "usage": {"total_tokens": 50},
            "row": compressed_row_data,
            "ts": "2026-09-16T00:00:01Z",
        },
    )

    # Write partial file
    partial_data = {
        "pilot_id": "bite15_billed_synthetic_v0.1",
        "calls_attempted": 2,
        "calls_succeeded": 1,
        "calls_skipped_ok": 0,
        "calls_resumed_retry": 0,
        "n_instance_rows": 1,
        "n_billed_rows": 1,
        "rate_limited": False,
        "results": [compressed_row_data],
    }
    partial.write_text(json.dumps(partial_data, indent=2), encoding="utf-8")

    # Resume run: raw_full succeeds on retry
    client = _SuccessClient()
    summary = run_billed_pilot(
        client=client,
        minimal=True,
        families=["clean_local"],
        n_per_family=1,
        methods=["raw_full", "compressed_passthrough"],
        paid_api=True,
        checkpoint_path=ckpt,
        partial_path=partial,
        resume=True,
    )

    # raw_full should have been retried and succeeded
    assert summary["calls_resumed_retry"] >= 1
    raw_rows = [r for r in summary["results"] if r["method_id"] == "raw_full"]
    assert len(raw_rows) == 1
    raw_row = raw_rows[0]
    assert raw_row["error"] is None
    assert raw_row["baseline_status"] == "ok"
    assert raw_row["Q"] > 0.0  # Should be correct answer

    # Bug 1 fix: Compressed row's baseline should be refreshed
    compressed_rows = [r for r in summary["results"] if r["method_id"] == "compressed_passthrough"]
    assert len(compressed_rows) == 1
    comp_row = compressed_rows[0]

    # Check that baseline was refreshed from successful raw_full
    assert comp_row["Q_baseline"] == raw_row["Q"], (
        f"Bug 1: Compressed Q_baseline should be refreshed to {raw_row['Q']} after raw_full retry success. "
        f"Got Q_baseline={comp_row['Q_baseline']}"
    )
    assert comp_row["baseline_status"] == "ok", (
        f"Bug 1: Compressed baseline_status should be refreshed to 'ok' after raw_full retry success. "
        f"Got baseline_status={comp_row['baseline_status']}"
    )


def test_bug1_multiple_compressed_rows_refreshed(tmp_path: Path):
    """Bug 1: Multiple compressed rows for same instance should all be refreshed."""
    ckpt = tmp_path / "ckpt.jsonl"
    partial = tmp_path / "partial.json"
    packets = generate_family_instances("clean_local", 1)
    pkt = packets[0]
    instance_id = str(pkt["instance_id"])

    # Simulate timed-out raw_full
    append_checkpoint(
        ckpt,
        {
            "family": pkt["family"],
            "instance_id": instance_id,
            "method": "raw_full",
            "status": "timeout",
            "error_type": "ProviderTimeoutError",
        },
    )

    # Simulate two compressed methods that both have stale baselines
    compressed_rows = []
    for method in ["compressed_passthrough", "synthetic_passthrough"]:
        row_data = {
            "instance_id": instance_id,
            "family": pkt["family"],
            "method_id": method,
            "Q": 1.0,
            "Q_baseline": 0.0,  # Stale
            "recall_vis": 1.0,
            "recall_rec": 1.0,
            "provenance": 1.0,
            "constraints_ok": False,
            "T_total": 50,
            "T_prompt": 40,
            "T_completion": 10,
            "T_cached": 0,
            "estimate_source": BILLED_USAGE_LABEL,
            "model": "glm-4.5-flash",
            "failures": [],
            "answer_text": "correct",
            "error": None,
            "baseline_status": "timeout",
        }
        compressed_rows.append(row_data)
        append_checkpoint(
            ckpt,
            {
                "family": pkt["family"],
                "instance_id": instance_id,
                "method": method,
                "status": "ok",
                "usage": {"total_tokens": 50},
                "row": row_data,
            },
        )

    partial.write_text(
        json.dumps(
            {
                "results": compressed_rows,
                "calls_attempted": 3,
                "calls_succeeded": 2,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # Resume: raw_full succeeds
    client = _SuccessClient()
    summary = run_billed_pilot(
        client=client,
        minimal=True,
        families=["clean_local"],
        n_per_family=1,
        methods=["raw_full", "compressed_passthrough", "synthetic_passthrough"],
        paid_api=True,
        checkpoint_path=ckpt,
        partial_path=partial,
        resume=True,
    )

    raw_rows = [r for r in summary["results"] if r["method_id"] == "raw_full"]
    assert len(raw_rows) == 1
    raw_q = raw_rows[0]["Q"]
    assert raw_q > 0.0

    # Bug 1 fix: Both compressed methods should have refreshed baselines
    comp_rows = [r for r in summary["results"] if r["method_id"] != "raw_full"]
    assert len(comp_rows) == 2

    for comp_row in comp_rows:
        assert comp_row["Q_baseline"] == raw_q, (
            f"Bug 1: All compressed rows should have refreshed Q_baseline={raw_q}. "
            f"Method {comp_row['method_id']} has Q_baseline={comp_row['Q_baseline']}"
        )
        assert comp_row["baseline_status"] == "ok", (
            f"Bug 1: All compressed rows should have refreshed baseline_status='ok'. "
            f"Method {comp_row['method_id']} has baseline_status={comp_row['baseline_status']}"
        )
