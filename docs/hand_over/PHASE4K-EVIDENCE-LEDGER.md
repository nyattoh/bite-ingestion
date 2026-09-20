# PHASE4K-EVIDENCE-LEDGER 引き継ぎ

- 担当: Grok
- 前提: `PHASE4J_REFERENCE_SCHEMA_AUDITED`
- ブランチ: `feat/phase4k-evidence-ledger`
- K0 freeze commit: `4b2adc2523f8eec73888cfbec75fbf413fa21631`
- K0 freeze blob: `86e83ff7f43e45721c7a436f1f21865f4342362e`
- Phase 4J HEAD: `7616c89542895a88726762069ef482d897b25335`
- 実行日: 2026-09-21
- 有料 API: **未使用**
- p3f: **未開封**（結果についての記述なし）
- 新規実験 / four arms / tokenizer / sensor replay: **なし**
- BITE / 閾値 / sensor / policy / operator / baseline: **未変更**
- Phase 4A–4J 成果物: **未上書き**
- main merge: **しない**

---

## 判定

```text
PHASE4K_EVIDENCE_LEDGER_FROZEN
```

Phase-4 documentation-only evidence ledger; no new experiment。winner 結論は出していない。

---

## 証拠カテゴリ（混在禁止）

1. mechanism evidence
2. real-corpus safety evidence
3. prospective REALSTRUCT-2 comparison evidence
4. retrospective measurement corrections

---

## Prospective REALSTRUCT-2（Phase4I 原文）

- primary documents = 18
- four arms = 72 rows
- raw reconstruction = 72/72 exact
- BITE safety = 18/18
- planner integrity = 18/18
- BITE model-visible reduction incidence = 1/18（win rate ではない）
- matched-budget unique identity **n=1**（`rs2-ini-genicam-harvesters_gui`）: BITE_v5=1.0, length_pi_v1=0.8461538461538461, delta=0.15384615384615385
- historical reference retention: **n=0 / not_observed**（legacy reader schema incompatibility）。上書きしない。
- route `[]` = 17/18、`REDUCE_v2` = 1/18、gate incidence = 4/18（成功変換 incidence ではない）

---

## Retrospective（Phase4J）

- corrected reference retention **n=1**（`rs2-ini-ahuacate-pve-medialab`）: BITE_v5=1.0, length_pi_v1=1.0, delta=0.0, tie=1。first-open の置き換えではない。
- ahuacate atom-aware: precision=1.0, recall=1.0, unadjudicated=0。gold 1 文書からの一般化はしない。

---

## 歴史的失敗

- `PHASE3Q_XFER2_TRANSFER_FAILED` を残す
- `PHASE3S_REFERENCE_SPECIFICITY_FAILED` を残す
- 後続の v3 / v2 修理は version ラベル付き。失敗判定は消さない

---

## Phase 4 閉包（非評価）

Phase 4 established a reproducible real-structured evaluation path, full-source safety under the frozen protocol, and one prospective four-arm convenience-sample measurement. The sample provided limited opportunity to evaluate BITE transformations because operator activation was sparse.

---

## 成果物

- `benchmarks/spec/phase4k-evidence-ledger-freeze.json`
- `artifacts/phase4k/evidence-ledger.json`
- `artifacts/phase4k/claim-matrix.json`
- `artifacts/phase4k/historical-verdict-timeline.json`
- `artifacts/phase4k/prospective-vs-retrospective.json`
- `artifacts/phase4k/known-limitations.json`
- `artifacts/phase4k/publication-safe-wording.json`
- `artifacts/phase4k/phase4-closure.json`

---

## 次

main へ merge しない。p3f は開けない。実験・再調整をしない。
