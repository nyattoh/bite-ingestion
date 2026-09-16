# BITE-03 — 四operatorとevidence packet contractを設計する

## Assignment

- Phase: `Gate A`
- Maker: `gpt-5.6-sol / High`
- Checker: `gpt-6-astra / Low`
- Depends on: `BITE-02`

## Objective

CUT、UNTANGLE、REDUCE、INTEGRATEのinterface、可逆性、順序、failure contractを固定する。

## Read first

- docs/02-formal-model.md
- docs/morphology-feature-contract.md
- spec/evidence-packet.schema.json

## Deliverables

- docs/03-operator-taxonomy.md
- docs/04-evidence-packet-contract.md
- docs/05-bounded-rebite.md
- spec/operator.schema.json
- spec/rebite-request.schema.json

## Acceptance criteria

- 各operatorのinput/output/invariants/allowed lossを記述する
- source location、version、transformation traceを保持する
- operator compositionの禁止順序とsafe defaultsを定義する
- bounded re-biteの回数、budget、request typeを定義する
- INTEGRATEだけがLLMを必要とするわけではない設計にする
- irreversible summaryを既定にしない

## Do not

- 歯種ごとにmodelを固定しない
- 全domainに同じparserを強制しない
- 無制限retrieval loopを作らない

## Verify

- schema round-trip test計画を作る
- checkerがoperator traceからsourceを再構成できるか検査する

## Completion record

`docs/hand_over/BITE-03.md` に、変更、検証結果、failure、未解決点、次taskが読むartifactを記録する。
