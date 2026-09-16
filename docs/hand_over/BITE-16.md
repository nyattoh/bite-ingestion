# BITE-16 handover — billed pilot **v2 pivot** からの解析

- **Date**: 2026-09-17 (UTC+9)
- **Depends on**: BITE-15b v2 @ [`967ec0b`](https://github.com/nyattoh/bite-ingestion/commit/967ec0b)
- **Tone**: Pivot-to-bench; **pivot / 負の部分結果を同粒度で記録**; Go/Survive 禁止

## Gate C 現状（権威ある記録）

| 項目 | 状態 |
| --- | --- |
| 有料 N_pilot v2 | **完走** → **`pivot`**（`c1=False c2=True c3=False`） |
| empty answers | **0/384**（v1 confounder 解消） |
| constraints_ok_rate | **0.880208**；弱点は `dependency_chain`（≈0.0417） |
| `output/main/aggregates.parquet` | **未作成** |
| 解析ブートストラップ | v2 向けに更新 |

v1 `stop`（`e44b5bd`）は履歴として残すが、**最終判定には使わない**。

## 本スライス成果物

| Path | Role |
| --- | --- |
| `analysis/main-results.md` | v2 pivot 主結果 |
| `analysis/error-atlas.md` | v2 失敗インベントリ |
| `analysis/bite15b_pilot_recompute_v2.json` | v2 再集計 |
| `analysis/pareto-data-v2.csv` | paired CSV |
| `figures/data/pareto-data-pilot-v2.csv` | 同上 |
| `analysis/hypothesis-tests.json` | C1/C2/C3 + pivot |
| `analysis/claim-evidence-draft.csv` | 主張↔証拠 |

## 検証

```bash
python3 -c "import json; d=json.load(open('artifacts/pilot/bite15b_billed_summary_v2.json')); assert d['decision']=='pivot'; assert len(d['results'])==384"
```

## 未解決（次の最小スライス）

1. `dependency_chain` の Q 失敗メカニズム（gold 不一致の型）をコード＋数例で文書化（再課金なし）
2. C2 placeholder を length-only arm へ置き換える設計メモ（実装は別タスク）
3. full matrix / `output/main/*` を走らせるか、pilot-pivot で Gate C 文書を閉じるか人間判断
4. CI / Holm は TBD（捏造しない）

## Do-not

- pivot を見て閾値を動かして Go 化しない
- `dependency_chain` 以外の family 成功を primary に昇格しない
- 平均 token だけで 46 件の Q 失敗を隠さない
- C2 placeholder を「形態素が勝った」と主張しない
