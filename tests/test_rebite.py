
"""BITE-11 bounded re-bite tests (synthetic fixtures only)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from bite_ingestion.recovery import (
    DEFAULT_BR_TOKENS,
    DEFAULT_J,
    OutcomeCode,
    RebiteRequest,
    RecoverBudget,
    RecoverEngine,
    RecoverState,
    RequestType,
    SourceStore,
    SufficiencyKind,
    estimate_tokens,
)

FIXTURES = Path(__file__).resolve().parents[1] / "output" / "rebite-fixtures"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def packet():
    return _load("packet_base.json")


@pytest.fixture
def store():
    return SourceStore.from_dict(_load("source_store.json"))


@pytest.fixture
def engine():
    return RecoverEngine(RecoverBudget(max_calls=DEFAULT_J, token_ceiling=DEFAULT_BR_TOKENS))


def test_defaults_are_tbd_calibrate():
    assert DEFAULT_J == 3
    assert DEFAULT_BR_TOKENS == 512
    b = RecoverBudget()
    assert b.label == "TBD_CALIBRATE"


def test_happy_fetch_unit(packet, store, engine):
    state = RecoverState()
    req = RebiteRequest.from_mapping(_load("request_fetch_unit.json"))
    result = engine.recover(packet, req, store, state)
    assert result.outcome == OutcomeCode.SUCCESS.value
    assert result.recovery_success == 1
    texts = [x["text"] for x in result.packet["visible_evidence"]]
    assert "beta secret fact=42" in texts
    assert result.returned_evidence_ids
    assert state.calls == 1
    assert state.rebite_tokens == estimate_tokens("beta secret fact=42")
    assert result.packet["accounting"]["rebite_tokens"] == state.rebite_tokens
    assert "RECOVER" in result.packet["tau"]["sequence"]
    assert result.packet["rebite"]["steps"]


def test_happy_fetch_span(packet, store, engine):
    state = RecoverState()
    req = RebiteRequest.from_mapping(_load("request_fetch_span.json"))
    result = engine.recover(packet, req, store, state)
    assert result.outcome == OutcomeCode.SUCCESS.value
    texts = [x["text"] for x in result.packet["visible_evidence"] if x.get("role") == "recovered"]
    assert texts == ["beta"]


def test_happy_aggregate_members(packet, store, engine):
    state = RecoverState()
    req = RebiteRequest.from_mapping(_load("request_aggregate.json"))
    result = engine.recover(packet, req, store, state)
    assert result.outcome == OutcomeCode.SUCCESS.value
    texts = {x["text"] for x in result.packet["visible_evidence"]}
    assert "gamma member one" in texts
    assert "delta member two" in texts
    assert len(result.returned_evidence_ids) == 2


def test_happy_quarantine(packet, store, engine):
    state = RecoverState()
    req = RebiteRequest.from_mapping(_load("request_quarantine.json"))
    result = engine.recover(packet, req, store, state)
    assert result.outcome == OutcomeCode.SUCCESS.value
    texts = [x["text"] for x in result.packet["visible_evidence"]]
    assert '{"broken": ' in texts


def test_budget_exhaustion_calls(packet, store):
    engine = RecoverEngine(RecoverBudget(max_calls=1, token_ceiling=10_000))
    state = RecoverState()
    req = RebiteRequest(request_type="fetch_unit", unit_id="u_beta")
    r1 = engine.recover(packet, req, store, state)
    assert r1.outcome == OutcomeCode.SUCCESS.value
    r2 = engine.recover(r1.packet, req, store, state)
    assert r2.outcome == OutcomeCode.BUDGET_EXHAUSTED.value
    assert state.calls == 2  # second attempt still counted


def test_budget_exhaustion_tokens(packet, store):
    engine = RecoverEngine(RecoverBudget(max_calls=5, token_ceiling=1))
    state = RecoverState()
    req = RebiteRequest(request_type="fetch_unit", unit_id="u_beta")
    result = engine.recover(packet, req, store, state)
    assert result.outcome == OutcomeCode.BUDGET_EXHAUSTED.value
    assert state.calls == 1


def test_stale_version(packet, store, engine):
    state = RecoverState()
    req = RebiteRequest.from_mapping(_load("request_stale.json"))
    result = engine.recover(packet, req, store, state)
    assert result.outcome == OutcomeCode.STALE_OR_BROKEN_LOCATOR.value
    texts = [x.get("text") for x in result.packet["visible_evidence"]]
    assert "old content" not in texts


def test_injection_suspect_refusal(packet, store, engine):
    state = RecoverState()
    req = RebiteRequest.from_mapping(_load("request_injection.json"))
    result = engine.recover(packet, req, store, state)
    assert result.outcome == OutcomeCode.REFUSED_INJECTION_SUSPECT.value
    assert not any(
        "INJECT" in (x.get("text") or "") for x in result.packet["visible_evidence"]
    )
    assert state.audit_log[-1]["outcome"] == OutcomeCode.REFUSED_INJECTION_SUSPECT.value


def test_recovery_bypass_outside_r(packet, store, engine):
    state = RecoverState()
    req = RebiteRequest.from_mapping(_load("request_bypass.json"))
    result = engine.recover(packet, req, store, state)
    assert result.outcome == OutcomeCode.RECOVER_MISS.value
    assert not any(
        "bypass" in (x.get("text") or "") for x in result.packet["visible_evidence"]
    )


def test_repeat_suppression(packet, store, engine):
    state = RecoverState()
    req = RebiteRequest(request_type="fetch_unit", unit_id="u_beta")
    r1 = engine.recover(packet, req, store, state)
    assert r1.outcome == OutcomeCode.SUCCESS.value
    n_vis = len(r1.packet["visible_evidence"])
    r2 = engine.recover(r1.packet, req, store, state)
    assert r2.outcome == OutcomeCode.SUPPRESSED_REPEAT.value
    assert len(r2.packet["visible_evidence"]) == n_vis


def test_clarify_sufficiency_meta_only(packet, store, engine):
    state = RecoverState()
    req = RebiteRequest.from_mapping(_load("request_clarify.json"))
    before = copy.deepcopy(packet["visible_evidence"])
    result = engine.recover(packet, req, store, state)
    assert result.outcome == OutcomeCode.CLARIFY_META.value
    assert result.packet["visible_evidence"] == before
    assert result.meta is not None
    assert result.meta["body_fetched"] is False
    assert result.sufficiency_kind == SufficiencyKind.MISSING_EVIDENCE.value
    assert "omitted_by_reduce" in result.meta["missing_evidence_types"] or result.meta[
        "missing_entries"
    ]


def test_clarify_model_indecision_when_nothing_missing(store, engine):
    pkt = {
        "packet_id": "empty_r",
        "visible_evidence": [{"text": "all here", "unit_ids": ["u_only"]}],
        "R": {"entries": []},
        "tau": {"sequence": [], "steps": []},
        "provenance": {"unit_id": "u_only"},
        "op_last_touch": "NONE",
    }
    state = RecoverState()
    req = RebiteRequest(request_type="clarify_sufficiency")
    result = engine.recover(pkt, req, store, state)
    assert result.outcome == OutcomeCode.CLARIFY_META.value
    assert result.sufficiency_kind == SufficiencyKind.MODEL_INDECISION.value


def test_invalid_request(packet, store, engine):
    state = RecoverState()
    req = RebiteRequest.from_mapping(_load("request_invalid.json"))
    result = engine.recover(packet, req, store, state)
    assert result.outcome == OutcomeCode.INVALID_REQUEST.value
    assert state.calls == 1


def test_withdrawn_refused(packet, store, engine):
    state = RecoverState()
    req = RebiteRequest.from_mapping(_load("request_withdrawn.json"))
    result = engine.recover(packet, req, store, state)
    assert result.outcome == OutcomeCode.REFUSED_WITHDRAWN.value
    assert not any(
        "should never appear" in (x.get("text") or "")
        for x in result.packet["visible_evidence"]
    )


def test_audit_log_contains_request_and_ids(packet, store, engine):
    state = RecoverState()
    req = RebiteRequest(request_type="fetch_unit", unit_id="u_beta", request_id="aud1")
    result = engine.recover(packet, req, store, state)
    assert state.audit_log
    row = state.audit_log[-1]
    assert row["request"]["request_type"] == "fetch_unit"
    assert row["request"]["unit_id"] == "u_beta"
    assert row["returned_evidence_ids"] == result.returned_evidence_ids
    assert row["outcome"] == OutcomeCode.SUCCESS.value


def test_token_accounting_increments(packet, store, engine):
    state = RecoverState()
    req = RebiteRequest(request_type="fetch_unit", unit_id="u_beta")
    result = engine.recover(packet, req, store, state)
    expected = estimate_tokens("beta secret fact=42")
    assert expected > 0
    assert state.rebite_tokens == expected
    assert result.packet["accounting"]["rebite_tokens"] == expected
    assert result.packet["accounting"].get("rebite_tokens_in_T_total") is True


def test_determinism(packet, store, engine):
    req = RebiteRequest(request_type="fetch_unit", unit_id="u_beta")
    r1 = engine.recover(copy.deepcopy(packet), req, store, RecoverState())
    r2 = engine.recover(copy.deepcopy(packet), req, store, RecoverState())
    assert r1.outcome == r2.outcome
    assert r1.returned_evidence_ids == r2.returned_evidence_ids
    assert r1.packet["visible_evidence"] == r2.packet["visible_evidence"]
    assert r1.packet["accounting"] == r2.packet["accounting"]


def test_fetch_by_version_success(packet, store, engine):
    state = RecoverState()
    req = RebiteRequest(request_type="fetch_by_version", unit_id="u_beta", version="v1")
    result = engine.recover(packet, req, store, state)
    assert result.outcome == OutcomeCode.SUCCESS.value


def test_fetch_by_version_mismatch(packet, store, engine):
    state = RecoverState()
    req = RebiteRequest(request_type="fetch_by_version", unit_id="u_beta", version="v9")
    result = engine.recover(packet, req, store, state)
    assert result.outcome == OutcomeCode.STALE_OR_BROKEN_LOCATOR.value


def test_handle_scoped_fetch(packet, store, engine):
    state = RecoverState()
    req = RebiteRequest(request_type="fetch_unit", handle_id="h_beta")
    result = engine.recover(packet, req, store, state)
    assert result.outcome == OutcomeCode.SUCCESS.value
    assert any("beta secret" in (x.get("text") or "") for x in result.packet["visible_evidence"])


def test_allowed_request_types_enum():
    assert {rt.value for rt in RequestType} == {
        "fetch_unit",
        "fetch_span",
        "fetch_aggregate_members",
        "fetch_quarantine",
        "fetch_by_version",
        "clarify_sufficiency",
    }
