from __future__ import annotations

import json
from pathlib import Path

from bite_ingestion.interfaces.operator import OperatorId
from bite_ingestion.operators import (
    CutOperator,
    IntegrateOperator,
    ReduceOperator,
    UntangleOperator,
    apply_operator,
)
from bite_ingestion.operators.base import packet_digest

FIXTURES = Path(__file__).resolve().parents[2] / "output" / "operator-fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_each_operator_deterministic():
    cases = [
        (CutOperator(), _load("cut_paragraph.json"), {"boundary": "paragraph"}),
        (UntangleOperator(), _load("untangle_mixed.json"), None),
        (ReduceOperator(), _load("reduce_dupes.json"), None),
        (IntegrateOperator(), _load("integrate_keys.json"), {"integrate_mode": "deterministic_join"}),
    ]
    for op, pkt, ctx in cases:
        a = op.apply(pkt, ctx)
        b = op.apply(pkt, ctx)
        assert packet_digest(a) == packet_digest(b), op.id


def test_property_style_several_packets():
    packets = [
        _load("cut_paragraph.json"),
        _load("cut_lines.json"),
        _load("untangle_mixed.json"),
        _load("reduce_dupes.json"),
        _load("integrate_keys.json"),
        _load("minimal_scaffold.json"),
    ]
    ops = [OperatorId.CUT, OperatorId.UNTANGLE, OperatorId.REDUCE, OperatorId.INTEGRATE]
    for pkt in packets:
        for op in ops:
            ctx = {"boundary": "line"} if op == OperatorId.CUT else None
            a = apply_operator(op, pkt, ctx)
            b = apply_operator(op, pkt, ctx)
            assert packet_digest(a) == packet_digest(b)
            assert a["tau"]["steps"][-1]["mode"] == "deterministic"
