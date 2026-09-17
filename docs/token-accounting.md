# Token accounting contract (BITE-13)

Pivot-to-bench / name plan B. Synthetic & offline scaffold. **Numeric thresholds TBD (D-2).**  
No confirmatory Go / Pivot / Stop judgments in this document.

## Two names, two meanings — never interchangeable

| Name | Meaning | Where |
| --- | --- | --- |
| `T_target_call` | Provider usage for **one** target call (prompt+completion) | `BilledInstanceResult.T_target_call` |
| `T_total` | **Full cost** — the ledger bucket sum below | `TokenLedger.totals()["T_total"]` |

`T_total` is never an alias for the target call. Pre-2026-09-17 billed
checkpoints stored the target call under the name `T_total`; the loader maps
those rows to `T_target_call` so a resumed run cannot reinterpret them.

## Formula

\[
T_{total}
  = T_{profiler}
  + T_{router}
  + T_{operator}
  + T^{\mathrm{in}}_{target}
  + T^{\mathrm{out}}_{target}
  + T_{rebite}
  + T_{baseline}
  + T_{calls\_other}
\]

Implementation buckets (manifest `token_buckets` / `token_totals`):

| Field | Role |
| --- | --- |
| `T_profiler` | Profiler LLM (or 0 if deterministic; DC-2) |
| `T_router` | Router / policy LLM (or 0 if deterministic) |
| `T_operator` | Operator / compressor calls (or 0 if deterministic) |
| `T_target_in` / `T_target_out` | Target model calls |
| `T_rebite` | Recover / re-bite calls (DC-6) |
| `T_baseline` | Baseline router/compressor accounting (DC-5) |
| `T_calls_other` | INTEGRATE and other counted calls |
| `sum_calls_in_out` | Sum of non-profiler/router call tokens |
| `T_total` | Full cost — **never** target-input-only |

### Re-bite must be billed

`RecoverEngine._finish` writes the recovery cost to
`packet["accounting"]["rebite_tokens"]`. `TokenLedger.merge_baseline_accounting`
folds that key into the `rebite` bucket. Without this, a re-bite arm receives
extra evidence at zero token cost and cannot be fairly compared with an arm
that has no recovery budget (DC-6).

## Double-counting rules (DC-1..6)

From BITE-04 §5.2 (locked as experiment contract; ledger field names filled by BITE-13):

| ID | Contract |
| --- | --- |
| **DC-1** | One API / model call = **one** ledger row (`call_id`) |
| **DC-2** | Deterministic preprocess → tokens **0**; CPU / wall in separate fields |
| **DC-3** | Cache policy label consistent across conditions (policy numeric TBD) |
| **DC-4** | Count only text **actually sent**; no logical dual-use double count |
| **DC-5** | Baselines use the **same** `T_total` contract |
| **DC-6** | INTEGRATE / Recover / profiler(LLM) / router(LLM) all counted |

## Provider usage vs local estimate

| Source | Field / label | Meaning |
| --- | --- | --- |
| Provider usage | `estimate_source=provider_usage` | Billed / reported tokens from a provider response (when available) |
| Local proxy | `estimate_source=local_char4_proxy` | `ceil(chars/4)` scaffold estimate |

**Local char/4 is a proxy only.** It must not be silently presented as provider usage. Prefer provider fields when an offline stub or future meter supplies them.

## Failures

Failed runs remain in the artifact ledger / manifest. Smoke harness does not silently drop failures from retained records. Averages (if computed later) must not silently exclude failures without an explicit, documented rule — **not implemented as calibrated stats here**.

## Secrets

Raw prompts may be hashed (`*_sha256`) or redacted. Secret-looking keys (`api_key`, `password`, …) must never be written to artifacts.
