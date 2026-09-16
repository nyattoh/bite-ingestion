# BITE-19 — demo、artifact、publication packageを仕上げる

## Assignment

- Phase: `Gate D`
- Maker: `gpt-5.6-terra / Medium`
- Checker: `gpt-5.6-sol / High`
- Depends on: `BITE-18`

## Objective

paperと同じcode pathで動くdemo、reproducibility bundle、説明素材、venue fit memoを作る。

## Read first

- review/release-decision.md
- paper/bite-before-you-think.md
- EXCITEMENT_STRATEGY.md

## Deliverables

- demo/
- release/README.md
- release/artifact-manifest.json
- release/reproduction.md
- release/90-second-script.md
- release/general-audience-ja.md
- release/general-audience-en-GB.md
- release/venue-fit.md

## Acceptance criteria

- demoがpaper fixtureと同じprofiler/operatorを使う
- raw vs BITEのtoken/evidence/operator traceを表示する
- offline sampleで動く
- artifactにlicenceとchecksumがある
- 一般解説が結果以上のことを言わない
- 英語版はBritish Englishで統一する

## Do not

- demo専用の成功caseを作らない
- unreviewed dataを公開しない
- 採択前提のpress copyを書かない

## Verify

- fresh machine reproduction
- demo smoke test
- checkerがpaperの数字とrelease pageを照合する

## Completion record

`docs/hand_over/BITE-19.md` に、変更、検証結果、failure、未解決点、次taskが読むartifactを記録する。
