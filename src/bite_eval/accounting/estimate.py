"""Local tokenizer proxy — NOT provider usage (BITE-13)."""

from __future__ import annotations

LOCAL_ESTIMATE_LABEL = "local_char4_proxy"
"""Explicit label: char/4 is a scaffold proxy, not billed provider tokens."""


def estimate_tokens_char4(text: str | None) -> int:
    """Rough local estimate: ceil(len(chars) / 4). Labeled as proxy only.

    Do NOT treat this as provider usage. Prefer provider usage fields when
    an offline stub or future meter supplies them.
    """
    if not text:
        return 0
    n = len(text)
    return (n + 3) // 4


__all__ = ["LOCAL_ESTIMATE_LABEL", "estimate_tokens_char4"]
