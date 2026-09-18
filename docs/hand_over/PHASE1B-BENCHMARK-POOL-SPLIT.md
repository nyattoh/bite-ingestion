# Phase 1B benchmark expansion / split handover

## Status

`BENCHMARK_POOL_SPLIT_READY`

This phase expands the canonical same-facts case pool and fixes a calibration/evaluation split. It does **not** claim BITE is better than length-only routing, and it does **not** run paid APIs.

## What changed

- Canonical pool expanded from 2 to 24 deterministic synthetic cases.
- Seeds 0..11 are calibration/development cases.
- Seeds 12..23 are evaluation/holdout cases.
- The split is machine-readable in `benchmarks/spec/phase1b-split-manifest.json`.
- Every canonical case still renders into the same six texture families.
- Same-facts invariants remain enforced: facts, question, answer, and required evidence identity are stable across textures.
- Seeds 0 and 1 preserve the previous v0.2 canonical identities, so existing frozen fixture checks remain valid.

## Why the split exists

The evaluation cases are the equivalent of an exam. They must not be used to decide:

- profiler features,
- thresholds,
- routing rules,
- operator choices.

Those decisions may use the calibration set only. If the evaluation set is later used to change those rules, a new benchmark revision is required.

## Current pool

- 24 canonical cases
- 12 calibration
- 12 evaluation
- 6 surface textures per case
- 144 ordinary rendered surfaces in total before contrast-pair diagnostics

The case templates cover six ordinary information shapes, repeated with distinct synthetic identities:

1. service -> error code
2. item -> quantity
3. application + environment -> version
4. sensor + location -> reading
5. order -> status
6. account + scope -> role

These are intentionally simple canonical facts. Texture complexity comes from the renderer, not from changing the answer.

## Important limitation: token length matching is still not done

The repository still has only character-length padding for its diagnostic contrast pair.

That is **not** token matching.

No target tokenizer has been selected, so the manifest explicitly records:

`token_length_matching.status = not_implemented`

Do not use the padded contrast pair as evidence that two inputs have equal model-token length.

This is the next blocker before a fully frozen confirmatory benchmark.

## What was not changed

- Phase 1 routing thresholds
- profiler feature definitions
- routing rules
- operators
- negative-control expectations
- paid/billed runner behavior

## Next step

Implement tokenizer-based length matching as a pluggable benchmark utility, then freeze a new benchmark revision with:

- tokenizer identity/version,
- matching tolerance,
- per-pair token counts,
- dataset fingerprint,
- generator/version information.

Only after that freeze should a confirmatory offline comparison be treated as an evaluation rather than development feedback.
