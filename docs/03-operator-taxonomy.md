# Operator taxonomy (Gate A pointer — condensed)

- **Status**: Pivot-to-bench. Evaluation / BITEBench / full-cost accounting first.
- **Not claimed**: Survive architecture primacy; optimality of any tooth mnemonic.
- **Source**: BITE-03 design (`bite-03-2026-09-16.md`). No invented numeric thresholds.

## Four operators (candidate system under test)

| Op | Intent | Invariants (summary) |
|---|---|---|
| **CUT** | Split/select along natural boundaries (paragraph / line / record) | Contiguous source spans or schema records only; no invented prose; provenance registrable in \(R\); no colliding `unit_id` |
| **UNTANGLE** | Isolate malformed / anomaly / injection-suspect / dependency regions | Isolation = quarantine into \(R\) (recoverable), not deletion; reason codes required; residual ∪ isolated covers input units |
| **REDUCE** | Dedupe / aggregate / canonicalise; prefer quasi-reversible paths | Every omitted/merged unit has \(R\) key; no free-text summary as primary path; omit map in trace; declare loss in ledger |
| **INTEGRATE** | Assemble multi-unit evidence (join) | Provenance pointers on outputs; `integrate_mode` distinguished; BITE-09 library ships **deterministic_join only** (no unbounded LM in-op) |

## Shared contracts

- Trace \(\tau\): each step records `op`, `mode=deterministic`, `inputs_ref`, `outputs_ref`, `omitted_ref`, `errors[]`.
- Accounting: deterministic preprocessing contributes **0 model tokens** (CPU/wall optional, separate).
- Soft fail: `op_status=failed|degraded` on packet; downstream policy is BITE-04/10 concern.
- Grammar reminder (BITE-02): \(\mathrm{CUT}? \to \mathrm{UNTANGLE}? \to \mathrm{REDUCE}? \to \mathrm{INTEGRATE}?\) (each at most once; ≥1 overall). Non-normal sequences are evaluation flags, not defaults.

## Morphology relation (non-prescriptive)

Features \(\mathbf{m}=(b,r,s,k,a,l,p,u)\) may *suggest* whether an op is useful; they do **not** prove a unique correct route. Transparent `rule-Π` must not receive oracle \(\mathbf{m}\) or gold routes.

## Numeric thresholds

Any detector threshold that would require calibration is **TBD** (BITE-04 / calibration). Structural rules are preferred over magic numbers.
