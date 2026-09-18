from __future__ import annotations

import pytest

from bite_bench.token_match import (
    TOKEN_MATCH_LEFT,
    TOKEN_MATCH_MAX_ABS_DELTA,
    TOKEN_MATCH_MAX_RELATIVE_DELTA,
    TOKEN_MATCH_RIGHT,
    relative_token_delta,
    token_length_match,
)


def test_phase1c_pair_is_frozen_before_holdout() -> None:
    assert (TOKEN_MATCH_LEFT, TOKEN_MATCH_RIGHT) == ("prose_narrative", "table_csv")
    assert TOKEN_MATCH_MAX_ABS_DELTA == 3
    assert TOKEN_MATCH_MAX_RELATIVE_DELTA == 0.04


def test_match_accepts_calibration_boundary_shape() -> None:
    assert token_length_match(82, 79)
    assert relative_token_delta(82, 79) < 0.04


def test_match_rejects_large_absolute_gap() -> None:
    assert not token_length_match(100, 96)


def test_match_rejects_large_relative_gap_even_if_small_absolute() -> None:
    assert not token_length_match(10, 7)


def test_zero_and_negative_handling() -> None:
    assert token_length_match(0, 0)
    with pytest.raises(ValueError):
        relative_token_delta(-1, 2)
