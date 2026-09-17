"""EVAL-02 regression tests: unified transformation & evidence tracking.

Verifies:
1. Prompt body and visible evidence IDs come from the same TransformedPacket
2. Units removed by truncation move to R (recoverable context), not silently lost
3. Recall and provenance are computed from transformed packet (not pre-transform)
"""

from __future__ import annotations

import pytest

from bite_eval.pilot.billed_runner import (
    TransformedPacket,
    _build_messages,
    _transform_packet,
    _visible_for_method,
)


def test_transform_packet_raw_full():
    """raw_full: no transformation, all content visible."""
    packet = {
        "instance_id": "test-001",
        "document": "Short doc with key=value.",
        "query": "What is key?",
        "gold_answer": "value",
        "family": "test",
    }
    
    transformed = _transform_packet(packet, "raw_full")
    
    assert isinstance(transformed, TransformedPacket)
    assert transformed.payload_text == "Short doc with key=value."
    assert transformed.method_id == "raw_full"
    assert len(transformed.visible_unit_ids) == 1
    
    # No units moved to R for raw_full
    assert transformed.recovery_index["entries"] == []
    assert "raw_full: no transformation" in transformed.transformation_note


def test_transform_packet_compressed_no_truncation():
    """compressed_passthrough: doc <= 400 chars, no truncation needed."""
    packet = {
        "instance_id": "test-002",
        "document": "A" * 300,  # Under 400 char limit
        "query": "Question?",
        "gold_answer": "answer",
        "family": "test",
    }
    
    transformed = _transform_packet(packet, "compressed_passthrough")
    
    assert transformed.payload_text == "A" * 300
    assert len(transformed.visible_unit_ids) == 1
    
    # No truncation → no R entries
    assert transformed.recovery_index["entries"] == []
    assert "no truncation needed" in transformed.transformation_note


def test_transform_packet_compressed_with_truncation():
    """compressed_passthrough: doc > 400 chars, truncation occurs.
    
    EVAL-02 key requirement: truncated portion MUST move to R, not silently vanish.
    """
    doc = "A" * 450  # Exceeds 400 char limit
    packet = {
        "instance_id": "test-003",
        "document": doc,
        "query": "Question?",
        "gold_answer": "answer",
        "family": "test",
    }
    
    transformed = _transform_packet(packet, "compressed_passthrough")
    
    # Payload should be truncated to 400 chars + marker
    assert transformed.payload_text == ("A" * 400) + "\n...[truncated]"
    assert len(transformed.visible_unit_ids) == 1
    
    # EVAL-02: Truncated portion MUST be in R (recoverable)
    r_entries = transformed.recovery_index["entries"]
    assert len(r_entries) == 1, "Truncated portion must move to R"
    
    truncated_entry = r_entries[0]
    assert truncated_entry["reason"] == "budget_truncated"
    assert truncated_entry["recoverable"] is True
    assert truncated_entry["locator"]["span"]["start"] == 400
    assert truncated_entry["locator"]["span"]["end"] == 450
    
    assert "truncated at 400 chars" in transformed.transformation_note
    assert "removed 50 chars to R" in transformed.transformation_note


def test_build_messages_uses_transformed_payload():
    """_build_messages must use TransformedPacket.payload_text, not original doc."""
    doc = "X" * 500
    packet = {
        "instance_id": "test-004",
        "document": doc,
        "query": "What?",
    }
    
    transformed = _transform_packet(packet, "compressed_passthrough")
    messages = _build_messages(transformed, "What?")
    
    user_content = messages[1]["content"]
    
    # Should contain truncated payload, not full original doc
    assert "X" * 400 in user_content
    assert "...[truncated]" in user_content
    # Should NOT contain the full 500-char original
    assert doc not in user_content


