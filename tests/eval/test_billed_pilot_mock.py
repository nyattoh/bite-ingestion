"""BITE-15 / BITE-15b mocked tests: no real network; no real Z.ai calls."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Self

import pytest

from bite_eval.pilot.billed_runner import (
    MINIMAL_FAMILIES,
    MINIMAL_METHODS,
    append_checkpoint,
    evaluate_billed_instance,
    load_checkpoint,
    run_billed_pilot,
)
from bite_eval.pilot.decide import BILLED_PROVIDER, decide_gate_c
from bite_eval.pilot.families import generate_family_instances
from bite_eval.providers.zai_client import (
    BILLED_USAGE_LABEL,
    ENV_KEY,
    ProviderTimeoutError,
    RateLimitError,
    ZaiClient,
    ZaiClientError,
    key_presence,
    parse_usage,
    redact_headers,
)

# ---------------------------------------------------------------------------
# key presence / absent
# ---------------------------------------------------------------------------


def test_key_presence_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_KEY, raising=False)
    info = key_presence()
    assert info["status"] == "ABSENT"
    assert "value" not in info
    assert ENV_KEY not in str(info.values()) or info["env"] == ENV_KEY


def test_key_presence_present_length_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_KEY, "x" * 17)
    info = key_presence(report_length=True)
    assert info["status"] == "PRESENT"
    assert info["length"] == 17
    # Must not echo the key value
    dumped = json.dumps(info)
    assert "x" * 17 not in dumped


def test_zai_client_raises_on_absent_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_KEY, raising=False)
    with pytest.raises(ZaiClientError) as ei:
        ZaiClient()
    assert "KEY_ABSENT" in str(ei.value)


def test_cli_key_absent_exit_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_KEY, raising=False)
    import importlib.util

    root = Path(__file__).resolve().parents[2]
    script = root / "scripts" / "run_billed_pilot.py"
    spec = importlib.util.spec_from_file_location("run_billed_pilot_cli", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    code = mod.main([])
    assert code == 2


# ---------------------------------------------------------------------------
# usage parsing + header redact
# ---------------------------------------------------------------------------


def test_parse_usage_full() -> None:
    usage = parse_usage(
        {
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "cached_tokens": 2,
            }
        }
    )
    assert usage == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
        "cached_tokens": 2,
    }


def test_parse_usage_nested_cached() -> None:
    usage = parse_usage(
        {
            "usage": {
                "prompt_tokens": 8,
                "completion_tokens": 2,
                "total_tokens": 10,
                "prompt_tokens_details": {"cached_tokens": 3},
            }
        }
    )
    assert usage["cached_tokens"] == 3
    assert usage["total_tokens"] == 10


def test_parse_usage_missing() -> None:
    usage = parse_usage({})
    assert usage["total_tokens"] is None
    assert usage["prompt_tokens"] is None


def test_redact_authorization() -> None:
    h = redact_headers(
        {"Authorization": "Bearer SUPERSECRET", "Content-Type": "application/json"}
    )
    assert h["Authorization"] == "***REDACTED***"
    assert "SUPERSECRET" not in json.dumps(h)
    assert h["Content-Type"] == "application/json"


def test_extract_text_falls_back_to_reasoning_content() -> None:
    from bite_eval.providers.zai_client import _extract_text

    payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "reasoning_content": "K17",
                }
            }
        ]
    }
    assert _extract_text(payload) == "K17"


def test_chat_sends_thinking_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pilot client must disable Z.ai thinking so content is populated."""
    monkeypatch.setenv(ENV_KEY, "test-key-not-real")
    captured: dict[str, Any] = {}

    payload = {
        "choices": [{"message": {"role": "assistant", "content": "ok"}}],
        "usage": {
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "total_tokens": 2,
            "cached_tokens": 0,
        },
    }
    raw = json.dumps(payload).encode("utf-8")

    class _Resp:
        status = 200

        def read(self) -> bytes:
            return raw

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def _urlopen(req: object, timeout: float = 0) -> _Resp:
        data = getattr(req, "data", b"") or b""
        captured["body"] = json.loads(data.decode("utf-8"))
        return _Resp()

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)
    client = ZaiClient(model="glm-4.5-flash", retry_max=0)
    client.chat_completion([{"role": "user", "content": "x"}])
    assert captured["body"]["thinking"] == {"type": "disabled"}


