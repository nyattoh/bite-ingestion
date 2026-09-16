from __future__ import annotations

from bite_ingestion.operators import ReduceOperator
from bite_ingestion.operators.loss_ledger import audit_undeclared_visible_loss


def test_reduce_declares_loss(reduce_dupes):
    before = reduce_dupes
    out = ReduceOperator().apply(before)
    assert out["op_status"] == "ok"
    assert out["op_last_touch"] == "REDUCE"
    omit = out["reduce"]["omit_map"]
    assert omit  # duplicates / whitespace should create omits
    ledger = out["irreversible_loss_ledger"]
    assert ledger
    assert all(row["declared"] is True for row in ledger)
    kinds = {row["kind"] for row in ledger}
    assert kinds & {"dedupe_collapse", "aggregate_count", "canonicalise_whitespace"}
    # omit map also in tau
    assert out["tau"]["steps"][-1]["extra"]["reduce.omit_map"] == omit
    report = audit_undeclared_visible_loss(before, out)
    assert report["ok"], report


def test_reduce_no_summary_overwrite(reduce_dupes):
    out = ReduceOperator().apply(reduce_dupes)
    # Primary visible texts remain structured (kv/count), not free prose summary
    for item in out["visible_evidence"]:
        t = item["text"]
        assert "In summary" not in t
        assert "TL;DR" not in t
