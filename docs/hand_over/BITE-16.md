# BITE-16 handover — pilot stop からの解析ブートストラップ

- **Date**: 2026-09-17 (UTC+9)
- **Depends on**: BITE-15 / BITE-15b（[`e44b5bd`](https://github.com/nyattoh/bite-ingestion/commit/e44b5bd)）
- **Tone**: Pivot-to-bench; **負の結果を同粒度で記録**; Go/Survive 禁止

## 現状

| 項目 | 状態 |
| --- | --- |
| 有料 N_pilot | **完走** → decision **`stop`** |
| `output/main/aggregates.parquet` | **未作成**（full matrix 未実行） |
| `output/main/failures.jsonl` | **未作成** |
| pilot 解析ブートストラップ | **本ブランチで追加** |

## 本スライスで追加した成果物

| Path | Role |
| --- | --- |
| `docs/hand_over/BITE-15b.md` | stop 決定・384 完走の確定記録 |
| `analysis/main-results.md` | pilot-scoped 主結果（stop） |
| `analysis/error-atlas.md` | 失敗インベントリ |
| `analysis/pareto-data.csv` | raw vs compressed 対の記述 CSV |
| `figures/data/pareto-data-pilot.csv` | 同上コピー |
| `analysis/hypothesis-tests.json` | C1–C3 false / stop（CI は TBD） |
| `analysis/claim-evidence-draft.csv` | 主張↔証拠ドラフト |
| `analysis/bite15b_pilot_recompute.json` | summary からの再集計 |

## 検証

```bash
python3 -c "import json; json.load(open('artifacts/pilot/bite15b_billed_summary.json')); json.load(open('analysis/bite15b_pilot_recompute.json'))"
# decision == stop, n_rows == 384
```

## 未解決（次の最小スライス）

1. Q≈0 / Q_baseline≈1 の採点経路をコードで追跡（harness が空応答を Q=0 にしているか）
2. full `output/main/*` が無い前提で、BITE-16 完了条件を **pilot-stop 文書化**に縮小するか、別アームを再設計するか人間判断
3. formal CI / Holm 数値は **捏造せず** TBD のまま（必要なら offline bootstrap を別タスクで）

## Do-not

- stop を見て閾値を動かして Go 化しない
- `texture_swap` を primary に昇格しない
- 平均 token だけで 354 件の Q 失敗を隠さない
