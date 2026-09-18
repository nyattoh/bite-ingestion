# PHASE1D-CONFIRMATORY-OFFLINE 引き継ぎ

- 担当: Grok
- ベース: `origin/main` = `0e50a2c54b2e56beaf749bc4e7ee28be444ca7bd`（PR #18 マージ後）
- ブランチ: `feat/phase1d-confirmatory-offline`
- 実行日: 2026-09-19
- 有料 API: **未使用**（Z.ai / OpenAI / Gemini / `ZAI_API_KEY` / billed pilot いずれも未使用）
- profiler feature / threshold / routing / operator / re-bite / split / freeze pair / tolerance: **未変更**

---

## 目的

BITE を改善することではない。Phase 1B / 1C で固定済みの本番問題とルールを動かさず、同じ evaluation case に 4 方式をかけて、何が起きるかを記録すること。

判定は科学的な Go/Stop ではない。

---

## 実行前 self-check

1. 既存 negative controls（`tests/test_negative_controls.py` + `run_phase1_matrix`）
   - 12 行を事前宣言どおり検出
   - `recall_vis` 低下 / re-bite 成功と失敗の区別 / provenance 欠損
   - violations = none
2. `benchmarks/spec/phase1c-token-freeze.json` の holdout 12 件が、凍結ルール（abs ≤ 3、rel ≤ 4%、padding なし、`prose_narrative` vs `table_csv`）を満たすことを算術検証
3. 凍結 tokenizer（`zai-org/GLM-4.5` @ `cbb2c7cfb52fa128a9660cb1a7a78e017899e115`、`tokenizer.json` SHA256 `93406650…`）で holdout を再カウントし、凍結表と一致することを確認

環境に入っていた `transformers==5.5.0` では `apply_chat_template` が全 pair で 2 token を返し、凍結表と一致しなかった。ルールは変えず、Phase 1C がピンした `transformers==4.54.0` で再測したところ 12/12 一致。tokenizer の再調整はしていない。

---

## 比較条件（固定）

- evaluation / holdout: `syn-case-012` … `syn-case-023` のみを confirmatory とする
- texture: 凍結ペア `prose_narrative` / `table_csv` のみ（padding なし）
- 4 arm: `raw_full` / `length_pi` / `rule_pi` / `rule_pi_rebite`
- 同一 surface では facts / question / answer / required evidence / wrapper / budget を共通
- token 会計は既存 contract（`T_total` = profiler + router + operator + target_in/out + rebite）。新定義なし
- calibration（seeds 0..11）は development / descriptive として別集計。confirmatory に混ぜていない

行数: confirmatory 96、calibration 96。

---

## Confirmatory で起きたこと（平均で結論しない）

| 一覧 | 件数 |
|---|---:|
| length_pi != rule_pi | **0** |
| rule_pi が同一 facts で texture 間で違う sequence | **0** |
| operator が実際に発火（transformed / not no-op） | **0** |
| re-bite 発火 | **0** |
| evidence recall < 1.0 | **0** |
| no-op だった surface | **24 / 24** |
| raw_full と payload 差なし | **24 / 24** |
| profiler は texture で違うが sequence は同じ | **12 / 12 facts_id** |

全 candidate arm の sequence は `CUT`。`raw_full` は空 sequence / `pass_through`。payload は raw と byte 一致。`n_transformed=0`。`T_rebite=0`。recall_vis / recall_rec / provenance は全 confirmatory 行で 1.0。

length_pi が `CUT` な理由（既存ルールのまま）: `extract_budget` が `char_len` を文書から埋め、68–120 文字は `CHAR_SHORT_MAX=256` 以下 → short band。

rule_pi が `CUT` な理由（既存ルールのまま）: `a=0`、`r=0`、`k∈{0, 0.125}` はいずれも `HIGH=0.66` 未満。UNTANGLE / REDUCE / INTEGRATE は載らない。CUT は `pre_segmented=false` のため残る。

### A. 形を見た判断差はあるか

**routing 上の差は無い。** length_pi と rule_pi は 24 surface すべてで同じ `CUT`。

profiler は形の差を観測している。全 12 facts_id で:

- `prose_narrative`: `b=0.35`
- `table_csv`: `b=1.0`

CUT 省略条件は `b≥HIGH AND pre_segmented`。今回 `pre_segmented` は付いていないので、`b=1.0` でも CUT は残る。形の信号は数値に出ているが、現行 routing は噛み方を変えない。

これを「差がある」とは数えない。判定は routing / payload / recall の実測差に置く。

### B. 必要情報を失ったか

失っていない。recall が 1.0 未満の confirmatory 行は 0。R へ動いた gold も 0。

### C. re-bite は必要なときだけか

発火していない。R が空なので取り戻す対象が無い。無駄な re-bite 課金も無い。

### D. 余計な処理コストか

candidate は CUT を選ぶが no-op で、最終 payload は raw_full と同じ。`T_total` 差は 0。圧縮も隔離もしていない。

### E. raw_full とのトレードオフ

情報保持は同じ。送る本文も同じ。オフラインでは 4 方式を区別する材料が、この holdout には無い。

calibration 96 行も同じ形（length_pi != rule_pi = 0、operator/rebite 発火 0）。confirmatory 判定には使っていない。

---

## 判定

```text
PHASE1D_OFFLINE_NO_SIGNAL
```

現在の凍結 benchmark（holdout 12 × 凍結ペア）では、長さだけの方式との差が実質的に観測できない。

「BITE wins」「morphology is superior」「Go」「production ready」ではない。
長さだけで説明できる、追加価値が見えない、4 方式がほぼ同じ、がこの matrix の記述になる。

有料モデルへ進めても、この holdout では 4 arm が同一 payload を送ることになる。それは課金比較ではなく、同じ prompt を 4 回払うことに近い。有料 smoke は Path B / 人間判断。

---

## 変更していないもの

| | |
|---|---|
| profiler feature | 未変更 |
| profiler 計算 | 未変更 |
| threshold / `TBD_CALIBRATE` | 未変更 |
| routing rule | 未変更 |
| CUT / UNTANGLE / REDUCE / INTEGRATE | 未変更 |
| re-bite / recovery | 未変更 |
| calibration / evaluation split | 未変更 |
| evaluation case / 問題文 / 正解 / required evidence | 未変更 |
| renderer / freeze pair / token-match tolerance | 未変更 |
| 有料 runner | 未変更 |

追加したのは、canonical packet を既存 4 arm へ渡す薄いアダプタ、記録、検証だけ。

---

## 作業中に直した記録上の欠陥（ルール変更ではない）

1. **tokenizer ライブラリ版**  
   5.5.0 では再測が全 2 token。凍結条件は 4.54.0。ルールは触らずピン版で再測した。
2. **texture 間の payload hash を「判断差」と数えていた**  
   prose と table は本文が違うので hash は必ず違う。初回はこれが 12 件の偽 SIGNAL になった。sequence / status の比較に直し、判定は `NO_SIGNAL`。BITE 側は変えていない。

---

## 成果物

- `artifacts/phase1d/confirmatory-offline.json` — 生行（family/arm/case を隠していない）
- `artifacts/phase1d/confirmatory-offline.md`
- 本 handover

再生成: `python scripts/run_phase1d_confirmatory.py`（tokenizer 再測あり。通常 CI には載せない）

---

## 検証

```text
ruff check src tests
mypy src
pytest
scripts/validate_artifacts.py
```

有料 API 禁止は維持。core tests はオフライン。
