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

## Current status (Gate C)

- **v2 billed pilot** (`967ec0b`): decision = **pivot** (not Go)
- C1=false, C2=not_evaluated, C3=false
- `compressed_passthrough` was effectively no-op on short synthetic docs; do not claim morphology win
- **Path B** (48-call family fix): separate `dependency_chain` prompt clarification slice; ok_rate=1.0 on that family ≠ full 384 matrix
- **Next**: Phase 0 evaluator fixes, then offline real arms — NOT full 384 rebill yet

See [`docs/hand_over/BITE-15b.md`](docs/hand_over/BITE-15b.md) and [`docs/hand_over/BITE-16.md`](docs/hand_over/BITE-16.md) for details.
