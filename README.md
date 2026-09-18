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
- Phase 1D confirmatory offline comparison: **PHASE1D_OFFLINE_NO_SIGNAL** (holdout 12 × frozen pair; length_pi and rule_pi both chose no-op CUT; not a paid-model result)
- Phase 2A factorial benchmark design: **DESIGN_READY_NOT_FROZEN** (24 canonical cases × 8 morphology surfaces; routing-independent)
- Phase 2B calibration length control: **PHASE2B_LENGTH_CONTROL_PARTIAL** (dispersion matches exactly; structure and redundancy covary with length; no padding; evaluation sealed)
- Phase 2C dispersion confirmatory freeze: **FROZEN_PRE_HOLDOUT** (`phase2c-dispersion-freeze-v0.2` supersedes v0.1)
- Phase 2D confirmatory offline evaluation: **PHASE2D_OFFLINE_NO_SIGNAL** (0/48 eligible dispersion pairs; evaluation opened once under v0.2; not a paid-model result)
- Phase 3A profiler mechanism audit: **PHASE3A_DISPERSION_UNOBSERVABLE** (post-hoc; current `l` is permutation-invariant query-hit mass, not positional locality; holdout not re-scored)
- Phase 3B gold-free dispersion sensor: **PHASE3B_SENSOR_READY** (development fixtures only; not wired to routing; v0 unchanged)
- **Next**: do not retune profiler / thresholds / routing on the spent Phase 2 holdout

See:
- [`docs/hand_over/PHASE1-NEGATIVE-CONTROLS.md`](docs/hand_over/PHASE1-NEGATIVE-CONTROLS.md)
- [`docs/hand_over/PHASE1B-BENCHMARK-POOL-SPLIT.md`](docs/hand_over/PHASE1B-BENCHMARK-POOL-SPLIT.md)
- [`benchmarks/spec/phase1b-split-manifest.json`](benchmarks/spec/phase1b-split-manifest.json)
- [`docs/hand_over/PHASE1C-TOKEN-MATCH-FREEZE.md`](docs/hand_over/PHASE1C-TOKEN-MATCH-FREEZE.md)
- [`docs/hand_over/PHASE1D-CONFIRMATORY-OFFLINE.md`](docs/hand_over/PHASE1D-CONFIRMATORY-OFFLINE.md)
- [`docs/hand_over/PHASE2A-FACTORIAL-BENCHMARK-DESIGN.md`](docs/hand_over/PHASE2A-FACTORIAL-BENCHMARK-DESIGN.md)
- [`benchmarks/spec/phase2a-design.json`](benchmarks/spec/phase2a-design.json)
- [`docs/hand_over/PHASE2B-CALIBRATION-LENGTH-CONTROL.md`](docs/hand_over/PHASE2B-CALIBRATION-LENGTH-CONTROL.md)
- [`benchmarks/spec/phase2b-length-control-draft.json`](benchmarks/spec/phase2b-length-control-draft.json)
- [`docs/hand_over/PHASE2C-DISPERSION-FREEZE.md`](docs/hand_over/PHASE2C-DISPERSION-FREEZE.md)
- [`benchmarks/spec/phase2c-dispersion-freeze.json`](benchmarks/spec/phase2c-dispersion-freeze.json) (v0.1, retained)
- [`benchmarks/spec/phase2c-dispersion-freeze-v0.2.json`](benchmarks/spec/phase2c-dispersion-freeze-v0.2.json)
- [`docs/hand_over/PHASE2D-CONFIRMATORY-OFFLINE.md`](docs/hand_over/PHASE2D-CONFIRMATORY-OFFLINE.md)
- [`artifacts/phase2d/confirmatory-offline.json`](artifacts/phase2d/confirmatory-offline.json)
- [`docs/hand_over/PHASE3A-PROFILER-MECHANISM-AUDIT.md`](docs/hand_over/PHASE3A-PROFILER-MECHANISM-AUDIT.md)
- [`artifacts/phase3a/profiler-mechanism-audit.json`](artifacts/phase3a/profiler-mechanism-audit.json)
- [`docs/hand_over/PHASE3B-DISPERSION-SENSOR.md`](docs/hand_over/PHASE3B-DISPERSION-SENSOR.md)
- [`artifacts/phase3b/sensor-evaluation.json`](artifacts/phase3b/sensor-evaluation.json)
