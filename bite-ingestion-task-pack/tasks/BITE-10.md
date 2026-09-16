# BITE-10 — transparent operator-sequence policyとoracleを実装する

## Assignment

- Phase: `Gate B`
- Maker: `gpt-5.6-terra / High`
- Checker: `gpt-6-astra / Low`
- Depends on: `BITE-08, BITE-09`

## Objective

morphology profileとbudgetからoperator sequenceを選ぶrule policy、length-only baseline、oracle routeを実装する。

## Read first

- docs/02-formal-model.md
- docs/03-operator-taxonomy.md
- research/metric-contract.json

## Deliverables

- src/bite_ingestion/policies/
- configs/policies/
- tests/test_policy.py
- docs/policy-decision-table.md

## Acceptance criteria

- 決定理由をfeatureとthresholdで説明できる
- length-only policyを別実装する
- oracleはevaluationだけで使用される
- oscillationまたはoperator loopを防ぐ
- budget超過時のfallbackがある
- query conditioningあり／なしを切り替えられる

## Do not

- oracle labelをprofilerへ漏らさない
- 一つのrouteを全caseへhard-codeしない
- accuracyを見ながらthresholdを無記録調整しない

## Verify

- decision-table coverage 100%
- counterexample fixtures
- checkerがlength-matched pairでroute差を確認する

## Completion record

`docs/hand_over/BITE-10.md` に、変更、検証結果、failure、未解決点、次taskが読むartifactを記録する。
