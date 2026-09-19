# Phase 2B calibration length control

BITE の性能評価ではない。profiler / routing / operator は走らせていない。
evaluation/holdout は封印。padding なし。

- base main SHA: `dce759efbb94ae941a86c3358b1b717da3224c14`
- verdict: **PHASE2B_LENGTH_CONTROL_PARTIAL**
- paid_api: False
- Phase 1C criterion: abs <= 3, rel <= 0.04, no padding
- calibration cases: 12 surfaces: 96

## Axis summaries (Phase 1C criterion only)

| axis | n | matched | match rate | mean abs | median abs | max abs |
|---|---:|---:|---:|---:|---:|---:|
| structure | 48 | 0 | 0.0 | 653.6666666666666 | 467.0 | 2039 |
| dispersion | 48 | 48 | 1.0 | 0.0 | 0.0 | 0 |
| redundancy | 48 | 0 | 0.0 | 1794.6666666666667 | 1260.0 | 4588 |

### Scale / dependency match rates

**structure**

- scale: large: 0/16 (0.0); medium: 0/16 (0.0); small: 0/16 (0.0)
- dependency: chain3: 0/24 (0.0); direct: 0/24 (0.0)

**dispersion**

- scale: large: 16/16 (1.0); medium: 16/16 (1.0); small: 16/16 (1.0)
- dependency: chain3: 24/24 (1.0); direct: 24/24 (1.0)

**redundancy**

- scale: large: 0/16 (0.0); medium: 0/16 (0.0); small: 0/16 (0.0)
- dependency: chain3: 0/24 (0.0); direct: 0/24 (0.0)

## Candidate alternative tolerances (not mixed, not frozen, not evaluation)

- `abs10_rel10pct` abs<=10 rel<=0.1: calibration inspection only; not a freeze; not applied to evaluation
  - dispersion: 48/48 (1.0)
  - redundancy: 0/48 (0.0)
  - structure: 0/48 (0.0)

- `abs25_rel15pct` abs<=25 rel<=0.15: calibration inspection only; not a freeze; not applied to evaluation
  - dispersion: 48/48 (1.0)
  - redundancy: 0/48 (0.0)
  - structure: 0/48 (0.0)

## Morphology coverage (not BITE profiler features)

- calibration cases checked: 12; ok: 12

## What we wanted to know

- dispersion: can it stay near equal token length?
  match_rate=1.0
- structure: can it match naturally?
  match_rate=0.0
- redundancy: separable from length, or covariant?
  match_rate=0.0
