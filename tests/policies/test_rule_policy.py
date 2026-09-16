"""rule-Π determinism, decision-table coverage, QC toggle, budget fallback."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bite_ingestion.interfaces.operator import OperatorId
from bite_ingestion.policies.grammar import is_normal_form
from bite_ingestion.policies.rule_policy import RulePolicy

FIXTURES = Path(__file__).resolve().parents[2] / "output" / "policy-fixtures"


def _vals(seq):
    return [o.value if isinstance(o, OperatorId) else o for o in seq]


def test_determinism():
    pol = RulePolicy(query_conditioned=True)
    m = {"b": 0.2, "r": 0.8, "s": 0.5, "k": 0.8, "a": 0.1, "l": 0.2, "p": 0.0, "u": 0.0}
    b = {"pre_segmented": False}
    a = pol.propose(m, b)
    b2 = pol.propose(m, b)
    assert a == b2
    assert is_normal_form(a)


@pytest.mark.parametrize(
    "fname",
    [
        "cut_include_low_b.json",
        "untangle_include_high_a.json",
        "untangle_omit_low_a.json",
        "untangle_include_malformed.json",
        "reduce_include_high_r.json",
        "reduce_omit_low_r.json",
        "integrate_include_qc.json",
        "integrate_omit_high_l.json",
        "integrate_include_noqc_ignores_l.json",
        "budget_fallback_max_ops.json",
        "empty_fallback_cut.json",
    ],
)
def test_decision_table_fixtures(fname):
    data = json.loads((FIXTURES / fname).read_text(encoding="utf-8"))
    pol = RulePolicy(query_conditioned=bool(data.get("query_conditioned", True)))
    seq = pol.propose(data["morphology"], data.get("budget"))
    assert is_normal_form(seq)
    vals = _vals(seq)
    for op in data.get("expected_contains", []):
        assert op in vals, f"{fname}: expected {op} in {vals}"
    for op in data.get("expected_omits", []):
        assert op not in vals, f"{fname}: expected {op} omitted from {vals}"
    if "expected_exact" in data:
        assert vals == data["expected_exact"]
    if "expected_max_len" in data:
        assert len(vals) <= data["expected_max_len"]
    # decision table row coverage via explain
    dec = pol.last_decision
    assert dec is not None
    rule_ids = {r.rule_id for r in dec.rules_fired}
    rid = data.get("rule_id")
    if rid and rid not in ("length-vs-rule", "leak_guard"):
        assert rid in rule_ids or any(rid.split("-")[0] in x for x in rule_ids)


def test_cut_omit_fixture():
    data = json.loads((FIXTURES / "cut_omit_high_b_preseg.json").read_text(encoding="utf-8"))
    pol = RulePolicy(query_conditioned=True)
    seq = pol.propose(data["morphology"], data["budget"])
    assert "CUT" not in _vals(seq) or _vals(seq) == ["CUT"]  # omit unless empty fallback
    # With all other omit + CUT omit → empty fallback to CUT
    assert _vals(seq) == ["CUT"]
    assert any(r.rule_id == "CUT-OMIT" for r in pol.last_decision.rules_fired)
    assert any(r.rule_id == "EMPTY-FALLBACK" for r in pol.last_decision.rules_fired)


def test_query_conditioned_changes_integrate():
    m = {"b": 0.2, "r": 0.1, "s": 0.5, "k": 0.8, "a": 0.1, "l": 0.9, "p": 0.0, "u": 0.0}
    b = {"pre_segmented": False}
    on = RulePolicy(query_conditioned=True).propose(m, b)
    off = RulePolicy(query_conditioned=False).propose(m, b)
    assert OperatorId.INTEGRATE not in on
    assert OperatorId.INTEGRATE in off


def test_budget_fallback_shrinks():
    m = {"b": 0.2, "r": 0.9, "s": 0.5, "k": 0.9, "a": 0.8, "l": 0.1, "p": 0.0, "u": 0.0}
    full = RulePolicy().propose(m, {"pre_segmented": False})
    shrunk = RulePolicy().propose(m, {"pre_segmented": False, "max_ops": 2})
    assert len(full) >= len(shrunk)
    assert len(shrunk) == 2
    assert is_normal_form(shrunk)
    # later ops dropped: INTEGRATE/REDUCE gone before CUT/UNTANGLE
    assert _vals(shrunk) == ["CUT", "UNTANGLE"]


def test_no_oscillation_emitted():
    pol = RulePolicy()
    for a in (0.1, 0.9):
        for r in (0.1, 0.9):
            for k in (0.1, 0.9):
                for l in (0.1, 0.9):
                    m = {"b": 0.2, "r": r, "s": 0.5, "k": k, "a": a, "l": l, "p": 0.0, "u": 0.0}
                    seq = pol.propose(m, {"pre_segmented": False})
                    assert is_normal_form(seq)
                    assert len(set(seq)) == len(seq)


def test_explain_propose_structure():
    pol = RulePolicy()
    dec = pol.explain_propose(
        {"b": 0.2, "r": 0.8, "s": 0.5, "k": 0.1, "a": 0.1, "l": 0.5, "p": 0.0, "u": 0.0},
        {"pre_segmented": False},
    )
    d = dec.as_dict()
    assert d["policy_name"] == "rule-Π"
    assert "CUT" in d["sequence"]
    assert "REDUCE" in d["sequence"]
