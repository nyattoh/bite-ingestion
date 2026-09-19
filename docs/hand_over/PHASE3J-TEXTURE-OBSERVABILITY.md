# PHASE3J-TEXTURE-OBSERVABILITY 引き継ぎ

- 担当: Grok
- 前提: Phase 3H `PHASE3H_CONDITIONAL_MAP_REQUIRED`、Phase 3I `PHASE3I_COMPOSITE_PROVENANCE_VALIDATED`
- ブランチ: `feat/phase3j-texture-observability-audit`
- J0 commit: `0cc696632e7bb7a01ea99d5141540f5dcd7088a8`
- 実行日: 2026-09-19
- 有料 API: **未使用**
- p3f evaluation replica 2/3: **未開封**
- deterministic_v0 / v1 / A / T_low=1 / T_high=4 / RulePolicy: **未変更・未実行**

high dispersion を固定し、canonical gold は同じまま intervening texture だけ変えた新規 generation `p3j` で、現行 gold-free feature が operator 選択に必要な texture を観測できるかを測った。p3h fixture は再利用していない。

---

## 判定

```text
PHASE3J_TEXTURE_SENSOR_REVISION_REQUIRED
```

BITE wins / Go ではない。profiler は直していない。RulePolicy には接続していない。新 threshold は作っていない。

---

## 測定

- 24 development surfaces（4 texture × 2 replica × 3 format）
- far / one_hop / pads=24。全 surface で `mean_edge_distance=25` → high
- profiler 入力は `payload` / `text` のみ。gold / texture / operator / query は渡していない

| axis | feature | KV | compact JSON | pretty JSON | format stable |
|---|---|---|---|---|---|
| redundancy | r | true | false | true | false |
| anomaly | a | true | true | true | true |
| reference | k | true | true | true | true |

`r` は stripped-line の重複比。compact JSON は配列全体が 1 行なので、レコード重複が line bag に出ない。KV と pretty JSON では redundant > neutral / unique_reference が成立する。serialization だけで同じ意味構造が別 texture に見える。

`a` は EXCEPTION / TRACEBACK 等の既存 regex で anomalous > neutral。ERROR / FATAL も fixture に入れたが、現行式は変えていない。

`k` は pad 上の `id=` / `key=` / `ref:` で unique_reference > neutral。絶対値の format 一致は要求していない。

---

## 成果物

- `benchmarks/spec/phase3j-texture-observability-freeze.json`
- `artifacts/phase3j/texture-observability.json`
- `artifacts/phase3j/texture-observability.md`
- `src/bite_bench/phase3j.py`
- `src/bite_eval/phase3j_audit.py`
- `tests/test_phase3j_texture_observability.py`

---

## 次

REVISION_REQUIRED なのでこの Phase では profiler を直さない。SUFFICIENT ではないので RulePolicy にも接続しない。p3f evaluation は開けない。
