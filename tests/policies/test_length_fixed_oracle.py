"""length-Π, fixed-Π, oracle-Π, length-matched pair."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bite_ingestion.interfaces.operator import OperatorId
from bite_ingestion.policies.fixed_policy import FixedPolicy
from bite_ingestion.policies.grammar import GrammarError, is_normal_form
from bite_ingestion.policies.length_policy import LengthOnlyPolicy
from bite_ingestion.policies.oracle_policy import OracleEvalForbiddenError, OraclePolicy
from bite_ingestion.policies.rule_policy import RulePolicy

FIXTURES = Path(__file__).resolve().parents[2] / "output" / "policy-fixtures"


def _vals(seq):
    return [o.value if isinstance(o, OperatorId) else o for o in seq]


def test_length_bands():
    pol = LengthOnlyPolicy()
    assert _vals(pol.propose({}, {"n_tokens": 10})) == ["CUT"]
    assert _vals(pol.propose({}, {"n_tokens": 100})) == ["CUT", "REDUCE"]
    assert _vals(pol.propose({}, {"n_tokens": 500})) == ["CUT", "REDUCE", "INTEGRATE"]


def test_length_ignores_morphology():
    pol = LengthOnlyPolicy()
    m1 = {"b": 0.1, "r": 0.1, "k": 0.1, "a": 0.1, "l": 0.1, "s": 0.0, "p": 0.0, "u": 0.0}
    m2 = {"b": 0.9, "r": 0.9, "k": 0.9, "a": 0.9, "l": 0.1, "s": 0.0, "p": 0.0, "u": 0.0}
    b = {"n_tokens": 200}
    assert pol.propose(m1, b) == pol.propose(m2, b)


def test_length_matched_pair_rule_differs_length_same():
    a = json.loads((FIXTURES / "length_matched_pair_A.json").read_text(encoding="utf-8"))
    b = json.loads((FIXTURES / "length_matched_pair_B.json").read_text(encoding="utf-8"))
    assert a["budget"]["n_tokens"] == b["budget"]["n_tokens"]
    rule = RulePolicy(query_conditioned=True)
    length = LengthOnlyPolicy()
    ra = _vals(rule.propose(a["morphology"], a["budget"]))
    rb = _vals(rule.propose(b["morphology"], b["budget"]))
    la = _vals(length.propose(a["morphology"], a["budget"]))
    lb = _vals(length.propose(b["morphology"], b["budget"]))
    assert ra == a["expected_rule"]
    assert rb == b["expected_rule"]
    assert ra != rb  # morphology changes rule route
    assert la == lb == a["expected_length"]  # length policy identical


def test_fixed_always_same():
    pol = FixedPolicy()
    m = {"b": 0.9, "r": 0.1, "k": 0.1, "a": 0.1, "l": 0.1, "s": 0.0, "p": 0.0, "u": 0.0}
    assert _vals(pol.propose(m, {})) == ["CUT", "REDUCE"]
    assert _vals(pol.propose({}, {"n_tokens": 999})) == ["CUT", "REDUCE"]


def test_fixed_rejects_illegal_ctor():
    with pytest.raises(GrammarError):
        FixedPolicy(["INTEGRATE", "CUT"])


def test_oracle_requires_eval_flag():
    with pytest.raises(OracleEvalForbiddenError):
        OraclePolicy(route_table={"t1": ["CUT"]}, allow_eval_use=False).propose(
            {}, {"task_id": "t1"}
        )


def test_oracle_lookup():
    pol = OraclePolicy(
        route_table={"fixture-cut-reduce": ["CUT", "REDUCE"]},
        allow_eval_use=True,
    )
    seq = pol.propose({}, {"task_id": "fixture-cut-reduce"})
    assert _vals(seq) == ["CUT", "REDUCE"]
    assert is_normal_form(seq)


def test_oracle_missing_task():
    pol = OraclePolicy(route_table={"t1": ["CUT"]}, allow_eval_use=True)
    with pytest.raises(KeyError):
        pol.propose({}, {"task_id": "missing"})


def test_oracle_evaluation_mode_alias():
    pol = OraclePolicy(route_table={"t1": ["REDUCE"]}, evaluation_mode=True)
    assert _vals(pol.propose({}, {"task_id": "t1"})) == ["REDUCE"]
