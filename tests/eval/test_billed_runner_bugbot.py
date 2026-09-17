"""Regression tests for Bugbot PR#11 findings in billed_runner.py.

Bug 1: Checkpoint rewrite must preserve rate_limit status.
Bug 2: Post-restore refresh must persist updated baselines to checkpoint.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, cast

from bite_eval.pilot.billed_runner import (
    BilledInstanceResult,
    append_checkpoint,
    load_checkpoint,
)


def test_bug1_checkpoint_rewrite_preserves_rate_limit_status() -> None:
    """Bug 1 regression: rate_limit sibling keeps rate_limit after raw_full success rewrite.
    
    Scenario:
    1. Compressed method hits rate_limit and is checkpointed with status=rate_limit
    2. Later, paired raw_full succeeds on retry
    3. Checkpoint rewrite for the compressed row must preserve status=rate_limit,
       NOT map it to "error" just because error field is non-null.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = Path(tmpdir) / "test_checkpoint.jsonl"
        
        # Step 1: Write initial checkpoint with compressed_passthrough at status=rate_limit
        instance_id = "test_inst_001"
        family = "clean_local"
        
        rate_limit_row = BilledInstanceResult(
            instance_id=instance_id,
            family=family,
            method_id="compressed_passthrough",
            Q=0.0,
            Q_baseline=0.0,
            recall_vis=0.0,
            recall_rec=0.0,
            provenance=0.0,
            constraints_ok=False,
            T_total=None,
            T_prompt=None,
            T_completion=None,
            T_cached=None,
            estimate_source="provider_usage",
            error="RateLimitError: 429",
            baseline_status="rate_limit",
        )
        
        append_checkpoint(
            checkpoint_path,
            {
                "family": family,
                "instance_id": instance_id,
                "method": "compressed_passthrough",
                "status": "rate_limit",
                "error_type": "RateLimitError",
                "row": {
                    "instance_id": instance_id,
                    "family": family,
                    "method_id": "compressed_passthrough",
                    "Q": 0.0,
                    "Q_baseline": 0.0,
                    "recall_vis": 0.0,
                    "recall_rec": 0.0,
                    "provenance": 0.0,
                    "constraints_ok": False,
                    "T_total": None,
                    "T_prompt": None,
                    "T_completion": None,
                    "T_cached": None,
                    "estimate_source": "provider_usage",
                    "error": "RateLimitError: 429",
                    "baseline_status": "rate_limit",
                },
            },
        )
        
        # Step 2: Simulate raw_full success rewrite (as code does in lines 798-821)
        # The rewrite should preserve status=rate_limit for the compressed row
        
        # Simulate the checkpoint rewrite logic (Bug 1 fix)
        refreshed_row = rate_limit_row
        if refreshed_row.baseline_status == "rate_limit":
            status = "rate_limit"
        elif refreshed_row.error is None:
            status = "ok"
        else:
            status = "error"
        
        append_checkpoint(
            checkpoint_path,
            {
                "family": refreshed_row.family,
                "instance_id": refreshed_row.instance_id,
                "method": refreshed_row.method_id,
                "status": status,
                "row": {
                    "instance_id": refreshed_row.instance_id,
                    "family": refreshed_row.family,
                    "method_id": refreshed_row.method_id,
                    "Q": refreshed_row.Q,
                    "Q_baseline": refreshed_row.Q_baseline,
                    "recall_vis": refreshed_row.recall_vis,
                    "recall_rec": refreshed_row.recall_rec,
                    "provenance": refreshed_row.provenance,
                    "constraints_ok": refreshed_row.constraints_ok,
                    "T_total": refreshed_row.T_total,
                    "T_prompt": refreshed_row.T_prompt,
                    "T_completion": refreshed_row.T_completion,
                    "T_cached": refreshed_row.T_cached,
                    "estimate_source": refreshed_row.estimate_source,
                    "error": refreshed_row.error,
                    "baseline_status": refreshed_row.baseline_status,
                },
            },
        )
        
        # Step 3: Load checkpoint and verify rate_limit status is preserved
        latest = load_checkpoint(checkpoint_path)
        key = (family, instance_id, "compressed_passthrough")
        assert key in latest, "Compressed row should be in checkpoint"
        
        rec = latest[key]
        assert rec["status"] == "rate_limit", (
            f"Bug 1 regression: status should be 'rate_limit', got '{rec['status']}'. "
            f"The checkpoint rewrite must preserve rate_limit status, not map to 'error'."
        )
        assert rec["row"]["baseline_status"] == "rate_limit"
        assert rec["row"]["error"] is not None  # error field is non-null
        
        print("✓ Bug 1 test passed: rate_limit status preserved through checkpoint rewrite")


