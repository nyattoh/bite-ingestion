"""Synthetic token ledger sums + DC-1 no double count."""

from __future__ import annotations

from bite_eval.accounting import (
    LOCAL_ESTIMATE_LABEL,
    TokenLedger,
    estimate_tokens_char4,
    validate_ledger_totals,
)
from bite_eval.accounting.estimate import LOCAL_ESTIMATE_LABEL as _LBL


def test_char4_proxy_labeled():
    assert estimate_tokens_char4("abcd") == 1
    assert estimate_tokens_char4("abcde") == 2
    assert LOCAL_ESTIMATE_LABEL == "local_char4_proxy"
    assert _LBL == "local_char4_proxy"


def test_t_total_bucket_sum():
    led = TokenLedger()
    led.record(
        {
            "category": "profiler",
            "kind": "api",
            "call_id": "p1",
            "tokens_in": 3,
            "tokens_out": 1,
        }
    )
    led.record(
        {
            "category": "router",
            "kind": "api",
            "call_id": "r1",
            "tokens_in": 2,
            "tokens_out": 0,
        }
    )
    led.record(
        {
            "category": "target",
            "kind": "api",
            "call_id": "t1",
            "tokens_in": 10,
            "tokens_out": 4,
        }
    )
    led.record(
        {
            "category": "rebite",
            "kind": "api",
            "call_id": "rb1",
            "tokens_in": 5,
            "tokens_out": 0,
        }
    )
    totals = led.totals()
    # T_total = profiler(4) + router(2) + sum_c(10+4+5) = 25
    assert totals["T_profiler"] == 4
    assert totals["T_router"] == 2
    assert totals["T_target_in"] == 10
    assert totals["T_target_out"] == 4
    assert totals["T_rebite"] == 5
    assert totals["T_total"] == 25
    assert totals["local_estimate_label"] == LOCAL_ESTIMATE_LABEL


def test_dc2_deterministic_preprocess_zero_tokens():
    led = TokenLedger()
    led.record(
        {
            "category": "target",
            "kind": "deterministic_preprocess",
            "tokens_in": 99,
            "tokens_out": 99,
            "cpu_ms": 1.5,
        }
    )
    totals = led.totals()
    assert totals["T_total"] == 0
    assert totals["cpu_ms"] == 1.5


def test_dc1_no_double_count_same_call_id():
    led = TokenLedger()
    led.record(
        {
            "category": "target",
            "kind": "api",
            "call_id": "dup",
            "tokens_in": 7,
            "tokens_out": 0,
        }
    )
    led.record(
        {
            "category": "target",
            "kind": "api",
            "call_id": "dup",
            "tokens_in": 7,
            "tokens_out": 0,
        }
    )
    # Ledger still stores both rows (observability) but validators flag DC-1
    viol = led.violations()
    assert any(v.startswith("DC-1:duplicate_call_id") for v in viol)


def test_dc4_dual_use_not_counted():
    led = TokenLedger()
    led.record(
        {
            "category": "target",
            "kind": "api",
            "call_id": "du",
            "tokens_in": 100,
            "tokens_out": 0,
            "dual_use_logical": True,
        }
    )
    assert led.totals()["T_total"] == 0


def test_validate_rejects_target_input_only_alias():
    rows = []
    totals = {"T_total": 10, "T_profiler": 0, "T_router": 0, "sum_calls_in_out": 10,
              "T_total_is_target_input_only": True}
    viol = validate_ledger_totals(rows, totals)
    assert "forbidden_target_input_only_total" in viol


def test_provider_vs_local_estimate_source():
    led = TokenLedger()
    led.record_text_estimate(
        category="target",
        text="hello world!!!!",  # 15 chars -> ceil(15/4)=4
        call_id="local1",
    )
    row = led.rows()[0]
    assert row["estimate_source"] == LOCAL_ESTIMATE_LABEL
    led2 = TokenLedger()
    led2.record_text_estimate(
        category="target",
        text="ignored",
        call_id="prov1",
        provider_usage={"tokens_in": 11, "tokens_out": 3, "kind": "api"},
    )
    assert led2.rows()[0]["estimate_source"] == "provider_usage"
    assert led2.totals()["T_total"] == 14