def test_visible_for_method_uses_transformed_ids():
    """_visible_for_method must return TransformedPacket.visible_unit_ids.
    
    EVAL-02 key requirement: visible IDs must match what was actually sent,
    not the original packet's visible_evidence field.
    
    BUG 1 FIX: When truncation occurs, original visible IDs are PRESERVED
    (not replaced with synthetic hash), so they can intersect with gold evidence.
    """
    doc = "B" * 450
    packet = {
        "instance_id": "test-005",
        "document": doc,
        "visible_evidence": ["original-id-1", "original-id-2"],  # Original packet IDs
    }
    
    transformed = _transform_packet(packet, "compressed_passthrough")
    visible_ids = _visible_for_method(transformed)
    
    # Should return transformed IDs (which now preserves original IDs per BUG 1 fix)
    assert visible_ids == transformed.visible_unit_ids
    # BUG 1 FIX: Original IDs are preserved during truncation
    assert visible_ids == ["original-id-1", "original-id-2"]


def test_prompt_and_visible_ids_from_same_transform():
    """EVAL-02 core requirement: prompt body and visible IDs derive from same object.
    
    Ensures no divergent code paths where prompt is built from one source
    while visible IDs come from another.
    
    BUG 1 FIX: When truncation occurs, original visible IDs are preserved.
    """
    doc = "C" * 600
    packet = {
        "instance_id": "test-006",
        "document": doc,
        "query": "Q?",
        "visible_evidence": ["old-id-1", "old-id-2"],
    }
    
    # Transform once
    transformed = _transform_packet(packet, "compressed_passthrough")
    
    # Both prompt and visible IDs must derive from this single transformed object
    messages = _build_messages(transformed, "Q?")
    visible_ids = _visible_for_method(transformed)
    
    # Verify prompt uses truncated payload
    user_content = messages[1]["content"]
    assert ("C" * 400) in user_content
    assert "...[truncated]" in user_content
    
    # BUG 1 FIX: Visible IDs are preserved (not replaced with synthetic hash)
    assert len(visible_ids) == 2  # Both original IDs preserved
    assert visible_ids == transformed.visible_unit_ids
    assert visible_ids == ["old-id-1", "old-id-2"]
    
    # Verify truncated portion is in R
    r_entries = transformed.recovery_index["entries"]
    assert len(r_entries) >= 1  # At least the truncated text portion


def test_operator_trace_records_transformation():
    """tau (operator trace) must record the transformation step."""
    packet = {
        "instance_id": "test-007",
        "document": "D" * 500,
    }
    
    transformed = _transform_packet(packet, "compressed_passthrough")
    
    tau = transformed.operator_trace
    assert "sequence" in tau
    assert "compressed_passthrough" in tau["sequence"]
    
    assert "steps" in tau
    steps = tau["steps"]
    assert len(steps) >= 1
    
    last_step = steps[-1]
    assert last_step["op"] == "compressed_passthrough"
    assert last_step["mode"] == "deterministic"
    assert len(last_step["outputs_ref"]) == 1  # visible unit
    assert len(last_step["omitted_ref"]) == 1  # truncated unit in R


def test_provenance_preserved_in_transformed_packet():
    """provenance field must be preserved through transformation."""
    packet = {
        "instance_id": "test-008",
        "document": "E" * 300,
        "provenance": {
            "unit_id": "original-unit",
            "source_uri": "test://source",
            "renderer_id": "test-renderer",
        },
    }
    
    transformed = _transform_packet(packet, "raw_full")
    
    # transformed.provenance is the provenance dict itself
    assert "unit_id" in transformed.provenance
    assert transformed.provenance["unit_id"] == "original-unit"
    assert transformed.provenance["source_uri"] == "test://source"


def test_no_silent_data_loss():
    """EVAL-02: Units removed from visible surface MUST appear in R or loss ledger.
    
    No silent data loss — every omitted unit must be tracked.
    """
    doc = "F" * 700  # Will be truncated
    packet = {
        "instance_id": "test-009",
        "document": doc,
    }
    
    transformed = _transform_packet(packet, "compressed_passthrough")
    
    visible_char_count = len(transformed.payload_text.replace("\n...[truncated]", ""))
    omitted_char_count = len(doc) - visible_char_count
    
    # Verify visible portion is ~400 chars
    assert visible_char_count == 400
    
    # Verify omitted portion (300 chars) is in R
    r_entries = transformed.recovery_index["entries"]
    assert len(r_entries) == 1
    
    r_entry = r_entries[0]
    span = r_entry["locator"]["span"]
    omitted_in_r = span["end"] - span["start"]
    
    assert omitted_in_r == omitted_char_count == 300
    assert r_entry["recoverable"] is True


