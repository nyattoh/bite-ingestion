# PHASE3K-STRUCTURAL-REDUNDANCY 引き継ぎ

- 担当: Grok
- 前提: Phase 3J `PHASE3J_TEXTURE_SENSOR_REVISION_REQUIRED`
- ブランチ: `feat/phase3k-structural-redundancy-v1`
- K0 commit: `526601b68a0eec9861b012ef5ddc67078447bf36`
- 実行日: 2026-09-19
- 有料 API: **未使用**
- p3k evaluation replica 2/3: **未開封**
- p3f evaluation replica 2/3: **未開封**
- deterministic_v0.r / a / k / v1 / A / T_low=1 / T_high=4 / RulePolicy: **未変更・未接続**

3J で `r` が stripped-line 重複率のため compact JSON で見えなくなった。行ではなく logical record の exact duplicate だけを測る `structural_redundancy_v1` を新規 module にした。v0 の `r` は上書きしていない。

---

## 判定

```text
PHASE3K_REDUNDANCY_SENSOR_READY
```

BITE wins / Go ではない。RulePolicy には接続していない。threshold は作っていない。

---

## Sensor

- primary: `duplicate_unit_ratio = 0 if n_records==0 else 1 - n_unique / n_records`
- equality: exact `(key, value)` のみ。near-duplicate / semantic は扱わない
- KV: 空でない行、最初の `=`、separator 周辺の外側 whitespace のみ除去
- JSON: top-level array の `{k,v}`。compact / pretty / object key order は identity に入れない
- malformed structured と NUL は fail closed。line fallback しない
- 集計は `Counter`。pairwise O(n²) は使わない

---

## Calibration（p3k, replicas 0/1）

exact duplicate / all unique / same-key-diff-value / same-value-diff-key / reorder / multiplicity 2・3 / prefix / suffix / identifier substring を key=value・compact JSON・pretty JSON で測定。evaluation 2/3 の ID は freeze 済み、未測定。

---

## 成果物

- `benchmarks/spec/phase3k-structural-redundancy-freeze.json`
- `benchmarks/spec/phase3k-split-manifest.json`
- `src/bite_ingestion/profilers/structural_redundancy_v1.py`
- `artifacts/phase3k/structural-redundancy.json`
- `tests/test_phase3k_structural_redundancy.py`

---

## 次

READY でもこの Phase では routing に接続しない。p3k / p3f evaluation は開けない。
