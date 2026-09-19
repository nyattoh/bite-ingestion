# PHASE3F-ROUTING-CALIBRATION-FREEZE 引き継ぎ

- 担当: Grok
- 前提: Phase 3E `PHASE3E_V1_VALIDATED`（PR #28）
- ブランチ: `feat/phase3f-routing-calibration-freeze`
- 実行日: 2026-09-19
- 有料 API: **未使用**
- Phase 2 evaluation: **未使用**
- v1 / v0 / RulePolicy / HIGH / LOW: **未変更・未接続**
- calibration 測定: **未実施**
- evaluation の routing/profiler 値: **未開封**
- threshold 値: **未決定**

データを見る前に、v1 を routing に使う場合の選び方だけを固定する。

---

## 現在の freeze

```text
phase3f-routing-calibration-freeze-v0.3
PHASE3F_ROUTING_CALIBRATION_PROTOCOL_FROZEN
```

v0.1 / v0.2 は削除していない。上書きしていない。v0.3 が v0.2 を supersede する。

- 残置: `benchmarks/spec/phase3f-routing-calibration-freeze.json`（v0.1）
- 残置: `benchmarks/spec/phase3f-routing-calibration-freeze-v0.2.json`
- 現行: `benchmarks/spec/phase3f-routing-calibration-freeze-v0.3.json`
- split: `benchmarks/spec/phase3f-split-manifest.json`（v0.1 のまま）

v0.3 で変えたのは Candidate C の threshold 前 metric 定義と、M1/M2 の採用タイミングだけ。generation / split / surfaces / adversarial / A・B・C / grids / threshold objective は v0.2 のまま。

BITE wins / Go ではない。

---

## v0.3 で直した曖昧さ

### Candidate の continuous ordering

- A: `continuous_score = mean_edge_distance`。cell ごとに `raw(near) < raw(medium) < raw(far)` なら pass。その割合が coverage。
- B: `continuous_score = mean_edge_distance_norm`。`norm(near) < norm(medium) < norm(far)`。
- C: 単一 scalar は作らない。raw と norm の双方が成立した cell だけ pass。重み付き加算はしない。

### scale_stability

replica ごとに判定し、その pass 率が `scale_stability`。tolerance は結果を見て足さない。exact comparison。

- A: one-hop medium の `mean_edge_distance` が small/medium/large で同一
- B: one-hop far の `mean_edge_distance_norm` が small/medium/large で同一
- C: A 条件 AND B 条件

### M1 / M2

Phase 3G では選ばない。sensor score / threshold bin / 3G calibration metric を変えないので、現行 priority list ではデータで識別できない。候補定義は残す。adoption は `phase3h_routing_semantics_freeze`。

3G で選ぶのは feature candidate A/B/C と threshold 値だけ。RulePolicy にはまだ接続しない。

---

## v0.2 で直した曖昧さ

v0.1 は `adversarial_false_positive_rate` と `dispersion_ordering_coverage` を grid objective に入れていた。どちらも threshold 値に依存しない。このままだと grid search が tie-break だけで T を選ぶ。

役割を次に分ける。calibration の数値はまだ見ない。

### sensor-level diagnostic

`edge_false_positive_rate` は v1 sensor 自体の診断。`intended_edges` と比較する。gold は scorer だけが使い、sensor 入力には渡さない。

A/B/C の threshold 選択にも candidate 選択にも使わない。この Phase で sensor は変えない。

`true_dep_plus_misleading_suffix` は intended edge を持つので negative rate に入れない。edge precision / extra-edge count を diagnostic として別保存する。

### candidate-level（threshold 適用前）

連続スコアについて:

- `continuous_dispersion_ordering_coverage`（near < medium < far）
- `scale_stability`

は A/B/C の性質として測る。grid point の比較には使わない。

### threshold-dependent

grid には、T で実際に変わる指標だけを使う。

- `bin_ordering_coverage`: calibration primary cell で `bin(near) <= bin(medium) <= bin(far)` かつ `bin(near) < bin(far)` の割合
- `negative_adversarial_elevated_bin_rate`: `intended_edges=[]` の adversarial surface が low 以外（mid/high）に入った割合
- `format_consistency`: kv/json が同じ bin になる割合
- `non_collapse`: どの 1 bin も calibration primary surfaces の 95% 以上を占めてはいけない

---

## Threshold grid の選び方（値はまだ決めない）

各 candidate 内で、事前固定 grid について:

1. `non_collapse` を満たすものだけ eligible
2. `negative_adversarial_elevated_bin_rate` 最小
3. `bin_ordering_coverage` 最大
4. `format_consistency` 最大
5. 完全 tie なら smallest T_high, then smallest T_low（C は T_raw_high → T_norm_high → T_raw_low → T_norm_low）

calibration を見て grid を追加・拡張しない。evaluation を見て T を変えない。

---

## Candidate 選択

各 candidate の best grid point を 1 つ決めたあと、A/B/C を比較する。

1. continuous dispersion ordering coverage（高い）
2. scale stability（高い）
3. threshold 後の format consistency（高い）
4. non-collapse を満たすものだけ eligible
5. 完全 tie なら A → B → C

sensor edge FP は全候補共通 diagnostic。n_signal / INTEGRATE rate を目的にしない。

---

## 新規 generation `p3f`（v0.1 から不変）

Phase 2 とは別。required format は key=value と JSON のみ。

near / medium / far は同一 logical unit の並べ替え。padding なし。

- scale: small 8 / medium 24 / large 48 distractors
- shape: one-hop / two-hop / branch
- replica: 0,1 calibration / 2,3 evaluation

---

## Operator 対応

high dispersion から単独で INTEGRATE を発火させない。M1 / M2 候補定義は残す。採用は Phase 3H。Phase 3G では選ばない。RulePolicy は変更しない。

---

## 成果物

- `src/bite_bench/phase3f.py`
- `benchmarks/spec/phase3f-routing-calibration-freeze.json`（v0.1 残置）
- `benchmarks/spec/phase3f-routing-calibration-freeze-v0.2.json`（残置）
- `benchmarks/spec/phase3f-routing-calibration-freeze-v0.3.json`
- `benchmarks/spec/phase3f-split-manifest.json`（未変更）
- `spec/phase3f-routing-calibration-freeze-v0.3.schema.json`
- `tests/test_phase3f_routing_calibration_freeze.py`

---

## 次

Phase 3G で calibration split だけを測り、この v0.3 規則で A/B/C と threshold をロックする。M1/M2 は選ばない。evaluation はまだ開けない。
