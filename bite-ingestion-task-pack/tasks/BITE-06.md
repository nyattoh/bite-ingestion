# BITE-06 — BITEBench counterfactual texture generatorを作る

## Assignment

- Phase: `Gate B`
- Maker: `gpt-5.6-terra / High`
- Checker: `gpt-5.6-sol / High`
- Depends on: `BITE-05`

## Objective

canonical fact graphから内容不変の複数textureとground-truth evidenceを生成するheadline benchmarkを実装する。

## Read first

- research/preregistration.md
- docs/02-formal-model.md
- docs/03-operator-taxonomy.md

## Deliverables

- src/bite_bench/
- benchmarks/spec/
- benchmarks/frozen-v0.1/
- docs/benchmark-generation.md
- tests/test_texture_invariance.py

## Acceptance criteria

- prose、CSV/table、nested JSON、logs、code/config、mixedを生成する
- canonical answerとrequired evidence IDsが全textureで一致する
- surface formだけでlabelが漏れないsplitを作る
- length-matched texture pairsを含む
- short-denseとlong-repetitiveの反例を含む
- generator seedとversionで完全再現できる

## Do not

- 各textureで問題難易度を変えない
- route labelを入力へ埋め込まない
- LLM生成fixtureを未検証で採用しない

## Verify

- hash-based invariance checks
- checkerが20 sampleを手動監査する

## Completion record

`docs/hand_over/BITE-06.md` に、変更、検証結果、failure、未解決点、次taskが読むartifactを記録する。
