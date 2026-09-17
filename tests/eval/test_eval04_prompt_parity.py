"""EVAL-04 regression tests: prompt parity across arms.

Verifies:
1. Unified wrapper: raw and all arms use identical prompt templates
2. Fixed overhead test: empty payload measures wrapper-only tokens
3. Separate measurement: payload tokens vs total tokens tracked independently
4. No-op detection: transformations that don't change payload are flagged

Phase 0 requirement: ensure fair comparison by eliminating wrapper differences.
"""

from __future__ import annotations

import pytest

from bite_eval.accounting.estimate import estimate_tokens_char4
from bite_eval.pilot.billed_runner import (
    _build_messages,
    _transform_packet,
)


def test_wrapper_parity_raw_vs_compressed():
    """EVAL-04: raw_full and compressed_passthrough must use identical wrappers.

    The only difference should be payload content, not prompt structure.
    Previously: raw used "Document:" and compressed used "Compressed document:"
    causing a 2-token wrapper bias in every comparison.
    """
    # Use identical payload for both arms to isolate wrapper comparison
    packet = {
        "instance_id": "parity-001",
        "document": "Test content.",
        "query": "What?",
        "gold_answer": "answer",
        "family": "test",
    }

    raw_transformed = _transform_packet(packet, "raw_full")
    comp_transformed = _transform_packet(packet, "compressed_passthrough")

    # Build messages for both
    raw_messages = _build_messages(raw_transformed, "What?")
    comp_messages = _build_messages(comp_transformed, "What?")

    # Extract user message content
    raw_user = raw_messages[1]["content"]
    comp_user = comp_messages[1]["content"]

    # EVAL-04: Wrapper structure must be identical
    # Both should use "Document:" prefix (not "Compressed document:")
    assert "Document:" in raw_user
    assert "Document:" in comp_user, (
        "EVAL-04: compressed arm must use same 'Document:' wrapper as raw, "
        f"not 'Compressed document:'. Got: {comp_user[:50]}"
    )

    # Verify no "Compressed document:" appears
    assert "Compressed document:" not in comp_user, (
        "EVAL-04: wrapper parity broken - compressed uses different prefix"
    )

    # System message must also be identical
    assert raw_messages[0]["content"] == comp_messages[0]["content"]


def test_empty_payload_overhead():
    """EVAL-04: Empty payload measures fixed wrapper overhead.

    With empty document, total tokens = wrapper tokens only.
    This baseline lets us separate payload contribution from wrapper contribution.
    """
    empty_packet = {
        "instance_id": "overhead-001",
        "document": "",  # Empty payload
        "query": "What is X?",
        "gold_answer": "none",
        "family": "test",
    }

    for method in ["raw_full", "compressed_passthrough"]:
        transformed = _transform_packet(empty_packet, method)
        messages = _build_messages(transformed, "What is X?")

        # Concatenate all message text
        full_text = " ".join(msg["content"] for msg in messages)

        # Estimate wrapper overhead (char/4 proxy)
        wrapper_tokens_proxy = estimate_tokens_char4(full_text)

        # EVAL-04: Wrapper overhead should be measurable and identical across arms
        assert wrapper_tokens_proxy > 0, (
            f"Empty payload should still have wrapper tokens for {method}"
        )

        # Store for cross-arm comparison
        if method == "raw_full":
            raw_overhead = wrapper_tokens_proxy
        else:
            comp_overhead = wrapper_tokens_proxy

    # EVAL-04: Fixed overhead must be identical between arms
    assert raw_overhead == comp_overhead, (
        f"EVAL-04: Wrapper overhead differs between arms: "
        f"raw={raw_overhead}, compressed={comp_overhead}. "
        "This breaks fair comparison."
    )


