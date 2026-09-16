# BITE-15 — 事前登録matrixでfull experimentsとablationsを実行する

## Assignment

- Phase: `Gate C`
- Maker: `gpt-5.6-terra / High`
- Checker: `gpt-5.6-sol / High`
- Depends on: `BITE-14`

## Objective

承認済み条件だけでcross-domain、texture-pair、ablation、model-strength experimentsを完了する。

## Read first

- analysis/go-pivot-stop-decision.md
- research/preregistration.md
- research/experiment-matrix.csv
- research/deviation-log.md

## Deliverables

- output/main/raw/
- output/main/manifests/
- output/main/aggregates.parquet
- output/main/failures.jsonl
- analysis/run-completeness.md

## Acceptance criteria

- 全primary conditionを完走または明示failureにする
- texture-pair、real workload、ablationを分けて保存する
- Astra spot-checkは小subsampleとしmain resultへ混ぜない
- model/effort/versionを固定する
- cost/usage limitによるmissing runを記録する
- raw artifact checksumを作る

## Do not

- 結果を見てthresholdを変えない
- 失敗domainを削除しない
- mainとexploratoryを混ぜない

## Verify

- matrix completeness script
- checksum validation
- checkerがrandom sampleを再実行する

## Completion record

`docs/hand_over/BITE-15.md` に、変更、検証結果、failure、未解決点、次taskが読むartifactを記録する。
