"""Exact reference identity v1 (Phase 3T).

Target tokens are maximal full identifiers only. No underscore suffix
expansion, substring, prefix, or case folding.
"""

from __future__ import annotations

import re

from bite_ingestion.profilers.dependency_dispersion import STOPWORDS

_ATOM = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_JOIN_SPAN = re.compile(r"\b(?:id|key)\s*=\s*[A-Za-z0-9_\-.]+", re.IGNORECASE)


def is_identifier(atom: str) -> bool:
    if atom.casefold() in STOPWORDS:
        return False
    if atom.isdigit():
        return False
    return len(atom) >= 4 or ("_" in atom)


def maximal_identifiers(text: str) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for match in _ATOM.finditer(text):
        atom = match.group(0)
        if is_identifier(atom) and atom not in seen:
            seen.add(atom)
            out.append(atom)
    return tuple(out)


def _blank_span(match: re.Match[str]) -> str:
    return " " * len(match.group(0))


def mask_join_spans(value: str) -> str:
    return _JOIN_SPAN.sub(_blank_span, value)


def join_span_count(text: str) -> int:
    return len(_JOIN_SPAN.findall(text))


def target_tokens(key_text: str) -> tuple[str, ...]:
    """KV key / JSON k full tokens only. Do not expand underscore suffixes."""
    return maximal_identifiers(key_text)


def source_tokens(value_text: str) -> tuple[str, ...]:
    return maximal_identifiers(mask_join_spans(value_text))
