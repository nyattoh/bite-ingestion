# BITE-14 — pilotを実行し、Go / Pivot / Stopを判定する

## Assignment

- Phase: `Gate C`
- Maker: `gpt-5.6-sol / High`
- Checker: `gpt-6-astra / Low`
- Depends on: `BITE-06, BITE-08, BITE-09, BITE-10, BITE-11, BITE-12, BITE-13`

## Objective

小規模pre-registered pilotでsystem feasibility、texture signal、overhead、failure modeを確認し、full experimentの続行を判定する。

## Read first

- research/preregistration.md
- research/go-pivot-stop.md
- docs/token-accounting.md

## Deliverables

- output/pilot/raw/
- output/pilot/summary.json
- analysis/pilot-report.md
- analysis/go-pivot-stop-decision.md
- research/deviation-log.md

## Acceptance criteria

- 最低3 texture familyと2 target model profileを含む
- qualityとtotal tokenの両方を報告する
- operator selection confusion matrixを出す
- evidence omission、re-bite、overheadを個別に分析する
- 事前規則でgo/pivot/stopを判定する
- parameter変更が必要ならfull run前にdeviationとして固定する

## Do not

- pilotをmain resultとしてpublishしない
- 良いseedだけを選ばない
- stop条件を無視して続けない

## Verify

- checkerがraw artifactsから主要表を再計算する
- decisionとpreregistrationの整合を確認する

## Completion record

`docs/hand_over/BITE-14.md` に、変更、検証結果、failure、未解決点、次taskが読むartifactを記録する。
