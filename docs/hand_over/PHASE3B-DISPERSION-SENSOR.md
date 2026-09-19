# PHASE3B-DISPERSION-SENSOR 引き継ぎ

- 担当: Grok
- 前提: Phase 3A `PHASE3A_DISPERSION_UNOBSERVABLE`（PR #24）
- ブランチ: `feat/phase3b-dispersion-sensor`
- 実行日: 2026-09-19
- 有料 API: **未使用**
- Phase 2 evaluation: **未使用**（spent holdout。再採点していない）
- deterministic_v0 / HIGH / LOW / RulePolicy: **未接続・未変更**

これは Phase 2D の 0/48 を改善する作業ではない。温度計が温度を測れるかの development 確認。

---

## 判定

```text
PHASE3B_SENSOR_READY
```

gold なしで dependency dispersion を、固定した development fixture 上で安定して観測できた。routing にはまだ接続していない。BITE wins / Go ではない。

---

## 何を測るか（v0 とは別 contract）

新 sensor: `dependency_dispersion_v0`（`DependencyDispersionSensor`）

deterministic_v0 の `b,r,s,k,a,l,p,u` は変更していない。過去 artifact を新定義で読み替えない。

入力は `payload` / `text` のみ。`required_evidence_ids` / `gold_answer` / `gold_route` / `is_required_evidence` / 正解位置は使わない。Phase 2 の `lookup_for_` / `next_for_` / `value_for_` も oracle として hard-code していない。

手続き:

1. 行の value 側から identifier atom を取る（`key=value` または JSON の string value）
2. 短く generic な exact token は捨てる（closed stopword。Phase 2 evaluation で最適化していない）
3. その atom が **別の、本文が同一でない行** に境界付きで再登場したら reference edge
4. 主量は `mean_edge_distance`（行インデックス差の平均）

検討した量のうち、routing に足す候補は今はこれ一つ。他は診断:

- n_edges / median / max / document 長正規化 / component span / multi-hop chain span

正規化距離は行数が変わると動くので、同じ multiset の順序対比では raw mean を主量にした。

---

## Query 側の別候補

`query_identifier_span_v0` は v0 の `l` を書き換えない。generic な疑問文では idle。query が rare identifier を含むときだけ span が動く。reference-graph の代用にはしない（質問文依存）。

---

## Development fixture（測定前に固定）

同じ行 multiset を、参照でつながった行が near / medium / far になるよう並べ替えた。期待は実行前から:

```text
near < medium < far
```

Phase 2 evaluation case は使っていない。

| 確認 | 結果 |
|---|---|
| one-hop mean_edge_distance | 1 < 4 < 9 |
| 同じ 3 配置で n_edges | すべて 1 |
| nested JSON でも順序 | 1 < 4 < 9 |
| two-hop chain_span | 2 < 6 < 10 |
| unrelated noise の並べ替え | near と同じ 1 |
| duplicate noise | raw distance も n_edges も不変 |
| no-reference | 0 |
| generic token の false positive | 0 |
| nul | fail-closed |
| v0 ベクトル | 3 配置で同一（permutation invariant） |

---

## やっていないこと

- Phase 2D の再採点
- threshold を動かして 0/48 を SIGNAL にすること
- RulePolicy への接続
- 「何度なら INTEGRATE」の後付け

---

## 成果物

- `src/bite_ingestion/profilers/dependency_dispersion.py`
- `benchmarks/spec/phase3b-dispersion-sensor.json`
- `src/bite_eval/phase3b_fixtures.py`
- `tests/test_phase3b_dispersion_sensor.py`
- `artifacts/phase3b/sensor-evaluation.json`
- `artifacts/phase3b/sensor-evaluation.md`

---

## 次

routing に載せるなら、spent holdout ではなく新しい設計と freeze が先。この PR ではやらない。
