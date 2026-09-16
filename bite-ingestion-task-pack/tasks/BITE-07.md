# BITE-07 — real workload、licence、privacy、dataset adaptersを固定する

## Assignment

- Phase: `Gate B`
- Maker: `gpt-5.6-terra / Medium`
- Checker: `gpt-5.6-sol / High`
- Depends on: `BITE-05, BITE-01`

## Objective

logs、structured data、code、long documentsから再配布可能で評価可能なworkloadを選び、adapter contractを作る。

## Read first

- research/prior-art-matrix.csv
- research/preregistration.md
- docs/01-claim-boundary.md

## Deliverables

- research/dataset-ledger.csv
- research/licence-review.md
- research/privacy-review.md
- src/bite_bench/adapters/
- docs/dataset-cards/

## Acceptance criteria

- 最低3 domain、できれば4 domainを含む
- 各datasetのlicence、download source、version、checksumを記録する
- PIIとsensitive dataの除外規則がある
- ground-truth evidenceまたは再現可能なannotation方法がある
- domain-specific baselineを適用できるdatasetを少なくとも2つ含む
- 再配布不可dataはdownload scriptとIDだけを公開する

## Do not

- private conversationをfixtureにしない
- licence不明dataをbundleしない
- accuracyだけでdatasetを選ばない

## Verify

- checkerがlicence URLとdataset versionを独立確認する
- adapter smoke testsを実行する

## Completion record

`docs/hand_over/BITE-07.md` に、変更、検証結果、failure、未解決点、次taskが読むartifactを記録する。
