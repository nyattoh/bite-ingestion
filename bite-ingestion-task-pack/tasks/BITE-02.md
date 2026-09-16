# BITE-02 — データmorphologyとoperator selectionの形式モデルを確定する

## Assignment

- Phase: `Gate A`
- Maker: `gpt-6-astra / Medium`
- Checker: `gpt-5.6-sol / High`
- Depends on: `BITE-00, BITE-01`

## Objective

morphology vector、operator sequence、evidence packet、recoverability、total-token objectiveを反証可能に定義する。

## Read first

- research/prior-art-matrix.csv
- research/novelty-risk.md
- PAPER_OUTLINE.md

## Deliverables

- docs/02-formal-model.md
- docs/notation.md
- docs/morphology-feature-contract.md
- docs/assumptions-and-counterexamples.md
- spec/morphology.schema.json
- spec/evidence-packet.schema.json

## Acceptance criteria

- boundary、redundancy、regularity、coupling、anomaly、locality、provenance、sufficiency uncertaintyを操作的に定義する
- featureの単位、観測方法、domain依存性、失敗例を書く
- operator sequenceを単一class labelに潰さない
- routerを含むtotal token式を定義する
- visible evidenceとrecoverable evidenceを分ける
- short-but-dense、long-but-repetitive、malformed、goal-ambiguousの反例を含む

## Do not

- sizeをmorphologyの代理にしない
- embedding scoreを意味の真理にしない
- biologyから数式を導かない

## Verify

- 2D toy examplesとsmall fixturesで手計算を確認する
- checkerが最低4つのcounterexampleを追加する

## Completion record

`docs/hand_over/BITE-02.md` に、変更、検証結果、failure、未解決点、次taskが読むartifactを記録する。
