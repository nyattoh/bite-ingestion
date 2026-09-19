# PHASE3M-CONDITIONAL-ROUTING 引き継ぎ

- 担当: Grok
- 前提: `PHASE3H_CONDITIONAL_MAP_REQUIRED` / `PHASE3I_COMPOSITE_PROVENANCE_VALIDATED` / `PHASE3L_REDUNDANCY_HOLDOUT_CONFIRMED`
- ブランチ: `feat/phase3m-conditional-routing-v1`
- M0 freeze commit: `ad95ed8bb0a60ec6c3a10c4a9ccc96f395bcf702`
- 実行日: 2026-09-19
- 有料 API: **未使用**
- p3m evaluation replica 2/3: **未開封**
- p3f evaluation replica 2/3: **未開封**
- RulePolicy / a / k / v1 / A=`mean_edge_distance` / T_low=1 / T_high=4: **未変更**
- Phase 3L artifact / verdict: **未改変**

3L の portability addendum は PR #35（metadata only）。本 Phase はそこから分岐した。

---

## 判定

```text
PHASE3M_CONDITIONAL_ROUTING_READY
```

development 0/1 の 48/48 で、frozen predicate が期待 sequence を出し、composition safety を満たした。BITE wins / Go ではない。p3m / p3f evaluation は開けていない。

---

## Routing

- 新 policy: `conditional_texture_policy_v1`。既存 `RulePolicy` は baseline のまま
- 起動条件: `n_edges > 0` AND `mean_edge_distance >= 4`
- `n_edges == 0` は low ではなく dependency-dispersion contribution なし
- high dispersion 単独では operator を選ばない（neutral → `[]`）
- REDUCE: `structural_redundancy_v1.fail_closed==false` AND `duplicate_unit_ratio > 0`
- UNTANGLE: 少なくとも 1 unit が `injection_suspect` / `malformed` / `anomaly_candidate`（`dependency_edge` 単独では発火しない。判定は `operators/preflight.py` を UNTANGLE 本体と共有）
- INTEGRATE: exact `id=` / `key=` の 2 unit 以上 cluster。k threshold なし。v1 edges は context に流さない
- 順序: UNTANGLE → REDUCE → INTEGRATE。CUT は含めない
- 空 sequence は identity（grammar の empty 禁止は RulePolicy 側のまま）

---

## Split（p3m）

- development: replicas 0, 1（測定済み）
- evaluation: replicas 2, 3（freeze 済み、未測定）
- p3h / p3j / p3k fixture は再利用していない

---

## 成果物

- `benchmarks/spec/phase3m-conditional-routing-freeze.json`
- `benchmarks/spec/phase3m-split-manifest.json`
- `src/bite_ingestion/policies/conditional_texture_policy_v1.py`
- `src/bite_ingestion/operators/preflight.py`
- `artifacts/phase3m/conditional-routing.json`
- `artifacts/phase3m/composition-safety.json`
- `docs/hand_over/PHASE3M-CONDITIONAL-ROUTING.md`

---

## 次

p3m evaluation 2/3 と p3f evaluation は開けない。PARTIAL/BLOCKED 時の predicate 再調整はしていない（READY のため不要）。main へ merge しない。
