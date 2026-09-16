# BITE-15b handover — billed N_pilot 完走と stop 決定

- **Date**: 2026-09-17 (UTC+9)
- **Phase**: Gate C billed N_pilot（checkpoint / resume 硬化 → 親機完走）
- **Tone**: Pivot-to-bench; no Survive; **Go 捏造禁止**
- **Standing**: 有料呼び出しはローカル（raytrek / Path B）。Cloud は mock 検証と文書のみ。

## 結果サマリ（検証済み）

| 項目 | 値 |
| --- | --- |
| 記録コミット | [`e44b5bd`](https://github.com/nyattoh/bite-ingestion/commit/e44b5bd)（`main`） |
| summary | `artifacts/pilot/bite15b_billed_summary.json` |
| partial | `artifacts/pilot/bite15b_billed_partial.json` |
| checkpoint JSONL | **未コミット**（`.gitignore` どおり） |
| 規模 | 8 families × 24 × 2 methods = **384** rows |
| `estimate_source` | 全行 `provider_usage_billed` |
| error / rate_limit | **0** / **false** |
| `sample_meets_n_pilot` | **true** |
| **decision** | **`stop`**（`c1=False c2=False c3=False`） |
| `constraints_ok_rate` | **0.078125**（30/384） |
| 主失敗 | `Q < Q_baseline - delta`（354） |
| `T_total` | sum **62489**（min 106 / max 240） |
| resume 痕跡 | `calls_skipped_ok=384`, `calls_attempted=0`（checkpoint から復元して summary 生成） |

再計算（summary JSON のみ・オフライン）: `analysis/bite15b_pilot_recompute.json`

### family 別（constraints_ok）

| family | n_method_rows | constraints_ok_rate |
| --- | ---: | ---: |
| clean_local | 48 | 0.0 |
| repeated_records | 48 | 0.0 |
| sparse_anomaly | 48 | 0.0625 |
| dependency_chain | 48 | 0.0 |
| malformed_mixed | 48 | 0.0 |
| dense_cross_reference | 48 | 0.0 |
| adversarial_omission | 48 | 0.0 |
| texture_swap | 48 | 0.5625 |

### 対 raw の粗い記述統計（192 paired; 捏造 CI なし）

- mean / median `(T_raw - T_comp)` ≈ **-2.19 / -2.0**（圧縮側が概ねわずかに高い T）
- `compressed` の方が T が低い割合 ≈ **1.6%**
- mean Q: raw ≈ **0.089**, compressed ≈ **0.068**（Q_baseline は概ね **1.0**）

→ confirmatory C1–C3 が全て false であることと整合。**Go ではない。stop。**

## なぜ BITE-15b があったか（失敗モード）

初回フル N_pilot が約51分後に `TimeoutError: The read operation timed out` で落ち、summary/partial が残らなかった。

根因:

1. bare `TimeoutError` がクライアント外へ未捕捉で伝播
2. 呼び出し単位 checkpoint が無く、途中失敗で集計が消える
3. resume が無く、再実行が二重課金しうる

## Fix summary（実装済み・main に含まれる）

| Area | Change |
| --- | --- |
| `zai_client.py` | `ProviderTimeoutError`; 有限指数バックオフ; 429 再試行なし |
| `billed_runner.py` | JSONL checkpoint + atomic partial; resume 方針 |
| `run_billed_pilot.py` | `--checkpoint`, `--resume`（既定 True） |
| `configs/pilot_bite15_billed.json` | retry / checkpoint 既定 |
| Tests | mock のみ（Cloud で 26 passed） |

## Resume policy

- **Skip** latest=`ok`（二重課金禁止）
- **Retry once** prior `timeout`/`error`
- **Skip** prior `rate_limit`（429 storm 回避）

## CLI（親機・完走済み参照）

```powershell
cd D:\develop\works\bite-ingestion
# ZAI_API_KEY via bw-env（値は出さない）

python scripts/run_billed_pilot.py --no-minimal --n-per-family 24 `
  --families clean_local repeated_records sparse_anomaly dependency_chain `
             malformed_mixed dense_cross_reference adversarial_omission texture_swap `
  --checkpoint artifacts/pilot\bite15b_checkpoint.jsonl `
  --partial-out artifacts/pilot\bite15b_billed_partial.json `
  --out artifacts/pilot\bite15b_billed_summary.json `
  --resume
```

## Cloud verification（2026-09-16 UTC・有料なし）

| Check | Result |
| --- | --- |
| `pytest tests/eval/test_billed_pilot_mock.py` | 26 passed |
| `pytest tests/eval/` | 54 passed |
| CLI KEY_ABSENT | exit 2 |

有料実行は Cloud では行わない（ローカル Path B）。

## 未解決 / 次

1. **BITE-15b 本体（有料完走＋決定記録）はクローズ可**
2. **BITE-16**: pilot stop を負の結果として記述統計・error atlas 化（full matrix / Survive 主張はしない）
3. Q≈0 かつ Q_baseline≈1 の系統的崩れの切り分け（評価ハーネス vs モデル応答）は BITE-16 / 後続で文書化

## Do-not

- Go / Survive 捏造禁止
- checkpoint JSONL・キー値をコミットしない
- Cloud から再課金しない
- post-hoc で閾値を動かして Go にしない
