# PHASE4F-PROSPECTIVE-COMPARISON 引き継ぎ

- 担当: Grok
- 前提: `PHASE4E_FULL_KEY_REFERENCE_VALIDATED`
- ブランチ: `feat/phase4f-prospective-comparison-protocol`
- F0 protocol freeze: `ee8d190567e0ce055d7ffa2b7163cffa8d94912a`
- F0 freeze blob: `9f4e957af859432036e9d150c85b5066892dad8f`
- Phase 4E HEAD: `03bc883b1e3ef0d1ab0c0332f544ce8c82613bfd`
- 実行日: 2026-09-20
- 有料 API: **未使用**
- p3f: **未開封**
- Phase 4C: **PHASE4C_REAL_HOLDOUT_MEASURED** のまま
- Phase 4D: **PHASE4D_MEASUREMENT_SEMANTICS_AUDITED** のまま
- Phase 4E: **PHASE4E_FULL_KEY_REFERENCE_VALIDATED** のまま
- BITE v2/v4/v5 / planner / operators: **未変更**
- REALSTRUCT-2: **未取得**

---

## 判定

```text
PHASE4F_COMPARISON_PROTOCOL_READY
```

prospective comparison protocol development only。REALSTRUCT-2 evidence / confirmatory comparison / real-world generalization / BITE superiority ではない。

```text
Phase3S remains FAILED
Phase3Q remains FAILED
Phase4C remains MEASURED
Phase4D remains AUDITED
Phase4E remains VALIDATED
```

---

## F0

比較 baseline 実装・実行の前に契約を凍結。tokenizer.json SHA256 は Phase1C と同一。主コスト単位は reference-tokenizer payload tokens。`local_char4_proxy` は使わない。model-visible と audit/recovery は分離。winner score なし。F0 後の BITE 再調整なし。

---

## Arms

- `raw_full`: 元文書そのまま。参照のみ。勝者ではない。
- `adapter_only`: 凍結 adapter の routing 単位のみ。policy / planner / operator なし。
- `length_pi_v1`: adapter_only 直列化の最長 source-exact prefix。長さと位置だけ。budget は同じ文書の BITE_v5 visible token 数。sidecar は省略 suffix（model-visible ではない）。
- `BITE_v5`: 凍結 policy v5 の post-policy routing visible のみ。R / source は audit。

---

## REALSTRUCT-1 development

12 文書は post-open 実装確認のみ。holdout / confirmatory / generalization ではない。結果で baseline も BITE も再調整していない。

---

## 成果物

- `benchmarks/spec/phase4f-prospective-comparison-freeze.json`
- `src/bite_eval/reference_tokenizer.py`
- `src/bite_eval/length_pi_v1.py`
- `src/bite_eval/phase4f_metrics.py`
- `artifacts/phase4f/prospective-comparison.json`
- `artifacts/phase4f/token-accounting.json`
- `artifacts/phase4f/length-pi-sidecar.json`
- `artifacts/phase4f/realstruct1-development.json`

---

## 次

p3f は開けない。main へ merge しない。REALSTRUCT-2 はまだ取得しない。BITE は再調整しない。
