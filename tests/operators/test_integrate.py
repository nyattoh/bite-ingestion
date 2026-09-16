from __future__ import annotations

from bite_ingestion.operators import IntegrateOperator


def test_integrate_join_plan(integrate_keys):
    out = IntegrateOperator().apply(integrate_keys, {"integrate_mode": "deterministic_join"})
    assert out["op_status"] == "ok"
    plan = out["integrate"]["join_plan"]
    used = out["integrate"]["used_evidence_ids"]
    assert plan
    assert used
    # Expect join on 42 and zz
    keys = {p["join_key"] for p in plan}
    assert "42" in keys or any("42" in p["join_key"] for p in plan)
    assert "zz" in keys or any("zz" in p["join_key"] for p in plan)
    for p in plan:
        assert "unit_ids" in p and "method" in p
        assert len(p["unit_ids"]) >= 2
    # Visible provenance pointers
    for item in out["visible_evidence"]:
        assert "unit_ids" in item
        assert item["unit_ids"]


def test_integrate_passthrough_empty(minimal_packet):
    # Single blob with no shared keys among multiple units after cut? use one unit packet
    out = IntegrateOperator().apply(minimal_packet)
    assert out["op_status"] == "ok"
    assert out["integrate"]["join_plan"] == []
    assert out["integrate"]["used_evidence_ids"] == []


def test_integrate_rejects_lm_mode(integrate_keys):
    out = IntegrateOperator().apply(integrate_keys, {"integrate_mode": "lm_synthesis"})
    assert out["op_status"] == "failed"
