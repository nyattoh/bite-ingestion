# PHASE3H-OPERATOR-MAP 引き継ぎ

- 担当: Grok
- 前提: Phase 3G `PHASE3G_CALIBRATION_LOCKED`（A `mean_edge_distance`, T_low=1, T_high=4）
- ブランチ: `feat/phase3h-operator-map-experiment`（3G HEAD から）
- H0 commit: `fb425a0a75a1077b32bc49a0036f2888ea17e802`
- 実行日: 2026-09-19
- 有料 API: **未使用**
- p3f evaluation replica 2/3: **未開封**
- v1 / A / thresholds / RulePolicy: **未変更・未接続・未実装**

high dispersion を固定し、間の texture（redundant / unique / anomalous）だけ変えた新規 generation `p3h` で、CUT / REDUCE / INTEGRATE / UNTANGLE を isolated に比較した。

---

## 判定

```text
PHASE3H_CONDITIONAL_MAP_REQUIRED
```

BITE wins / Go ではない。M1 / M2 は選んでいない。RulePolicy は実装していない。

H0 の事前規則:

- redundant × REDUCE が効く
- unique × INTEGRATE が効く
- anomalous × UNTANGLE が効く
- の三点が同時なら、high bin だけでは operator を決めない

---

## 測定

- 12 development surfaces（3 texture × 2 replica × 2 format）
- far / one_hop / medium pads=24。全 surface で `mean_edge_distance=25` → high
- 48 isolated rows
- gold recall は全 arm で 1.0
- token 削減は記録したが verdict には使っていない

| texture | 効いた arm | 内容 |
|---|---|---|
| redundant | REDUCE | 重複 pad 12 本を除去。gold は残る |
| unique | INTEGRATE | gold 2 unit を `id=` で join。CUT/REDUCE は no-op |
| anomalous | UNTANGLE | ERROR pad 4 本を隔離。gold は残る |

CUT は pre-split logical units では全 texture で no-op。

---

## 成果物

- `benchmarks/spec/phase3h-operator-map-freeze.json`
- `artifacts/phase3h/operator-map-experiment.json`
- `artifacts/phase3h/operator-map-experiment.md`
- `src/bite_bench/phase3h.py`
- `src/bite_eval/phase3h_experiment.py`
- `tests/test_phase3h_operator_map.py`

---

## 次

CONDITIONAL なのでここで停止する。high bin を operator に変換しない。p3f evaluation は開けない。A / T / v1 を動かさない。
