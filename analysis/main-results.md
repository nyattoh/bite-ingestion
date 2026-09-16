# Main results — BITE-15b billed pilot **v2** (Gate C = pivot)

- **Authoritative pilot record**: `artifacts/pilot/bite15b_billed_summary_v2.json` @ [`967ec0b`](https://github.com/nyattoh/bite-ingestion/commit/967ec0b)
- **Recompute**: `analysis/bite15b_pilot_recompute_v2.json`
- **Stance**: Pivot-to-bench. **No Survive. No Go.**

## Decision (v2)

| Field | Value |
| --- | --- |
| decision | **pivot** |
| reason | `c1=False c2=True c3=False` |
| paid_api | true |
| estimate_source | `provider_usage_billed`（384/384） |
| empty answers | **0/384**（minimal smoke も 0/12） |
| sample_meets_n_pilot | true |
| constraints_ok_rate | **0.880208**（338/384） |
| rate_limit / timeout | none |

C2 is a **runner placeholder**（compressed constraints_ok_rate ≥ raw）. It is **not** a true morphology-vs-length-only contrast. Partial confirmatory → **pivot**, not go.

## v1 superseded (not final science)

| | v1 (`e44b5bd`) | v2 (`967ec0b`) |
| --- | --- | --- |
| decision | stop | **pivot** |
| empty answers | 354/384 | **0/384** |
| T_completion | always 64 | min 2 / max 5 / mean ≈ 2.86 |
| confounder | thinking/empty content | mitigated（thinking disabled） |

## Descriptive tallies (v2; no invented CIs)

| Metric | Value |
| --- | --- |
| paired instances | 192 |
| mean / median (T_raw − T_comp) | **-2 / -2** |
| fraction compressed lower T | **0** |
| mean Q raw / compressed | **0.880 / 0.880** |
| failure `Q < Q_baseline − δ` | **46**（ほぼ `dependency_chain`） |

## Family constraints_ok_rate (v2)

| family | rate |
| --- | ---: |
| clean_local | 1.0 |
| repeated_records | 1.0 |
| sparse_anomaly | 1.0 |
| **dependency_chain** | **0.0417** |
| malformed_mixed | 1.0 |
| dense_cross_reference | 1.0 |
| adversarial_omission | 1.0 |
| texture_swap | 1.0 |

## What this is not

- Not Go（C1∧C3 false; C2 placeholder）
- Not full `N_full` matrix / `output/main/aggregates.parquet`
- Not Survive architecture claim

## Next

- Error atlas: concentrate on `dependency_chain` Q failures
- BITE-16 continues under **pivot** standing; do not promote post-hoc subgroups to primary
