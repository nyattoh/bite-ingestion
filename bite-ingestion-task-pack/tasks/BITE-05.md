# BITE-05 — offline reproducible repository scaffoldを作る

## Assignment

- Phase: `Gate B`
- Maker: `gpt-5.6-terra / Medium`
- Checker: `gpt-5.6-luna / Medium`
- Depends on: `BITE-04`

## Objective

provider-independentなcore、schema、tests、artifact layoutを持つ最小repositoryを作る。

## Read first

- docs/00-research-scope.md
- docs/02-formal-model.md
- research/metric-contract.json
- CODEX_RUNBOOK.md

## Deliverables

- pyproject.toml
- src/bite_ingestion/
- tests/
- configs/default.toml
- scripts/gate.sh
- README.md
- AGENTS.md

## Acceptance criteria

- Python 3.11+でinstallできる
- profiler、operator、policy、target model、token meterがinterfaceで分離される
- core testはnetworkと有料APIを使わない
- artifact、seed、config、checksumを中央管理する
- gate.shがlint/typecheck/test/schema validationを実行する
- source unitとevidence packetのschema testsがある

## Do not

- UIを作らない
- cloud databaseを必須にしない
- 未承認のlearned modelを追加しない

## Verify

- ./scripts/gate.sh
- clean virtual environmentでinstall/testする

## Completion record

`docs/hand_over/BITE-05.md` に、変更、検証結果、failure、未解決点、次taskが読むartifactを記録する。
