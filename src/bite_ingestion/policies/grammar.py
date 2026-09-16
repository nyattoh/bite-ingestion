"""Normal-form operator-sequence grammar (BITE-02 §3.2).

Legal sequences are non-empty subsequences of:
    CUT? → UNTANGLE? → REDUCE? → INTEGRATE?
each operator at most once; length ≥ 1. Loops and oscillation
(repeated ops, INTEGRATE→CUT, etc.) are rejected.
"""

from __future__ import annotations

from collections.abc import Sequence

from bite_ingestion.interfaces.operator import OperatorId

# Canonical order for normal-form subsequences.
NORMAL_ORDER: tuple[OperatorId, ...] = (
    OperatorId.CUT,
    OperatorId.UNTANGLE,
    OperatorId.REDUCE,
    OperatorId.INTEGRATE,
)

_ORDER_INDEX: dict[OperatorId, int] = {op: i for i, op in enumerate(NORMAL_ORDER)}


class GrammarError(ValueError):
    """Raised when a sequence violates the normal-form grammar."""


def _coerce(op: OperatorId | str) -> OperatorId:
    if isinstance(op, OperatorId):
        return op
    return OperatorId(op)


def is_normal_form(sequence: Sequence[OperatorId | str]) -> bool:
    """Return True iff *sequence* is a non-empty normal-form subsequence."""
    if not sequence:
        return False
    seen: set[OperatorId] = set()
    last_idx = -1
    for raw in sequence:
        try:
            op = _coerce(raw)
        except ValueError:
            return False
        if op not in _ORDER_INDEX:
            return False
        if op in seen:
            return False  # loop / repeat
        idx = _ORDER_INDEX[op]
        if idx <= last_idx:
            return False  # oscillation / wrong order
        seen.add(op)
        last_idx = idx
    return True


def validate_sequence(
    sequence: Sequence[OperatorId | str],
    *,
    normalize: bool = False,
) -> tuple[OperatorId, ...]:
    """Validate (and optionally normalize) a proposed sequence.

    Raises GrammarError on empty, unknown ops, repeats, or non-normal order.
    When normalize=True, coerces strings to OperatorId but does **not**
    reorder — only coerces types after validation.
    """
    if not sequence:
        raise GrammarError("empty operator sequence is forbidden (length ≥ 1)")
    coerced: list[OperatorId] = []
    for raw in sequence:
        try:
            op = _coerce(raw)
        except ValueError as exc:
            raise GrammarError(f"unknown operator: {raw!r}") from exc
        coerced.append(op)
    if not is_normal_form(coerced):
        raise GrammarError(
            f"sequence not in normal form CUT?→UNTANGLE?→REDUCE?→INTEGRATE?: "
            f"{tuple(o.value for o in coerced)}"
        )
    return tuple(coerced)


def normalize_sequence(sequence: Sequence[OperatorId | str]) -> tuple[OperatorId, ...]:
    """Alias: validate and return a typed tuple (no reordering of illegal forms)."""
    return validate_sequence(sequence, normalize=True)


def enumerate_legal_sequences() -> tuple[tuple[OperatorId, ...], ...]:
    """Enumerate all non-empty normal-form subsequences (2^4 - 1 = 15)."""
    n = len(NORMAL_ORDER)
    out: list[tuple[OperatorId, ...]] = []
    for mask in range(1, 1 << n):
        seq = tuple(NORMAL_ORDER[i] for i in range(n) if mask & (1 << i))
        out.append(seq)
    # Stable order: by length then by NORMAL_ORDER bit mask
    out.sort(key=lambda s: (len(s), [_ORDER_INDEX[o] for o in s]))
    return tuple(out)


def drop_later_ops(
    sequence: Sequence[OperatorId],
    max_ops: int,
) -> tuple[OperatorId, ...]:
    """Keep the first *max_ops* ops in normal order (drop later ops first).

    Drop priority when shrinking: INTEGRATE, then REDUCE, then UNTANGLE,
    then CUT — i.e. keep earliest ops in NORMAL_ORDER.
    Guarantees ≥1 when input was non-empty and max_ops ≥ 1.
    """
    if max_ops < 1:
        raise GrammarError("max_ops must be ≥ 1 to keep a non-empty sequence")
    validated = validate_sequence(sequence)
    if len(validated) <= max_ops:
        return validated
    return validated[:max_ops]


def legal_ops() -> frozenset[OperatorId]:
    return frozenset(NORMAL_ORDER)


__all__ = [
    "NORMAL_ORDER",
    "GrammarError",
    "drop_later_ops",
    "enumerate_legal_sequences",
    "is_normal_form",
    "legal_ops",
    "normalize_sequence",
    "validate_sequence",
]
