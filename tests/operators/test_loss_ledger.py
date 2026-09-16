from __future__ import annotations

from bite_ingestion.operators import ReduceOperator
from bite_ingestion.operators.loss_ledger import (
    assert_no_undeclared_loss,
    audit_undeclared_visible_loss,
)


def test_auditor_ok_after_reduce(reduce_dupes):
    after = ReduceOperator().apply(reduce_dupes)
    report = audit_undeclared_visible_loss(reduce_dupes, after)
    assert report["ok"], report
    assert_no_undeclared_loss(reduce_dupes, after)


def test_auditor_flags_undeclared_shrink():
    before = {
        "packet_id": "audit-before",
        "visible_evidence": [{"text": "keep-me"}, {"text": "drop-me-silently"}],
        "provenance": {"unit_id": "x"},
        "op_last_touch": "NONE",
        "units": [
            {"unit_id": "u_keep", "text": "keep-me", "span": {"start": 0, "end": 7, "unit": "char"}},
            {"unit_id": "u_drop", "text": "drop-me-silently", "span": {"start": 8, "end": 24, "unit": "char"}},
        ],
        "R": {"entries": []},
        "irreversible_loss_ledger": [],
    }
    after = {
        "packet_id": "audit-after",
        "visible_evidence": [{"text": "keep-me"}],
        "provenance": {"unit_id": "x"},
        "op_last_touch": "REDUCE",
        "units": [
            {"unit_id": "u_keep", "text": "keep-me", "span": {"start": 0, "end": 7, "unit": "char"}},
        ],
        "R": {"entries": []},
        "irreversible_loss_ledger": [],
    }
    report = audit_undeclared_visible_loss(before, after)
    assert report["ok"] is False
    assert "drop-me-silently" in report["undeclared_texts"] or "u_drop" in report["undeclared_units"]
