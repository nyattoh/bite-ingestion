# BITE-12 — 公平なbaseline adaptersを実装する

## Assignment

- Phase: `Gate B`
- Maker: `gpt-5.6-terra / High`
- Checker: `gpt-5.6-sol / High`
- Depends on: `BITE-05, BITE-06, BITE-07`

## Objective

raw full-context、chunking、compression、domain-specific context engineeringを同一evaluation interfaceへ載せる。

## Read first

- research/prior-art-matrix.csv
- research/preregistration.md
- research/experiment-matrix.csv

## Deliverables

- src/bite_eval/baselines/
- configs/baselines/
- docs/baseline-parity.md
- tests/test_baseline_contract.py

## Acceptance criteria

- 必須baselineを全て同一target model interfaceで動かす
- 外部implementationのversion、licence、configを固定する
- domain-specific baselineを不適用domainへ無理に使わない
- baseline側のrouter/compressor tokenも計上する
- 失敗またはcontext overflowを明示statusで残す
- BITEだけ追加tool permissionを持たない

## Do not

- 弱いbaseline設定を選ばない
- paperのreported numberを自分のrunのように使わない
- baseline failureを除外しない

## Verify

- parity checklist
- small shared fixtureでmanual expected outputと照合する

## Completion record

`docs/hand_over/BITE-12.md` に、変更、検証結果、failure、未解決点、次taskが読むartifactを記録する。
