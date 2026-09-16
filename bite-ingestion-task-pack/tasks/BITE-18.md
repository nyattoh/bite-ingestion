# BITE-18 — 独立再現、claim audit、adversarial reviewer simulationを行う

## Assignment

- Phase: `Gate D`
- Maker: `gpt-6-astra / Medium`
- Checker: `gpt-5.6-sol / High`
- Depends on: `BITE-17`

## Objective

clean環境で再現し、近接研究・統計・claim・benchmark leakageへの最も強い反論を作って解消する。

## Read first

- paper/bite-before-you-think.md
- research/prior-art-matrix.csv
- research/preregistration.md
- analysis/claim-evidence-draft.csv

## Deliverables

- review/independent-reproduction.md
- review/claim-audit.csv
- review/reviewer-1.md
- review/reviewer-2.md
- review/rebuttal-plan.md
- review/release-decision.md

## Acceptance criteria

- clean checkoutから主要table/figureを再生成する
- HYVE、ContextSniper、Adaptive Chunkingとの差分を最強形で反論する
- texture-pair leakageを独立検査する
- 全claimをsupported/overstated/unsupportedで分類する
- unsupported claimをpaperから削る
- reject相当のreviewも保存する

## Do not

- makerの要約だけを読む
- reviewを優しくする
- unsupported claimをfuture workで誤魔化さない

## Verify

- checkerがaudit修正後のpaper diffを確認する
- release-decisionに明示的pass/failを出す

## Completion record

`docs/hand_over/BITE-18.md` に、変更、検証結果、failure、未解決点、次taskが読むartifactを記録する。