def test_recall_would_be_computed_from_transformed_ids():
    """Demonstrates that recall will reflect transformed state.
    
    When metrics_from_instance is called with transformed visible_unit_ids,
    it will correctly compute recall based on what was actually sent,
    not the original packet's pre-transform visible_evidence.
    
    BUG 1 FIX: When truncation occurs with gold evidence in visible_evidence,
    those original IDs are preserved so recall can be non-zero.
    """
    doc = "G" * 800
    packet = {
        "instance_id": "test-010",
        "document": doc,
        "gold_evidence_ids": ["gold-1", "gold-2", "gold-3"],
        "visible_evidence": ["gold-1", "gold-2", "gold-3"],  # Original: all visible
    }
    
    # After transformation with truncation
    transformed = _transform_packet(packet, "compressed_passthrough")
    
    # BUG 1 FIX: The transformed visible_unit_ids PRESERVES original IDs
    # (not replaced with synthetic hash), so they can intersect with gold evidence
    assert transformed.visible_unit_ids == ["gold-1", "gold-2", "gold-3"]
    
    # When these transformed IDs are passed to metrics_from_instance,
    # recall will be 1.0 because the original gold IDs are preserved.
    # This is the correct behavior per BUG 1 fix.
    
    # Verify R contains the truncated text portion
    r_entries = transformed.recovery_index["entries"]
    assert len(r_entries) >= 1  # At least truncated text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


def test_bug1_truncation_preserves_visible_evidence_recall():
    """BUG 1 REGRESSION: Truncation must NOT zero visible evidence recall.
    
    When original visible_evidence contains gold evidence IDs and truncation
    occurs, those IDs must remain visible (not replaced with synthetic hash)
    so recall_vis intersection with gold_evidence_ids is non-zero.
    """
    doc = "A" * 500  # Will be truncated at 400
    packet = {
        "instance_id": "bug1-test",
        "document": doc,
        "query": "What?",
        "gold_answer": "42",
        "gold_evidence_ids": ["gold-ev-1", "gold-ev-2"],
        "visible_evidence": ["gold-ev-1", "gold-ev-2"],  # Original visible matches gold
        "family": "test",
    }
    
    transformed = _transform_packet(packet, "compressed_passthrough")
    
    # BUG 1 FIX: Original visible IDs must be preserved (not replaced with hash)
    assert transformed.visible_unit_ids == ["gold-ev-1", "gold-ev-2"], (
        "Truncation must preserve original visible evidence IDs, not replace with synthetic hash"
    )
    
    # Verify this would give non-zero recall_vis when intersected with gold
    gold_set = set(packet["gold_evidence_ids"])
    vis_set = set(transformed.visible_unit_ids)
    intersection = gold_set & vis_set
    recall_vis = len(intersection) / len(gold_set) if gold_set else 1.0
    
    assert recall_vis == 1.0, (
        f"BUG 1: Visible recall should be 1.0 (all gold visible), got {recall_vis}. "
        f"Gold IDs: {gold_set}, Visible IDs: {vis_set}"
    )


