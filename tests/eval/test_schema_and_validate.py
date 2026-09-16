"""Schema validation + validate_artifacts script checks."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from bite_eval.harness import EvalHarness

ROOT = Path(__file__).resolve().parents[2]


def test_schema_files_match():
    a = json.loads((ROOT / "spec" / "run-manifest.schema.json").read_text(encoding="utf-8"))
    b = json.loads((ROOT / "schemas" / "run-manifest.schema.json").read_text(encoding="utf-8"))
    assert a == b
    assert "token_buckets" in a["properties"]
    assert "metrics" in a["required"]


def test_smoke_manifest_has_required_fields(tmp_path: Path):
    h = EvalHarness(artifact_root=tmp_path, persist=True)
    m = h.run_smoke(
        "synthetic_passthrough",
        {"document": "schema field check ALPHA", "query": "q"},
        {"stub_profiler_tokens": 2, "stub_router_tokens": 1},
    )
    for key in (
        "schema",
        "method_id",
        "status",
        "offline",
        "paid_api",
        "synthetic",
        "token_buckets",
        "T_total",
        "metrics",
    ):
        assert key in m
    assert m["paid_api"] is False
    assert m["offline"] is True
    metrics = m["metrics"]
    for k in (
        "quality",
        "evidence_recall_visible",
        "evidence_recall_recoverable",
        "provenance",
        "latency",
    ):
        assert k in metrics
    buckets = m["token_buckets"]
    assert buckets["T_profiler"] == 2
    assert buckets["T_router"] == 1
    # T_total includes profiler+router+target
    assert m["T_total"] == (
        buckets["T_profiler"]
        + buckets["T_router"]
        + buckets["sum_calls_in_out"]
    )
    assert m["gates"]["go_pivot_stop"] == "not_run"
    assert m["gates"]["numeric_thresholds"] == "TBD"


def test_validate_artifacts_cli(tmp_path: Path):
    h = EvalHarness(artifact_root=tmp_path, persist=True)
    h.run_smoke("synthetic_passthrough", {"document": "cli validate", "query": "q"}, {})
    # Copy schema into tmp so validator finds it
    for name in ("spec", "schemas"):
        d = tmp_path / name
        d.mkdir(exist_ok=True)
        (d / "run-manifest.schema.json").write_text(
            (ROOT / "spec" / "run-manifest.schema.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    script = ROOT / "scripts" / "validate_artifacts.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_validate_rejects_secret_keys(tmp_path: Path):
    h = EvalHarness(artifact_root=tmp_path, persist=True)
    m = h.run_smoke("synthetic_passthrough", {"document": "x", "query": "q"}, {})
    # Manually poison a written manifest
    path = tmp_path / "artifacts" / "runs" / str(m["run_id"]) / "manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["api_key"] = "sk-leaked-should-fail"
    path.write_text(json.dumps(data), encoding="utf-8")
    for name in ("spec", "schemas"):
        d = tmp_path / name
        d.mkdir(exist_ok=True)
        (d / "run-manifest.schema.json").write_text(
            (ROOT / "spec" / "run-manifest.schema.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    script = ROOT / "scripts" / "validate_artifacts.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "secret" in (proc.stdout + proc.stderr).lower() or "api_key" in (
        proc.stdout + proc.stderr
    )
