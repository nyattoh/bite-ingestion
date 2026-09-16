"""BITE-12 baseline adapter contract tests (synthetic only)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bite_eval.baselines import REQUIRED_BASELINE_IDS, get_baseline, list_baselines
from bite_eval.interface import STATUS_VALUES

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "output" / "baseline-fixtures"
PARITY = ROOT / "docs" / "baseline-parity.md"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _assert_contract(out: dict, baseline_id: str) -> None:
    assert out["baseline_id"] == baseline_id
    assert out["status"] in STATUS_VALUES
    assert "visible_evidence" in out
    acc = out["accounting"]
    assert "baseline_router_tokens" in acc
    assert "baseline_compressor_tokens" in acc
    assert "tau" in out or "baseline_trace" in out
    if out["status"] != "ok":
        assert out.get("reason"), "non-ok status must carry reason (no silent drop)"


def test_registry_lists_all_required_ids():
    ids = list_baselines()
    for required in REQUIRED_BASELINE_IDS:
        assert required in ids
    # BITE-04 §4 core + fixed_pi
    for bid in (
        "raw_full",
        "length_pi",
        "fixed_chunk_topk",
        "adaptive_chunk_like",
        "universal_reduce",
        "query_aware_compress_like",
        "hyve_like",
        "contextsniper_like",
        "rule_pi",
        "rule_pi_rebite",
        "oracle_pi",
        "fixed_pi",
    ):
        assert bid in ids
        assert get_baseline(bid) is not None


def test_each_baseline_runs_on_synthetic_fixture():
    pkt = _load("prose_short.json")
    # domain-specific need their own fixtures for ok; others should ok/failed-not-silent
    expected_ok = {
        "raw_full",
        "fixed_chunk_topk",
        "adaptive_chunk_like",
        "query_aware_compress_like",
        "universal_reduce",
    }
    expected_na = {"hyve_like", "contextsniper_like"}  # prose domain
    for bid in REQUIRED_BASELINE_IDS:
        adapter = get_baseline(bid)
        if bid == "oracle_pi":
            out = dict(adapter.run(pkt, {"allow_eval_use": False}))  # type: ignore[attr-defined]
            # without flag → failed
            assert out["status"] == "failed"
            _assert_contract(out, bid)
            continue
        ctx = {"domain": pkt.get("domain")}
        out = dict(adapter.run(pkt, ctx))  # type: ignore[attr-defined]
        _assert_contract(out, bid)
        if bid in expected_na:
            assert out["status"] == "not_applicable"
        elif bid in expected_ok:
            assert out["status"] == "ok", (bid, out.get("reason"))
        else:
            # policy wrappers: ok if policies on path, else failed with reason
            assert out["status"] in {"ok", "failed"}


def test_hyve_and_cs_domain_not_applicable():
    wrong_hyve = _load("wrong_domain_for_hyve.json")
    out = dict(get_baseline("hyve_like").run(wrong_hyve, {"domain": "code"}))  # type: ignore[attr-defined]
    assert out["status"] == "not_applicable"
    _assert_contract(out, "hyve_like")

    wrong_cs = _load("wrong_domain_for_cs.json")
    out2 = dict(get_baseline("contextsniper_like").run(wrong_cs, {"domain": "machine_data"}))  # type: ignore[attr-defined]
    assert out2["status"] == "not_applicable"
    _assert_contract(out2, "contextsniper_like")


def test_hyve_ok_on_machine_data():
    pkt = _load("machine_data_json.json")
    out = dict(get_baseline("hyve_like").run(pkt, {"domain": "machine_data"}))  # type: ignore[attr-defined]
    assert out["status"] == "ok"
    _assert_contract(out, "hyve_like")
    assert "error_code" in str(out["visible_evidence"]) or "E42" in str(out["visible_evidence"])


def test_contextsniper_ok_on_code():
    pkt = _load("code_sample.json")
    out = dict(get_baseline("contextsniper_like").run(pkt, {"domain": "code"}))  # type: ignore[attr-defined]
    assert out["status"] == "ok"
    _assert_contract(out, "contextsniper_like")
    ve = str(out["visible_evidence"])
    assert "parse_config" in ve or "Validator" in ve


def test_overflow_path():
    pkt = _load("overflow_long.json")
    out = dict(get_baseline("raw_full").run(pkt, {"max_chars": 100}))  # type: ignore[attr-defined]
    assert out["status"] == "overflow"
    _assert_contract(out, "raw_full")
    assert len(str(out["visible_evidence"])) <= 100


def test_accounting_keys_present():
    pkt = _load("prose_short.json")
    for bid in ("raw_full", "fixed_chunk_topk", "query_aware_compress_like"):
        out = dict(get_baseline(bid).run(pkt, {}))  # type: ignore[attr-defined]
        acc = out["accounting"]
        assert isinstance(acc["baseline_router_tokens"], int)
        assert isinstance(acc["baseline_compressor_tokens"], int)


def test_oracle_requires_eval_flag():
    pkt = _load("oracle_eval.json")
    # strip flags
    bare = {k: v for k, v in pkt.items() if k not in ("allow_eval_use", "evaluation_mode")}
    out = dict(get_baseline("oracle_pi").run(bare, {}))  # type: ignore[attr-defined]
    assert out["status"] == "failed"
    assert "eval" in out.get("reason", "").lower() or "allow_eval" in out.get("reason", "")
    _assert_contract(out, "oracle_pi")

    # with flag
    out_ok = dict(get_baseline("oracle_pi").run(pkt, {"allow_eval_use": True}))  # type: ignore[attr-defined]
    # may be ok or failed if policies missing — but if ok, sequence present
    _assert_contract(out_ok, "oracle_pi")
    if out_ok["status"] == "ok":
        assert out_ok.get("proposed_sequence") or (
            out_ok.get("baseline_trace") or {}
        ).get("sequence")


def test_parity_checklist_mentions_no_full_reimplementation():
    assert PARITY.is_file()
    text = PARITY.read_text(encoding="utf-8").lower()
    assert "hyve" in text
    assert "contextsniper" in text
    assert "not reimplemented" in text or "no full" in text
    assert "not a" in text or "no unauthorized" in text or "not reimplemented" in text


def test_rule_pi_rebite_exposes_hook():
    adapter = get_baseline("rule_pi_rebite")
    assert getattr(adapter, "rebite_enabled", False) is True
    pkt = _load("prose_short.json")
    out = dict(adapter.run(pkt, {"domain": "prose"}))  # type: ignore[attr-defined]
    _assert_contract(out, "rule_pi_rebite")
    # hook callable
    hook = getattr(adapter, "rebite", None)
    assert callable(hook)
    stub = hook(pkt, {"request_type": "clarify_sufficiency"})
    assert isinstance(stub, dict)


def test_failures_not_excluded_from_fixtures():
    # overflow fixture exists and is exercised
    assert (FIXTURES / "overflow_long.json").is_file()
    assert (FIXTURES / "wrong_domain_for_hyve.json").is_file()
    assert (FIXTURES / "wrong_domain_for_cs.json").is_file()


@pytest.mark.parametrize(
    "bid",
    [
        "length_pi",
        "fixed_pi",
        "rule_pi",
        "universal_reduce",
        "oracle_pi",
    ],
)
def test_policy_wrappers_contract(bid: str):
    """When bite_ingestion.policies is importable, wrappers should return ok."""
    policies = pytest.importorskip("bite_ingestion.policies")
    _ = policies
    if bid == "oracle_pi":
        pkt = _load("oracle_eval.json")
        out = dict(get_baseline(bid).run(pkt, {"allow_eval_use": True}))  # type: ignore[attr-defined]
    else:
        pkt = _load("prose_short.json")
        out = dict(get_baseline(bid).run(pkt, {"domain": "prose"}))  # type: ignore[attr-defined]
    _assert_contract(out, bid)
    assert out["status"] == "ok", out.get("reason")
