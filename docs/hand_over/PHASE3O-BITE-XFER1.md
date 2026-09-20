# PHASE3O-BITE-XFER1 引き継ぎ

- 担当: Grok
- 前提: `PHASE3N_CONDITIONAL_ROUTING_HOLDOUT_CONFIRMED`
- ブランチ: `feat/phase3o-bite-xfer1`
- O0 freeze: `76998156d3cbf67fc0a53e151688e46bd3c26dc7`
- 実行日: 2026-09-19
- 有料 API: **未使用**
- p3f evaluation replica 2/3: **未開封**
- RulePolicy / policy / sensor / preflight / operator: **未変更**
- calibration / predicate 再調整: **していない**

---

## 判定

```text
PHASE3O_XFER1_TRANSFER_FAILED
```

104/104 expected routing、104/104 gate、26/26 cross-format sequence identity。ok は 99/104。

failure_class:

- `sensor_operator_mismatch` — high + duplicate の `mixed_order_json` 3 件（c018 / c021 / c022）。`structural_redundancy_v1` は論理 duplicate を見て REDUCE を選ぶが、k/v field order 差で REDUCE は no-op。
- `composition_safety` — high で REDUCE+INTEGRATE の `pretty_json` 2 件（c022 / c024）。whitespace canonicalise が unit id を差し替えたあと、既存 composition_safety が join cluster を original id で照合できない。

この PR では REDUCE / sensor / predicate を直していない。再測定していない。

claim は `independently-authored synthetic cross-corpus / cross-serialization transfer` まで。real-world generalization / BITE superiority ではない。

---

## O0

26 canonical × 4 rendering = 104。scorer annotation に `expected_sequence` は無い。unitizer は source-exact span。policy 実行前に freeze commit。

---

## 成果物

- `corpora/bite-xfer-1/`
- `benchmarks/spec/phase3o-xfer1-freeze.json`
- `artifacts/phase3o/xfer1-transfer.json`
- `artifacts/phase3o/cross-format.json`
- `artifacts/phase3o/actionability.json`
- `artifacts/phase3o/composition-safety.json`
- `artifacts/phase3o/failure-classification.json`

---

## 次

FAILED の修正・再測定は別 PR。p3f evaluation は開けない。main へ merge しない。
