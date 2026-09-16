# BITE-09 handover

## 変更（raytrek: D:\\develop\\works\\bite-ingestion）

- `src/bite_ingestion/operators/` — CUT / UNTANGLE / REDUCE / INTEGRATE + base + loss_ledger
- `tests/operators/` — determinism / recovery / loss ledger / per-op
- `docs/03-operator-taxonomy.md`, `docs/04-evidence-packet-contract.md`, `docs/operator-catalogue.md`
- `spec/operator.schema.json`
- `output/operator-fixtures/*.json`

## 検証

- `ruff check src tests`: All checks passed
- `mypy src`: Success (27 source files)
- `pytest`: **37 passed**
- `scripts/gate.ps1`: **PASS**
- no push / no publish / no paid API / no real-data DL

## 契約メモ

- 決定論 `mode=deterministic` のみ（INTEGRATE は deterministic_join）
- R / tau / recovery handles を維持。silent drop 禁止。REDUCE は loss を宣言
- Survive 断定なし。閾値数値の捏造なし（TBD-calibrate 定数のみ）

## 次

BITE-10: transparent operator-sequence policy と oracle。投入可。
