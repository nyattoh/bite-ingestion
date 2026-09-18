# bite-ingestion (research scaffold)

Offline-reproducible **repository scaffold** for Gate B (BITE-05).

## Stance (locked from Gate A)

- Official interim direction: **Pivot-to-bench** (evaluation / BITEBench / full-cost accounting first).
- Do **not** treat this README as a claim of architecture superiority.
- Working folder name remains `bite-ingestion`. Prefer talking about **BITEBench** and a *morphology-aware ingestion candidate*; do not advertise a standalone product acronym as settled.

## Layout

| Area | Path | Status |
| --- | --- | --- |
| Package | `src/bite_ingestion/` | Interfaces + JSON Schemas |
| Tests | `tests/` | Offline schema / smoke |
| Config | `configs/default.toml` | Placeholders (`TBD`) |
| Gate | `scripts/gate.sh`, `scripts/gate.ps1` | lint / typecheck / test / schema |
| BITEBench slot | `bitebench/` | For BITE-06 |
| Harness slot | `harness/` | For BITE-13 |
| Artifacts / seeds | `artifacts/`, `seeds/` | Managed empties |

## Install

```bash
python -m venv .venv
pip install -e ".[dev]"
```

## Verify

```bash
./scripts/gate.sh
# or Windows: ./scripts/gate.ps1
```

## TBD (human only)

Names, datasets, APIs, numeric thresholds/budgets: keep literal `TBD`.

## Non-goals

No UI, no mandatory cloud DB, no unapproved learned models, no push/publish/purchase.

## Current status

- Historical billed pilot (`967ec0b`): decision = **pivot** (not Go)
- Phase 0 evaluator repair: complete
- Phase 1 foundation / offline arm wiring: complete
- Negative controls: complete; the instrument now reports known evidence/provenance failures
- Phase 1B benchmark pool: **24 canonical cases**, fixed **12 calibration / 12 evaluation** split
- No architecture-superiority claim
- No new paid run yet
- Phase 1C token-length condition: frozen and holdout-validated (12/12 matched without padding)
- **Next**: confirmatory offline comparison under the frozen benchmark, then a small paid smoke if it is clean

See:
- [`docs/hand_over/PHASE1-NEGATIVE-CONTROLS.md`](docs/hand_over/PHASE1-NEGATIVE-CONTROLS.md)
- [`docs/hand_over/PHASE1B-BENCHMARK-POOL-SPLIT.md`](docs/hand_over/PHASE1B-BENCHMARK-POOL-SPLIT.md)
- [`benchmarks/spec/phase1b-split-manifest.json`](benchmarks/spec/phase1b-split-manifest.json)
- [`docs/hand_over/PHASE1C-TOKEN-MATCH-FREEZE.md`](docs/hand_over/PHASE1C-TOKEN-MATCH-FREEZE.md)
