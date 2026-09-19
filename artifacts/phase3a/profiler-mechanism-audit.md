# Phase 3A profiler mechanism audit

post-hoc。confirmatory ではない。holdout を再評価していない。
profiler / threshold / routing は未変更。有料 API 未使用。

- verdict: **PHASE3A_DISPERSION_UNOBSERVABLE**
- Phase 2D: PHASE2D_OFFLINE_NO_SIGNAL (0/48)
- profiler vectors identical: 48/48
- required-evidence span spread differs: 48/48 (audit diagnostic, not a routing feature)
- query-hit line-index span differs: 24/48 (order-sensitive diagnostic; not `l`. On this benchmark many query tokens also substring-match distractor lines, so this is a weak proxy.)

## `l` is not positional locality

query-token substring hit mass on stripped lines; hits are sorted descending and the top min(3,n) / total is kept. Line order and inter-line distance are discarded. Not positional evidence locality.

## Feature abs delta (clustered vs dispersed)

- `b` (routing): n_nonzero=0 max_abs=0.0 mean_abs=0.0
- `r` (routing): n_nonzero=0 max_abs=0.0 mean_abs=0.0
- `s` (non-routing): n_nonzero=0 max_abs=0.0 mean_abs=0.0
- `k` (routing): n_nonzero=0 max_abs=0.0 mean_abs=0.0
- `a` (routing): n_nonzero=0 max_abs=0.0 mean_abs=0.0
- `l` (routing): n_nonzero=0 max_abs=0.0 mean_abs=0.0
- `p` (non-routing): n_nonzero=0 max_abs=0.0 mean_abs=0.0
- `u` (routing): n_nonzero=0 max_abs=0.0 mean_abs=0.0

## Policy

- rule-Π routing keys: ['b', 'a', 'r', 'k', 'l', 'u']
- `u` is accepted but unused for routing (existing rule-Π note)
- INTEGRATE needs `k≥HIGH` and `l≤LOW`; this audit does not retune that

