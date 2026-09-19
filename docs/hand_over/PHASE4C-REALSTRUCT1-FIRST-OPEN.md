# PHASE4C-REALSTRUCT1-FIRST-OPEN 引き継ぎ

- 担当: Grok
- 前提: `PHASE4B_REAL_ADAPTER_READY`
- ブランチ: `feat/phase4c-realstruct1-first-open`
- C0 protocol freeze: `8ed272fc7cd0487386656f2be7120b554be7921a`
- C0 freeze blob: `8e7dc9196bb5c98e79198263b0d4eeadc6254ff2`
- Phase 4B HEAD: `8dd13d20cc06339ef07811d0d9438f0da8718106`
- 実行日: 2026-09-20
- 有料 API: **未使用**
- p3f evaluation replica 2/3: **未開封**
- Phase 4A raw / SHA256 / split / annotations.json / verdict: **未変更**
- frozen BITE コンポーネント: **未変更**
- T_high_reference: **4**
- XFER-3: **未作成**
- baseline: raw_full / adapter_only のみ。winner score なし

---

## 判定

```text
PHASE4C_REAL_HOLDOUT_MEASURED
```

frozen evaluation 9 文書の first-open 測定。small convenience sample。representative / real-world generalization / downstream answer-quality / BITE superiority ではない。

```text
Phase3S remains FAILED
Phase3Q remains FAILED
Phase3T remains VALIDATED
Phase4A remains FROZEN
```

---

## 何を固定して測ったか

- C0 で eval 9 実行前に harness / overlay / adapter / T_high=4 / baselines 2 件を freeze
- evaluator-local `chain_span_reachable` は frozen `_chain_span` の semantics-preserving computational replacement。sensor ソース変更とは書かない。runtime 完全未変更とも書かない。n<=4 exhaustive で return value exact
- BITE と baseline は同じ raw bytes。raw_full は identity。adapter_only は routing のみで policy/planner/operator なし
- gold recall は overlay v2 の `${NAME}` directed pair。gold=0 は NA
- scoped precision は source value に literal `${NAME}` がある sensor edge だけ。unadjudicated extras は FP ではない
- exact duplicate gold は `(assignment_key, assignment_value)` のみ。polybar 3 / gogs 12 で REDUCE_v2、post-reduce multiplicity 0

---

## 測定メモ（capability。FAILED 条件ではない）

- `${NAME}` recall 1.0: koel, laravel, ratis-log4j, tegra-common
- gold NA: bookstack, kafka-server, tomcat-logging, polybar, gogs
- scoped precision 1.0: koel, laravel。tegra-common は 8/23。ratis は gold recall 1.0 だが `${NAME}` adjudicated 0 のため precision NA
- UNTANGLE: koel。REDUCE_v2: polybar, gogs。laravel ほかは gate true でも sequence `[]`

---

## 成果物

- `benchmarks/spec/phase4c-holdout-first-open-freeze.json`
- `artifacts/phase4c/reachability-equivalence.json`
- `artifacts/phase4c/eval-rows.json`
- `artifacts/phase4c/reference-coverage.json`
- `artifacts/phase4c/exact-duplicate.json`
- `artifacts/phase4c/route-observation.json`
- `artifacts/phase4c/full-source-provenance.json`
- `artifacts/phase4c/baselines.json`
- `artifacts/phase4c/runtime-diagnostic.json`
- `artifacts/phase4c/failure-classification.json`
- `artifacts/phase4c/real-holdout.json`

---

## 次

MEASURED なので holdout を見て sensor / T_high / policy を再調整しない。source 差し替え禁止。p3f は開けない。main へ merge しない。XFER-3 は作らない。
