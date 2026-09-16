# BITE-01 — 近接研究を再現可能に調べ、novelty kill gateを実行する

## Assignment

- Phase: `Gate A`
- Maker: `gpt-6-astra / Medium`
- Checker: `gpt-5.6-sol / High`
- Depends on: `BITE-00`

## Objective

HYVE、ContextSniper、Adaptive Chunking、LongLLMLingua等との操作単位の差分を検証し、研究を続ける価値があるか判定する。

## Read first

- docs/00-research-scope.md
- PRIOR_ART_SEEDS.md
- PAPER_OUTLINE.md

## Deliverables

- research/search-protocol.md
- research/query-log.csv
- research/inclusion-exclusion.md
- research/prior-art-matrix.csv
- research/novelty-risk.md
- research/go-pivot-stop.md
- references.bib

## Acceptance criteria

- prompt compression、adaptive chunking、hybrid views、code context gates、active retrieval、provenance、dynamic computeを別query familyで調べる
- 各workをinput、feature、operator、routing time、recoverability、domain、metricで比較する
- same-facts/different-texture benchmarkの先行例を明示的に検索する
- cross-domain operator sequence routingの先行例を検索する
- 差分が消えた場合のstopまたはbenchmark-only pivotを明記する
- 原論文以外を主要根拠にしない

## Do not

- 見つからないことを不存在と断定しない
- 比喩の新しさを技術的新規性にしない
- citation countで優先度を決めない

## Verify

- checkerが独立queryを最低5本再実行する
- 上位20件のtitle/abstract screeningを二者で照合する

## Completion record

`docs/hand_over/BITE-01.md` に、変更、検証結果、failure、未解決点、次taskが読むartifactを記録する。
