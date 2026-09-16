# BITE-17 — 結果拘束型の論文、hero figure、abstractを作る

## Assignment

- Phase: `Gate D`
- Maker: `gpt-5.6-sol / High`
- Checker: `gpt-6-astra / Medium`
- Depends on: `BITE-16`

## Objective

memorableなframingを保ちつつ、全claimをartifactに拘束したpaper draftとfigure setを作る。

## Read first

- PAPER_OUTLINE.md
- EXCITEMENT_STRATEGY.md
- analysis/main-results.md
- analysis/error-atlas.md
- analysis/claim-evidence-draft.csv

## Deliverables

- paper/bite-before-you-think.md
- paper/abstract-variants.md
- paper/title-test.md
- figures/hero/
- figures/results/
- paper/limitations.md
- paper/references.bib

## Acceptance criteria

- abstractの全数字がartifactへ追跡できる
- hero figureだけでsame facts/different textureが伝わる
- close workを正面から比較する
- 歯の比喩とformal methodを混同しない
- negative resultsとfailure galleryを含む
- energy、biology、general superiorityを過大主張しない

## Do not

- placeholder数字を残さない
- best-caseだけをtitleに入れない
- attentionをscientific claimにしない

## Verify

- checkerがclaim-evidence traceを全件確認する
- title/abstract/figure blind testを3名以上で実施する

## Completion record

`docs/hand_over/BITE-17.md` に、変更、検証結果、failure、未解決点、次taskが読むartifactを記録する。
