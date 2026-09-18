# Phase 1C token-length freeze handover

## Status

`PHASE1C_TOKEN_MATCH_FROZEN`

No paid API calls were made. This phase only fixes a fair length-comparison condition.

## What we did

The previous benchmark could make two surfaces the same **character** length, but character length is not model token length. Phase 1C replaces that diagnostic shortcut with a real tokenizer-based measurement.

The repo's billed pilot targets Z.ai `glm-4.5-flash`. For reproducible offline counting we pinned the public GLM-4.5-family tokenizer:

- repository: `zai-org/GLM-4.5`
- revision: `cbb2c7cfb52fa128a9660cb1a7a78e017899e115`
- Transformers: `4.54.0`
- `tokenizer.json` SHA256: `9340665016419c825c4bdabbcc9acc43b7ca2c68ce142724afa829abb1be5efd`

Important limitation: we do **not** claim that Z.ai's hosted `glm-4.5-flash` exposes a tokenizer byte-for-byte identical to this public reference. The benchmark records this explicitly.

## Rule selection was calibration-only

Before opening the evaluation/holdout cases, calibration seeds 0..11 were measured across every fixed texture pair.

The frozen pair is:

- `prose_narrative`
- `table_csv`

No padding is added.

A pair counts as length-matched only when both conditions hold:

- absolute difference <= 3 tokens
- symmetric relative difference <= 4%

On the 12 calibration cases:

- 12/12 matched
- mean absolute difference: 1.25 tokens
- maximum absolute difference: 3 tokens
- mean relative difference: 1.58%
- maximum relative difference: 3.73%

The rule was committed in `benchmarks/spec/phase1c-token-freeze.json` at commit
`2217253b0cad455cd18851a0b5fc42ac6bd73030` **before** the holdout was opened.

## Holdout result

The untouched evaluation seeds 12..23 were then measured under the already-frozen rule. The rule was not changed afterward.

Result:

- 12/12 matched
- mean absolute difference: 1.17 tokens
- maximum absolute difference: 3 tokens
- mean relative difference: 1.36%
- maximum relative difference: 3.64%

The holdout was opened under commit
`2eb24dc1ff88ebf490803f9ce1a072bd4b68c97b`.

Exact per-case counts are stored in
`benchmarks/spec/phase1c-token-freeze.json`.

## Why this matters

We now have a same-facts comparison where the two surface forms are naturally almost the same token length. We did not make them equal by appending filler.

That means a later difference between the two forms is much harder to dismiss as merely "one input was longer."

This still does **not** show that morphology-aware routing is better. It only makes the next comparison fairer.

## Reproduction

`scripts/measure_phase1c_token_lengths.py` reproduces the token counts. The tokenizer dependency is intentionally **not** part of normal project CI; install the pinned measurement dependencies only when reproducing the freeze.

The script hashes `tokenizer.json` and fails closed if that file differs from the frozen hash.

## Next phase

Run the four offline arms against the frozen benchmark conditions without changing:

- the 24-case calibration/evaluation split,
- the prose/table token-match pair,
- the token-match tolerance,
- profiler features,
- routing thresholds,
- operators.

The confirmatory offline run should be reported separately from development/calibration results. Only after that result is inspected should a small paid smoke be considered.
