# PHASE3C-SENSOR-GENERALIZATION 引き継ぎ

- 担当: Grok
- 前提: Phase 3B `PHASE3B_SENSOR_READY`（PR #25）。固定 development fixture 上で dependency dispersion を観測できたことだけを意味する。
- ブランチ: `feat/phase3c-sensor-generalization`
- 実行日: 2026-09-19
- 有料 API: **未使用**
- Phase 2 evaluation: **未使用**（spent holdout。入力にも再採点にも使っていない）
- deterministic_v0 / HIGH / LOW / RulePolicy: **未接続・未変更**
- `dependency_dispersion_v0`: **未変更**（新 revision なし）

これは routing 接続作業ではない。主量 `mean_edge_distance` が文書長・行分割・無関係 identifier・表現形式にどの程度動くかの development audit。

---

## 判定

```text
PHASE3C_SENSOR_SCOPED
```

key=value と 1行 JSON では、raw が絶対行間距離、norm が相対行間距離として契約どおり動く。pretty JSON / CSV / YAML / prose は未対応。空行・折り返しは line-index を歪める。環境名・サービス名などの再出現は依存でなくても edge になる。reference と mere co-occurrence は現方式では区別できない。制限付き sensor として記録する。BITE wins / Go ではない。

---

## A. Scale

測定前の期待（sensor 契約から）:

- 同じ edge の絶対距離 4、無関係 noise だけ増やす → raw は等しく、norm は文書が長いほど下がる
- 両端に置く（相対位置固定）→ raw は行数とともに増え、norm は 1.0

| 条件 | n_lines | mean_edge_distance | mean_edge_distance_norm |
|---|---|---|---|
| abs short | 9 | 4.0 | 0.5 |
| abs medium | 25 | 4.0 | 0.1667 |
| abs long | 85 | 4.0 | 0.0476 |
| rel 12 | 12 | 11.0 | 1.0 |
| rel 24 | 24 | 23.0 | 1.0 |
| rel 48 | 48 | 47.0 | 1.0 |

意味（routing 用途の選択はしない）:

- `mean_edge_distance` = **absolute** dependency separation（行インデックス差）
- `mean_edge_distance_norm` = **relative** dependency separation（差 / (n_lines-1)）

median / component_span / chain_span は 1-edge のこの fixture では raw と同じ値になる。並べたが、routing feature は決めていない。

---

## B. Line granularity

同じ参照（`id_alpha_77` → `id_result_99`）:

| 表現 | n_edges | raw |
|---|---|---|
| 1 record = 1 kv line | 1 | 1.0 |
| 1 record = 1 JSON line | 1 | 1.0 |
| pretty JSON | 0 | 0 |
| compact JSON 1行 | 0 | 0 |
| 空行あり | 1 | 2.0 |
| レコード間 wrap | 1 | 2.0 |
| identifier 途中 wrap | 0 | 0 |

semantic graph が同じでも、pretty / 空行 / wrap で sensor 値は変わるか消える。Phase 3B の nested JSON 1行だけでは形式 robust とは言えない。

---

## C. False-positive

gold なし。stopword は fixture を見て追加していない。

env / service / owner / category / 無関係 record の同一 identifier は、すべて n_edges=1。真の1-hop（距離1）に遠い共有ラベルを足すと n_edges=2、mean=3.5 に引き上げられる。

**限界:** 現 edge 規則は「value 側 identifier が別行に再出現」だけなので、reference と mere co-occurrence を区別できない。

---

## D. Format coverage

| 形式 | 判定 |
|---|---|
| key=value | supported |
| one-line JSON | supported |
| pretty JSON | unsupported |
| CSV 風 | unsupported |
| YAML 風 | unsupported |
| prose 中の identifier | unsupported |

extractor は行が `{`/`[` で始まる完結 JSON、または `=` の右側だけを value と見る。未対応形式を無理に読ませていない。目的は万能化ではなく適用範囲の確定。

---

## E. Cost

v0 は value atom ごとに他行を走査する。synthetic、1 edge + 一意 noise。有料 model なし。性能 SLO は作らない。

| n_lines | wall_time_s | n_edges |
|---|---|---|
| 100 | 0.011 | 1 |
| 500 | 0.243 | 1 |
| 1000 | 0.918 | 1 |
| 5000 | 41.5 | 1 |

t5000/t1000 ≈ 45（線形なら 5、二乗なら 25）。**superlinear**。閾値にはしない。

---

## やっていないこと

- `dependency_dispersion_v0` の黙った改変
- RulePolicy / HIGH / LOW への接続
- routing feature の一本化
- Phase 2 holdout の再採点
- stopword 追加による偽陽性の救済
- 性能閾値の後付け

---

## 成果物

- `src/bite_eval/phase3c_fixtures.py`
- `src/bite_eval/phase3c_audit.py`
- `scripts/run_phase3c_audit.py`
- `tests/test_phase3c_sensor_generalization.py`
- `artifacts/phase3c/sensor-generalization.json`
- `artifacts/phase3c/sensor-generalization.md`

---

## 次

routing に載せるなら、spent holdout ではなく、この適用範囲（kv / 1行 JSON、co-occurrence 限界）を前提にした新しい設計と freeze が先。この PR ではやらない。
