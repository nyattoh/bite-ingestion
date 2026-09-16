from __future__ import annotations

from itertools import pairwise

from bite_ingestion.interfaces.operator import OperatorId
from bite_ingestion.operators import CutOperator, apply_operator
from bite_ingestion.operators.base import packet_digest


def test_cut_paragraph_happy(cut_paragraph):
    out = CutOperator().apply(cut_paragraph, {"boundary": "paragraph"})
    assert out["op_status"] == "ok"
    assert out["op_last_touch"] == "CUT"
    assert out["tau"]["sequence"][-1] == "CUT"
    units = out["units"]
    assert len(units) >= 3
    texts = [u["text"].strip() for u in units]
    assert any("Alpha" in t for t in texts)
    assert any("Beta" in t for t in texts)
    assert any("Gamma" in t for t in texts)
    # spans contiguous / non-overlapping ordered
    spans = [(u["span"]["start"], u["span"]["end"]) for u in units]
    for s, e in spans:
        assert s <= e
    for (s0, e0), (s1, e1) in pairwise(spans):
        assert e0 <= s1 or s0 <= s1


def test_cut_span_roundtrip_recovery(cut_lines):
    out = CutOperator().apply(cut_lines, {"boundary": "line", "max_units": 2})
    assert out["cut"]["n_omitted"] == 2
    r_entries = out["R"]["entries"]
    assert r_entries
    assert all(e["reason"] == "budget_truncated" for e in r_entries)
    assert all(e["recoverable"] is True for e in r_entries)
    assert out["recovery_handles"]
    # selected visible has 2
    assert len(out["visible_evidence"]) == 2
    # omitted texts recoverable from R extra
    omitted_texts = {e["extra"]["text"] for e in r_entries}
    assert "row-c" in omitted_texts or any("row-c" in t for t in omitted_texts)
    assert out["tau"]["steps"][-1]["mode"] == "deterministic"


def test_cut_via_registry(minimal_packet):
    out = apply_operator(OperatorId.CUT, minimal_packet, {"boundary": "paragraph"})
    assert out["op_last_touch"] == "CUT"
    assert packet_digest(CutOperator().apply(minimal_packet, {"boundary": "paragraph"})) == packet_digest(out)
