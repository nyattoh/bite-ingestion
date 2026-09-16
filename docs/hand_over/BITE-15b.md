# BITE-15b handover — billed N_pilot（v2 = **pivot**）

- **Date**: 2026-09-17 (UTC+9)
- **Phase**: Gate C billed N_pilot（checkpoint / resume → thinking 修正 → v2 再課金）
- **Tone**: Pivot-to-bench; no Survive; **Go 捏造禁止**
- **Standing**: 有料はローカル（raytrek / Path B）。Cloud は mock / 文書のみ。
- **Authoritative Gate C record**: **v2 @ [`967ec0b`](https://github.com/nyattoh/bite-ingestion/commit/967ec0b)** → **`pivot`**

## 権威ある結果（v2）

| 項目 | 値 |
| --- | --- |
| コミット | [`967ec0b`](https://github.com/nyattoh/bite-ingestion/commit/967ec0b) |
| summary | `artifacts/pilot/bite15b_billed_summary_v2.json` |
| partial | `artifacts/pilot/bite15b_billed_partial_v2.json` |
| checkpoint | 未コミット（`bite15b_checkpoint_v2.jsonl`） |
| 規模 | 384/384 billed rows |
| empty answers | **0/384**（minimal 0/12） |
| T_completion | min 2 / max 5 / mean ≈ 2.86 |
| **decision** | **`pivot`**（`c1=False c2=True c3=False`）— **Go ではない** |
| constraints_ok_rate | **0.880208**（338/384） |
| 弱点 family | `dependency_chain` ≈ 0.0417；他 7 family = 1.0 |
| 429 / timeout | なし |

再計算: `analysis/bite15b_pilot_recompute_v2.json`

## v1（履歴・非最終）

| 項目 | 値 |
| --- | --- |
| コミット | [`e44b5bd`](https://github.com/nyattoh/bite-ingestion/commit/e44b5bd) |
| decision | `stop`（empty-answer confounder 付き） |
| empty / T_completion | 354/384 empty；T_completion 常に 64 |

v1 は thinking/抽出バグ込み。科学的最終判定には使わない。

## なぜ BITE-15b があったか

初回フルランが `TimeoutError` で集計喪失 → checkpoint/resume/timeout 硬化。その後 v1 完走が empty×64 で汚染 → thinking disabled + 抽出 fallback + max_tokens=256 で v2 再課金。

## Fix summary（main に含まれる）

| Area | Change |
| --- | --- |
| `zai_client.py` | timeout retry；`thinking: disabled`；`reasoning_content` fallback |
| `billed_runner.py` | checkpoint/resume；pilot `max_tokens=256` |
| CLI / config | bite15b パス・retry・thinking 注記 |
| Tests | mock（thinking disabled / reasoning fallback 含む） |

## Resume policy

- Skip `ok`；retry `timeout`/`error` once；skip `rate_limit`
- v2 再課金は `--no-resume` + 新パス。以降の再開は **v2 checkpoint のみ**

## 未解決 / 次

1. Gate C 記録は **pivot**（確定）。Go ではない
2. **Path B（進行中）**: `dependency_chain` の質問を「数字だけ答えよ」に明確化（gold は元から数字）。閾値は動かさない。小さく再課金して ok_rate を見る
3. full matrix 実施可否は人間判断

## Path B — dependency_chain 質問修正

- **問題**: gold=`100`、モデルが `K00=100` と返して exact-match で落とされていた
- **修正**: `families.py` の query を「{code} の数値だけ答えよ（key=value 禁止）」に変更
- **変えないもの**: δ / ρ / η、採点関数、Go 条件
- **再課金**: まず `dependency_chain` だけ（24×2=48 calls）。全体 384 の即再実行はしない

## Do-not

- Go / Survive 捏造禁止
- checkpoint JSONL・キー値をコミットしない
- Cloud から再課金しない
- post-hoc で閾値を動かして Go にしない