def test_payload_vs_total_token_separation():
    """EVAL-04: Payload tokens and total tokens must be tracked separately.

    total_tokens = wrapper_tokens + payload_tokens

    This separation is required to detect wrapper differences and measure
    actual payload reduction independent of prompt template choice.
    """
    packet = {
        "instance_id": "separation-001",
        "document": "A" * 100,  # Known payload size
        "query": "Question?",
        "gold_answer": "answer",
        "family": "test",
    }

    transformed = _transform_packet(packet, "raw_full")
    messages = _build_messages(transformed, "Question?")

    # Calculate total tokens (wrapper + payload)
    full_text = " ".join(msg["content"] for msg in messages)
    total_tokens_proxy = estimate_tokens_char4(full_text)

    # Calculate payload-only tokens
    payload_text = transformed.payload_text
    payload_tokens_proxy = estimate_tokens_char4(payload_text)

    # Calculate wrapper-only tokens (total - payload)
    wrapper_tokens_proxy = total_tokens_proxy - payload_tokens_proxy

    # EVAL-04: All three measurements should be available
    assert payload_tokens_proxy > 0, "Payload tokens must be measurable"
    assert wrapper_tokens_proxy > 0, "Wrapper tokens must be measurable"
    assert total_tokens_proxy > payload_tokens_proxy, (
        "Total tokens must exceed payload tokens (wrapper overhead exists)"
    )

    # EVAL-04: Wrapper should be a reasonable fraction (not dominant)
    wrapper_fraction = wrapper_tokens_proxy / total_tokens_proxy
    assert 0.05 < wrapper_fraction < 0.95, (
        f"Wrapper fraction {wrapper_fraction:.2f} looks suspicious"
    )


def test_no_op_transformation_detection():
    """EVAL-04: Detect when a transformation is a no-op.

    No-op cases:
    1. Transformation returns identical payload to raw (when it shouldn't)
    2. Wrapper that adds nothing (empty overhead)
    3. Two arms produce identical prompts (dedupe needed)
    """
    # Case 1: compressed_passthrough with short doc is a no-op
    short_packet = {
        "instance_id": "noop-001",
        "document": "Short doc.",  # Under 400 chars
        "query": "What?",
        "family": "test",
    }

    raw_t = _transform_packet(short_packet, "raw_full")
    comp_t = _transform_packet(short_packet, "compressed_passthrough")

    # EVAL-04: Payloads are identical (no-op transformation)
    payload_identical = raw_t.payload_text == comp_t.payload_text
    assert payload_identical, (
        "Expected no-op: short doc should not be transformed by compressed_passthrough"
    )

    # Build full prompts
    raw_msg = _build_messages(raw_t, "What?")
    comp_msg = _build_messages(comp_t, "What?")

    raw_full_text = " ".join(m["content"] for m in raw_msg)
    comp_full_text = " ".join(m["content"] for m in comp_msg)

    # EVAL-04: After wrapper unification, full prompts should also be identical for no-op
    prompts_identical = raw_full_text == comp_full_text
    assert prompts_identical, (
        "EVAL-04: No-op transformation with unified wrapper should produce "
        "identical prompts. If not, wrapper parity is broken."
    )

    # No-op must be machine-readable, not only free text in a note.
    assert comp_t.is_no_op is True, (
        "EVAL-04: a transformation that removed nothing must set is_no_op=True"
    )
    assert raw_t.is_no_op is True
    assert comp_t.omitted_unit_ids == [], "no-op must not omit any unit"


def test_no_op_detection_with_truncation():
    """EVAL-04: Detect when truncation actually changes payload vs no-op.

    Distinguishes real transformation from pass-through.
    """
    # Long doc: should be transformed
    long_packet = {
        "instance_id": "noop-002",
        "document": "A" * 500,  # Over 400 chars
        "query": "What?",
        "family": "test",
    }

    raw_t = _transform_packet(long_packet, "raw_full")
    comp_t = _transform_packet(long_packet, "compressed_passthrough")

    # EVAL-04: Payloads should differ (actual transformation occurred)
    payload_differs = raw_t.payload_text != comp_t.payload_text
    assert payload_differs, (
        "Long doc should be truncated by compressed_passthrough, "
        "producing different payload than raw_full"
    )

    # Real transformation must be machine-readable, not only free text.
    assert comp_t.is_no_op is False, "A transformation that removed a unit must set is_no_op=False"
    assert raw_t.is_no_op is True, "raw_full never removes anything"

    # Verify R entry exists for truncated content
    assert len(comp_t.recovery_index["entries"]) > 0, (
        "Truncated content must be in R (recovery index)"
    )
    # Every omitted unit id must appear in R under its ORIGINAL id.
    r_ids = {e["unit_id"] for e in comp_t.recovery_index["entries"]}
    assert set(comp_t.omitted_unit_ids) == r_ids, (
        "omitted units must land in R under their original unit_ids"
    )
    assert not (set(comp_t.visible_unit_ids) & r_ids), (
        "a unit cannot be both visible and recovered-only"
    )


