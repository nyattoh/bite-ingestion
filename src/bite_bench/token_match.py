"""Frozen Phase-1C token-length matching rule.

The rule was selected using *calibration seeds 0..11 only*.  Holdout seeds
12..23 must not be used to change these constants.  If they are changed after
holdout inspection, bump the freeze revision and treat the old holdout as spent.
"""

from __future__ import annotations

TOKEN_MATCH_FREEZE_REVISION = "phase1c-token-match-v0.1"
TOKEN_MATCH_LEFT = "prose_narrative"
TOKEN_MATCH_RIGHT = "table_csv"
TOKEN_MATCH_MAX_ABS_DELTA = 3
TOKEN_MATCH_MAX_RELATIVE_DELTA = 0.04


def relative_token_delta(left_tokens: int, right_tokens: int) -> float:
    """Symmetric relative token-count difference."""
    if left_tokens < 0 or right_tokens < 0:
        raise ValueError("token counts must be non-negative")
    mean = (left_tokens + right_tokens) / 2.0
    if mean == 0:
        return 0.0
    return abs(left_tokens - right_tokens) / mean


def token_length_match(left_tokens: int, right_tokens: int) -> bool:
    """Return whether a pair satisfies the pre-holdout frozen tolerance."""
    return (
        abs(left_tokens - right_tokens) <= TOKEN_MATCH_MAX_ABS_DELTA
        and relative_token_delta(left_tokens, right_tokens)
        <= TOKEN_MATCH_MAX_RELATIVE_DELTA
    )
