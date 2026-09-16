# Main results (BITE-15b pilot scope) — billed N_pilot stop

- **Scope**: Gate C **pilot** only (`N_pilot=24` / family). Not full `N_full=100` matrix.
- **Source**: `artifacts/pilot/bite15b_billed_summary.json` @ `e44b5bd`
- **Recompute**: `analysis/bite15b_pilot_recompute.json`（summary からの再集計のみ）
- **Stance**: Pivot-to-bench. **No Survive. No Go.**

## Decision

| Field | Value |
| --- | --- |
| decision | **stop** |
| reason | `c1=False c2=False c3=False` |
| paid_api | true |
| estimate_source | `provider_usage_billed`（384/384） |
| sample_meets_n_pilot | true |
| constraints_ok_rate | 0.078125（30/384） |

Confirmatory C1–C3 are all false under billed usage at pilot scale → **stop** per `decide_gate_c`. This is a **negative result**, reported at the same granularity as a positive would be.

## Descriptive tallies (no invented CIs)

| Metric | Value |
| --- | --- |
| rows | 384 |
| paired instances (raw vs compressed) | 192 |
| T_total sum / min / max | 62489 / 106 / 240 |
| mean (T_raw − T_comp) | ≈ −2.19 |
| median (T_raw − T_comp) | −2.0 |
| fraction compressed lower T | ≈ 1.6% |
| mean Q raw / compressed | ≈ 0.089 / 0.068 |
| mean Q_baseline | ≈ 1.0 |

Primary failure mode: **`Q < Q_baseline − δ`** (354 rows). Token “savings” from `compressed_passthrough` are **not** observed on average; quality collapses relative to baseline.

## Domain / family

See `per_family` in summary and recompute JSON. Only `texture_swap` has non-trivial constraint pass rate (0.5625); most families are 0.

## What this is not

- Not matched-quality Pareto on full experiment matrix（`output/main/aggregates.parquet` 未存在）
- Not formal Holm-adjusted confirmatory tests beyond the pilot decision label
- Not a claim that morphology-aware ingestion fails in general — only that **this billed pilot arm** did not support C1–C3

## Next artifacts

- `analysis/error-atlas.md`
- `analysis/pareto-data.csv`（pilot paired descriptive only）
- `docs/hand_over/BITE-16.md`
