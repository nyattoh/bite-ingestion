# BITEBench generation (BITE-06)

## Goal

Counterfactual **same facts / different texture** surfaces for evaluation-first (Pivot-to-bench) work.

## Contract

- Canonical identity: `facts`, `question`, `answer`, `required_evidence_ids`
- Textures change **surface form only**
- Real dataset names / licences / human fact-identity locks remain `TBD` (BITE-07)
- No architecture-superiority claims

## Families

`prose_narrative`, `table_csv`, `nested_json`, `event_logs`, `code_config`, `mixed_payload`

## Reproduce

```bash
python -m bite_bench.cli --seed 0 --out benchmarks/frozen-v0.1/syn-case-000.json
```

Generator version is embedded in each bundle (`generator_version`).


## Phase 1B canonical pool and holdout split

The current synthetic pool is fixed at 24 canonical cases for Phase 1B.

- calibration/development: seeds 0..11
- evaluation/holdout: seeds 12..23

The split is recorded in `benchmarks/spec/phase1b-split-manifest.json`.

Evaluation cases must not be used to tune profiler features, thresholds, routing
rules, or operators. If evaluation results are used to change those choices,
create a new benchmark revision rather than silently reusing the same holdout.

Each canonical case renders into the same six texture families while keeping
facts, question, answer, and required evidence identity fixed.

### Length matching

The current contrast-pair padding is character-based diagnostic padding only.
It is explicitly **not** token-length matching. A target tokenizer and matching
tolerance must be selected and recorded before the confirmatory benchmark is
fully frozen.


## Phase 2A factorial benchmark generation

Phase 2A starts a **new benchmark generation** rather than editing the spent
Phase 1 holdout.

Canonical axes:

- scale: small / medium / large
- dependency: direct / chain3
- replicas: 0..3, with 0..1 calibration and 2..3 evaluation

Surface axes use a full 2 x 2 x 2 factorial:

- structure: flat / nested
- dispersion: clustered / dispersed
- redundancy: low / high

This yields 24 canonical cases and 192 rendered surfaces.

The design is declared in `benchmarks/spec/phase2a-design.json` and implemented
in `src/bite_bench/phase2a.py`. The module intentionally does not import
profiler/routing/operator code and stores no expected route labels.

### Phase 2A limitation

Token-length matching is **not frozen yet**. These surfaces must not be used for
arm-performance claims. Phase 2B may use the calibration split only to build a
fair length-controlled construction. Evaluation routing outcomes must remain
unopened until that construction is frozen.
