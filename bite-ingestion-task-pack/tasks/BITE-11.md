# BITE-11 — bounded re-biteとsource recoveryを実装する

## Assignment

- Phase: `Gate B`
- Maker: `gpt-5.6-terra / High`
- Checker: `gpt-5.6-sol / High`
- Depends on: `BITE-09, BITE-10`

## Objective

evidence不足時に元data全体を再送せず、schema化した追加要求で必要箇所だけを復元する。

## Read first

- docs/05-bounded-rebite.md
- spec/rebite-request.schema.json
- docs/04-evidence-packet-contract.md

## Deliverables

- src/bite_ingestion/recovery/
- tests/test_rebite.py
- docs/recovery-security.md
- output/rebite-fixtures/

## Acceptance criteria

- max calls、token ceiling、allowed query typesを強制する
- source access controlとversion freshnessを再確認する
- requestとreturned evidence IDsを監査ログへ残す
- 同じevidenceの反復要求を抑止する
- missing evidenceとmodel indecisionを区別する
- re-bite tokenをtotalへ加算する

## Do not

- 任意shellやSQLを無制限許可しない
- withdrawn/forbidden sourceを復元しない
- loopをsuccess扱いしない

## Verify

- budget exhaustion tests
- stale-version tests
- prompt-injection fixtures
- checkerがrecovery bypassを試す

## Completion record

`docs/hand_over/BITE-11.md` に、変更、検証結果、failure、未解決点、次taskが読むartifactを記録する。
