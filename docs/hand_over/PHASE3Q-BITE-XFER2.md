# PHASE3Q-BITE-XFER2 引き継ぎ

- 担当: Grok
- 前提: `PHASE3P_RECORD_ALIGNMENT_VALIDATED`
- ブランチ: `feat/phase3q-bite-xfer2`
- Q0 freeze: `67bfd22f782c6663de6e977848a5a381cd62ae51`
- 実行日: 2026-09-19
- 有料 API: **未使用**
- p3f evaluation replica 2/3: **未開封**
- Phase 3O artifact / verdict: **未変更** (`PHASE3O_XFER1_TRANSFER_FAILED`)
- Phase 3P: development repair evidence。confirmatory ではない
- v2 policy / sensor / operator / safety evaluator: **Q0 以降未変更**
- calibration / predicate 再調整: **していない**

---

## 判定

```text
PHASE3Q_XFER2_TRANSFER_FAILED
```

112 surfaces。ok は 100/112。cross-format gate/predicate/sequence identity は 28/28。

failure_class:

- `operator_interference` — high adversarial `xfer2-q027`（duplicate が explicit join cluster と重なり、REDUCE_v2 のあと INTEGRATE が no-op）と `xfer2-q028`（anomaly が join member で、UNTANGLE のあと INTEGRATE が no-op）。4 rendering ずつ。
- `composition_safety` — `xfer2-q027` のみ（干渉後の join が composite にならない）。
- `other` — mid `xfer2-q014`（duplicate+join）。intended は ungated だが mean_edge_distance>=4 で gate が開き、sequence が `REDUCE_v2 → INTEGRATE` になった。

この PR では fixture / threshold / predicate / operator を直していない。再測定していない。

claim は `fresh independently-authored synthetic cross-corpus / cross-serialization transfer for v2` まで。real-world generalization / BITE superiority ではない。

Phase3O remains FAILED; known failures are repaired in development.

---

## Q0

28 canonical × 4 rendering = 112。scorer annotation に `expected_sequence` は無い。unitizer は source-exact span。policy 実行前に freeze commit。

---

## 成果物

- `corpora/bite-xfer-2/`
- `benchmarks/spec/phase3q-xfer2-freeze.json`
- `benchmarks/spec/phase3q-locked-blobs.json`
- `artifacts/phase3q/xfer2-transfer.json`
- `artifacts/phase3q/cross-format.json`
- `artifacts/phase3q/actionability.json`
- `artifacts/phase3q/composition-safety.json`
- `artifacts/phase3q/operator-interference.json`
- `artifacts/phase3q/failure-classification.json`

---

## 次

FAILED の修正・再測定は別 PR。p3f evaluation は開けない。main へ merge しない。
