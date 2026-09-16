# BITE Codex runbook

## 1. Repository recommendation

既定は新規独立repository `nyattoh/bite-ingestion` です。BITE-00でname collision、licence、既存repo境界を確認してから確定します。TopoDialogue、TopoPhase、TopoLoadへ直接混ぜません。

## 2. 共通prompt前置き

各taskへ次を付けます。

```text
このtaskだけを実行してください。未承認のscopeを追加しないでください。
最初にrepository instructions、git status、read_firstを全て読んでください。
既存のユーザー変更を壊さず、推測・実装済み事実・実験結果を区別してください。
BITEの歯の比喩を、技術的証拠や生物学的必然性として扱わないでください。
router、profiler、re-biteを含む総tokenとoverheadを隠さないでください。
受入条件を満たせない場合は成功に見せかけず、failure artifactを残してください。
完了前にverifyを実行し、pass / fail / not testedを記録してください。
最後に docs/hand_over/<task-id>.md へ、変更、検証、未解決点、次taskが読むartifactを日本語で記録してください。
```

## 3. Gate

### Gate A — idea survival

対象: BITE-00〜04

- 近接研究との差分が残る。
- morphology vectorが測定可能。
- texture-pair benchmarkにtarget leakageがない。
- hypotheses、metrics、budget、kill criteriaが事前固定される。
- 人の承認前にfull implementationへ進まない。

### Gate B — offline system and benchmark

対象: BITE-05〜13

- networkなしでcore testsが通る。
- canonical factsから全textureを再現可能に生成できる。
- source provenanceとversionが保持される。
- baselineは同一target model／effortで動く。
- total token accountingが全callを数える。

### Gate C — evidence

対象: BITE-14〜16

- pilotのgo/pivot/stopを事前基準で判定する。
- full experimentはpilot後にparameterを無記録で変えない。
- negative runs、evidence omissions、re-bite failuresを保存する。
- statistical analysisはeffect size、uncertainty、domain別結果を含む。

### Gate D — paper and release

対象: BITE-17〜19

- abstractにplaceholder数字を残さない。
- claim/evidence matrixが全claimをartifactへ結ぶ。
- independent reproductionがclean environmentで通る。
- demoがpaper fixtureと同じcode pathを使う。

## 4. 実行順

```text
Batch 1: BITE-00
Batch 2: BITE-01 || BITE-02 draft
Batch 3: BITE-02 final -> BITE-03 -> BITE-04
Batch 4: BITE-05 -> BITE-06 || BITE-07
Batch 5: BITE-08 -> BITE-09 -> BITE-10
Batch 6: BITE-11 -> BITE-12 -> BITE-13
Batch 7: BITE-14
Batch 8: BITE-15 -> BITE-16
Batch 9: BITE-17 -> BITE-18 -> BITE-19
```

BITE-01のnovelty reviewで差分が消えたら、以降を止めてpivot memoだけを作ります。

## 5. Required manifests

各runは次を保存します。

- task ID
- git commit
- date/time/timezone
- maker/checker model and effort
- model version if exposed
- target model and effort
- temperature / seed / context limit
- dataset split and checksum
- operator config
- all model-visible input/output token
- deterministic preprocessing time
- re-bite calls
- failure status

## 6. Stop rule

- task verifyがexit 0
- acceptanceが全てpass
- checkerがrejectしていない
- Gate A / C / Dでは人の承認がある

以上を満たした時だけcompleteとします。
