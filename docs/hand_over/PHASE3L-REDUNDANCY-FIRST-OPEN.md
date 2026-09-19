# PHASE3L-REDUNDANCY-FIRST-OPEN 引き継ぎ

- 担当: Grok
- 前提: Phase 3K `PHASE3K_REDUNDANCY_SENSOR_READY`
- ブランチ: `feat/phase3l-redundancy-first-open`
- K0: `526601b68a0eec9861b012ef5ddc67078447bf36`
- L0 commit: `d365d0b1bd4cb3dcdad617ed4e78df19fdf23ce6`
- 実行日: 2026-09-19
- 有料 API: **未使用**
- p3k evaluation replica 2/3: **今回初測定**
- p3f evaluation replica 2/3: **未開封**
- `structural_redundancy_v1` / p3k generation / split / FAMILY_EXPECT / v0 / v1 / A / T / a / k / RulePolicy: **未変更**

K0 で freeze 済みの family を、新しい replica 値（2/3）で exact 比較した。unseen morphology / 外部 generalization ではない。

---

## 判定

```text
PHASE3L_REDUNDANCY_HOLDOUT_CONFIRMED
```

BITE wins / Go ではない。RulePolicy には接続していない。redundancy threshold は作っていない。

---

## 測定

- 60 evaluation surfaces（10 family × replica 2/3 × 3 format）
- development 0/1 は再測定していない
- malformed / NUL / top-level object は holdout 成功項目に含めていない
- 60/60 frozen expect exact
- cross-format 4 指標 exact
- exact_dup_pairs と reordered_duplicates が exact
- negative families は `duplicate_unit_ratio == 0`

---

## 成果物

- `benchmarks/spec/phase3l-redundancy-first-open-freeze.json`
- `artifacts/phase3l/redundancy-first-open.json`
- `src/bite_eval/phase3l_eval.py`
- `tests/test_phase3l_redundancy_holdout.py`

---

## 次

CONFIRMED でも routing に接続しない。p3f evaluation は開けない。sensor は直さない。
