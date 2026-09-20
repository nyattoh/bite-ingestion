# PHASE3L portability addendum

metadata only。Phase 3L の artifact / verdict は書き換えていない。evaluation の再実行・再選択はしていない。

## Commits

| 役割 | SHA |
|---|---|
| original L0 | `d365d0b1bd4cb3dcdad617ed4e78df19fdf23ce6` |
| first-open result | `fcc3fb0b202410702d0d74aef8899a076f60b3bd` |
| CRLF portability amendment | `21dd64d29c15ae055f77d9bbf2b874e607156111` |

amendment は first-open **後**。変更は checkout newline に依存しない locked-blob hash 計算のみ。

未変更: `structural_redundancy_v1` / p3k split / FAMILY_EXPECT / evaluation rows / verdict rule。

## Immutable git blob SHA

| path | blob |
|---|---|
| `src/bite_ingestion/profilers/structural_redundancy_v1.py` | `aca6fcd6664f9942b9f72a0d2fd171bfbfe41a35` |
| `benchmarks/spec/phase3k-split-manifest.json` | `ddfde740ef4c06a688e2a76830fda0ad024bcde2` |
| `artifacts/phase3k/structural-redundancy.json` | `d1f3438190f25c0c2b0f0e7451351d5f8a3b81ea` |

判定はいまも `PHASE3L_REDUNDANCY_HOLDOUT_CONFIRMED`。
