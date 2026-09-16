"""Load D-2 locked metric-contract + configs (no paid API)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "research" / "metric-contract.json"
LOCK_CFG = ROOT / "configs" / "d2_lock_v0.1.json"
PILOT_CFG = ROOT / "configs" / "pilot_bite14.json"
LOCK_MD = ROOT / "research" / "d2-threshold-lock-2026-09-16.md"


def test_metric_contract_status_locked() -> None:
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert data["status"] == "d2_locked_v0.1"
    assert data["pivot"] == "Pivot-to-bench"
    pt = data["policy_thresholds"]
    assert pt["delta"] == 0.05
    assert pt["rho_visible"] == 0.50
    assert pt["rho_recoverable"] == 0.90
    assert pt["eta"] == 0.95
    assert pt["J"] == 3
    assert pt["N_pilot"] == 24
    assert pt["N_full"] == 100
    assert pt["alpha"] == 0.05
    assert pt["confirmatory_set"] == ["C1", "C2", "C3"]
    assert pt["oracle_budget"]["max_T_total_evals_per_instance"] == 15
    assert pt["B_r"]["formula"] == "min(4096, floor(0.5 * T_in(raw)))"
    assert pt["cache_accounting"]["offline_pilot_estimate"] == "local_char4_proxy"
    assert "offline-proxy" in pt["cache_accounting"]["dc3_status"]
    # Formula/buckets preserved
    assert "T_profiler" in data["full_cost"]["buckets"]
    assert data["full_cost"]["formula"].startswith("T_total =")


def test_d2_lock_config_matches_contract() -> None:
    lock = json.loads(LOCK_CFG.read_text(encoding="utf-8"))
    assert lock["delta"] == 0.05
    assert lock["rho_visible"] == 0.50
    assert lock["rho_recoverable"] == 0.90
    assert lock["eta"] == 0.95
    assert lock["J"] == 3
    assert lock["N_pilot"] == 24
    assert lock["N_full"] == 100
    assert lock["alpha"] == 0.05
    assert lock["oracle_budget_max_evals_per_instance"] == 15
    assert lock["paid_api"] is False
    assert len(lock["synthetic_families"]) == 8


def test_pilot_config_labels_proxy_limitation() -> None:
    pilot = json.loads(PILOT_CFG.read_text(encoding="utf-8"))
    assert pilot["paid_api"] is False
    assert pilot["estimate_source"] == "local_char4_proxy"
    assert "insufficient_offline" in pilot["estimate_source_limitation"]
    assert pilot["N_pilot_target"] == 24
    assert pilot["N_full_recorded"] == 100


def test_lock_md_present_and_nonempty() -> None:
    text = LOCK_MD.read_text(encoding="utf-8")
    assert "D-2" in text
    assert "0.05" in text
    assert "rho" in text.lower() or "ρ" in text or "rho_visible" in text
