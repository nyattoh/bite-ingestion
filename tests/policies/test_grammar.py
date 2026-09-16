"""Grammar: normal-form enumeration and rejection of illegal sequences."""

from __future__ import annotations

import pytest

from bite_ingestion.interfaces.operator import OperatorId
from bite_ingestion.policies.grammar import (
    GrammarError,
    enumerate_legal_sequences,
    is_normal_form,
    validate_sequence,
)


def test_enumerate_all_normal_form_and_count():
    legal = enumerate_legal_sequences()
    assert len(legal) == 15  # 2^4 - 1
    for seq in legal:
        assert is_normal_form(seq)
        assert validate_sequence(seq) == seq


def test_illegal_empty():
    assert not is_normal_form(())
    with pytest.raises(GrammarError):
        validate_sequence([])


def test_illegal_repeat_loop():
    assert not is_normal_form([OperatorId.CUT, OperatorId.CUT])
    with pytest.raises(GrammarError):
        validate_sequence([OperatorId.REDUCE, OperatorId.REDUCE])


def test_illegal_oscillation_integrate_then_cut():
    bad = [OperatorId.INTEGRATE, OperatorId.CUT]
    assert not is_normal_form(bad)
    with pytest.raises(GrammarError):
        validate_sequence(bad)


def test_illegal_wrong_order_reduce_untangle():
    # Allowed in some OUTLINE examples historically, but v0.1 normal-form lock rejects.
    bad = [OperatorId.REDUCE, OperatorId.UNTANGLE]
    assert not is_normal_form(bad)
    with pytest.raises(GrammarError):
        validate_sequence(bad)


def test_string_coercion():
    assert validate_sequence(["CUT", "REDUCE"]) == (
        OperatorId.CUT,
        OperatorId.REDUCE,
    )