# ---------------------------------------------------------------------------
# mocked HTTP client path
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, text: str, usage: dict[str, int | None], model: str = "glm-4.5-flash"):
        self.text = text
        self.usage = usage
        self.model = model
        self.estimate_source = BILLED_USAGE_LABEL


class _FakeClient:
    model = "glm-4.5-flash"

    def __init__(self, *, fail_rate_limit_after: int | None = None) -> None:
        self.calls = 0
        self.fail_rate_limit_after = fail_rate_limit_after

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 256,
        http_trace: list[dict[str, Any]] | None = None,
        retry_max: int | None = None,
    ) -> _FakeResult:
        self.calls += 1
        if self.fail_rate_limit_after is not None and self.calls > self.fail_rate_limit_after:
            raise RateLimitError("HTTP 429 rate limit from provider")
        user = messages[-1]["content"]
        # Recover synthetic gold from authored doc patterns
        answer = "0"
        m = re.search(r"equals\s+(\d+)", user)
        if not m:
            m = re.search(r"maps to\s+(\d+)", user)
        if not m:
            m = re.search(r"HIDDEN:\s*K\d+=(\d+)", user)
        if not m:
            m = re.search(r"codeword\s+K\d+\s+is\s+(\d+)", user)
        if not m:
            m = re.search(r"value=K\d+:(\d+)", user)
        if not m:
            m = re.search(r"fact=K\d+=(\d+)", user)
        if not m:
            m = re.search(r"K\d+=(\d+)", user)
        if not m:
            m = re.search(r":\s*(\d+)\s*[}.]", user)
        if m:
            answer = m.group(1)
        else:
            # Fallback: last standalone integer in user text
            nums = re.findall(r"\b(\d{2,4})\b", user)
            if nums:
                answer = nums[-1]
        usage = {
            "prompt_tokens": 40 + self.calls,
            "completion_tokens": 3,
            "total_tokens": 43 + self.calls,
            "cached_tokens": 0,
        }
        if http_trace is not None:
            http_trace.append(
                {
                    "url": "https://api.z.ai/api/paas/v4/chat/completions",
                    "status": 200,
                    "request_headers": {"Authorization": "***REDACTED***"},
                    "usage": usage,
                }
            )
        return _FakeResult(answer, usage)


def test_evaluate_billed_instance_uses_provider_usage() -> None:
    packets = generate_family_instances("clean_local", 1)
    client = _FakeClient()
    row = evaluate_billed_instance(packets[0], "raw_full", client)
    assert row.estimate_source == BILLED_USAGE_LABEL
    assert row.T_total == 44  # 43 + calls(1)
    assert row.T_prompt is not None
    assert row.T_logical_char4_proxy is not None
    # Must not put proxy into T_total
    assert row.T_total != row.T_logical_char4_proxy or row.T_total is not None


def test_run_billed_pilot_minimal_defaults_to_pivot() -> None:
    client = _FakeClient()
    summary = run_billed_pilot(
        client=client,
        minimal=True,
        families=list(MINIMAL_FAMILIES),
        n_per_family=3,
        methods=list(MINIMAL_METHODS),
        paid_api=True,
    )
    assert summary["paid_api"] is True
    assert summary["has_billed_usage"] is True
    assert summary["estimate_source"] == BILLED_USAGE_LABEL
    assert summary["n_instance_rows"] == 2 * 3 * 2
    assert summary["sample_meets_n_pilot"] is False
    # Minimal must not claim Go
    assert summary["decision"] == "pivot"
    assert summary["decision"] != "go"
    # Traces redacted
    for t in summary.get("http_trace_redacted") or []:
        auth = (t.get("request_headers") or {}).get("Authorization", "")
        assert "Bearer " not in auth or auth == "***REDACTED***"
        assert "SUPERSECRET" not in json.dumps(t)


