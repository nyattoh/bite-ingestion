# PHASE4G-COMPARISON-ACCOUNTING 引き継ぎ

- 担当: Grok
- 前提: `PHASE4F_COMPARISON_PROTOCOL_READY`
- ブランチ: `feat/phase4g-comparison-accounting-v2`
- G0 protocol freeze: `df096829d7178e6d33094494e93712fde37580b5`
- G0 freeze blob: `b74b591f61a030134fb35272e20f01bceea295bf`
- Phase 4F HEAD: `48eaba1a8f55363da3beccec726460b961199300`
- 実行日: 2026-09-21
- 有料 API: **未使用**
- p3f: **未開封**
- Phase 4F artifacts / F0 / F1: **未変更**
- BITE v5 / length_pi_v1: **未変更**
- REALSTRUCT-2: **未取得**

---

## 判定

```text
PHASE4G_COMPARISON_ACCOUNTING_VALIDATED
```

comparison-measurement amendment before prospective corpus acquisition。新しい BITE / baseline evidence、holdout、confirmatory comparison、generalization、BITE superiority ではない。

---

## Track A

全 arm で `reconstruct(visible, recovery_bundle) == raw bytes`。
`audit_sidecar_*` は `arm_local_sidecar_*_legacy` として残し、arm 間比較に使わない。

---

## Track B

`visible_source_record_ids_v2` は pass-through（unit_id + 完全一致）または INTEGRATE（lineage かつ改行区切りの完全成分）。lineage だけ / 部分文字列 / 対応なしテキストは非可視。

fresh 10 fixtures が primary。REALSTRUCT-1 に INTEGRATE が無くても Track B は消えない。

---

## 次

p3f は開けない。main へ merge しない。REALSTRUCT-2 はまだ取得しない。BITE / length_pi は再調整しない。