def test_wrapper_overhead_is_measurable_artifact():
    """EVAL-04: Wrapper overhead should be reportable as artifact metadata.

    For each pilot run, we should be able to report:
    - wrapper_tokens (fixed overhead)
    - payload_tokens_before (input document)
    - payload_tokens_after (transformed payload)
    - total_tokens (wrapper + payload_after)
    """
    packet = {
        "instance_id": "artifact-001",
        "document": "B" * 200,
        "query": "Q?",
        "family": "test",
    }

    methods = ["raw_full", "compressed_passthrough"]
    overhead_report = {}

    for method in methods:
        transformed = _transform_packet(packet, method)
        messages = _build_messages(transformed, "Q?")

        # Measure components
        full_text = " ".join(m["content"] for m in messages)
        total_tok = estimate_tokens_char4(full_text)
        payload_tok = estimate_tokens_char4(transformed.payload_text)
        wrapper_tok = total_tok - payload_tok

        overhead_report[method] = {
            "wrapper_tokens": wrapper_tok,
            "payload_tokens": payload_tok,
            "total_tokens": total_tok,
        }

    # EVAL-04: Both arms should have identical wrapper overhead
    assert (
        overhead_report["raw_full"]["wrapper_tokens"]
        == overhead_report["compressed_passthrough"]["wrapper_tokens"]
    ), f"EVAL-04: Wrapper overhead mismatch: {overhead_report}"

    # EVAL-04: Report should be structured for artifact output
    for method, report in overhead_report.items():
        assert all(k in report for k in ["wrapper_tokens", "payload_tokens", "total_tokens"])
        assert report["total_tokens"] == report["wrapper_tokens"] + report["payload_tokens"]


def test_regression_bite15b_wrapper_bias():
    """EVAL-04 REGRESSION: BITE-15b had 2-token wrapper bias.

    Original v2 pilot results:
    - mean(T_raw - T_comp) = -2 (compressed always 2 tokens MORE than raw)
    - 0 cases where compressed < raw

    Root cause: raw used "Document:" (1 token), compressed used "Compressed
    document:" (3 tokens), causing systematic 2-token bias favoring raw.

    This test ensures the fix prevents recurrence.
    """
    # Replicate BITE-15b condition: short synthetic doc (no actual compression)
    packet = {
        "instance_id": "bite15b-replica",
        "document": "K01=100\nK02=150",  # Typical dependency_chain size (~13 chars)
        "query": "What is K01?",
        "gold_answer": "100",
        "family": "dependency_chain",
    }

    raw_t = _transform_packet(packet, "raw_full")
    comp_t = _transform_packet(packet, "compressed_passthrough")

    # Payloads should be identical (no truncation at 13 chars)
    assert raw_t.payload_text == comp_t.payload_text

    # Build prompts
    raw_msg = _build_messages(raw_t, "What is K01?")
    comp_msg = _build_messages(comp_t, "What is K01?")

    raw_text = " ".join(m["content"] for m in raw_msg)
    comp_text = " ".join(m["content"] for m in comp_msg)

    # EVAL-04: Token counts should be identical (no wrapper bias)
    raw_tokens = estimate_tokens_char4(raw_text)
    comp_tokens = estimate_tokens_char4(comp_text)

    assert raw_tokens == comp_tokens, (
        f"EVAL-04 REGRESSION: Wrapper bias detected. "
        f"raw_tokens={raw_tokens}, comp_tokens={comp_tokens}, "
        f"delta={comp_tokens - raw_tokens}. "
        "Original BITE-15b had delta=-2 due to 'Compressed document:' prefix. "
        "After fix, delta should be 0 for identical payloads."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
