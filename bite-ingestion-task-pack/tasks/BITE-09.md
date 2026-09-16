# BITE-09 — CUT / UNTANGLE / REDUCE / INTEGRATE operator libraryを実装する

## Assignment

- Phase: `Gate B`
- Maker: `gpt-5.6-terra / High`
- Checker: `gpt-5.6-sol / High`
- Depends on: `BITE-05, BITE-06, BITE-07`

## Objective

異種dataへ適用できるoperator interfaceとdomain pluginsを、provenance-preservingに実装する。

## Read first

- docs/03-operator-taxonomy.md
- docs/04-evidence-packet-contract.md
- spec/operator.schema.json

## Deliverables

- src/bite_ingestion/operators/
- tests/operators/
- docs/operator-catalogue.md
- output/operator-fixtures/

## Acceptance criteria

- CUTは自然境界とsource spanを保持する
- UNTANGLEはdependency/anomaly/malformed regionと理由を返す
- REDUCEはdedupe/aggregate/canonicaliseのlossを宣言する
- INTEGRATEはjoin planとused evidence IDsを返す
- 全operatorがtraceとrecovery handleを出す
- 同じinputでdeterministic modeが再現する

## Do not

- silent data lossを許さない
- summaryをsource recordで上書きしない
- operator内で無制限model callをしない

## Verify

- round-trip/recovery tests
- property-based tests
- checkerがirreversible loss ledgerを監査する

## Completion record

`docs/hand_over/BITE-09.md` に、変更、検証結果、failure、未解決点、次taskが読むartifactを記録する。