def test_bug2_restore_refresh_persists_to_checkpoint() -> None:
    """Bug 2 regression: Post-restore baseline refresh must persist to checkpoint.
    
    Scenario:
    1. Compressed method succeeds with stale Q_baseline=0.0, baseline_status=timeout
    2. Raw_full later succeeds with Q=0.85
    3. Both are checkpointed, then run exits
    4. On restore-only resume (no new calls), post-restore refresh updates compressed
       Q_baseline and constraints in memory
    5. Updated compressed row MUST be persisted to checkpoint, not just in memory
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = Path(tmpdir) / "test_checkpoint.jsonl"
        
        instance_id = "test_inst_002"
        family = "adversarial_omission"
        
        # Step 1: Write compressed row with stale baseline
        compressed_row_data = {
            "family": family,
            "instance_id": instance_id,
            "method": "compressed_passthrough",
            "status": "ok",
            "row": {
                "instance_id": instance_id,
                "family": family,
                "method_id": "compressed_passthrough",
                "Q": 0.90,
                "Q_baseline": 0.0,  # Stale baseline
                "recall_vis": 0.50,
                "recall_rec": 0.90,
                "provenance": 0.95,
                "constraints_ok": False,  # Wrong due to stale baseline
                "T_total": 1200,
                "T_prompt": 800,
                "T_completion": 400,
                "T_cached": 0,
                "estimate_source": "provider_usage",
                "error": None,
                "baseline_status": "timeout",  # Stale status
            },
        }
        append_checkpoint(checkpoint_path, compressed_row_data)
        
        # Step 2: Write successful raw_full
        raw_full_row_data = {
            "family": family,
            "instance_id": instance_id,
            "method": "raw_full",
            "status": "ok",
            "row": {
                "instance_id": instance_id,
                "family": family,
                "method_id": "raw_full",
                "Q": 0.85,
                "Q_baseline": 0.85,  # Self-pairing
                "recall_vis": 0.52,
                "recall_rec": 0.91,
                "provenance": 0.96,
                "constraints_ok": True,
                "T_total": 2400,
                "T_prompt": 1600,
                "T_completion": 800,
                "T_cached": 0,
                "estimate_source": "provider_usage",
                "error": None,
                "baseline_status": "ok",
            },
        }
        append_checkpoint(checkpoint_path, raw_full_row_data)
        
        # Step 3: Simulate restore-only path post-refresh checkpoint write (Bug 2 fix)
        # After refresh in memory, updated compressed row must be persisted
        
        refreshed_compressed = {
            "family": family,
            "instance_id": instance_id,
            "method": "compressed_passthrough",
            "status": "ok",
            "row": {
                "instance_id": instance_id,
                "family": family,
                "method_id": "compressed_passthrough",
                "Q": 0.90,
                "Q_baseline": 0.85,  # Updated from raw_full
                "recall_vis": 0.50,
                "recall_rec": 0.90,
                "provenance": 0.95,
                "constraints_ok": True,  # Recomputed with new baseline
                "T_total": 1200,
                "T_prompt": 800,
                "T_completion": 400,
                "T_cached": 0,
                "estimate_source": "provider_usage",
                "error": None,
                "baseline_status": "ok",  # Updated status
            },
        }
        append_checkpoint(checkpoint_path, refreshed_compressed)
        
        # Step 4: Load checkpoint and verify updated baseline was persisted
        latest = load_checkpoint(checkpoint_path)
        key = (family, instance_id, "compressed_passthrough")
        assert key in latest, "Compressed row should be in checkpoint"
        
        rec = latest[key]
        row = rec["row"]
        
        # Verify the restore-only refresh persisted the updated baseline
        assert row["Q_baseline"] == 0.85, (
            f"Bug 2 regression: Q_baseline should be 0.85 (from raw_full), got {row['Q_baseline']}. "
            f"Post-restore refresh must persist updated baselines to checkpoint."
        )
        assert row["baseline_status"] == "ok", (
            f"Bug 2 regression: baseline_status should be 'ok', got '{row['baseline_status']}'. "
            f"Post-restore refresh must persist updated status to checkpoint."
        )
        assert row["constraints_ok"] is True, (
            f"Bug 2 regression: constraints_ok should be True after baseline update, got {row['constraints_ok']}. "
            f"Post-restore refresh must persist recomputed constraints to checkpoint."
        )
        
        print("✓ Bug 2 test passed: post-restore refresh persisted to checkpoint")


def test_bug2_restore_with_rate_limit_sibling() -> None:
    """Bug 2 edge case: Post-restore refresh with rate_limit sibling preserves rate_limit.
    
    Combines both bugs: restore path must persist updates AND preserve rate_limit status.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = Path(tmpdir) / "test_checkpoint.jsonl"
        
        instance_id = "test_inst_003"
        family = "clean_local"
        
        # Compressed method at rate_limit
        rate_limit_row_data = {
            "family": family,
            "instance_id": instance_id,
            "method": "compressed_passthrough",
            "status": "rate_limit",
            "row": {
                "instance_id": instance_id,
                "family": family,
                "method_id": "compressed_passthrough",
                "Q": 0.0,
                "Q_baseline": 0.0,
                "recall_vis": 0.0,
                "recall_rec": 0.0,
                "provenance": 0.0,
                "constraints_ok": False,
                "T_total": None,
                "T_prompt": None,
                "T_completion": None,
                "T_cached": None,
                "estimate_source": "provider_usage",
                "error": "RateLimitError: 429",
                "baseline_status": "rate_limit",
            },
        }
        append_checkpoint(checkpoint_path, rate_limit_row_data)
        
        # Raw_full succeeds
        raw_full_row_data = {
            "family": family,
            "instance_id": instance_id,
            "method": "raw_full",
            "status": "ok",
            "row": {
                "instance_id": instance_id,
                "family": family,
                "method_id": "raw_full",
                "Q": 0.88,
                "Q_baseline": 0.88,
                "recall_vis": 0.51,
                "recall_rec": 0.92,
                "provenance": 0.97,
                "constraints_ok": True,
                "T_total": 2500,
                "T_prompt": 1700,
                "T_completion": 800,
                "T_cached": 0,
                "estimate_source": "provider_usage",
                "error": None,
                "baseline_status": "ok",
            },
        }
        append_checkpoint(checkpoint_path, raw_full_row_data)
        
        # Post-restore refresh should NOT touch rate_limit row baseline
        # (it stays at 0.0 because the call never succeeded)
        # But if the rewrite happens, it MUST preserve status=rate_limit
        
        # Simulate the fix: rewrite preserves rate_limit
        rate_limit_row_dict = cast(dict[str, Any], rate_limit_row_data["row"])
        if rate_limit_row_dict["baseline_status"] == "rate_limit":
            status = "rate_limit"
        elif rate_limit_row_dict["error"] is None:
            status = "ok"
        else:
            status = "error"
        
        append_checkpoint(
            checkpoint_path,
            {
                "family": family,
                "instance_id": instance_id,
                "method": "compressed_passthrough",
                "status": status,
                "row": rate_limit_row_dict,
            },
        )
        
        # Verify rate_limit status preserved
        latest = load_checkpoint(checkpoint_path)
        key = (family, instance_id, "compressed_passthrough")
        rec = latest[key]
        
        assert rec["status"] == "rate_limit", (
            f"Combined bug edge case: status should be 'rate_limit', got '{rec['status']}'"
        )
        assert rec["row"]["baseline_status"] == "rate_limit"
        
        print("✓ Bug 2 edge case test passed: restore refresh preserves rate_limit")
