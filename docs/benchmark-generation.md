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
