"""Artifact ledger: reproducibility, no duplicate run_ids, failed runs retained."""

from __future__ import annotations

from pathlib import Path

from bite_eval.artifacts import ArtifactLedger, redact_secrets
from bite_eval.harness import EvalHarness


def _base_manifest(**extra):
    m = {
        "schema": "bite-run-manifest/v0.1",
        "method_id": "synthetic_passthrough",
        "status": "ok",
        "reason": None,
        "offline": True,
        "paid_api": False,
        "synthetic": True,
        "token_buckets": {
            "T_profiler": 0,
            "T_router": 0,
            "T_target_in": 4,
            "T_target_out": 0,
            "T_rebite": 0,
            "T_baseline": 0,
            "T_calls_other": 0,
            "sum_calls_in_out": 4,
        },
        "T_total": 4,
        "metrics": {
            "quality": None,
            "evidence_recall_visible": None,
            "evidence_recall_recoverable": None,
            "provenance": None,
            "latency": {"wall_ms": 1.0},
        },
        "ledger_rows": [
            {
                "category": "target",
                "kind": "local_estimate",
                "tokens_in": 4,
                "tokens_out": 0,
                "call_id": "c1",
            }
        ],
    }
    m.update(extra)
    return m


def test_two_run_reproducibility_same_digest(tmp_path: Path):
    al = ArtifactLedger(tmp_path)
    m1 = al.write_run(_base_manifest(packet_digest="abc"))
    m2 = al.write_run(_base_manifest(packet_digest="abc"))
    assert m1["content_digest"] == m2["content_digest"]
    assert m2.get("resumed") is True
    assert m1["run_id"] == m2["run_id"]
    # Only one run directory for same content
    runs = al.list_runs()
    assert len(runs) == 1


def test_failed_runs_retained(tmp_path: Path):
    al = ArtifactLedger(tmp_path)
    failed = _base_manifest(status="failed", reason="boom", method_id="x")
    written = al.write_run(failed)
    loaded = al.get_run(str(written["run_id"]))
    assert loaded is not None
    assert loaded["status"] == "failed"
    assert loaded["reason"] == "boom"


def test_redact_secrets_and_hash_prompts():
    obj = {
        "api_key": "sk-should-not-persist",
        "prompt": "secret user text",
        "ok": 1,
    }
    cleaned = redact_secrets(obj)
    assert cleaned["api_key"] == "[REDACTED]"
    assert cleaned["prompt"] == "[REDACTED_HASHED]"
    assert "prompt_sha256" in cleaned
    assert cleaned["ok"] == 1


def test_harness_smoke_idempotent(tmp_path: Path):
    h = EvalHarness(artifact_root=tmp_path, persist=True)
    packet = {"document": "Same input twice for digest.", "query": "q"}
    a = h.run_smoke("synthetic_passthrough", packet, {})
    b = h.run_smoke("synthetic_passthrough", packet, {})
    assert a["content_digest"] == b["content_digest"]
    assert b.get("resumed") is True
    assert a["T_total"] == b["T_total"]


def test_harness_retains_force_fail(tmp_path: Path):
    h = EvalHarness(artifact_root=tmp_path, persist=True)
    packet = {"document": "fail me", "query": "q"}
    m = h.run_smoke("synthetic_passthrough", packet, {"force_fail": True})
    assert m["status"] == "failed"
    assert m.get("reason")
    loaded = ArtifactLedger(tmp_path).get_run(str(m["run_id"]))
    assert loaded is not None
    assert loaded["status"] == "failed"
