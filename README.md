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
- Phase 3C sensor generalization audit: **PHASE3C_SENSOR_SCOPED** (development fixtures only; scale/format/co-occurrence limits recorded; not wired to routing; v0 unchanged)
- Phase 3D v1 sensor design freeze: **PHASE3D_V1_DESIGN_FROZEN** (index lookup, value→key/record-id, logical units; kv+JSON required; not implemented; not wired)
- Phase 3E v1 sensor implementation: **PHASE3E_V1_VALIDATED** (development freeze fixtures; v0 retained; routing unconnected)
- Phase 3F routing calibration protocol freeze: **PHASE3F_ROUTING_CALIBRATION_PROTOCOL_FROZEN** (`phase3f-routing-calibration-freeze-v0.3` supersedes v0.2; thresholds not set; RulePolicy unconnected)
- Phase 3G calibration lock: **PHASE3G_CALIBRATION_LOCKED** (candidate A `mean_edge_distance`, T_low=1 T_high=4; evaluation sealed; RulePolicy unconnected)
- Phase 3H operator-map development experiment: **PHASE3H_CONDITIONAL_MAP_REQUIRED** (p3h high-dispersion textures; p3f evaluation sealed; RulePolicy not implemented)
- Phase 3I composite provenance: **PHASE3I_COMPOSITE_PROVENANCE_VALIDATED** (multi-source derived units; p3f evaluation sealed; RulePolicy unconnected)
- Phase 3J texture observability: **PHASE3J_TEXTURE_SENSOR_REVISION_REQUIRED** (p3j gold-free audit; r is format-unstable on compact JSON; profiler unchanged)
- Phase 3K structural redundancy v1: **PHASE3K_REDUNDANCY_SENSOR_READY** (logical-record duplicate_unit_ratio; v0.r retained; RulePolicy unconnected)
- Phase 3L redundancy first-open: **PHASE3L_REDUNDANCY_HOLDOUT_CONFIRMED** (p3k replicas 2/3; same frozen families / new replica values; RulePolicy unconnected)
- Phase 3M gold-free conditional routing: **PHASE3M_CONDITIONAL_ROUTING_READY** (p3m development 0/1; `conditional_texture_policy_v1`; RulePolicy retained; p3m/p3f evaluation sealed)
- Phase 3N conditional routing first-open: **PHASE3N_CONDITIONAL_ROUTING_HOLDOUT_CONFIRMED** (p3m replicas 2/3; same frozen p3m texture families / new replica identifiers; p3f evaluation sealed)
- Phase 3O BITE-XFER-1 transfer: **PHASE3O_XFER1_TRANSFER_FAILED** (104 surfaces; routing/cross-format identity held; mixed_order sensor/operator mismatch + pretty_json composition safety; no retune; p3f evaluation sealed)
- Phase 3P record alignment v2: **PHASE3P_RECORD_ALIGNMENT_VALIDATED** (fresh p3p; sensor/operator biconditional; lineage-aware safety; Phase 3O remains FAILED; p3f sealed)
- Phase 3Q BITE-XFER-2 transfer: **PHASE3Q_XFER2_TRANSFER_FAILED** (112 surfaces; 100/112 ok; operator_interference on overlap/anomaly-join adversarial; mid case gated; no retune; p3f sealed)
- Phase 3R relation-channel + projected planner: **PHASE3R_CHANNEL_PLANNER_VALIDATED** (fresh p3r; v2 reference channel; projected actionability; T_high=4 carry-forward; Phase 3Q remains FAILED; p3f sealed)
- Phase 3S reference-edge specificity: **PHASE3S_REFERENCE_SPECIFICITY_FAILED** (fresh p3s; suffix collision false edges; no repair; Phase 3Q remains FAILED; p3f sealed)
- Phase 3T exact reference identity v3: **PHASE3T_EXACT_REFERENCE_VALIDATED** (fresh p3t; full-token exact edges; T_high=4 carry-forward; Phase 3S/3Q remain FAILED; p3f sealed)
- Phase 4A REALSTRUCT-1 corpus freeze: **PHASE4A_REAL_CORPUS_FROZEN** (12 public key=value configs; scorer-only annotation; no BITE run; Phase 3S/3Q remain FAILED; p3f sealed)
- Phase 4B REALSTRUCT-1 development adapter: **PHASE4B_REAL_ADAPTER_READY** (dev 3 only; source-exact dual-plane adapter; eval 9 sealed; no baseline; Phase 3S/3Q remain FAILED; p3f sealed)
- Phase 4C REALSTRUCT-1 holdout first-open: **PHASE4C_REAL_HOLDOUT_MEASURED** (frozen eval 9 once; full-source conservation safety 9/9; raw_full/adapter_only ablation; no retune; Phase 3S/3Q remain FAILED; p3f sealed)
- Phase 4D REALSTRUCT-1 measurement-semantics audit: **PHASE4D_MEASUREMENT_SEMANTICS_AUDITED** (retrospective atom-aware metric + safety-check decomposition; not a new holdout; no retune; p3f sealed)
- Phase 4E full-key reference identity v2: **PHASE4E_FULL_KEY_REFERENCE_VALIDATED** (fresh 80 surfaces; v3/v4 bridge exact; T=4 carry-forward; REALSTRUCT-1 retrospective only; p3f sealed)
- **Next**: do not invent XFER-3; do not swap REALSTRUCT-1 sources; do not retune T_high on this holdout

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
- [`docs/hand_over/PHASE3C-SENSOR-GENERALIZATION.md`](docs/hand_over/PHASE3C-SENSOR-GENERALIZATION.md)
- [`artifacts/phase3c/sensor-generalization.json`](artifacts/phase3c/sensor-generalization.json)
- [`docs/hand_over/PHASE3D-SENSOR-V1-DESIGN-FREEZE.md`](docs/hand_over/PHASE3D-SENSOR-V1-DESIGN-FREEZE.md)
- [`benchmarks/spec/phase3d-sensor-v1-design-freeze.json`](benchmarks/spec/phase3d-sensor-v1-design-freeze.json)
- [`docs/hand_over/PHASE3E-SENSOR-V1-VALIDATION.md`](docs/hand_over/PHASE3E-SENSOR-V1-VALIDATION.md)
- [`artifacts/phase3e/sensor-v1-validation.json`](artifacts/phase3e/sensor-v1-validation.json)
- [`docs/hand_over/PHASE3F-ROUTING-CALIBRATION-FREEZE.md`](docs/hand_over/PHASE3F-ROUTING-CALIBRATION-FREEZE.md)
- [`benchmarks/spec/phase3f-routing-calibration-freeze.json`](benchmarks/spec/phase3f-routing-calibration-freeze.json) (v0.1, retained)
- [`benchmarks/spec/phase3f-routing-calibration-freeze-v0.2.json`](benchmarks/spec/phase3f-routing-calibration-freeze-v0.2.json) (v0.2, retained)
- [`benchmarks/spec/phase3f-routing-calibration-freeze-v0.3.json`](benchmarks/spec/phase3f-routing-calibration-freeze-v0.3.json)
- [`docs/hand_over/PHASE3G-CALIBRATION-LOCK.md`](docs/hand_over/PHASE3G-CALIBRATION-LOCK.md)
- [`artifacts/phase3g/calibration-lock.json`](artifacts/phase3g/calibration-lock.json)
- [`docs/hand_over/PHASE3H-OPERATOR-MAP.md`](docs/hand_over/PHASE3H-OPERATOR-MAP.md)
- [`benchmarks/spec/phase3h-operator-map-freeze.json`](benchmarks/spec/phase3h-operator-map-freeze.json)
- [`artifacts/phase3h/operator-map-experiment.json`](artifacts/phase3h/operator-map-experiment.json)
- [`docs/hand_over/PHASE3I-COMPOSITE-PROVENANCE.md`](docs/hand_over/PHASE3I-COMPOSITE-PROVENANCE.md)
- [`benchmarks/spec/phase3i-composite-provenance-freeze.json`](benchmarks/spec/phase3i-composite-provenance-freeze.json)
- [`artifacts/phase3i/composite-provenance.json`](artifacts/phase3i/composite-provenance.json)
- [`docs/hand_over/PHASE3J-TEXTURE-OBSERVABILITY.md`](docs/hand_over/PHASE3J-TEXTURE-OBSERVABILITY.md)
- [`benchmarks/spec/phase3j-texture-observability-freeze.json`](benchmarks/spec/phase3j-texture-observability-freeze.json)
- [`artifacts/phase3j/texture-observability.json`](artifacts/phase3j/texture-observability.json)
- [`docs/hand_over/PHASE3K-STRUCTURAL-REDUNDANCY.md`](docs/hand_over/PHASE3K-STRUCTURAL-REDUNDANCY.md)
- [`benchmarks/spec/phase3k-structural-redundancy-freeze.json`](benchmarks/spec/phase3k-structural-redundancy-freeze.json)
- [`benchmarks/spec/phase3k-split-manifest.json`](benchmarks/spec/phase3k-split-manifest.json)
- [`artifacts/phase3k/structural-redundancy.json`](artifacts/phase3k/structural-redundancy.json)
- [`docs/hand_over/PHASE3L-REDUNDANCY-FIRST-OPEN.md`](docs/hand_over/PHASE3L-REDUNDANCY-FIRST-OPEN.md)
- [`benchmarks/spec/phase3l-redundancy-first-open-freeze.json`](benchmarks/spec/phase3l-redundancy-first-open-freeze.json)
- [`artifacts/phase3l/redundancy-first-open.json`](artifacts/phase3l/redundancy-first-open.json)
- [`docs/hand_over/PHASE3M-CONDITIONAL-ROUTING.md`](docs/hand_over/PHASE3M-CONDITIONAL-ROUTING.md)
- [`benchmarks/spec/phase3m-conditional-routing-freeze.json`](benchmarks/spec/phase3m-conditional-routing-freeze.json)
- [`benchmarks/spec/phase3m-split-manifest.json`](benchmarks/spec/phase3m-split-manifest.json)
- [`artifacts/phase3m/conditional-routing.json`](artifacts/phase3m/conditional-routing.json)
- [`docs/hand_over/PHASE3N-CONDITIONAL-ROUTING-FIRST-OPEN.md`](docs/hand_over/PHASE3N-CONDITIONAL-ROUTING-FIRST-OPEN.md)
- [`benchmarks/spec/phase3n-conditional-routing-first-open-freeze.json`](benchmarks/spec/phase3n-conditional-routing-first-open-freeze.json)
- [`artifacts/phase3n/conditional-routing-first-open.json`](artifacts/phase3n/conditional-routing-first-open.json)
- [`docs/hand_over/PHASE3O-BITE-XFER1.md`](docs/hand_over/PHASE3O-BITE-XFER1.md)
- [`benchmarks/spec/phase3o-xfer1-freeze.json`](benchmarks/spec/phase3o-xfer1-freeze.json)
- [`artifacts/phase3o/xfer1-transfer.json`](artifacts/phase3o/xfer1-transfer.json)
- [`docs/hand_over/PHASE3P-RECORD-ALIGNMENT.md`](docs/hand_over/PHASE3P-RECORD-ALIGNMENT.md)
- [`benchmarks/spec/phase3p-record-alignment-freeze.json`](benchmarks/spec/phase3p-record-alignment-freeze.json)
- [`artifacts/phase3p/record-alignment.json`](artifacts/phase3p/record-alignment.json)
- [`docs/hand_over/PHASE3Q-BITE-XFER2.md`](docs/hand_over/PHASE3Q-BITE-XFER2.md)
- [`benchmarks/spec/phase3q-xfer2-freeze.json`](benchmarks/spec/phase3q-xfer2-freeze.json)
- [`artifacts/phase3q/xfer2-transfer.json`](artifacts/phase3q/xfer2-transfer.json)
- [`docs/hand_over/PHASE3R-CHANNEL-PLANNER.md`](docs/hand_over/PHASE3R-CHANNEL-PLANNER.md)
- [`benchmarks/spec/phase3r-channel-planner-freeze.json`](benchmarks/spec/phase3r-channel-planner-freeze.json)
- [`artifacts/phase3r/channel-planner.json`](artifacts/phase3r/channel-planner.json)
- [`docs/hand_over/PHASE3S-REFERENCE-SPECIFICITY.md`](docs/hand_over/PHASE3S-REFERENCE-SPECIFICITY.md)
- [`benchmarks/spec/phase3s-reference-specificity-freeze.json`](benchmarks/spec/phase3s-reference-specificity-freeze.json)
- [`artifacts/phase3s/reference-specificity.json`](artifacts/phase3s/reference-specificity.json)
- [`docs/hand_over/PHASE3T-EXACT-REFERENCE.md`](docs/hand_over/PHASE3T-EXACT-REFERENCE.md)
- [`benchmarks/spec/phase3t-exact-reference-freeze.json`](benchmarks/spec/phase3t-exact-reference-freeze.json)
- [`artifacts/phase3t/exact-reference.json`](artifacts/phase3t/exact-reference.json)
- [`docs/hand_over/PHASE4A-REALSTRUCT1.md`](docs/hand_over/PHASE4A-REALSTRUCT1.md)
- [`benchmarks/spec/phase4a-realstruct1-freeze.json`](benchmarks/spec/phase4a-realstruct1-freeze.json)
- [`artifacts/phase4a/realstruct-1.json`](artifacts/phase4a/realstruct-1.json)
- [`corpora/realstruct-1/manifest.json`](corpora/realstruct-1/manifest.json)
- [`docs/hand_over/PHASE4B-REALSTRUCT1-DEV-ADAPTER.md`](docs/hand_over/PHASE4B-REALSTRUCT1-DEV-ADAPTER.md)
- [`benchmarks/spec/phase4b-scorer-addendum-freeze.json`](benchmarks/spec/phase4b-scorer-addendum-freeze.json)
- [`artifacts/phase4b/real-adapter.json`](artifacts/phase4b/real-adapter.json)
- [`docs/hand_over/PHASE4C-REALSTRUCT1-FIRST-OPEN.md`](docs/hand_over/PHASE4C-REALSTRUCT1-FIRST-OPEN.md)
- [`benchmarks/spec/phase4c-holdout-first-open-freeze.json`](benchmarks/spec/phase4c-holdout-first-open-freeze.json)
- [`artifacts/phase4c/real-holdout.json`](artifacts/phase4c/real-holdout.json)
- [`docs/hand_over/PHASE4D-MEASUREMENT-SEMANTICS.md`](docs/hand_over/PHASE4D-MEASUREMENT-SEMANTICS.md)
- [`benchmarks/spec/phase4d-measurement-semantics-freeze.json`](benchmarks/spec/phase4d-measurement-semantics-freeze.json)
- [`artifacts/phase4d/measurement-semantics.json`](artifacts/phase4d/measurement-semantics.json)
- [`docs/hand_over/PHASE4E-FULL-KEY-REFERENCE.md`](docs/hand_over/PHASE4E-FULL-KEY-REFERENCE.md)
- [`benchmarks/spec/phase4e-full-key-reference-freeze.json`](benchmarks/spec/phase4e-full-key-reference-freeze.json)
- [`artifacts/phase4e/full-key-reference.json`](artifacts/phase4e/full-key-reference.json)
