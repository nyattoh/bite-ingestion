from __future__ import annotations

from bite_ingestion.operators import UntangleOperator


def test_untangle_happy_and_coverage(untangle_mixed):
    op = UntangleOperator()
    out = op.apply(untangle_mixed)
    assert out["op_status"] == "ok"
    assert out["op_last_touch"] == "UNTANGLE"
    # Ensure units were synthesized then partitioned
    # Reconstruct input unit ids from a fresh ensure path
    from bite_ingestion.operators.base import deep_copy_packet, ensure_units

    base = deep_copy_packet(untangle_mixed)
    input_ids = {u["unit_id"] for u in ensure_units(base)}
    residual = set(out["untangle"]["residual_ids"])
    isolated = {x["unit_id"] for x in out["untangle"]["isolated"]}
    assert residual | isolated == input_ids
    assert residual.isdisjoint(isolated)
    reasons = out["untangle"]["reasons"]
    # Expect some quarantine reasons present
    flat = {c for codes in reasons.values() for c in codes}
    assert "malformed" in flat or "anomaly_candidate" in flat or "injection_suspect" in flat
    # All isolated in R recoverable
    r_uids = {e["unit_id"] for e in out["R"]["entries"]}
    assert isolated <= r_uids
    assert all(e["recoverable"] for e in out["R"]["entries"])
    assert out["tau"]["steps"][-1]["extra"]["untangle.residual_ids"] == out["untangle"]["residual_ids"]


def test_untangle_no_silent_delete(untangle_mixed):
    out = UntangleOperator().apply(untangle_mixed)
    # visible may shrink but R holds quarantine
    assert out["R"]["entries"] or out["untangle"]["isolated"] == []
    if out["untangle"]["isolated"]:
        assert out["recovery_handles"]
