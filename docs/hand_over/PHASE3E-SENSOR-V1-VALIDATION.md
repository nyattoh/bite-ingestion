# PHASE3E-SENSOR-V1-VALIDATION 引き継ぎ

- 担当: Grok
- 前提: Phase 3D `PHASE3D_V1_DESIGN_FROZEN`（PR #27）
- ブランチ: `feat/phase3e-sensor-v1-implementation`（3D HEAD から作成）
- 実行日: 2026-09-19
- 有料 API: **未使用**
- Phase 2 evaluation: **未使用**
- Phase 3D freeze の期待値 / edge rule / format scope: **未変更**
- `dependency_dispersion_v0` / deterministic_v0 / RulePolicy / HIGH / LOW: **未変更・未接続**

v1 は別モジュール。v0 は残した。routing には載せていない。

---

## 判定

```text
PHASE3E_V1_VALIDATED
```

required formats で動作。freeze した fixture 関係をすべて満たす。false-positive は edge=0。NUL は fail-closed。per-value 全文書再走査はアルゴリズムから除去。BITE wins / Go ではない。

---

## 実装

`src/bite_ingestion/profilers/dependency_dispersion_v1.py`

- 距離: logical unit index。空行は unit にしない。JSON は document parse。pretty / compact が同じ構造なら同じ unit 列
- edge: `value_to_key_or_record_id`。value-side identifier が別 unit の key-side または record-id フィールド（`id` / `k`）に出たときだけ
- key-side は `_` 区切り suffix も index する（`bin_id_alpha_77` が `id_alpha_77` を露出）。Phase 2 prefix の hard-code ではない
- 同一 canonical copy と自己参照は edge にしない。value-value 共起は primary にしない
- 1 パスで target index を作り、value identifier は `dict.get`。`_contains_atom` による全行スキャンは無い
- feature: n_edges / mean_edge_distance / mean_edge_distance_norm / component_span / chain_span
- diagnostic: n_logical_units / n_identifier_occurrences / n_value_identifiers / n_index_lookups / n_candidate_targets（routing にしない）

raw / normalized の routing 採用と INTEGRATE 閾値は未決定。

---

## Fixture（freeze のまま）

21/21 一致。near < medium < far は 1 < 4 < 9。pretty=compact。blank で距離不変。共有 env/service/owner/label と無関係同一 id は n_edges=0。pollution は true near と同じ 1 edge / distance 1。one-hop / two-hop / branch も freeze 値。

---

## Cost

protocol: warmup 1 + 5 runs、median が primary。SLO なし。

| n_lines | median_s | n_edges | n_index_lookups |
|---|---|---|---|
| 100 | 0.00048 | 1 | 100 |
| 500 | 0.00242 | 1 | 500 |
| 1000 | 0.00576 | 1 | 1000 |
| 5000 | 0.0305 | 1 | 5000 |
| 10000 | 0.0655 | 1 | 10000 |

t5000/t1000 ≈ 5.3（線形 5）。成功条件は速さではなく全行再走査の除去。

---

## やっていないこと

- v0 の置き換え
- RulePolicy 接続
- Phase 2 再採点
- freeze の後付け変更
- CSV / YAML / prose の required 化
- 性能閾値

---

## 成果物

- `src/bite_ingestion/profilers/dependency_dispersion_v1.py`
- `src/bite_eval/phase3e_validate.py`
- `tests/test_phase3e_sensor_v1.py`
- `artifacts/phase3e/sensor-v1-validation.json`
- `artifacts/phase3e/sensor-v1-validation.md`

---

## 次

routing に載せるなら、spent holdout ではなく新しい freeze。この PR ではやらない。
