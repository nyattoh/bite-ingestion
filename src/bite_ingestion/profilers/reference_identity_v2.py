"""Exact full-key reference identity v2 (Phase 4E).

Does not change reference_identity_v1. Dotted and hyphenated configuration
keys are one identifier. No component / prefix / suffix / substring emit.
"""

from __future__ import annotations

import re

from bite_ingestion.profilers.reference_identity_v1 import (
    is_identifier,
    join_span_count,
    mask_join_spans,
)

FULL_KEY_GRAMMAR = r"[A-Za-z_][A-Za-z0-9_]*(?:[.-][A-Za-z0-9_]+)*"
_FULL_KEY = re.compile(FULL_KEY_GRAMMAR)


def full_key_match(text: str) -> str | None:
    stripped = text.strip()
    if _FULL_KEY.fullmatch(stripped) and is_identifier(stripped):
        return stripped
    return None


def maximal_full_keys(text: str) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for match in _FULL_KEY.finditer(text):
        atom = match.group(0)
        if is_identifier(atom) and atom not in seen:
            seen.add(atom)
            out.append(atom)
    return tuple(out)


def target_tokens(key_text: str) -> tuple[str, ...]:
    """Complete logical key only. Do not tokenize into components."""
    matched = full_key_match(key_text)
    if matched is None:
        return ()
    return (matched,)


def source_tokens(value_text: str) -> tuple[str, ...]:
    return maximal_full_keys(mask_join_spans(value_text))


__all__ = [
    "FULL_KEY_GRAMMAR",
    "full_key_match",
    "join_span_count",
    "mask_join_spans",
    "maximal_full_keys",
    "source_tokens",
    "target_tokens",
]
