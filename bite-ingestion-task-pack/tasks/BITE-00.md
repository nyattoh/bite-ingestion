# BITE-00 — 研究境界、名称、注目フックを固定する

## Assignment

- Phase: `Gate A`
- Maker: `gpt-6-astra / Low`
- Checker: `gpt-5.6-sol / High`
- Depends on: `none`

## Objective

BITEを独立研究として定義し、仮称、repository境界、技術的問い、非目標、attention framingを人が承認できる形にする。

## Read first

- PAPER_OUTLINE.md
- EXCITEMENT_STRATEGY.md
- PRIOR_ART_SEEDS.md
- topodialogue/README.md
- h2o-memory-topophase/README.md

## Deliverables

- docs/00-research-scope.md
- docs/01-claim-boundary.md
- docs/adr/0001-repository-and-name.md
- docs/name-collision-check.md
- docs/REVIEW_QUEUE.md

## Acceptance criteria

- 主研究問いが一文で書かれている
- BITE、BITEBench、BITE Before You Thinkの名称衝突を論文・software・商標の観点で調べている
- 歯の比喩はmnemonicであり証拠ではないと明記されている
- Topo系とは独立しadapter接続だけを許す
- attention hookとformal contributionが別欄にある
- v0.1、v0.2、非目標、pivot条件が分離されている

## Do not

- 実装を始めない
- 新規性を確定しない
- 採択や注目を保証しない

## Verify

- checkerが一文問いをRAG／prompt compressionの言い換えだけでないか批判する
- 名称衝突結果に検索日とqueryを残す

## Completion record

`docs/hand_over/BITE-00.md` に、変更、検証結果、failure、未解決点、次taskが読むartifactを記録する。
