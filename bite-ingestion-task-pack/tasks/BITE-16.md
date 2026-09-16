# BITE-16 — 統計解析、Pareto分析、error atlasを作る

## Assignment

- Phase: `Gate C`
- Maker: `gpt-5.6-sol / High`
- Checker: `gpt-6-astra / Medium`
- Depends on: `BITE-15`

## Objective

primary hypothesesを事前計画どおり評価し、effect size、uncertainty、domain差、失敗例をまとめる。

## Read first

- research/statistical-analysis-plan.md
- output/main/aggregates.parquet
- output/main/failures.jsonl

## Deliverables

- analysis/main-results.md
- analysis/hypothesis-tests.json
- analysis/pareto-data.csv
- analysis/error-atlas.md
- figures/data/
- analysis/claim-evidence-draft.csv

## Acceptance criteria

- matched-quality Paretoをprimaryにする
- effect sizeとconfidence/credible intervalを報告する
- domain aggregateだけでなくdomain別とtexture別を示す
- operator regret、evidence recall、re-bite recoveryを分析する
- negative and null resultを同じ粒度で書く
- multiple comparisonとmissing dataの扱いを明記する

## Do not

- p値だけで結論を出さない
- 平均token reductionでtail failureを隠さない
- post-hoc subgroupをprimaryに昇格しない

## Verify

- checkerがraw manifestsから主要数値を再計算する
- plot dataと本文表の一致を検査する

## Completion record

`docs/hand_over/BITE-16.md` に、変更、検証結果、failure、未解決点、次taskが読むartifactを記録する。
