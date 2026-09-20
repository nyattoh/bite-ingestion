# PHASE4I-REALSTRUCT2-FIRST-OPEN 引き継ぎ

- 担当: Grok
- 前提: `PHASE4H2_REALSTRUCT2_AUGMENTED_FROZEN`
- ブランチ: `feat/phase4i-realstruct2-first-open-comparison`
- I0 execution freeze: `435be913dab61e29077d49009602ef5e457ee621`
- I0 freeze blob: `260c5ae4847776c33d27ea6718466d1dd814abdf`
- Phase 4H2 HEAD: `461ae71e646728018890e87e5d0cada5af25906e`
- 実行日: 2026-09-21
- 有料 API: **未使用**
- p3f: **未開封**
- 追加取得 / license 変更 / source 置換: **なし**
- BITE / length_pi / tokenizer: **未再調整**
- 結果を見たあとの arm / policy / metric 修理: **なし**

---

## 判定

```text
PHASE4I_PROSPECTIVE_COMPARISON_MEASURED
```

prospective four-arm measurement on the frozen two-wave REALSTRUCT-2 convenience sample。representative real-world sample / population generalization / downstream answer-quality / BITE superiority ではない。

Performance は判定に使っていない。18/18・4 arms・tokenizer lock・raw reconstruction・BITE safety・planner integrity が通った。

---

## 実行順

1. I0 でハーネスと corpus / tokenizer / 分析契約を凍結（REALSTRUCT-2 tokenizer/arms は未実行）
2. 合成 fixture 5 + REALSTRUCT-1 12 で preflight（I0 確定前）
3. I0 commit のあと、augmented-manifest の primary 18 を一度だけ first-open

historical Phase4H 10-document manifest にはフォールバックしていない。

---

## 凍結分析（Phase4H H0 契約のまま）

- A `visible_reference_retention_v2`: **n=0 / not_observed**。凍結 `gold_triples()` は RS1 overlay の `dest_lines` を読む。REALSTRUCT-2 注釈は `dest_line` 単数なので、凍結 reader では gold が 0 件になる。文書を足していない。この PR では reader を直していない。
- B `unique_assignment_identity_retention_v2` on matched_budget_subset: **n=1**（`rs2-ini-genicam-harvesters_gui`）。delta = 0.15384615384615385（positive 1）
- C recovery_bundle_bytes / tokens は arm 別に記録。visible cost と合算していない
- D model-visible tokens: BITE reduction incidence = **1/18**。win rate ではない
- E safety: reconstruction 72/72 exact。BITE invariants 18/18。planner integrity 18/18。加重スコア化していない
- F mechanism: route `[]` が 17、`REDUCE_v2` が 1。gate incidence 4。atom-aware / unadjudicated は比較結果ではない

wave は provenance のみ。wave1 vs wave2 の outcome 比較はしていない。secondary=0 のまま。secondary 分析は作っていない。

---

## 事実として言えること（凍結データが支える範囲）

- BITE used fewer model-visible tokens on 1/18 documents.
- On the n eligible reference-gold documents, the observed retention delta was not_observed.
- At matched budget, unique identity retention differed by n=1 mean=0.15384615384615385 median=0.15384615384615385 positive=1 tie=0 negative=0.

overall winner / ranking / BITE superiority は出していない。

---

## 成果物

- `benchmarks/spec/phase4i-first-open-freeze.json`
- `artifacts/phase4i/arm-rows.json`
- `artifacts/phase4i/paired-reference-retention.json`
- `artifacts/phase4i/paired-unique-identity.json`
- `artifacts/phase4i/model-visible-cost.json`
- `artifacts/phase4i/recovery-accounting.json`
- `artifacts/phase4i/safety.json`
- `artifacts/phase4i/mechanism-diagnostic.json`
- `artifacts/phase4i/first-open.json`
- `artifacts/phase4i/failure-classification.json`

---

## 次

結果を見て再調整しない。p3f は開けない。main へ merge しない。license 政策の見直しは別 phase。A の `dest_line` reader も、やるなら別の明示 phase。
