# Baseline parity checklist (BITE-12)

**Tone**: Pivot-to-bench. Name plan B — morphology-aware ingestion candidate vs fair baselines under BITEBench. No Survive product claims. Thresholds TBD placeholders only.

## Same evaluation interface

| Check | Status |
| --- | --- |
| All baselines expose `baseline_id` + `run(packet, context) -> Mapping` | required |
| Output always has `status` ∈ {ok, failed, overflow, not_applicable} | required |
| Output has `visible_evidence` | required |
| Output has `accounting.baseline_router_tokens` and `baseline_compressor_tokens` | required (0 OK for pure deterministic offline) |
| Output has `tau` and/or `baseline_trace` | required |
| Failures / overflow never silently dropped | required |
| No extra tool permissions vs candidate | required |
| No paid API / keys / real personal data | required (D-3, D-4) |

## Required adapter ids

| # | id | Family | Parity notes |
| --- | --- | --- | --- |
| 1 | `raw_full` | Raw full context | Pass-through; `overflow` if `max_chars` exceeded |
| 2 | `length_pi` | Length-only router | Wraps `LengthOnlyPolicy` |
| 3 | `fixed_chunk_topk` | Fixed chunk + top-k | Offline char-chunk + lexical overlap; cutpoints TBD |
| 4 | `adaptive_chunk_like` | Adaptive-*like* | Boundary heuristics only |
| 5 | `universal_reduce` | Universal REDUCE | FixedPolicy(REDUCE) |
| 6 | `query_aware_compress_like` | Query-aware compress-*like* | Irreversible sentence keep; declares loss |
| 7 | `hyve_like` | Domain machine_data | Field projection stub; else `not_applicable` |
| 8 | `contextsniper_like` | Domain code | def/class gate stub; else `not_applicable` |
| 9 | `rule_pi` | Candidate rule-Π | Wraps `RulePolicy` |
| 10 | `rule_pi_rebite` | rule-Π + re-bite hook | `rebite_enabled=True`; RecoverEngine optional |
| 11 | `oracle_pi` | Oracle-Π | Eval flag required |
| — | `fixed_pi` | Fixed-Π | Format-fixed baseline (統括) |

## Explicitly NOT reimplemented

| System / paper | What we ship instead | Why |
| --- | --- | --- |
| **HYVE** | `hyve_like` JSON/CSV projection stub | No unauthorized full reimplementation; trademark-safe `-like`; fairness contrast only |
| **ContextSniper** | `contextsniper_like` def/class query-token gate | Same — no full reimplementation |
| Adaptive Chunking (paper code) | `adaptive_chunk_like` boundary heuristics | Offline stub; not a port |
| LongLLMLingua / CompAct | `query_aware_compress_like` sentence overlap keep | Irreversible stub; not a reimplementation |

## Domain gates

- `hyve_like`: only `domain=machine_data` (aliases: machine-data, tabular, observability). Wrong domain → `not_applicable` + reason.
- `contextsniper_like`: only `domain=code` (aliases: code_config, repository, source_code). Wrong domain → `not_applicable` + reason.

## Accounting

- Pure deterministic offline adapters report `baseline_router_tokens=0`, `baseline_compressor_tokens=0`.
- Policy wrappers that only *propose* sequences (no LLM call) likewise report 0.
- Future LLM-backed compressors must meter compressor tokens here (BITE-13 harness).

## Do not

- Use paper-reported numbers as run results
- Exclude failures from fixtures/tests
- Apply hyve/cs on wrong domains
- Implement non-normal-form mappings (D-5a)
- Claim Survive architecture / Go thresholds (D-1, D-2)

## Config pins

See `configs/baselines/*.json` — version / licence / fairness_limits. `-like` stubs use `licence=stub-offline`, `version=0.1-synthetic`.