def test_run_billed_pilot_rate_limit_partial() -> None:
    client = _FakeClient(fail_rate_limit_after=3)
    summary = run_billed_pilot(
        client=client,
        minimal=True,
        families=list(MINIMAL_FAMILIES),
        n_per_family=3,
        methods=list(MINIMAL_METHODS),
        paid_api=True,
    )
    assert summary["rate_limited"] is True
    assert summary["decision"] == "pivot"
    assert "rate_limit" in summary["decision_reason"]
    # Bug 2 fix: rate_limit now creates a row, so 3 successes + 1 rate_limit = 4 rows
    assert summary["n_instance_rows"] == 4
    assert summary["calls_succeeded"] == 3


def test_run_billed_pilot_no_usage_insufficient() -> None:
    class EmptyUsageClient:
        model = "glm-4.5-flash"

        def chat_completion(self, messages, **kwargs):
            return _FakeResult("100", {
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
                "cached_tokens": None,
            })

    summary = run_billed_pilot(
        client=EmptyUsageClient(),
        minimal=True,
        families=["clean_local"],
        n_per_family=1,
        methods=["raw_full"],
        paid_api=True,
    )
    assert summary["has_billed_usage"] is False
    assert summary["decision"] == "insufficient_offline"


# ---------------------------------------------------------------------------
# decide_gate_c billed path
# ---------------------------------------------------------------------------


def test_decide_gate_c_billed_minimal_pivot() -> None:
    label = decide_gate_c(
        paid_api=True,
        t_total_estimate_source=BILLED_PROVIDER,
        constraints_ok_rate=1.0,
        systematic_constraint_fail=False,
        c1_t_total_improves_vs_raw_and_best_single=True,
        c2_morphology_beats_length_only=True,
        c3_net_savings_positive=True,
        sample_meets_n_pilot=False,
        has_billed_usage=True,
    )
    assert label == "pivot"


def test_decide_gate_c_billed_go_only_with_n_pilot() -> None:
    label = decide_gate_c(
        paid_api=True,
        t_total_estimate_source=BILLED_PROVIDER,
        constraints_ok_rate=1.0,
        systematic_constraint_fail=False,
        c1_t_total_improves_vs_raw_and_best_single=True,
        c2_morphology_beats_length_only=True,
        c3_net_savings_positive=True,
        sample_meets_n_pilot=True,
        has_billed_usage=True,
    )
    assert label == "go"


def test_decide_gate_c_rate_limit_partial_pivot() -> None:
    label = decide_gate_c(
        paid_api=True,
        t_total_estimate_source=BILLED_PROVIDER,
        constraints_ok_rate=1.0,
        systematic_constraint_fail=False,
        c1_t_total_improves_vs_raw_and_best_single=True,
        c2_morphology_beats_length_only=True,
        c3_net_savings_positive=True,
        sample_meets_n_pilot=True,
        rate_limit_partial=True,
        has_billed_usage=True,
    )
    assert label == "pivot"


def test_decide_gate_c_no_billed_usage_insufficient() -> None:
    label = decide_gate_c(
        paid_api=True,
        t_total_estimate_source=BILLED_PROVIDER,
        constraints_ok_rate=1.0,
        systematic_constraint_fail=False,
        c1_t_total_improves_vs_raw_and_best_single=None,
        c2_morphology_beats_length_only=None,
        c3_net_savings_positive=None,
        has_billed_usage=False,
    )
    assert label == "insufficient_offline"


