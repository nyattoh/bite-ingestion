# PHASE2D-CONFIRMATORY-OFFLINE 引き継ぎ

- 担当: Grok
- ベース: `origin/main` = `dce759efbb94ae941a86c3358b1b717da3224c14`（Phase 2A merge 後）
- 前提: Phase 2C v0.2（PR #22）を唯一の判定規則とする
- ブランチ: `feat/phase2d-confirmatory-offline`
- 実行日: 2026-09-19
- 有料 API: **未使用**
- profiler feature / threshold / routing / operator / re-bite: **未変更**
- Phase 2A canonical / surface generation: **未変更**
- tokenizer / prompt contract / Phase 1C length criterion: **未変更（緩めず、padding なし）**
- Phase 2C eligible / signal / verdict 定義: **未変更**（`classify_dispersion_pair` / `decide_phase2d_verdict` を import しただけ）

---

## 判定

```text
PHASE2D_OFFLINE_NO_SIGNAL
n_signal / n_eligible = 0 / 48
```

これは有料モデル精度ではない。BITE の優劣主張ではない。1 pair からの一般化もしない。今回は 0/48 なので一般化対象の SIGNAL pair はない。

---

## 実行順

1. Phase 2C v0.2 freeze が `freeze_manifest()` と一致することを確認
2. 既存 negative controls / instrumentation self-check
3. 両方成功したあとだけ evaluation を開封（replicas 2, 3）
4. 48 frozen dispersion pair の prompt token 長を Phase 1C tokenizer で測定
5. Phase 1C criterion を満たす pair だけ 4 arm × clustered/dispersed を実行
6. 外れ pair は記録して除外。救済しない

self-check 失敗時は evaluation を開かず `PHASE2D_BLOCKED`。今回は freeze ok、negative controls ok、tokenizer pin ok。

---

## Tokenizer / prompt

Phase 1C 凍結を再利用:

- repo: `zai-org/GLM-4.5`
- revision: `cbb2c7cfb52fa128a9660cb1a7a78e017899e115`
- `transformers==4.54.0`
- `tokenizer.json` SHA256: `9340665016419c825c4bdabbcc9acc43b7ca2c68ce142724afa829abb1be5efd`

環境の `transformers==5.5.0` は使っていない。hosted `glm-4.5-flash` との byte 一致は主張しない。

token 長は Phase 1C の system + user wrapper + generation prompt。arm 実行は既存 `arm_rows_for_packet` / `OFFLINE_WRAPPER`。どちらも変えていない。

---

## Length criterion（48 pair）

| 項目 | 値 |
|---|---:|
| planned pairs | 48 |
| abs_delta = 0 | 48 |
| length_matched | 48 |
| excluded (not rescued) | 0 |
| eligible | 48 |
| confirmatory rows | 384（上限どおり） |

calibration（Phase 2B）と同じく、evaluation でも dispersion pair の prompt token 数は完全一致した。基準は広げていない。

---

## v0.2 signal 判定（eligible 48）

| 項目 | 件数 | signal? |
|---|---:|---|
| length_pi clustered/dispersed behavior 同一 | 48 | 前提（不一致なら consistency issue） |
| rule_pi sequence 差 | 0 | これがあれば signal |
| rule_pi transformed/no-op 差 | 0 | これがあれば signal |
| rule_pi_rebite recovery-fire 差 | 0 | これがあれば signal |
| raw payload hash 差 | 48 | **しない**（入力順が違う） |
| recall 差 | 0 | 単独ではしない |
| provenance 差 | 0 | 単独ではしない |
| T_total 差 | 2 | 単独ではしない |
| length_pi != rule_pi | 48 | 単独ではしない |

`dispersion_specific_signal` は 0。consistency issue は 0。failed arm は 0。re-bite 発火は 0。visible/recoverable recall と provenance は全 confirmatory 行で 1.0。

T_total 差の 2 pair はどちらも large / direct / flat / high。rule_pi sequence は両 surface とも `CUT, REDUCE`。値は clustered 1184 vs dispersed 1183。1 token の差であり、v0.2 では signal にしない。

---

## 分布（n_signal / n_eligible）

| 軸 | 内訳 |
|---|---|
| scale | small 0/16, medium 0/16, large 0/16 |
| dependency | direct 0/24, chain3 0/24 |
| structure | flat 0/24, nested 0/24 |
| redundancy | low 0/24, high 0/24 |

---

## 観測（signal ではない）

Phase 1D の短文 holdout と違い、Phase 2A evaluation surface は 516–23318 文字。既存ルールのまま operator は載る。

length_pi（96 surface）:

- small: `CUT, REDUCE` 16 行は no_op、`CUT, REDUCE, INTEGRATE` 16 行も no_op
- medium/large: `CUT, REDUCE, INTEGRATE`。transformed 48 / no_op 32
- clustered と dispersed で sequence / status は一致

rule_pi / rule_pi_rebite（各 96 surface、両者同じ）:

- flat: ほぼ `CUT`（no_op）。large の一部だけ `CUT, REDUCE` で transformed 4 行
- nested: `CUT, UNTANGLE`（no_op 44）。large の一部だけ `CUT, UNTANGLE, REDUCE` で transformed 4 行
- clustered と dispersed で sequence / status は一致

length_pi と rule_pi は **同じ packet でも sequence が違う**（48/48）。これは dispersion 対比ではなく、length policy と rule policy の差。v0.2 どおり endpoint として数えるだけで signal にしない。

raw_full は常に空 sequence / pass_through。payload hash は clustered と dispersed で常に違う（並び替え）。

---

## 変更していないもの

- profiler features / thresholds
- routing rules / operators / re-bite
- Phase 2A generation
- Phase 1C tokenizer / prompt / abs≤3 / rel≤4% / no padding
- Phase 2C v0.2 の eligible / signal / verdict 定義

---

## 成果物

- `artifacts/phase2d/confirmatory-offline.json`
- `artifacts/phase2d/confirmatory-offline.md`
- `src/bite_eval/phase2d_confirmatory.py`
- `scripts/run_phase2d_confirmatory.py`
- `spec/phase2d-confirmatory-offline.schema.json`
- `tests/test_phase2d_confirmatory.py`

---

## 次にやらないこと

結果を見て threshold / routing / operator を再調整しない。
paid API を呼ばない。
main へ merge しない（この作業の範囲）。
