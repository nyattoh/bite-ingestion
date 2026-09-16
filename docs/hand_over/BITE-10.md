# BITE-10 handover

## 変更（raytrek: D:\\develop\\works\\bite-ingestion）

- `src/bite_ingestion/policies/` — grammar, rule-Π, length-Π, fixed-Π, oracle-Π, leak_guard, decision, thresholds, executor
- `configs/policies/{rule,fixed,length,oracle}_pi.json`
- `docs/policy-decision-table.md`
- `tests/test_policy.py`, `tests/policies/*`
- `output/policy-fixtures/*`
- `research/metric-contract.json`（TBD stub）

## 検証

- `ruff check src tests`: All checks passed
- `mypy src`: Success (37 source files)
- `pytest`: **76 passed**
- `scripts/gate.ps1`: **PASS**
- no push / no publish / no paid API / no real-data DL

## 契約メモ

- 正規形 `CUT?→UNTANGLE?→REDUCE?→INTEGRATE?`（各高々1、≥1）を強制
- transparent rule-Π は oracle / gold / eval_* リーク拒否
- oracle-Π は eval-only（`allow_eval_use` / `evaluation_mode`）
- 閾値は TBD_CALIBRATE（合成・非実測）。Survive 断定なし

## 次

BITE-11: bounded re-bite と source recovery。投入可。
