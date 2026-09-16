# BITE-12 handover

## 変更（raytrek: D:\\develop\\works\\bite-ingestion）

- `src/bite_eval/` — BaselineAdapter + registry（12 ids）
- `configs/baselines/*.json`
- `docs/baseline-parity.md`
- `tests/test_baseline_contract.py`
- `output/baseline-fixtures/*`
- research TBD pointers（prior-art-matrix / preregistration / experiment-matrix）

## 検証

- `ruff check src tests`: All checks passed
- `mypy src`: Success (60 source files)
- `pytest`: **114 passed**
- `scripts/gate.ps1`: **PASS**
- no push / no publish / no paid API / no keys / no real-data DL

## 契約メモ（D-1〜D-5b）

- HYVE / ContextSniper は **-like stub のみ**（フル再実装・許諾なし複製なし）
- 閾値は TBD_CALIBRATE（Go判定不可）
- Survive 断定なし。synthetic のみ。オフライン

## 次

BITE-13: total-token evaluation harness と artifact ledger。投入可。
