# Phase 2A — Factorial benchmark design handover

## Status

`PHASE2A_DESIGN_READY_NOT_FROZEN`

Base main: `302d3ef069edf7b905a954d76edd6ae2b59a0374` (Phase 1D merged)

This phase designs a new benchmark generation space after
`PHASE1D_OFFLINE_NO_SIGNAL`. It does **not** modify the Phase 1 benchmark,
profiler, routing rules, thresholds, operators, or recovery behaviour.

No paid API was used.

## Why a new benchmark generation is needed

Phase 1D showed that the frozen Phase 1 holdout was too simple for the four
arms to behave differently: every candidate route was a no-op `CUT`.

That result remains valid and immutable. Phase 2 does not rewrite or "fix"
those cases.

The new benchmark is defined from independent complexity factors first. It is
not built by asking which inputs would trigger the current BITE thresholds.

## Canonical design

24 canonical cases:

- scale: `small`, `medium`, `large`
- dependency: `direct`, `chain3`
- replica: 0, 1, 2, 3

Scale is implemented as neutral distractor fact count:

- small: 8
- medium: 32
- large: 96

These counts are benchmark design levels, not copies of BITE router threshold
constants.

Dependency:

- `direct`: two required evidence facts form a one-link lookup plus final value
- `chain3`: three required evidence facts form a two-link path plus final value

Split is assigned before any routing result is observed:

- replicas 0, 1: calibration/development
- replicas 2, 3: evaluation/holdout

That gives 12 calibration and 12 evaluation canonical cases.

## Surface design

Every canonical case is rendered into the full 2 x 2 x 2 factorial:

- structure: `flat` / `nested`
- dispersion: `clustered` / `dispersed`
- redundancy: `low` / `high`

Eight surface profiles per case, 192 surfaces total.

### Structure

The same key/value facts are emitted either as simple flat records or nested
JSON records.

### Dispersion

At both dependency levels, required evidence is either adjacent or spread
across the document. The facts themselves do not change. The `direct` design
uses two required facts specifically so this axis is active there as well.

### Redundancy

High redundancy repeats **non-gold** material only. Required evidence remains
single-occurrence, so answer/evidence identity does not become easier through
gold repetition.

## Independence from BITE routing

`src/bite_bench/phase2a.py` deliberately does not import `bite_eval`.

The design contains:

- no expected route
- no threshold values from the router
- no desired operator sequence
- no "BITE should win" labels

The evaluation split must not be used to tune those things later.

## What is not frozen yet

Token length matching is intentionally marked `not_frozen`.

The eight morphology profiles naturally have different lengths, especially the
redundancy axis. Phase 2A therefore **must not** be used for arm-performance
comparison.

The next development phase should work only on calibration replicas and decide
how to construct fair length-controlled contrasts without looking at evaluation
routing outcomes.

## Files

- `src/bite_bench/phase2a.py`
- `benchmarks/spec/phase2a-design.json`
- `tests/test_phase2a_design.py`

## Required next step: Phase 2B

Calibration/development only:

1. measure the 12 calibration canonical cases with the pinned tokenizer policy;
2. define length-controlled contrast construction without importing current
   routing thresholds;
3. inspect whether the factor generator actually spans useful morphology
   variation;
4. if routing rules are later calibrated, use calibration only and record every
   change;
5. do not open evaluation routing outcomes yet.

Only after the construction and any calibration choices are locked should a
new Phase 2 evaluation freeze be created.

## Research interpretation

Phase 2A is benchmark engineering, not evidence for BITE.

The Phase 1D result remains:

`PHASE1D_OFFLINE_NO_SIGNAL`

Phase 2A asks a new question: whether a broader, predeclared complexity space
contains conditions under which morphology-aware ingestion behaves differently
from length-only routing.
