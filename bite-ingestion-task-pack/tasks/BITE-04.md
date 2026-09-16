# BITE-04 — 仮説、benchmark、統計、kill criteriaを事前登録する

## Assignment

- Phase: `Gate A`
- Maker: `gpt-5.6-sol / High`
- Checker: `gpt-6-astra / Low`
- Depends on: `BITE-01, BITE-02, BITE-03`

## Objective

結果を見てから成功条件を変えないよう、primary hypotheses、baselines、metrics、budget、go/pivot/stopを固定する。

## Read first

- research/go-pivot-stop.md
- docs/02-formal-model.md
- docs/03-operator-taxonomy.md
- PAPER_OUTLINE.md

## Deliverables

- research/preregistration.md
- research/metric-contract.json
- research/experiment-matrix.csv
- research/statistical-analysis-plan.md
- research/threat-model.md

## Acceptance criteria

- H1〜H6のprimary/secondaryを分ける
- raw、length-only、fixed chunk、adaptive chunk、universal compressor、domain-specific baselineを含む
- quality tolerance delta、seed、budget、sample size方針を固定する
- total tokenに全model callを含める
- texture-pair splitがcanonical factsを跨いでleakしない
- go/pivot/stopが数値または明確な判定規則になっている

## Do not

- best compression ratioだけをprimaryにしない
- 単一aggregate scoreだけで勝敗を決めない
- energyをproxyだけで主張しない

## Verify

- metric-contractをJSON schemaで検証する
- checkerが仮のpositive/negative結果に判定規則を適用する

## Completion record

`docs/hand_over/BITE-04.md` に、変更、検証結果、failure、未解決点、次taskが読むartifactを記録する。
