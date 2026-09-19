# PHASE3I-COMPOSITE-PROVENANCE 引き継ぎ

- 担当: Grok
- 前提: Phase 3H `PHASE3H_CONDITIONAL_MAP_REQUIRED`（変更・上書きしない）
- ブランチ: `feat/phase3i-composite-provenance`
- I0 commit: `e6bc818ec37c2b31f33a800b4e724b10acbfb887`
- 実行日: 2026-09-19
- 有料 API: **未使用**
- p3f evaluation replica 2/3: **未開封**
- A / T_low=1 / T_high=4 / v1 / RulePolicy: **未変更・未接続**

Phase 3H unique+INTEGRATE で `provenance_completeness=0.96` になった原因は、joined unit が `joined_from` だけ持ち、packet contract の complete provenance を持たず、先頭 unit の連続 span を流用していたこと。routing とは分けて、multi-source derived unit の contract を直した。

---

## 判定

```text
PHASE3I_COMPOSITE_PROVENANCE_VALIDATED
```

BITE wins / Go ではない。conditional map は RulePolicy に接続していない。

---

## Contract

- `provenance.kind = source | composite`（legacy の kind 省略は source）
- composite は parent ごとに `unit_id` / `source_uri` / `byte_or_token_span` / `renderer_id`
- top-level span は `kind=envelope` かつ `contiguous=false`。source-exact ではない
- mixed URI の join に単一 `source_uri` を付けない
- `joined_from` だけでは complete とみなさない
- malformed は fail closed

---

## 測定（p3i development、p3h 非再利用）

| case | 結果 |
|---|---|
| same-uri non-contiguous 2-way | completeness 1.0 / lineage 1.0 |
| 3-way | 同上 |
| mixed URI | 同上。top-level source_uri なし |
| pass-through | join なし。completeness 1.0 |
| dependency-edge | join あり |
| explicit key= | join あり |
| joined_from only | fail closed |
| composite + source-exact span | fail closed |

CUT / UNTANGLE / REDUCE の provenance 意味は変えていない。

---

## 成果物

- `benchmarks/spec/phase3i-composite-provenance-freeze.json`
- `artifacts/phase3i/composite-provenance.json`
- `src/bite_bench/phase3i.py`
- `src/bite_eval/phase3i_validate.py`
- `src/bite_ingestion/packet_contract.py`
- `src/bite_ingestion/operators/integrate.py`

---

## 次

VALIDATED なので composite provenance は使える。それでも conditional routing を RulePolicy へ接続する作業はこの PR には含めない。p3f evaluation は開けない。
