# PHASE2B-CALIBRATION-LENGTH-CONTROL 引き継ぎ

- 担当: Grok
- ベース: `origin/main` = `dce759efbb94ae941a86c3358b1b717da3224c14`（PR #20 Phase 2A merge 後。remote で確認）
- ブランチ: `feat/phase2b-calibration-length-control`
- 実行日: 2026-09-19
- 有料 API: **未使用**
- profiler / routing / threshold / operator / re-bite: **未実行・未import**
- Phase 2A 設計（canonical / scale / dependency / split / surface axes / evidence / Q+A / replica）: **未変更**
- Phase 1C tokenizer 条件・match 閾値: **未変更（緩めず）**
- evaluation / holdout: **封印**（replicas 2,3 の surface 生成・token 計測・coverage なし）

---

## 目的

BITE の性能評価ではない。

Phase 2A の 12 calibration canonical cases について、同じ facts / question / answer / required evidence のまま、形だけ変えた 8 surface が、Phase 1C の prompt contract でどれだけ token 長が近いかを測る。

padding / filler / whitespace / comment / 書き換え / distractor 削除による長さ合わせはしていない。

---

## Tokenizer / prompt

Phase 1C 凍結を再利用:

- repo: `zai-org/GLM-4.5`
- revision: `cbb2c7cfb52fa128a9660cb1a7a78e017899e115`
- `transformers==4.54.0`
- `tokenizer.json` SHA256: `9340665016419c825c4bdabbcc9acc43b7ca2c68ce142724afa829abb1be5efd`

環境に入っていた `transformers==5.5.0` は使っていない。ハッシュ不一致なら停止する。hosted `glm-4.5-flash` との byte 一致は主張しない。

prompt は Phase 1C と同じ `system + user wrapper + document + question + generation prompt`（`enable_thinking=False`）。wrapper は新設していない。

---

## 測定範囲

- split: calibration only（replicas 0, 1）
- 12 canonical × 8 surface = 96
- within-case paired contrast: 軸 3 × 4 pair × 12 cases = 144
- 別 case 同士は pair にしない
- runner は `--split evaluation` で生成前に fail-closed

## Morphology coverage（profiler 値は未使用）

12/12 calibration cases で:

- structure: surface hash が異なる（4/4 pair）
- dispersion: required evidence の span 距離が広がる（4/4 pair）
- redundancy: non-gold 出現が増える（4/4 pair）
- canonical required evidence は 8 surface で同一

---

## Phase 1C 基準（abs ≤ 3 かつ rel ≤ 4%、padding なし）

| axis | n | matched | match rate | mean abs | median abs | max abs |
|---|---:|---:|---:|---:|---:|---:|
| dispersion | 48 | 48 | 1.0 | 0 | 0 | 0 |
| structure | 48 | 0 | 0.0 | 654 | 467 | 2039 |
| redundancy | 48 | 0 | 0.0 | 1795 | 1260 | 4588 |

scale / dependency 別:

- dispersion: small/medium/large すべて 16/16、direct/chain3 すべて 24/24。delta は常に 0。
- structure: どの scale / dependency でも 0/。small でも min abs=71、min rel≈26%。large は max abs=2039、rel≈36%。
- redundancy: どの scale / dependency でも 0/。small でも min abs=240、min rel≈66%。large は max abs=4588、rel≈98%。

## 知りたかったこと

1. **dispersion** — 同じ token 長のまま比較できる。この renderer では並び替えだけで、prompt token 数は完全一致した。
2. **structure** — 自然なままでは Phase 1C 基準に入らない。nested JSON は fact ごとに wrapper が乗り、文書が長いほど差が開く。small でも失敗。
3. **redundancy** — 長さと本質的に共変する。high は non-gold を 3 回書く設計なので、失敗ではなく観測。small でも失敗し、scale とともに差が拡大する。
4. **scale** — dispersion は不変。structure / redundancy は large ほど差が大きいが、small でも基準内には入らない。
5. **dependency** — direct と chain3 で判定は変わらない。

## Candidate alternative tolerance（混ぜない・凍結しない・evaluation に使わない）

公式基準は見てから広げていない。

検査用に `abs<=10 / rel<=10%` と `abs<=25 / rel<=15%` を別表で出した。どちらも structure 0/48、redundancy 0/48 のまま。dispersion だけ 48/48。

つまり「閾値を少し緩める」では structure / redundancy の自然マッチは救えない。padding もしていない。次の construction が要るなら、それは公式 Phase 1C 閾値の拡張ではない。

---

## 判定

```text
PHASE2B_LENGTH_CONTROL_PARTIAL
```

dispersion だけは、次の freeze に使える自然な length-controlled contrast が calibration で揃った。structure と redundancy は、padding なしの現行 surface では長さと形を分離できない。

BITE wins / morphology superior / Go ではない。有料評価には進んでいない。evaluation は未開封。

---

## 成果物

- `src/bite_bench/phase2b.py`
- `scripts/measure_phase2b_calibration_lengths.py`
- `artifacts/phase2b/calibration-token-matrix.json`
- `artifacts/phase2b/calibration-length-control.md`
- `benchmarks/spec/phase2b-length-control-draft.json`（draft。freeze ではない）
- `tests/test_phase2b_length_control.py`
- 本 handover

再測: `python scripts/measure_phase2b_calibration_lengths.py`（`transformers==4.54.0` が必要。通常 CI には載せない）

---

## 検証

```text
ruff check src tests
mypy src
pytest
scripts/validate_artifacts.py
```

core tests はオフライン。有料 API 禁止は維持。