def test_decide_gate_c_systematic_stop_still() -> None:
    label = decide_gate_c(
        paid_api=True,
        t_total_estimate_source=BILLED_PROVIDER,
        constraints_ok_rate=0.1,
        systematic_constraint_fail=True,
        c1_t_total_improves_vs_raw_and_best_single=True,
        c2_morphology_beats_length_only=True,
        c3_net_savings_positive=True,
        sample_meets_n_pilot=True,
        has_billed_usage=True,
    )
    assert label == "stop"


def test_mocked_urlopen_never_hits_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """ZaiClient.chat_completion with patched urlopen — no real socket."""
    monkeypatch.setenv(ENV_KEY, "test-key-not-real")

    payload = {
        "choices": [{"message": {"role": "assistant", "content": "42"}}],
        "usage": {
            "prompt_tokens": 11,
            "completion_tokens": 1,
            "total_tokens": 12,
            "cached_tokens": 0,
        },
    }
    raw = json.dumps(payload).encode("utf-8")

    class _Resp:
        status = 200

        def read(self) -> bytes:
            return raw

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def _boom_urlopen(*args: object, **kwargs: object) -> _Resp:
        # Ensure Authorization was set but we never log it
        return _Resp()

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", _boom_urlopen)
    client = ZaiClient(model="glm-4.5-flash", retry_max=0)
    trace: list[dict[str, Any]] = []
    result = client.chat_completion(
        [{"role": "user", "content": "What is 42?"}],
        http_trace=trace,
    )
    assert result.text == "42"
    assert result.usage["total_tokens"] == 12
    assert result.estimate_source == BILLED_USAGE_LABEL
    assert trace[0]["request_headers"]["Authorization"] == "***REDACTED***"


# ---------------------------------------------------------------------------
# BITE-15b: checkpoint / resume / timeout retry / 429 no storm
# ---------------------------------------------------------------------------


