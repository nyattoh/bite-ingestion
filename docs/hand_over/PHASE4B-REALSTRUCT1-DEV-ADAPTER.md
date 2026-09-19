# PHASE4B-REALSTRUCT1-DEV-ADAPTER 引き継ぎ

- 担当: Grok
- 前提: `PHASE4A_REAL_CORPUS_FROZEN`
- ブランチ: `feat/phase4b-realstruct1-dev-adapter`
- B0 scorer addendum: `70fa0ce678611db122a74a5fbe730fccf5bf12fb`
- B0 freeze blob: `51af36d70b29ef74c797ed3f547b8f848319184d`
- 実行日: 2026-09-20
- 有料 API: **未使用**
- p3f evaluation replica 2/3: **未開封**
- REALSTRUCT-1 eval 9: **未開封**
- baseline: **未実行**
- XFER-3: **未作成**
- Phase 4A raw / SHA256 / split / annotations.json / verdict: **未変更**
- frozen BITE コンポーネント: **未変更**
- T_high_reference: **4**

---

## 判定

```text
PHASE4B_REAL_ADAPTER_READY
```

development 3 文書だけの adapter 証拠。evaluation 結果ではない。real-world generalization / BITE superiority ではない。

```text
Phase3S remains FAILED
Phase3Q remains FAILED
Phase3T remains VALIDATED
```

---

## 何を固定したか

- B0 で overlay v2 を BITE 実行前に freeze。Phase4A `duplicate_groups` は repeated-key diagnostic。one-pass は前方参照を落とす
- annotations-v2 は two-pass key index。exact duplicate gold は `(assignment_key, assignment_value)` のみ
- `realstruct1_adapter_v1` は dual-plane。source 再連結は raw SHA256 exact。policy には raw document を渡さない
- dev 3 のみ BITE 実行。eval 9 / baseline / p3f は未開封
- gold recall 低下は BLOCKED にしない。hadoop `${NAME}` recall=1.0、bitbake は gap_observed、linkding は not_observed

---

## 成果物

- `benchmarks/spec/phase4b-scorer-addendum-freeze.json`
- `corpora/realstruct-1/annotations-v2.json`
- `artifacts/phase4b/annotation-diff.json`
- `src/bite_ingestion/adapters/realstruct1_adapter_v1.py`
- `artifacts/phase4b/dev-rows.json`
- `artifacts/phase4b/reference-coverage.json`
- `artifacts/phase4b/route-observation.json`
- `artifacts/phase4b/full-source-provenance.json`
- `artifacts/phase4b/evaluation-lock.json`
- `artifacts/phase4b/real-adapter.json`

---

## 次

READY なので次は frozen eval 9 の測定。4B では eval を開けない。source 差し替え禁止。sensor / T_high / policy / operator を 4B 結果で再調整しない。main へ merge しない。XFER-3 は作らない。
