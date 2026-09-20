# PHASE4D-MEASUREMENT-SEMANTICS 引き継ぎ

- 担当: Grok
- 前提: `PHASE4C_REAL_HOLDOUT_MEASURED`
- ブランチ: `feat/phase4d-measurement-semantics-audit`
- D0 protocol freeze: `45748770815016439aeb11d2ac052b3b19946136`
- D0 freeze blob: `5e4c252963b3898ff7665e880a77777f66547320`
- Phase 4C HEAD: `21035872a377e23ad2c5bd01030e312330de005a`
- 実行日: 2026-09-20
- 有料 API: **未使用**
- p3f evaluation replica 2/3: **未開封**
- Phase 4C C0 / C1 / artifacts / verdict: **未変更**
- frozen BITE コンポーネント: **未変更**
- baseline: **未追加**
- XFER-3: **未作成**

---

## 判定

```text
PHASE4D_MEASUREMENT_SEMANTICS_AUDITED
```

retrospective measurement-semantics audit on REALSTRUCT-1。新しい holdout result / generalization / BITE superiority ではない。second holdout / confirmatory ではない。

Phase 4C の safety 表現は **full-source conservation safety 9/9**。`composition_safety_v2 aggregate ok 9/9` とは言わない。

```text
Phase3S remains FAILED
Phase3Q remains FAILED
Phase3T remains VALIDATED
Phase4A remains FROZEN
Phase4C remains MEASURED
```

---

## Track A — atom-aware

- 旧 metric は `line_pair_recall_legacy` として保存。4C `gold_reference_recall` と eval 9 で exact 一致
- gold identity: `(source_line, NAME, dest_line)`
- adjudicated prediction: source value に literal `${atom}` かつ dest key が atom と case-sensitive exact
- ratis: legacy 1.0、atom-aware recall 0.0、precision NA。legacy 1.0 を atom-aware 1.0 と仮定しない
- hadoop も同様に legacy 1.0 / atom-aware 0.0
- koel / laravel / tegra は両者 1.0

---

## Track B — safety

- polybar / gogs: conservation safety は pass。failed check は `reduce_only_logical_duplicates` のみ
- routing 直後の同 check は pass。passthrough が duplicate identity に混入
- 分類: `full_source_merge_interaction`
- operator 自体の semantic failure ではない。推測で REDUCE を直していない

---

## 成果物

- `benchmarks/spec/phase4d-measurement-semantics-freeze.json`
- `artifacts/phase4d/atom-aware-reference.json`
- `artifacts/phase4d/legacy-vs-atom-aware.json`
- `artifacts/phase4d/safety-check-decomposition.json`
- `artifacts/phase4d/routing-vs-full-source-safety.json`
- `artifacts/phase4d/measurement-semantics.json`

---

## 次

holdout を見て sensor / T_high / policy を再調整しない。p3f は開けない。main へ merge しない。XFER-3 は作らない。
