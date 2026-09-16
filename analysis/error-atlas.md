# Error atlas — BITE-15b billed pilot (stop)

Source: `artifacts/pilot/bite15b_billed_summary.json` @ `e44b5bd`. Offline recount only.

## Failure inventory

| Failure string | Count (of 384 rows) |
| --- | ---: |
| `Q < Q_baseline - delta` | 354 |
| (no failure / constraints_ok) | 30 |

Provider / transport:

| Class | Count |
| --- | ---: |
| row `error` non-null | 0 |
| rate_limit stop | 0 |

## Pattern notes (descriptive)

1. **Quality collapse vs baseline**: Q_baseline ≈ 1.0 while observed Q is near 0 on most families. This dominates constraint failures and drives stop (C1–C3 false).
2. **Compression does not buy T**: paired mean `(T_raw − T_comp) < 0` → compressed path is slightly costlier on average; C1-style T improvement is not supported.
3. **Family exception**: `texture_swap` has constraints_ok_rate 0.5625 and higher mean Q (~0.54–0.58). Treat as exploratory texture signal only — **not** promoted to primary claim.
4. **Empty / weak answers**: many rows store empty `answer_text` in artifacts; atlas does not invent content. Investigate whether scoring treats empty replies as Q=0 systematically（harness vs model）.

## Example slots (ids only; no prompt dump)

Use summary `results[]` filtered by `constraints_ok==false` and family:

- Systematic: `clean_local-*` / `raw_full` and `compressed_passthrough`（ok_rate 0）
- Partial: `sparse_anomaly-*`（3/48 ok）
- Relative better: `texture_swap-*`（27/48 ok）

## Missing data

- Checkpoint JSONL not in git（intentional）. Resume tallies in summary: `calls_skipped_ok=384`.
- No `output/main/failures.jsonl` yet — this atlas is **pilot-scoped** substitute for BITE-16 bootstrap.

## Do not

- Hide the 354 Q failures behind mean token stats
- Elevate `texture_swap` to primary hypothesis post-hoc
- Claim Go / Survive
