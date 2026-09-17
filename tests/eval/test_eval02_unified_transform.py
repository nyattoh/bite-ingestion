"""EVAL-02 (span-corrected): prompt body and visible ids share one unit graph.

Supersedes the first EVAL-02 revision, whose regression tests froze an
incorrect specification. The retired assertions were:

- ``test_bug1_truncation_preserves_visible_evidence_recall`` required
  ``recall_vis == 1.0`` after truncating ``"A" * 500``, on the stated
  assumption that "the visible evidence is usually in the first part of the
  document". That makes an evidence id visible while its body is outside the
  payload — a false-positive recall.
- The truncated remainder was given a **fresh synthetic** unit id, so it could
  never intersect ``gold_evidence_ids`` and recoverable recall could not
  credit it either.

The corrected contract is span-based:

    span fully inside payload  -> visible, absent from R
    span crosses the cut point -> not visible, in R under its ORIGINAL id
"""

from __future__ import annotations

import pytest

from bite_eval.pilot.billed_runner import (
    _build_messages,
    _transform_packet,
    _visible_for_method,
)
from bite_eval.pilot.constraints import metrics_from_instance
from bite_ingestion.packet_contract import PacketContractError, make_unit

SRC = "synthetic://eval02"


def _packet_with_evidence_at(start: int, *, doc_len: int = 500, ev: str = "SECRET=99"):
    """Document of ``doc_len`` filler chars with one evidence unit at ``start``."""
    filler = "A" * doc_len
    doc = filler[:start] + ev + filler[start + len(ev) :]
    return {
        "instance_id": "eval02-case",
        "family": "test",
        "document": doc,
        "query": "What?",
        "gold_answer": "99",
        "gold_evidence_ids": ["ev-1"],
        "recoverable_evidence_ids": [],
        "units": [
            make_unit(
                unit_id="ev-1",
                text=ev,
                start=start,
                end=start + len(ev),
                source_uri=SRC,
            )
        ],
    }


def _metrics_for(packet, transformed, answer="99"):
    working = dict(packet)
    working["recoverable_evidence_ids"] = [
        e["unit_id"] for e in transformed.recovery_index.get("entries", [])
    ]
    working["provenance_complete_rate"] = transformed.provenance_complete_rate
    return metrics_from_instance(working, transformed.visible_unit_ids, answer=answer)


# --------------------------------------------------------------------------
# Required behaviour 1: evidence before the cut point
# --------------------------------------------------------------------------


def test_evidence_before_cut_point_stays_visible():
    packet = _packet_with_evidence_at(10)
    t = _transform_packet(packet, "compressed_passthrough")

    assert t.visible_unit_ids == ["ev-1"]
    assert t.omitted_unit_ids == []
    assert t.recovery_index["entries"] == [], "nothing was cut, R must stay empty"

    m = _metrics_for(packet, t)
    assert m["evidence_recall_visible"] == 1.0
    assert m["evidence_recall_recoverable"] == 1.0


# --------------------------------------------------------------------------
# Required behaviour 2: evidence after the cut point
# --------------------------------------------------------------------------


def test_evidence_after_cut_point_moves_to_R_under_original_id():
    packet = _packet_with_evidence_at(450)  # beyond the 400-char budget
    t = _transform_packet(packet, "compressed_passthrough")

    assert t.visible_unit_ids == [], "evidence outside the payload is not visible"
    assert t.omitted_unit_ids == ["ev-1"]

    r_ids = [e["unit_id"] for e in t.recovery_index["entries"]]
    assert r_ids == ["ev-1"], (
        "the omitted unit must keep its ORIGINAL id in R; a fresh synthetic id "
        "can never intersect gold_evidence_ids"
    )

    m = _metrics_for(packet, t)
    assert m["evidence_recall_visible"] == 0.0
    assert m["evidence_recall_recoverable"] == 1.0


def test_evidence_straddling_cut_point_is_not_visible():
    """Partial survival is omission — never 'probably still there'."""
    packet = _packet_with_evidence_at(396)  # spans 396..405, cut at 400
    t = _transform_packet(packet, "compressed_passthrough")
    assert t.visible_unit_ids == []
    assert t.omitted_unit_ids == ["ev-1"]


