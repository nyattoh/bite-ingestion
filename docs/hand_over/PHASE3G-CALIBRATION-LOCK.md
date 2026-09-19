# PHASE3G-CALIBRATION-LOCK 引き継ぎ

- 担当: Grok
- 前提: Phase 3F v0.3 `PHASE3F_ROUTING_CALIBRATION_PROTOCOL_FROZEN`（PR #29）
- ブランチ: `feat/phase3g-calibration-lock`（3F HEAD から）
- 実行日: 2026-09-19
- 有料 API: **未使用**
- Phase 2 holdout: **未使用**
- v1 / RulePolicy / HIGH / LOW: **未変更・未接続**
- evaluation split: **未開封**（replica 2,3 は fail closed）
- M1 / M2: **未選択**
- grid 拡張 / tolerance 追加: **なし**

calibration split（replica 0,1）だけを v0.3 規則で初めて測定し、candidate と threshold をロックした。

---

## 判定

```text
PHASE3G_CALIBRATION_LOCKED
```

BITE wins / Go ではない。

- selected candidate: `A_mean_edge_distance`
- selected thresholds: `T_low=1`, `T_high=4`
- high bin は operator に変換していない
- RulePolicy には接続していない

---

## 測定

- primary 108 + adversarial 24 = 132 calibration surfaces
- sensor: `dependency_dispersion_v1` を 1 回ずつ
- gold / intended_edges は scorer のみ。sensor 入力は `payload` / `text`

`edge_false_positive_rate` は記録した。grid にも A/B/C 選択にも使っていない。sensor は変えていない。

`true_dep_plus_misleading_suffix` の edge precision / extra-edge count は別 diagnostic。suffix rule は変えていない。

---

## Pre-threshold（v0.3 定義、exact comparison）

A / B / C とも:

- continuous_dispersion_ordering_coverage = 1.0
- scale_stability = 1.0

C に scalar score は作っていない。weighted sum はしていない。

---

## Grid

凍結 grid のみ。A 32 / B 30 / C 20 点。全 candidate に eligible point あり。救済なし。

A の best: negative elevated bin rate 0、bin_ordering 1.0、format_consistency 1.0 のうえ smallest T_high then T_low → `T_low=1`, `T_high=4`。

A/B/C の pre-threshold が同一なので、v0.3 の tie は A → B → C。A を採用。

---

## 成果物

- `artifacts/phase3g/calibration-measurements.json`
- `artifacts/phase3g/calibration-grid-search.json`
- `artifacts/phase3g/calibration-lock.json`
- `artifacts/phase3g/calibration-lock.md`
- `src/bite_eval/phase3g_calibrate.py`
- `tests/test_phase3g_calibration_lock.py`

---

## 次

evaluation はまだ開けない。M1/M2 は Phase 3H。この lock の A と T を RulePolicy に接続しない。
