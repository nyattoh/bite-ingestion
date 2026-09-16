# BITE-06 handover

## 変更

- `src/bite_bench/`：synthetic same-facts × multi-texture generator
- `benchmarks/spec/texture_families.json`
- `benchmarks/frozen-v0.1/syn-case-000.json`, `syn-case-001.json`
- `tests/test_texture_invariance.py`
- `docs/benchmark-generation.md`, `docs/hand_over/BITE-06.md`
- `harness/bitebench_hook.py`（T_total フックスタブ）
- `bitebench/README.md`

## 検証

- ruff：PASS
- mypy：PASS
- pytest：12 passed

## 未解決

- fact 同一性人間ロック TBD
- real dataset / licence は BITE-07（捏造せず）

## BITE-07

設計枠としては投入可。実データ取得・再配布は本人確認後。