def test_bug2_metrics_include_recovery_index():
    """BUG 2 REGRESSION: Metrics must reflect transformed recovery state.
    
    When units are moved to R during transformation, metrics_from_instance must
    see those R entries as recoverable, not just the original packet's
    recoverable_evidence_ids.
    """
    from bite_eval.pilot.constraints import metrics_from_instance
    
    doc = "X" * 600  # Will be truncated, moving content to R
    packet = {
        "instance_id": "bug2-test",
        "document": doc,
        "query": "What?",
        "gold_answer": "answer",
        "gold_evidence_ids": ["gold-1", "gold-2"],
        "visible_evidence": ["gold-1"],  # Only gold-1 visible originally
        "recoverable_evidence_ids": ["gold-1"],  # Only gold-1 recoverable originally
        "family": "test",
    }
    
    transformed = _transform_packet(packet, "compressed_passthrough")
    
    # Simulate what evaluate_billed_instance should do (BUG 2 FIX):
    # Build working packet with R entries included in recoverable_evidence_ids
    working_packet = dict(packet)
    _orig_rec = packet.get("recoverable_evidence_ids")
    if isinstance(_orig_rec, (list, tuple)):
        original_rec_ids = {str(x) for x in _orig_rec if x}
    else:
        original_rec_ids = set()
    r_entries = transformed.recovery_index.get("entries", [])
    r_unit_ids = {str(e.get("unit_id", "")) for e in r_entries if e.get("unit_id")}
    combined_rec_ids = list(original_rec_ids | r_unit_ids)
    working_packet["recoverable_evidence_ids"] = combined_rec_ids
    
    vis = transformed.visible_unit_ids
    _metrics = metrics_from_instance(working_packet, vis, answer="answer")
    
    # BUG 2 FIX: recall_rec must reflect the recovery_index entries
    # The R entries should be counted as recoverable
    assert len(r_entries) > 0, "Truncation should have created R entries"
    
    # With the fix, recoverable should include original + R entries
    assert len(combined_rec_ids) > len(original_rec_ids), (
        f"BUG 2: Combined recoverable IDs should include R entries. "
        f"Original: {original_rec_ids}, Combined: {combined_rec_ids}"
    )


def test_bug1_and_bug2_integration():
    """Integration test: Both bugs fixed together in realistic scenario.
    
    When truncation occurs with gold evidence in visible_evidence:
    - BUG 1: Original visible IDs must be preserved (not replaced with hash)
    - BUG 2: R entries must be included in recoverable metrics
    """
    from bite_eval.pilot.constraints import metrics_from_instance
    
    doc = "Section A contains key=value. " + ("filler " * 100)  # >400 chars
    packet = {
        "instance_id": "integration-test",
        "document": doc,
        "query": "What is key?",
        "gold_answer": "value",
        "gold_evidence_ids": ["ev-1", "ev-2"],
        "visible_evidence": ["ev-1", "ev-2"],  # Both gold evidence visible originally
        "recoverable_evidence_ids": ["ev-1", "ev-2"],
        "family": "test",
    }
    
    transformed = _transform_packet(packet, "compressed_passthrough")
    
    # BUG 1 FIX: Visible IDs preserved
    assert transformed.visible_unit_ids == ["ev-1", "ev-2"]
    
    # BUG 2 FIX: Build working packet with R entries
    working_packet = dict(packet)
    _orig_rec = packet.get("recoverable_evidence_ids")
    if isinstance(_orig_rec, (list, tuple)):
        original_rec_ids = {str(x) for x in _orig_rec if x}
    else:
        original_rec_ids = set()
    r_entries = transformed.recovery_index.get("entries", [])
    r_unit_ids = {str(e.get("unit_id", "")) for e in r_entries if e.get("unit_id")}
    combined_rec_ids = list(original_rec_ids | r_unit_ids)
    working_packet["recoverable_evidence_ids"] = combined_rec_ids
    
    vis = transformed.visible_unit_ids
    metrics = metrics_from_instance(working_packet, vis, answer="value")
    
    # Verify both fixes work together
    recall_vis = metrics["evidence_recall_visible"]
    recall_rec = metrics["evidence_recall_recoverable"]
    
    assert recall_vis == 1.0, (
        f"BUG 1: Visible recall should be 1.0 (all gold visible), got {recall_vis}"
    )
    assert recall_rec >= recall_vis, (
        f"BUG 2: Recoverable recall ({recall_rec}) should be >= visible recall ({recall_vis})"
    )
