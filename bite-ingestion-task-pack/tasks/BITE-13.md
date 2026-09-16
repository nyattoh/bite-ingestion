# BITE-13 — total-token evaluation harnessとartifact ledgerを実装する

## Assignment

- Phase: `Gate B`
- Maker: `gpt-5.6-terra / High`
- Checker: `gpt-5.6-sol / High`
- Depends on: `BITE-10, BITE-11, BITE-12`

## Objective

全methodを同一run contractで実行し、token、quality、evidence、latency、overheadを再現可能に記録する。

## Read first

- research/metric-contract.json
- research/statistical-analysis-plan.md
- MODEL_EFFORT_POLICY.md

## Deliverables

- src/bite_eval/
- scripts/run_matrix.py
- scripts/validate_artifacts.py
- schemas/run-manifest.schema.json
- tests/eval/
- docs/token-accounting.md

## Acceptance criteria

- profiler/router/target/re-biteのtokenを別々かつ総計で記録する
- provider usage fieldsとlocal tokenizer estimateを区別する
- quality、evidence recall、provenance、latencyを同時に記録する
- raw prompts/responsesはprivacy policyに従いhashまたはredactできる
- resumeしてもduplicate runを作らない
- all failuresをmanifestに残す

## Do not

- target input tokenだけをtotalと呼ばない
- failed runを平均から黙って除く
- secretをartifactへ書かない

## Verify

- synthetic token ledger sums
- schema validation
- two-run reproducibility check

## Completion record

`docs/hand_over/BITE-13.md` に、変更、検証結果、failure、未解決点、次taskが読むartifactを記録する。
