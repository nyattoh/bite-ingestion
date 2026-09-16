# Main results — BITE-15b billed pilot **v2** (Gate C = pivot)

- **Authoritative pilot record**: `artifacts/pilot/bite15b_billed_summary_v2.json` @ [`967ec0b`](https://github.com/nyattoh/bite-ingestion/commit/967ec0b)
- **Recompute**: `analysis/bite15b_pilot_recompute_v2.json`
- **Stance**: Pivot-to-bench. **No Survive. No Go.**

## Decision (v2)

| Field | Value |
| --- | --- |
| decision | **pivot** |
| reason | `c1=False c2=True c3=False` |
| paid_api | true |
| estimate_source | `provider_usage_billed`（384/384） |
| empty answers | **0/384**（minimal smoke も 0/12） |
| sample_meets_n_pilot | true |
| constraints_ok_rate | **0.880208**（338/384） |
| rate_limit / timeout | none |

C2 is a **runner placeholder**（compressed constraints_ok_rate ≥ raw）. It is **not** a true morphology-vs-length-only contrast. Partial confirmatory → **pivot**, not go.

## v1 superseded (not final science)

| | v1 (`e44b5bd`) | v2 (`967ec0b`) |
| --- | --- | --- |
| decision | stop | **pivot** |
| empty answers | 354/384 | **0/384** |
| T_completion | always 64 | min 2 / max 5 / mean ≈ 2.86 |
| confounder | thinking/empty content | mitigated（thinking disabled） |

## Descriptive tallies (v2; no invented CIs)

| Metric | Value |
| --- | --- |
| paired instances | 192 |
| mean / median (T_raw − T_comp) | **-2 / -2** |
| fraction compressed lower T | **0** |
| mean Q raw / compressed | **0.880 / 0.880** |
| failure `Q < Q_baseline − δ` | **46**（ほぼ `dependency_chain`） |

## Family constraints_ok_rate (v2)

| family | rate |
| --- | ---: |
| clean_local | 1.0 |
| repeated_records | 1.0 |
| sparse_anomaly | 1.0 |
| **dependency_chain** | **0.0417** |
| malformed_mixed | 1.0 |
| dense_cross_reference | 1.0 |
| adversarial_omission | 1.0 |
| texture_swap | 1.0 |

---

## ⚠️ Path B vs v2 full pilot — dependency_chain 分離

### A) Path B 48-call slice（family-only 再課金）

- **When**: 2026-09-17 05:48:59–05:49:29 JST
- **Scope**: `dependency_chain` のみ；24×2 methods = **48 calls**（全 384 では**ない**）
- **constraints_ok_rate**: **1.0**（48/48）
- **decision**: **pivot**（Go ではない）
- **Artifacts**: `artifacts/pilot/bite15b_pathb_depchain_summary.json` + partial/checkpoint siblings
- **質問修正**: 「{code} の数値だけ答えよ」に明確化；gold は元から数字のみ
- **変更なし**: δ / ρ / η、採点関数、Go 条件は不変

### B) v2 full pilot（本ページ主記録）

- **When**: 2026-09-17（時刻範囲は Path B より前）
- **Scope**: 全 8 family；24×2×8 = **384 calls**
- **dependency_chain constraints_ok_rate**: **≈ 0.0417**（2/48）— **この 0.0417 が上表の値**
- **decision**: **pivot**（`c1=False c2=True c3=False`）
- **Artifacts**: `artifacts/pilot/bite15b_billed_summary_v2.json`（このページの権威ある記録）
- **質問**: 修正前（`K00=100` 形式が exact-match で Q=0）

### 重要な注意

1. **Path B は full Gate C 再実行ではない** — `dependency_chain` 単独の 48-call slice
2. **decision は両方とも pivot** — Path B で 1.0 を達成しても Go へ変更しない
3. **閾値・採点・Go 条件は不変** — post-hoc adjustment 禁止
4. **全 384 calls は再実行しない** — Path B 結果で v2 full の dependency_chain 率（0.0417）を**置き換えない**
5. **上表の 0.0417 は v2 full pilot の値** — Path B の 1.0 と混同しない
6. **Cloud 有料実行は hold** — Path B もローカル（raytrek / Path B）のみ

---

## What this is not

- Not Go（C1∧C3 false; C2 placeholder）
- Not full `N_full` matrix / `output/main/aggregates.parquet`
- Not Survive architecture claim

## Next

- Error atlas: concentrate on `dependency_chain` Q failures
- BITE-16 continues under **pivot** standing; do not promote post-hoc subgroups to primary
