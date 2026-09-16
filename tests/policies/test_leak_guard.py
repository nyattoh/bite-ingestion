"""Leak guard: forbidden oracle/eval keys."""

from __future__ import annotations

import pytest

from bite_ingestion.policies.leak_guard import (
    OracleLeakError,
    assert_no_oracle_leak,
    check_leak,
    is_forbidden_key,
)
from bite_ingestion.policies.rule_policy import RulePolicy


def test_forbidden_key_detection():
    assert is_forbidden_key("gold_route")
    assert is_forbidden_key("oracle_m")
    assert is_forbidden_key("eval_visible_recall")
    assert is_forbidden_key("oracle_anything")
    assert not is_forbidden_key("b")
    assert not is_forbidden_key("pre_segmented")


def test_assert_raises():
    with pytest.raises(OracleLeakError):
        assert_no_oracle_leak({"b": 0.1, "gold_route": ["CUT"]})


def test_rule_policy_rejects_leak():
    pol = RulePolicy()
    with pytest.raises(OracleLeakError):
        pol.propose({"b": 0.2, "eval_visible_recall": 1.0}, {})


def test_check_leak_list():
    found = check_leak({"oracle_route": "x", "b": 0.1}, None, {"gold_sequence": []})
    assert "oracle_route" in found
    assert "gold_sequence" in found