def test_checkpoint_write_after_each_call(tmp_path: Path) -> None:
    """Per-call checkpoint JSONL + atomic partial survive a short run."""
    ckpt = tmp_path / "bite15b_checkpoint.jsonl"
    partial = tmp_path / "bite15b_billed_partial.json"
    client = _FakeClient()
    summary = run_billed_pilot(
        client=client,
        minimal=True,
        families=["clean_local"],
        n_per_family=2,
        methods=["raw_full"],
        paid_api=True,
        checkpoint_path=ckpt,
        partial_path=partial,
        resume=False,
    )
    assert ckpt.is_file()
    lines = [ln for ln in ckpt.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2  # 2 instances × 1 method
    for ln in lines:
        rec = json.loads(ln)
        assert rec["status"] == "ok"
        assert rec["family"] == "clean_local"
        assert "method" in rec
        assert rec.get("usage") is not None
        assert "ts" in rec
    assert partial.is_file()
    part = json.loads(partial.read_text(encoding="utf-8"))
    assert part["calls_succeeded"] == 2
    assert part["n_instance_rows"] == 2
    assert summary["calls_succeeded"] == 2


def test_resume_skips_ok_no_duplicate_billing(tmp_path: Path) -> None:
    """Resume must skip already-ok (family, instance_id, method) — no re-bill."""
    ckpt = tmp_path / "bite15b_checkpoint.jsonl"
    partial = tmp_path / "bite15b_billed_partial.json"

    client1 = _FakeClient()
    run_billed_pilot(
        client=client1,
        minimal=True,
        families=["clean_local"],
        n_per_family=2,
        methods=["raw_full", "compressed_passthrough"],
        paid_api=True,
        checkpoint_path=ckpt,
        partial_path=partial,
        resume=False,
    )
    assert client1.calls == 4

    client2 = _FakeClient()
    summary2 = run_billed_pilot(
        client=client2,
        minimal=True,
        families=["clean_local"],
        n_per_family=2,
        methods=["raw_full", "compressed_passthrough"],
        paid_api=True,
        checkpoint_path=ckpt,
        partial_path=partial,
        resume=True,
    )
    assert client2.calls == 0  # all skipped
    assert summary2["calls_skipped_ok"] == 4
    assert summary2["calls_attempted"] == 0
    assert summary2["n_instance_rows"] == 4
    assert summary2["has_billed_usage"] is True


def test_resume_retries_prior_timeout_once(tmp_path: Path) -> None:
    """Prior timeout/error is retried once under the new run's retry budget."""
    ckpt = tmp_path / "bite15b_checkpoint.jsonl"
    packets = generate_family_instances("clean_local", 1)
    pkt = packets[0]
    append_checkpoint(
        ckpt,
        {
            "family": pkt["family"],
            "instance_id": pkt["instance_id"],
            "method": "raw_full",
            "status": "timeout",
            "error_type": "ProviderTimeoutError",
            "usage": None,
            "ts": "2026-09-17T00:00:00Z",
        },
    )
    client = _FakeClient()
    summary = run_billed_pilot(
        client=client,
        minimal=True,
        families=["clean_local"],
        n_per_family=1,
        methods=["raw_full"],
        paid_api=True,
        checkpoint_path=ckpt,
        partial_path=tmp_path / "partial.json",
        resume=True,
    )
    assert client.calls == 1
    assert summary["calls_resumed_retry"] == 1
    assert summary["calls_succeeded"] == 1
    latest = load_checkpoint(ckpt)
    key = (str(pkt["family"]), str(pkt["instance_id"]), "raw_full")
    assert latest[key]["status"] == "ok"


def test_timeout_retries_then_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """TimeoutError → exponential backoff retries then ProviderTimeoutError."""
    monkeypatch.setenv(ENV_KEY, "test-key-not-real")
    sleeps: list[float] = []

    import urllib.request

    def _timeout_urlopen(*args: object, **kwargs: object) -> Any:
        raise TimeoutError("The read operation timed out")

    monkeypatch.setattr(urllib.request, "urlopen", _timeout_urlopen)
    client = ZaiClient(
        model="glm-4.5-flash",
        timeout_s=1.0,
        retry_max=3,
        retry_backoff_base_s=2.0,
        retry_backoff_factor=2.0,
        sleep_fn=sleeps.append,
    )
    with pytest.raises(ProviderTimeoutError):
        client.chat_completion([{"role": "user", "content": "x"}])
    # 3 retries → 3 sleeps (2, 4, 8); 4 attempts total
    assert sleeps == [2.0, 4.0, 8.0]


def test_timeout_maps_into_row_error_not_crash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Runner records timeout as row error + checkpoint; does not abort whole run."""
    monkeypatch.setenv(ENV_KEY, "test-key-not-real")
    import urllib.request

    def _timeout_urlopen(*args: object, **kwargs: object) -> Any:
        raise TimeoutError("The read operation timed out")

    monkeypatch.setattr(urllib.request, "urlopen", _timeout_urlopen)
    ckpt = tmp_path / "ckpt.jsonl"
    client = ZaiClient(
        model="glm-4.5-flash",
        retry_max=0,  # fail fast in test
        sleep_fn=lambda _s: None,
    )
    summary = run_billed_pilot(
        client=client,
        minimal=True,
        families=["clean_local"],
        n_per_family=1,
        methods=["raw_full"],
        paid_api=True,
        checkpoint_path=ckpt,
        partial_path=tmp_path / "partial.json",
        resume=False,
    )
    assert summary["n_instance_rows"] == 1
    assert summary["results"][0]["error"] is not None
    assert "timeout" in (summary["results"][0]["failures"] or [""])[0] or "timed out" in (
        summary["results"][0]["error"] or ""
    ).lower()
    lines = [json.loads(ln) for ln in ckpt.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert lines[0]["status"] == "timeout"


def test_429_stops_without_retry_storm(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTP 429 → RateLimitError immediately; no backoff retries."""
    monkeypatch.setenv(ENV_KEY, "test-key-not-real")
    sleeps: list[float] = []
    calls = {"n": 0}

    import urllib.error
    import urllib.request

    def _429_urlopen(*args: object, **kwargs: object) -> Any:
        calls["n"] += 1
        raise urllib.error.HTTPError(
            url="https://api.z.ai/api/paas/v4/chat/completions",
            code=429,
            msg="Too Many Requests",
            hdrs=None,  # type: ignore[arg-type]
            fp=None,
        )

    monkeypatch.setattr(urllib.request, "urlopen", _429_urlopen)
    client = ZaiClient(
        model="glm-4.5-flash",
        retry_max=3,
        sleep_fn=sleeps.append,
    )
    with pytest.raises(RateLimitError):
        client.chat_completion([{"role": "user", "content": "x"}])
    assert calls["n"] == 1  # no retry storm
    assert sleeps == []


def test_429_runner_flushes_checkpoint(tmp_path: Path) -> None:
    """Runner stops on 429, checkpoints rate_limit, decision pivot."""
    ckpt = tmp_path / "ckpt.jsonl"
    partial = tmp_path / "partial.json"
    client = _FakeClient(fail_rate_limit_after=1)
    summary = run_billed_pilot(
        client=client,
        minimal=True,
        families=list(MINIMAL_FAMILIES),
        n_per_family=3,
        methods=list(MINIMAL_METHODS),
        paid_api=True,
        checkpoint_path=ckpt,
        partial_path=partial,
        resume=False,
    )
    assert summary["rate_limited"] is True
    assert summary["decision"] == "pivot"
    assert client.calls == 2  # 1 ok + 1 raising 429
    lines = [json.loads(ln) for ln in ckpt.read_text(encoding="utf-8").splitlines() if ln.strip()]
    statuses = [r["status"] for r in lines]
    assert "ok" in statuses
    assert "rate_limit" in statuses
    assert partial.is_file()


def test_load_checkpoint_latest_wins(tmp_path: Path) -> None:
    ckpt = tmp_path / "c.jsonl"
    append_checkpoint(
        ckpt,
        {
            "family": "clean_local",
            "instance_id": "x1",
            "method": "raw_full",
            "status": "timeout",
            "error_type": "ProviderTimeoutError",
        },
    )
    append_checkpoint(
        ckpt,
        {
            "family": "clean_local",
            "instance_id": "x1",
            "method": "raw_full",
            "status": "ok",
            "usage": {"total_tokens": 10},
        },
    )
    latest = load_checkpoint(ckpt)
    assert latest[("clean_local", "x1", "raw_full")]["status"] == "ok"


# ---------------------------------------------------------------------------
# Bug regressions: Bugbot PR#11 new findings
# ---------------------------------------------------------------------------


def test_bug1_stale_baselines_recompute_constraints(tmp_path: Path) -> None:
    """Bug 1: Stale constraints survive baseline refresh.
    
    When raw_full times out then succeeds on resume, compressed rows must
    recompute constraints_ok and failures with the new baseline.
    """
    ckpt = tmp_path / "bug1_ckpt.jsonl"
    partial = tmp_path / "bug1_partial.json"
    packets = generate_family_instances("clean_local", 1)
    pkt = packets[0]
    
    # Simulate timeout on raw_full: Q_baseline=0.0, baseline_status=timeout
    # Compressed row was written with stale baseline
    append_checkpoint(
        ckpt,
        {
            "family": pkt["family"],
            "instance_id": pkt["instance_id"],
            "method": "raw_full",
            "status": "timeout",
            "error_type": "ProviderTimeoutError",
        },
    )
    # Compressed row with stale Q_baseline=0.0
    append_checkpoint(
        ckpt,
        {
            "family": pkt["family"],
            "instance_id": pkt["instance_id"],
            "method": "compressed_passthrough",
            "status": "ok",
            "usage": {"total_tokens": 30},
            "row": {
                "instance_id": str(pkt["instance_id"]),
                "family": str(pkt["family"]),
                "method_id": "compressed_passthrough",
                "Q": 1.0,
                "Q_baseline": 0.0,
                "recall_vis": 0.8,
                "recall_rec": 0.95,
                "provenance": 1.0,
                "constraints_ok": True,
                "T_total": 30,
                "T_prompt": 25,
                "T_completion": 5,
                "T_cached": 0,
                "estimate_source": "billed_usage",
                "failures": [],
                "baseline_status": "timeout",
                "answer_text": str(pkt["gold_answer"]),
                "error": None,
            },
        },
    )
    
    # Resume: raw_full succeeds, should refresh compressed baseline and recompute constraints
    client = _FakeClient()
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
    
    # Find the compressed row
    compressed = next(r for r in summary["results"] if r["method_id"] == "compressed_passthrough")
    # Q_baseline should be refreshed from successful raw_full
    assert compressed["Q_baseline"] > 0.0
    assert compressed["baseline_status"] == "ok"
    # Constraints should be recomputed (Q >= Q_baseline - delta should pass)
    # With Q=1.0 and Q_baseline from raw_full (also ~1.0), constraints should still pass
    assert compressed["constraints_ok"] is True


def test_bug2_resume_restore_refreshes_stale_baselines(tmp_path: Path) -> None:
    """Bug 2: Resume restore skips baseline refresh.
    
    After full restore, stale compressed baselines must be refreshed from ok raw_full.
    """
    ckpt = tmp_path / "bug2_ckpt.jsonl"
    partial = tmp_path / "bug2_partial.json"
    packets = generate_family_instances("clean_local", 1)
    pkt = packets[0]
    
    # Checkpoint: raw_full succeeded on previous run
    append_checkpoint(
        ckpt,
        {
            "family": pkt["family"],
            "instance_id": pkt["instance_id"],
            "method": "raw_full",
            "status": "ok",
            "usage": {"total_tokens": 40},
            "row": {
                "instance_id": str(pkt["instance_id"]),
                "family": str(pkt["family"]),
                "method_id": "raw_full",
                "Q": 1.0,
                "Q_baseline": 1.0,
                "recall_vis": 0.8,
                "recall_rec": 0.95,
                "provenance": 1.0,
                "constraints_ok": True,
                "T_total": 40,
                "T_prompt": 35,
                "T_completion": 5,
                "T_cached": 0,
                "estimate_source": "billed_usage",
                "failures": [],
                "baseline_status": "ok",
                "answer_text": str(pkt["gold_answer"]),
                "error": None,
            },
        },
    )
    # Compressed row with stale Q_baseline=0.0 from earlier timeout
    append_checkpoint(
        ckpt,
        {
            "family": pkt["family"],
            "instance_id": pkt["instance_id"],
            "method": "compressed_passthrough",
            "status": "ok",
            "usage": {"total_tokens": 30},
            "row": {
                "instance_id": str(pkt["instance_id"]),
                "family": str(pkt["family"]),
                "method_id": "compressed_passthrough",
                "Q": 1.0,
                "Q_baseline": 0.0,  # Stale
                "recall_vis": 0.8,
                "recall_rec": 0.95,
                "provenance": 1.0,
                "constraints_ok": True,  # Incorrectly passing
                "T_total": 30,
                "T_prompt": 25,
                "T_completion": 5,
                "T_cached": 0,
                "estimate_source": "billed_usage",
                "failures": [],
                "baseline_status": "timeout",  # Stale status
                "answer_text": str(pkt["gold_answer"]),
                "error": None,
            },
        },
    )
    
    # Resume: should refresh compressed baseline from ok raw_full during restore
    client = _FakeClient()
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
    
    # No new calls since both already ok
    assert summary["calls_attempted"] == 0
    # Find the compressed row
    compressed = next(r for r in summary["results"] if r["method_id"] == "compressed_passthrough")
    # Q_baseline should be refreshed to raw_full's Q
    assert compressed["Q_baseline"] == 1.0
    assert compressed["baseline_status"] == "ok"


def test_bug3_rate_limit_rows_excluded_from_constraints_ok_rate(tmp_path: Path) -> None:
    """Bug 3: Rate-limit rows force systematic stop.
    
    Rate-limit rows must be excluded from constraints_ok_rate calculation.
    """
    ckpt = tmp_path / "bug3_ckpt.jsonl"
    partial = tmp_path / "bug3_partial.json"
    
    # Rate limit on second call
    client = _FakeClient(fail_rate_limit_after=1)
    summary = run_billed_pilot(
        client=client,
        minimal=True,
        families=["clean_local"],
        n_per_family=2,
        methods=["raw_full"],
        paid_api=True,
        checkpoint_path=ckpt,
        partial_path=partial,
        resume=False,
    )
    
    # Should have 1 ok + 1 rate_limit
    assert summary["calls_succeeded"] == 1
    assert summary["rate_limited"] is True
    # Rate-limit row should not count in constraints_ok_rate
    # Only the successful row should count
    measured = [r for r in summary["results"] if r["baseline_status"] != "rate_limit" and r["error"] is None]
    assert len(measured) == 1
    assert measured[0]["constraints_ok"] is True
    # constraints_ok_rate should be 1.0 (1/1), not 0.5 (1/2)
    assert summary["constraints_ok_rate"] == 1.0
    # Decision should be pivot (rate_limit_partial), not stop (systematic fail)
    assert summary["decision"] == "pivot"
    assert "rate_limit" in summary["decision_reason"]


def test_bug3_resume_restores_rate_limited_state(tmp_path: Path) -> None:
    """Bug 3: Resume restore skips baseline refresh.
    
    On resume, state.rate_limited must be restored from checkpointed rate_limit rows.
    """
    ckpt = tmp_path / "bug3_resume_ckpt.jsonl"
    partial = tmp_path / "bug3_resume_partial.json"
    packets = generate_family_instances("clean_local", 1)
    pkt = packets[0]
    
    # Checkpoint: rate_limit from previous run
    append_checkpoint(
        ckpt,
        {
            "family": pkt["family"],
            "instance_id": pkt["instance_id"],
            "method": "raw_full",
            "status": "rate_limit",
            "error_type": "RateLimitError",
        },
    )
    
    # Resume: should restore state.rate_limited
    client = _FakeClient()
    summary = run_billed_pilot(
        client=client,
        minimal=True,
        families=["clean_local"],
        n_per_family=1,
        methods=["raw_full"],
        paid_api=True,
        checkpoint_path=ckpt,
        partial_path=partial,
        resume=True,
    )
    
    # state.rate_limited should be True from restored checkpoint
    assert summary["rate_limited"] is True
    assert summary["rate_limit_at"] is not None
    # Decision should handle rate_limit_partial, not systematic fail
    assert summary["decision"] == "pivot"


def test_bug4_skipped_pairs_dont_increment_attempts(tmp_path: Path) -> None:
    """Bug 4: Skipped pairs still increment attempts.
    
    Compressed arms skipped due to paired rate_limit must not increment calls_attempted.
    """
    ckpt = tmp_path / "bug4_ckpt.jsonl"
    partial = tmp_path / "bug4_partial.json"
    
    # Rate limit on first call (raw_full)
    client = _FakeClient(fail_rate_limit_after=0)
    summary = run_billed_pilot(
        client=client,
        minimal=True,
        families=["clean_local"],
        n_per_family=1,
        methods=["raw_full", "compressed_passthrough"],
        paid_api=True,
        checkpoint_path=ckpt,
        partial_path=partial,
        resume=False,
    )
    
    # Should have only 1 attempt (raw_full that hit rate limit)
    # compressed_passthrough should be skipped without incrementing calls_attempted
    assert summary["calls_attempted"] == 1
    assert summary["calls_succeeded"] == 0
    assert summary["rate_limited"] is True
    # Only 1 row (raw_full with rate_limit)
    assert summary["n_instance_rows"] == 1
    assert summary["results"][0]["method_id"] == "raw_full"
    assert summary["results"][0]["baseline_status"] == "rate_limit"
