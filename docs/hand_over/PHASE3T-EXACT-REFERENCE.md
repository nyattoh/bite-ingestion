# PHASE3T-EXACT-REFERENCE 引き継ぎ

- 担当: Grok
- 前提: `PHASE3S_REFERENCE_SPECIFICITY_FAILED`
- ブランチ: `feat/phase3t-exact-reference-v3`
- T0 freeze: `70a3f7792a5baee1382b890fb7021dc7fb234ce1`
- 実行日: 2026-09-19
- 有料 API: **未使用**
- p3f evaluation replica 2/3: **未開封**
- Phase 3S artifact / verdict / S0: **未変更**
- Phase 3Q: **FAILED のまま**
- v2 sensor / policy v3 / planner / operators / composition_safety_v2: **未変更**
- threshold grid 再探索 / T_high 再校正: **していない**
- T_high=4 は exact-reference bridge で v2/v3 が edge set / n_edges / mean まで exact 一致した距離尺度の carry-forward

---

## 判定

```text
PHASE3T_EXACT_REFERENCE_VALIDATED
```

fresh p3t 128 surfaces。ok は 128/128。4 format で edge set / gate / policy sequence exact。

exact hop の距離 1 / 3 / 4 / 9 は intended edge だけ。suffix collision は edge=0。true+collision でも true edge だけ残り、d4 の mean は 4 のまま gate=true。actionability 家族は d4/d9 でも gate=false、sequence=`[]`。

exact-reference bridge 16/16 で v2/v3 exact。`T_high_reference=4` を policy v4 へ接続。

Phase 3S の 48 surface は secondary のみ。suffix collision と actionability は false edge が消える（32/48 ok）。mix 16 surface は 3S の “true hop” が `cider_press`→`dst_cider_press` の suffix 一致だったため、v3 では edge=0。narrowing であり primary に入れない。3S verdict は FAILED のまま。

```text
Phase3S remains FAILED
Phase3Q remains FAILED
```

claim は last synthetic-only mechanism repair: exact reference identity まで。routing / real-world generalization / BITE superiority ではない。

---

## 何を直したか

- `reference_identity_v1` は KV key / JSON `k` の maximal full identifier だけを target にする。underscore suffix を展開しない。
- `dependency_dispersion_v3` の edge は source value atom と target full token の exact equality のみ。
- `conditional_texture_policy_v4` の gate は `n_reference_edges > 0 AND mean_reference_edge_distance >= 4`。sequence は既存 `projected_actionability_plan_v1`。

---

## 成果物

- `benchmarks/spec/phase3t-exact-reference-freeze.json`
- `artifacts/phase3t/exact-reference.json`
- `artifacts/phase3t/exact-edge.json`
- `artifacts/phase3t/threshold-bridge.json`
- `artifacts/phase3t/gate.json`
- `artifacts/phase3t/policy-consequence.json`
- `artifacts/phase3t/phase3s-regression.json`

---

## 次

VALIDATED なので次は Phase 4 real-structured corpus。XFER-3 は作らない。p3f evaluation は開けない。main へ merge しない。Phase 3S / 3Q を CONFIRMED に書き換えない。
