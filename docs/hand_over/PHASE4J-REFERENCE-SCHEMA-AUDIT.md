# PHASE4J-REFERENCE-SCHEMA-AUDIT 引き継ぎ

- 担当: Grok
- 前提: `PHASE4I_PROSPECTIVE_COMPARISON_MEASURED`
- ブランチ: `feat/phase4j-reference-schema-audit`
- J0 freeze commit: `8e0ed24213238ae089fdba937b56082c02ad72be`
- J0 freeze blob: `731ffbc7db9652ad03928c3defdb775ca0b83c8e`
- Phase 4I HEAD: `88f3b26d32c96e17cbb001179953a7ad0c235068`
- 実行日: 2026-09-21
- 有料 API: **未使用**
- p3f: **未開封**
- four arms / tokenizer: **再実行なし**
- BITE / length_pi / corpus: **未再調整・未変更**
- Phase 4I 成果物: **未上書き**

---

## 判定

```text
PHASE4J_REFERENCE_SCHEMA_AUDITED
```

retrospective correction of annotation-schema compatibility for Phase4I reference metrics。new holdout / confirmatory comparison / generalization / BITE superiority ではない。

---

## 実行順

1. J0 で監査契約を凍結（`gold_triples_v2` 導入前）
2. 合成 fixture だけで reader の fail-closed 規則を試験
3. 凍結 Phase4I `arm-rows.json` と REALSTRUCT-2 注釈だけで Track A を再スコア
4. 凍結 raw に対して `dependency_dispersion_v4` だけを replay し、18/18 exact のあと atom-aware を再スコア

historical `gold_triples()`（`dest_lines` のみ）は変更していない。

---

## Track A（paired reference）

Phase4I の `n=0 / not_observed` は `phase4i_legacy_schema_reader_result` として原文のまま残している。

理由: Phase4D reader expected dest_lines; REALSTRUCT-2 annotation uses dest_line.

補正後 `visible_reference_retention_v2`（BITE_v5 − length_pi_v1）:

- n=1（`rs2-ini-ahuacate-pve-medialab`、gold 25 triples）
- mean=0.0
- median=0.0
- positive=0
- tie=1
- negative=0

四 arm とも retention=1.0。first-open の置き換えではない。

---

## Track F（atom-aware）

sensor replay は 18/18 exact（`n_reference_edges` / `mean_reference_edge_distance` / `gate_result`）。

補正後（ahuacate）:

- atom_aware_precision=1.0
- atom_aware_recall=1.0
- unadjudicated_extra_edges=0

Phase4I 記録値（precision 0.0 / recall NA）は legacy として併記し、上書きしていない。

---

## 成果物

- `benchmarks/spec/phase4j-reference-schema-freeze.json`
- `src/bite_eval/gold_triples_v2.py`
- `tests/fixtures/phase4j/`
- `artifacts/phase4j/annotation-compatibility.json`
- `artifacts/phase4j/legacy-vs-corrected-paired-reference.json`
- `artifacts/phase4j/sensor-replay.json`
- `artifacts/phase4j/corrected-atom-aware.json`
- `artifacts/phase4j/reference-schema-audit.json`

---

## 次

main へ merge しない。p3f は開けない。four arms を再実行しない。BITE / length_pi を再調整しない。
