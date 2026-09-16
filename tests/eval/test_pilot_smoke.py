"""Pilot smoke: synthetic families + decide_gate_c → insufficient_offline."""

from __future__ import annotations

from bite_eval.pilot.constraints import check_constraints
from bite_eval.pilot.decide import decide_gate_c
from bite_eval.pilot.families import SYNTHETIC_FAMILIES, generate_family_instances
from bite_eval.pilot.runner import run_pilot


def test_eight_families_generate_n24() -> None:
    assert len(SYNTHETIC_FAMILIES) == 8
    for fam in SYNTHETIC_FAMILIES:
        packets = generate_family_instances(fam, 24)
        assert len(packets) == 24, fam
        assert packets[0]["family"] == fam
        assert packets[0]["synthetic"] is True
        assert packets[0].get("paid_api") is False


def test_dependency_chain_asks_for_bare_numeric_gold() -> None:
    """Path B: query must request bare number matching gold (not key=value)."""
    packets = generate_family_instances("dependency_chain", 3)
    assert len(packets) == 3
    for p in packets:
        gold = str(p["gold_answer"])
        assert gold.isdigit(), gold
        q = str(p["query"]).lower()
        assert "only that number" in q or "only the number" in q
        assert "key=value" in q
        # Document still contains key=value form for the model to read
        assert f"={gold}" in str(p["document"])


def test_unknown_family_empty() -> None:
    assert generate_family_instances("not_a_real_family", 24) == []


def test_constraints_lock_numbers() -> None:
    ok = check_constraints(
        Q=0.95,
        Q_baseline=1.0,
        recall_vis=0.50,
        recall_rec=0.90,
        provenance=0.95,
    )
    assert ok.ok
    bad = check_constraints(
        Q=0.90,
        Q_baseline=1.0,
        recall_vis=0.50,
        recall_rec=0.90,
        provenance=0.95,
    )
    # Q=0.90 < 1.0 - 0.05 = 0.95
    assert not bad.ok
    assert not bad.q_ok


def test_decide_gate_c_offline_proxy_insufficient() -> None:
    label = decide_gate_c(
        paid_api=False,
        t_total_estimate_source="local_char4_proxy",
        constraints_ok_rate=1.0,
        systematic_constraint_fail=False,
        c1_t_total_improves_vs_raw_and_best_single=None,
        c2_morphology_beats_length_only=None,
        c3_net_savings_positive=None,
    )
    assert label == "insufficient_offline"


def test_decide_gate_c_systematic_stop() -> None:
    label = decide_gate_c(
        paid_api=True,
        t_total_estimate_source="provider_usage",
        constraints_ok_rate=0.1,
        systematic_constraint_fail=True,
        c1_t_total_improves_vs_raw_and_best_single=True,
        c2_morphology_beats_length_only=True,
        c3_net_savings_positive=True,
    )
    assert label == "stop"


def test_decide_gate_c_go_requires_billed_and_c123() -> None:
    label = decide_gate_c(
        paid_api=True,
        t_total_estimate_source="provider_usage",
        constraints_ok_rate=1.0,
        systematic_constraint_fail=False,
        c1_t_total_improves_vs_raw_and_best_single=True,
        c2_morphology_beats_length_only=True,
        c3_net_savings_positive=True,
    )
    assert label == "go"


def test_run_pilot_smoke_insufficient_offline() -> None:
    # Small n for unit smoke speed; full pilot uses 24 via CLI
    summary = run_pilot(n_per_family=2, paid_api=False)
    assert summary["paid_api"] is False
    assert summary["estimate_source"] == "local_char4_proxy"
    assert summary["decision"] == "insufficient_offline"
    assert len(summary["families_run"]) == 8
    for fam, n in summary["families_run"].items():
        assert n == 2, fam
    assert summary["n_instance_rows"] == 8 * 2 * 2  # families * n * methods
