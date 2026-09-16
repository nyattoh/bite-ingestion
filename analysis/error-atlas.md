# Error atlas — BITE-15b billed pilot **v2** (pivot)

Source: `artifacts/pilot/bite15b_billed_summary_v2.json` @ `967ec0b`.

## Transport / protocol

| Class | Count |
| --- | ---: |
| empty `answer_text` | **0 / 384** |
| row `error` | 0 |
| rate_limit | 0 |
| T_completion | min 2 / max 5 / mean ≈ 2.86 |

v1 empty×64 confounder is **cleared** on v2.

## Constraint failures (v2)

| Failure string | Count |
| --- | ---: |
| `Q < Q_baseline - delta` | 46 |
| constraints_ok | 338 |

Almost all failures sit in **`dependency_chain`**（2/48 ok ≈ 0.0417）. Other 7 families are **1.0**.

---

## ⚠️ Path B vs v2 full pilot — dependency_chain 分離

### A) Path B 48-call slice（family-only 再課金）

- **When**: 2026-09-17 05:48:59–05:49:29 JST
- **Scope**: `dependency_chain` のみ；24×2 methods = **48 calls**
- **constraints_ok_rate**: **1.0**（48/48）
- **decision**: **pivot**（Go ではない）
- **Artifacts**: `artifacts/pilot/bite15b_pathb_depchain_summary.json` + partial/checkpoint siblings
- **質問修正**: 「数値だけ答えよ」に明確化；gold は元から数字のみ
- **変更なし**: 閾値・採点関数・Go 条件は不変

### B) v2 full pilot（384-call 全 family 記録）

- **When**: 2026-09-17（時刻範囲は Path B より前）
- **Scope**: 全 8 family；24×2×8 = **384 calls**
- **dependency_chain constraints_ok_rate**: **≈ 0.0417**（2/48）
- **decision**: **pivot**（`c1=False c2=True c3=False`）
- **Artifacts**: `artifacts/pilot/bite15b_billed_summary_v2.json`
- **質問**: 修正前（`K00=100` 形式が exact-match で Q=0）

### 重要な注意

1. **Path B は full Gate C 再実行ではない** — `dependency_chain` 単独の 48-call slice
2. **decision は両方とも pivot** — 1.0 を見ても Go へ変更しない
3. **閾値は不変** — post-hoc adjustment 禁止
4. **全 384 calls は再実行しない** — Path B 結果で v2 full の 0.0417 を置き換えない
5. **Cloud 有料実行は hold** — Path B もローカル（raytrek）のみ

---

## Pattern notes

1. **Gate C = pivot**: C1 false（compressed not cheaper on mean T）, C3 false（net savings ≤ 0）, C2 true only as placeholder equality of constraint rates.
2. **No token win from compressed_passthrough**: every paired `dT_raw_minus_comp = -2` in recompute（comp slightly higher T）.
3. **Quality generally holds** except dependency_chain — treat that family as the primary error locus for follow-up, **not** as a reason to flip Go.
4. **Do not** hide the 46 Q failures behind the 0.88 aggregate ok rate alone.
5. **`dependency_chain` mismatch type（再課金なしで確認）**: gold は数値のみ（例 `100`）だがモデル応答は `K00=100` 形式。exact-match 採点（`metrics_from_instance`）で Q=0。プロンプト/gold 仕様のずれであり、C1/C3 の token 失敗とは別軸。

## Exploratory (not primary)

High ok rates on 7/8 families are descriptive only. No post-hoc promotion to confirmatory win.

## Missing data

- checkpoint JSONL not in git
- no `output/main/failures.jsonl` yet — this atlas is pilot-scoped
