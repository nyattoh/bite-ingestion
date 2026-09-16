"""Detect oracle / eval leaks into transparent rule-Π inputs.

Transparent policies must NOT accept oracle m-vector keys, gold routes,
or eval coverage fields (BITE-02 / BITE-03 §3.4).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# Exact forbidden keys (morphology or budget/context).
FORBIDDEN_EXACT: frozenset[str] = frozenset(
    {
        "gold_route",
        "gold_sequence",
        "oracle_route",
        "oracle_sequence",
        "oracle_m",
        "oracle_morphology",
        "eval_visible_recall",
        "eval_recoverable_recall",
        "eval_coverage",
        "pi_star",
        "π_star",
        "best_route",
    }
)

# Prefixes that mark oracle / gold / eval-only fields.
FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "oracle_",
    "gold_",
    "eval_",
)


class OracleLeakError(ValueError):
    """Raised when forbidden oracle/eval keys appear on the transparent path."""


def is_forbidden_key(key: str) -> bool:
    if key in FORBIDDEN_EXACT:
        return True
    return any(key.startswith(p) for p in FORBIDDEN_PREFIXES)


def find_forbidden_keys(mapping: Mapping[str, Any] | None) -> list[str]:
    if not mapping:
        return []
    return sorted(k for k in mapping if is_forbidden_key(str(k)))


def assert_no_oracle_leak(
    *mappings: Mapping[str, Any] | None,
    where: str = "morphology/context",
) -> None:
    """Raise OracleLeakError if any forbidden key is present."""
    found: list[str] = []
    for m in mappings:
        found.extend(find_forbidden_keys(m))
    if found:
        uniq = sorted(set(found))
        raise OracleLeakError(
            f"oracle/eval leak into transparent path ({where}): forbidden keys {uniq}"
        )


def check_leak(
    morphology: Mapping[str, Any] | None = None,
    budget: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
) -> list[str]:
    """Return list of forbidden keys (empty if clean). Does not raise."""
    found: list[str] = []
    for m in (morphology, budget, context):
        found.extend(find_forbidden_keys(m))
    return sorted(set(found))


__all__ = [
    "FORBIDDEN_EXACT",
    "FORBIDDEN_PREFIXES",
    "OracleLeakError",
    "assert_no_oracle_leak",
    "check_leak",
    "find_forbidden_keys",
    "is_forbidden_key",
]
