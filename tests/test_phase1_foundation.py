"""Phase 1 foundation regression tests.

Covers the four contracts that had to hold before an offline arm comparison
can mean anything:

1. packet contract — evidence ids have bodies, spans resolve
2. fail-closed — no silent empty output, no routing on a default vector
3. evidence integrity — visible ids match the payload; omissions reach R
4. token accounting — one T_total definition, re-bite cost is billed
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bite_eval.accounting.dc_validators import validate_ledger_totals
from bite_eval.accounting.ledger import TokenLedger
from bite_eval.baselines import get_baseline
from bite_eval.pilot.families import SYNTHETIC_FAMILIES, generate_family_instances
from bite_ingestion.interfaces.operator import OperatorId
from bite_ingestion.operators import apply_operator
from bite_ingestion.packet_contract import (
    PacketContractError,
    assert_evidence_ids_resolve,
    provenance_completeness,
    resolve_packet_units,
    split_units_by_char_limit,
    validate_units,
)
from bite_ingestion.policies import MorphologyRequiredError, RulePolicy, apply_sequence
from bite_ingestion.recovery import (
    DEFAULT_BR_TOKENS,
    DEFAULT_J,
    OutcomeCode,
    RebiteRequest,
    RecoverBudget,
    RecoverEngine,
    RecoverState,
    SourceStore,
)

REBITE_FIXTURES = Path(__file__).resolve().parent.parent / "output" / "rebite-fixtures"


# ===========================================================================
# 1. Packet contract
# ===========================================================================


@pytest.mark.parametrize("family", SYNTHETIC_FAMILIES)
def test_every_pilot_packet_has_a_resolvable_unit_graph(family: str) -> None:
    for packet in generate_family_instances(family, 3):
        doc = str(packet["document"])
        units = resolve_packet_units(packet, document=doc)
        assert units, f"{family}: no units"
        validate_units(units, document=doc)
        assert_evidence_ids_resolve(list(packet["gold_evidence_ids"]), units)


@pytest.mark.parametrize("family", SYNTHETIC_FAMILIES)
def test_gold_evidence_text_is_really_in_the_document(family: str) -> None:
    """The core rule: an evidence id must not live in a different world."""
    for packet in generate_family_instances(family, 3):
        doc = str(packet["document"])
        by_id = {str(u["unit_id"]): u for u in packet["units"]}
        for gid in packet["gold_evidence_ids"]:
            unit = by_id[str(gid)]
            span = unit["span"]
            assert doc[span["start"] : span["end"]] == unit["text"]
            assert unit["text"] in doc


@pytest.mark.parametrize("family", SYNTHETIC_FAMILIES)
def test_units_carry_full_provenance(family: str) -> None:
    packet = generate_family_instances(family, 1)[0]
    assert provenance_completeness(packet["units"]) == 1.0
    for unit in packet["units"]:
        assert unit["source_uri"]
        assert unit["provenance"]["byte_or_token_span"]
        assert "parent_unit_id" in unit


def test_pilot_packets_do_not_predeclare_recoverability() -> None:
    """Recoverability must be earned via R, not asserted on the packet."""
    for family in SYNTHETIC_FAMILIES:
        packet = generate_family_instances(family, 1)[0]
        assert packet["recoverable_evidence_ids"] == [], family


# ===========================================================================
# 2. Fail-closed
# ===========================================================================


def test_string_evidence_list_is_not_silently_skipped() -> None:
    """A list of bare ids used to yield 0 units and a 'clean' operator run."""
    packet = {"packet_id": "strings", "visible_evidence": ["some-id", "other-id"]}
    with pytest.raises(PacketContractError):
        apply_operator(OperatorId.CUT, packet, None)


def test_nonempty_input_never_yields_silent_empty_output() -> None:
    packet = {"packet_id": "strings", "visible_evidence": ["only-an-id"]}
    with pytest.raises(PacketContractError):
        apply_sequence((OperatorId.CUT, OperatorId.REDUCE), packet)


def test_operator_on_real_units_conserves_evidence() -> None:
    """visible + R + declared loss must cover the input units."""
    packet = {
        "packet_id": "conserve",
        "visible_evidence": [
            {"text": "status=ok"},
            {"text": "status=ok"},
            {"text": "name=alice"},
        ],
        "provenance": {"unit_id": "src", "source_uri": "synthetic://conserve"},
    }
    out = apply_operator(OperatorId.REDUCE, packet, None)
    n_visible = len(out["visible_evidence"])
    r_ids = {e["unit_id"] for e in out["R"]["entries"]}
    assert n_visible >= 1
    assert n_visible + len(r_ids) >= 3, "a dropped unit must appear in R"
    assert out["irreversible_loss_ledger"], "collapsed duplicates must be declared"


def test_dangling_gold_evidence_id_fails_closed() -> None:
    packet = {
        "instance_id": "dangling",
        "document": "hello world",
        "gold_evidence_ids": ["nope"],
    }
    with pytest.raises(PacketContractError):
        resolve_packet_units(packet)


def test_unresolvable_span_fails_closed() -> None:
    packet = {
        "instance_id": "bad-span",
        "document": "hello",
        "units": [
            {
                "unit_id": "u1",
                "text": "hello",
                "span": {"start": 0, "end": 999, "unit": "char"},
                "source_uri": "s://x",
            }
        ],
    }
    with pytest.raises(PacketContractError):
        resolve_packet_units(packet)


def test_rule_policy_refuses_empty_morphology() -> None:
    with pytest.raises(MorphologyRequiredError):
        RulePolicy().explain_propose({}, {"pre_segmented": False})


def test_rule_policy_refuses_morphology_without_routing_features() -> None:
    with pytest.raises(MorphologyRequiredError):
        RulePolicy().explain_propose({"unrelated": 1.0}, {"pre_segmented": False})


def test_rule_pi_baseline_reports_morphology_missing() -> None:
    """The adapter must fail with a reason code, not a silent constant route."""
    packet = {"document": "text with no morphology", "query": "q"}
    out = dict(get_baseline("rule_pi").run(packet, {"domain": "prose"}))
    assert out["status"] == "failed"
    assert "morphology_missing" in out["reason"]
    assert out["baseline_trace"]["reason_code"] == "morphology_missing"


def test_rule_pi_baseline_ok_with_morphology() -> None:
    packet = {
        "document": "text",
        "query": "q",
        "morphology": {"b": 0.2, "a": 0.1, "r": 0.9, "k": 0.1, "l": 0.5, "u": 0.1},
    }
    out = dict(get_baseline("rule_pi").run(packet, {"domain": "prose"}))
    assert out["status"] == "ok", out.get("reason")
    assert "REDUCE" in out["proposed_sequence"]


# ===========================================================================
# 3. Evidence integrity across a cut point
# ===========================================================================


def test_split_by_char_limit_is_span_based() -> None:
    packet = generate_family_instances("adversarial_omission", 1)[0]
    doc = str(packet["document"])
    units = resolve_packet_units(packet, document=doc)

    visible, omitted = split_units_by_char_limit(units, limit=len(doc))
    assert omitted == [] and len(visible) == len(units)

    # Cut just after the first gold unit.
    first_gold = next(u for u in units if u["unit_id"] == packet["gold_evidence_ids"][0])
    limit = int(first_gold["span"]["end"])
    visible, omitted = split_units_by_char_limit(units, limit=limit)
    vis_ids = {u["unit_id"] for u in visible}
    om_ids = {u["unit_id"] for u in omitted}
    assert first_gold["unit_id"] in vis_ids
    assert packet["gold_evidence_ids"][1] in om_ids
    assert not (vis_ids & om_ids)


def test_partial_survival_counts_as_omitted() -> None:
    units = [
        {
            "unit_id": "u1",
            "text": "abcdef",
            "span": {"start": 0, "end": 6, "unit": "char"},
            "source_uri": "s://x",
        }
    ]
    visible, omitted = split_units_by_char_limit(units, limit=3)
    assert visible == []
    assert [u["unit_id"] for u in omitted] == ["u1"]


# ===========================================================================
# 4. Token accounting
# ===========================================================================


def test_t_total_equals_bucket_sum() -> None:
    ledger = TokenLedger()
    ledger.record({"category": "profiler", "kind": "api", "call_id": "p", "tokens_in": 3})
    ledger.record({"category": "router", "kind": "api", "call_id": "r", "tokens_in": 2})
    ledger.record({"category": "operator", "kind": "api", "call_id": "o", "tokens_in": 7})
    ledger.record(
        {"category": "target", "kind": "api", "call_id": "t", "tokens_in": 10, "tokens_out": 4}
    )
    ledger.record({"category": "rebite", "kind": "api", "call_id": "rb", "tokens_in": 5})
    totals = ledger.totals()

    assert totals["T_operator"] == 7
    expected = (
        totals["T_profiler"]
        + totals["T_router"]
        + totals["T_operator"]
        + totals["T_target_in"]
        + totals["T_target_out"]
        + totals["T_rebite"]
        + totals["T_baseline"]
        + totals["T_calls_other"]
    )
    assert totals["T_total"] == expected == 31
    assert validate_ledger_totals(ledger.rows(), dict(totals)) == []


def test_rebite_tokens_from_accounting_reach_the_ledger() -> None:
    """A re-bite arm must not get its extra evidence for free."""
    ledger = TokenLedger()
    ledger.merge_baseline_accounting(
        {"baseline_router_tokens": 0, "baseline_compressor_tokens": 0, "rebite_tokens": 42}
    )
    totals = ledger.totals()
    assert totals["T_rebite"] == 42
    assert totals["T_total"] == 42


def test_recover_engine_cost_flows_into_T_rebite() -> None:
    """End-to-end: RecoverEngine -> packet accounting -> ledger T_rebite."""
    packet = json.loads((REBITE_FIXTURES / "packet_base.json").read_text(encoding="utf-8"))
    store = SourceStore.from_dict(
        json.loads((REBITE_FIXTURES / "source_store.json").read_text(encoding="utf-8"))
    )
    request = RebiteRequest.from_mapping(
        json.loads((REBITE_FIXTURES / "request_fetch_unit.json").read_text(encoding="utf-8"))
    )
    engine = RecoverEngine(RecoverBudget(max_calls=DEFAULT_J, token_ceiling=DEFAULT_BR_TOKENS))
    result = engine.recover(packet, request, store, RecoverState())
    assert result.outcome == OutcomeCode.SUCCESS.value
    assert result.estimated_tokens > 0

    accounting = result.packet["accounting"]
    assert accounting["rebite_tokens"] == result.estimated_tokens

    ledger = TokenLedger()
    ledger.merge_baseline_accounting(accounting)
    assert ledger.totals()["T_rebite"] == result.estimated_tokens
    assert ledger.totals()["T_total"] == result.estimated_tokens


def test_rule_pi_rebite_reports_recovery_cost() -> None:
    packet = json.loads((REBITE_FIXTURES / "packet_base.json").read_text(encoding="utf-8"))
    store = SourceStore.from_dict(
        json.loads((REBITE_FIXTURES / "source_store.json").read_text(encoding="utf-8"))
    )
    request = json.loads((REBITE_FIXTURES / "request_fetch_unit.json").read_text(encoding="utf-8"))

    adapter = get_baseline("rule_pi_rebite")
    assert adapter.rebite_tokens == 0
    adapter.rebite(packet, request, source_store=store, state=RecoverState())
    assert adapter.rebite_tokens > 0, "recovery cost must be accumulated"

    out = dict(
        adapter.run(
            {
                "document": "text",
                "query": "q",
                "morphology": {"b": 0.2, "a": 0.1, "r": 0.9, "k": 0.1, "l": 0.5, "u": 0.1},
            },
            {"domain": "prose"},
        )
    )
    assert out["status"] == "ok", out.get("reason")
    assert out["accounting"]["rebite_tokens"] == adapter.rebite_tokens

    ledger = TokenLedger()
    ledger.merge_baseline_accounting(out["accounting"])
    assert ledger.totals()["T_rebite"] == adapter.rebite_tokens


def test_no_duplicate_call_id_across_buckets() -> None:
    ledger = TokenLedger()
    ledger.record({"category": "target", "kind": "api", "call_id": "same", "tokens_in": 5})
    ledger.record({"category": "rebite", "kind": "api", "call_id": "same", "tokens_in": 5})
    assert any(v.startswith("DC-1:duplicate_call_id") for v in ledger.violations())
