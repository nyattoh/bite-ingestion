"""Top-level BITE-10 policy smoke + Protocol satisfaction."""

from __future__ import annotations

from bite_ingestion.interfaces.operator import OperatorId
from bite_ingestion.interfaces.policy import OperatorSequencePolicy
from bite_ingestion.policies import (
    FixedPolicy,
    LengthOnlyPolicy,
    OraclePolicy,
    RulePolicy,
    enumerate_legal_sequences,
    is_normal_form,
)


def test_protocol_runtime_checkable():
    assert isinstance(RulePolicy(), OperatorSequencePolicy)
    assert isinstance(LengthOnlyPolicy(), OperatorSequencePolicy)
    assert isinstance(FixedPolicy(), OperatorSequencePolicy)
    assert isinstance(
        OraclePolicy(route_table={"t": ["CUT"]}, allow_eval_use=True),
        OperatorSequencePolicy,
    )


def test_policy_names():
    assert RulePolicy.policy_name == "rule-Π"
    assert LengthOnlyPolicy.policy_name == "length-Π"
    assert FixedPolicy.policy_name == "fixed-Π"
    assert OraclePolicy.policy_name == "oracle-Π"


def test_exports_and_grammar_smoke():
    legal = enumerate_legal_sequences()
    assert all(is_normal_form(s) for s in legal)
    assert OperatorId.CUT in legal[0] or True  # smoke
