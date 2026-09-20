# PHASE3S-REFERENCE-SPECIFICITY 引き継ぎ

- 担当: Grok
- 前提: `PHASE3R_CHANNEL_PLANNER_VALIDATED`
- ブランチ: `feat/phase3s-reference-specificity-audit`
- S0 freeze: `3525506c4601f4471489a15f78d013900c05eda1`
- 実行日: 2026-09-19
- 有料 API: **未使用**
- p3f evaluation replica 2/3: **未開封**
- Phase 3R artifact / R0 / policy v3 / planner / sensor v2: **未変更**
- Phase 3Q: **FAILED のまま**
- `_key_side_atoms` / threshold / gate / planner / operator: **修理していない**

---

## 判定

```text
PHASE3S_REFERENCE_SPECIFICITY_FAILED
```

fresh p3s 112 surfaces。ok は 64/112。cross-format は 28/28。

true / prefix / suffix-text / substring は edge set exact。

suffix collision 3 family は false reference edge が 1 本ずつ付く（atom は dest key の underscore suffix）。距離 4 / 9 では intended 0 なのに gate が開く。`suffix_collision_plus_actionability` の d4/d9 では sequence が `[UNTANGLE, REDUCE_v2, INTEGRATE]` になる。

この PR では sensor / threshold / predicate を直していない。

```text
Phase3Q remains FAILED
```

claim は reference-edge specificity audit only。routing / real-world generalization / BITE superiority ではない。

---

## 成果物

- `benchmarks/spec/phase3s-reference-specificity-freeze.json`
- `artifacts/phase3s/reference-specificity.json`
- `artifacts/phase3s/edge-rows.json`
- `artifacts/phase3s/edge-precision.json`
- `artifacts/phase3s/gate.json`
- `artifacts/phase3s/policy-consequence.json`
- `artifacts/phase3s/cross-format.json`

---

## 次

FAIL の修理は別 PR。p3f evaluation は開けない。main へ merge しない。
