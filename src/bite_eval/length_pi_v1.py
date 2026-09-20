"""length_pi_v1 — prefix truncation on token length and position only.

Must not inspect keys, values, identities, duplicates, anomalies,
joinability, BITE features, or gold.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

PrefixFn = Callable[[str, int], int]
CountFn = Callable[[str], int]


def apply_length_pi_v1(
    payload: str,
    budget: int,
    *,
    payload_tokens: CountFn,
    prefix_char_end: PrefixFn,
) -> dict[str, Any]:
    adapter_tokens = int(payload_tokens(payload))
    target = int(budget)
    if target >= adapter_tokens:
        visible = payload
        sidecar = ""
        applicable = False
        no_reduction = True
        boundary = len(payload)
    else:
        boundary = int(prefix_char_end(payload, target))
        if boundary < 0 or boundary > len(payload):
            raise ValueError("prefix_char_end out of range")
        visible = payload[:boundary]
        sidecar = payload[boundary:]
        applicable = True
        no_reduction = False
    if visible + sidecar != payload:
        raise ValueError("length_pi_v1 rewrote retained text")
    sidecar_bytes = sidecar.encode("utf-8")
    return {
        "visible": visible,
        "sidecar": sidecar,
        "target_budget_tokens": target,
        "adapter_only_tokens": adapter_tokens,
        "actual_visible_tokens": int(payload_tokens(visible)),
        "budget_slack_tokens": max(0, target - int(payload_tokens(visible))),
        "visible_char_boundary": boundary,
        "sidecar_bytes": len(sidecar_bytes),
        "sidecar_tokens": int(payload_tokens(sidecar)),
        "budget_match_applicable": applicable,
        "bite_expanded_or_no_reduction": no_reduction,
        "adapter_payload_reconstructed": visible + sidecar == payload,
    }


if __name__ == "__main__":

    def _count(text: str) -> int:
        return len(text)

    def _end(text: str, budget: int) -> int:
        return max(0, min(int(budget), len(text)))

    row = apply_length_pi_v1("abcdef", 3, payload_tokens=_count, prefix_char_end=_end)
    assert row["visible"] == "abc" and row["sidecar"] == "def"
    full = apply_length_pi_v1("ab", 9, payload_tokens=_count, prefix_char_end=_end)
    assert full["visible"] == "ab" and full["sidecar"] == ""
    assert full["bite_expanded_or_no_reduction"] is True
    print("length_pi_v1 ok")