# --------------------------------------------------------------------------
# Required behaviour 3: every visible unit really occurs in the payload
# --------------------------------------------------------------------------


@pytest.mark.parametrize("start", [0, 10, 200, 390, 450, 480])
def test_visible_units_are_present_in_payload(start):
    packet = _packet_with_evidence_at(start)
    for method in ("raw_full", "compressed_passthrough"):
        t = _transform_packet(packet, method)
        units = {u["unit_id"]: u for u in packet["units"]}
        for uid in t.visible_unit_ids:
            body = units[uid]["text"]
            assert body in t.payload_text, (
                f"{method}: unit {uid} is visible by id but its body is not in the payload"
            )


def test_visible_and_recovered_sets_are_disjoint():
    packet = _packet_with_evidence_at(450)
    t = _transform_packet(packet, "compressed_passthrough")
    r_ids = {e["unit_id"] for e in t.recovery_index["entries"]}
    assert not (set(t.visible_unit_ids) & r_ids)


# --------------------------------------------------------------------------
# Prompt / visible ids come from the same object
# --------------------------------------------------------------------------


def test_prompt_and_visible_ids_from_same_transform():
    packet = _packet_with_evidence_at(450)
    t = _transform_packet(packet, "compressed_passthrough")
    messages = _build_messages(t, str(packet["query"]))
    user = messages[1]["content"]

    assert t.payload_text in user
    assert _visible_for_method(t) == t.visible_unit_ids
    # The omitted body must be absent from the prompt we actually send.
    assert "SECRET=99" not in user


def test_raw_full_shows_every_unit():
    packet = _packet_with_evidence_at(450)
    t = _transform_packet(packet, "raw_full")
    assert t.visible_unit_ids == ["ev-1"]
    assert t.omitted_unit_ids == []
    assert t.is_no_op is True
    assert t.payload_text == packet["document"]


def test_operator_trace_records_omitted_refs():
    packet = _packet_with_evidence_at(450)
    t = _transform_packet(packet, "compressed_passthrough")
    step = t.operator_trace["steps"][-1]
    assert step["op"] == "compressed_passthrough"
    assert step["outputs_ref"] == t.visible_unit_ids
    assert step["omitted_ref"] == ["ev-1"]
    assert step["extra"]["no_op"] is False


def test_provenance_is_measured_not_declared():
    packet = _packet_with_evidence_at(10)
    t = _transform_packet(packet, "raw_full")
    assert t.provenance_complete_rate == 1.0

    # Strip provenance from the unit: the measured rate must drop.
    stripped = dict(packet)
    unit = dict(packet["units"][0])
    unit.pop("provenance")
    stripped["units"] = [unit]
    t2 = _transform_packet(stripped, "raw_full")
    assert t2.provenance_complete_rate == 0.0, (
        "provenance must be measured from the unit graph, not self-reported"
    )


# --------------------------------------------------------------------------
# Fail-closed
# --------------------------------------------------------------------------


def test_gold_evidence_without_unit_body_fails_closed():
    """An evidence id with no unit is a contract violation, not a warning."""
    packet = {
        "instance_id": "dangling",
        "document": "some text",
        "query": "q",
        "gold_answer": "x",
        "gold_evidence_ids": ["ghost-1"],
    }
    with pytest.raises(PacketContractError):
        _transform_packet(packet, "raw_full")


def test_dangling_evidence_id_against_real_units_fails_closed():
    packet = _packet_with_evidence_at(10)
    packet["gold_evidence_ids"] = ["ev-1", "ghost-2"]
    with pytest.raises(PacketContractError):
        _transform_packet(packet, "raw_full")


def test_unit_text_not_matching_document_fails_closed():
    packet = _packet_with_evidence_at(10)
    bad = dict(packet["units"][0])
    bad["text"] = "NOT-WHAT-IS-THERE"
    packet["units"] = [bad]
    with pytest.raises(PacketContractError):
        _transform_packet(packet, "raw_full")


def test_packet_without_evidence_ids_gets_whole_document_unit():
    """Legacy eval packets (document only) stay usable and resolvable."""
    packet = {"instance_id": "legacy", "document": "Short doc.", "query": "q"}
    t = _transform_packet(packet, "raw_full")
    assert len(t.visible_unit_ids) == 1
    assert t.payload_text == "Short doc."
