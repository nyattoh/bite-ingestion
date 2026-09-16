# BITE ingestion リポジトリ評価

**結論：研究の骨格と監査姿勢はかなり強い。ただし、現行の有料 pilot は BITE の中心仮説をまだ検証していない。次に行うべきことは追加課金ではなく、評価器の意味契約を直して、本物の morphology-aware arm と length-only arm を接続すること。**

- 対象リポジトリ: [`nyattoh/bite-ingestion`](https://github.com/nyattoh/bite-ingestion)
- 評価基準時刻: **2026-09-17 06:33 JST**
- 主に確認した `main`: [`6b7b574ba5c7855e7eaf672df02628c3c3720ade`](https://github.com/nyattoh/bite-ingestion/commit/6b7b574ba5c7855e7eaf672df02628c3c3720ade)
- 追加確認: draft PR [#8 C2 length-only arm 設計メモ](https://github.com/nyattoh/bite-ingestion/pull/8)
- 確認範囲: 研究文書、実装構造、pilot runner、生成データ、集計結果、failure analysis、公開準備状態
- 未実施: 私の環境での clone、テスト実行、Z.ai API の再実行。以下は GitHub 上のコード・文書・保存 artifact の静的評価である

---

## Executive Summary

### 1. `pivot` 判定は正しい

384回の provider-billed pilot を完走し、都合の悪い結果も隠さず、`Go` にしなかった判断は非常に良い。現行結果は次の通り。

| 指標 | 現行 v2 pilot |
|---|---:|
| 対象行 | 384 |
| paired instances | 192 |
| provider usage を取得できた行 | 384 / 384 |
| empty answer | 0 / 384 |
| constraints_ok | 338 / 384 = 0.880208 |
| 総 `T_total` | 40,626 |
| 平均 `T_raw - T_comp` | **-2** |
| compressed が raw より低tokenだった割合 | **0.0** |
| 判定 | **pivot** |

参照: [`analysis/main-results.md`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/analysis/main-results.md)、[`analysis/bite15b_pilot_recompute_v2.json`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/analysis/bite15b_pilot_recompute_v2.json)

### 2. ただし、これは「BITEがtokenを減らせなかった」結果ではない

有料 pilot の比較条件は、実装上、次の2つだけである。

- `raw_full`
- `compressed_passthrough`

後者は **documentの先頭400文字を残す単純切詰め**であり、CUT / UNTANGLE / REDUCE / INTEGRATE、morphology profiler、`rule_pi`、re-bite は使われていない。

さらに、pilot の8 familyを生成する document は、コードから再計算すると全て400文字以下である。

| family | document文字数の目安 |
|---|---:|
| clean_local | 91 |
| repeated_records | 278 |
| sparse_anomaly | 397 |
| dependency_chain | 65 |
| malformed_mixed | 77 |
| dense_cross_reference | 57 |
| adversarial_omission | 339 |
| texture_swap | 22–42 |

したがって **`compressed_passthrough` は実質的に一件も圧縮していない**。raw prompt の `Document:` が compressed arm では `Compressed document:` になるため、全paired caseで compressedが2 token多いという結果は、prompt wrapperの差と強く整合する。

参照: [`src/bite_eval/pilot/billed_runner.py`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/src/bite_eval/pilot/billed_runner.py)、[`src/bite_eval/pilot/families.py`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/src/bite_eval/pilot/families.py)

### 3. 現行評価器には、論文上の重大な意味ずれが2つある

1. **`Q_baseline` が実際の raw model出力ではなく、gold answerを評価して作られている。** そのため常に完全正答の `1.0` が基準になる。事前文書の「同一model・同一taskにおける raw full context 条件」と一致していない。
2. **visible evidence recall が、実際にtarget modelへ提示したdocumentから計算されていない。** `raw_full` と `compressed_passthrough` の両方で、packetに事前記入された同一 `visible_evidence` IDが使われる。今後本当に削除・圧縮した場合でも、その証拠がpromptから消えたことをrecallが検出できない可能性がある。

この2点は、追加pilotの前に修正すべき **P0 blocker** である。

### 4. 現段階で一番強い論文候補は「architecture勝利」ではなく benchmark / evaluation 論文

近接研究には、machine dataをhybrid viewへ変換して必要部分だけ提示するHYVE、code evidenceをcompact packet化してrecoverable contextを残すContextSniper、multi-hop QAで反復的に証拠を圧縮するIterCOMPなどが既にある。

BITEの差分候補は、単なる「前処理で短くする」ではない。最も強いのは次の組合せである。

- **同じ意味・同じ答えを保ったまま、表面形状だけを変える counterfactual texture pair**
- **length-only と morphology-aware を長さmatchedで直接比較**
- **visible evidence と recoverable evidenceを分離**
- **router・compressor・recovery・target outputまで含めた full-cost accounting**
- **勝ったcaseだけでなく、どのtextureで壊れるかをfailure atlasとして公開**

仮題としては、現状なら次が最も誠実かつ注目を集めやすい。

> **Length Is Not Texture: A Morphology-Controlled Benchmark for LLM Context Ingestion**

---

## 総合評価

| 軸 | 評価 | 所見 |
|---|---:|---|
| 研究問い・見せ方 | **4.0 / 5** | 「長さではなく食感／形態で処理を変える」は直観的で、benchmark化できれば強い |
| 研究規律・監査可能性 | **4.5 / 5** | prereg風threshold lock、negative result保存、artifact分離、post-hoc Go禁止が優秀 |
| 実装の広がり | **4.0 / 5** | operator、policy、recovery、baseline、provider、artifact layerまで既にある |
| 中心仮説を検証できている度合い | **1.0 / 5** | billed pilotが実際のBITE pipelineを通しておらず、comparisonもno-opに近い |
| 現時点の再現性 | **3.0 / 5** | script・artifact・checksumはあるが、CIなし、checkpoint欠落、release metadata未整備 |
| 論文投稿準備度 | **1.5 / 5** | 面白い研究装置はあるが、claimを支えるmain experimentは未実施 |

**現在地を一文で言うと:**

> かなり良い研究prototypeと評価基盤が出来ている。しかし、今ある有料結果は「評価配管が動いた」ことを示すpilotであり、「morphology-aware ingestionが効いた／効かなかった」を示す実験ではない。

---

## 良いところ

### 1. 負の結果をGoへ変換しなかった

v1では354/384件がempty answerとなり、thinkingがcompletion budgetを食った可能性をconfounderとして記録した。その後、thinkingを無効化してv2を実施し、empty answerを0/384にしたうえで、なお `pivot` とした。

さらに、`dependency_chain` の0.0417をprompt/gold format mismatchと特定し、48-callのPath B sliceで1.0へ改善しても、**full 384-call pilotを置き換えず、Goへ昇格させていない**。

これは論文の信頼性に直結する強みである。

参照:

- [`analysis/error-atlas.md`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/analysis/error-atlas.md)
- [`docs/hand_over/BITE-16.md`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/docs/hand_over/BITE-16.md)

### 2. 「何を捨てたか」を追跡する設計がある

Evidence Packetを、

- `E`: target modelへ見せるvisible evidence
- `R`: 省略・隔離したsourceへのrecovery index
- `τ`: operator trace
- provenance / version / freshness

へ分けた設計はよい。単純要約ではなく、消えた情報を後から取り戻せるcontractになっている。

参照:

- [`docs/04-evidence-packet-contract.md`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/docs/04-evidence-packet-contract.md)
- [`docs/05-bounded-rebite.md`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/docs/05-bounded-rebite.md)

### 3. operatorを具体的な不変条件へ落としている

CUT / UNTANGLE / REDUCE / INTEGRATEは、歯の比喩だけではなく、source span、quarantine、omit map、recovery key、deterministic joinなどの実装制約へ落ちている。

特に、

- UNTANGLEは削除ではなく `R` への隔離
- REDUCEで省略したunitはrecovery可能にする
- free-text summaryをprimary pathにしない
- INTEGRATE outputへprovenanceを残す

という設計は、単純なprompt compressionとの差分になり得る。

参照: [`docs/03-operator-taxonomy.md`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/docs/03-operator-taxonomy.md)

### 4. full-cost accountingを最初から意識している

provider-billed usageをprimary token countとして記録し、char/4 proxyと混ぜない実装は良い。checkpoint、resume、rate-limit stop、partial artifact、API key非表示も、実験運用として堅実である。

参照:

- [`scripts/run_billed_pilot.py`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/scripts/run_billed_pilot.py)
- [`src/bite_eval/pilot/billed_runner.py`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/src/bite_eval/pilot/billed_runner.py)

### 5. 事前に止まる条件を作っている

`delta=0.05`、visible / recoverable recall、provenance、`J=3`、recovery budget、pilot size、Holm予定などを実験前にロックした姿勢はよい。数字の妥当性は今後sensitivity analysisが必要だが、結果を見てから都合よく線を引いていない点は高く評価できる。

参照: [`docs/d2-threshold-lock-2026-09-16.md`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/docs/d2-threshold-lock-2026-09-16.md)

---

## 重大な問題と修正方針

### P0-1. billed pilotのcompressed armが一件も圧縮していない

現行コードは、documentが400文字を超えた場合だけ先頭400文字へ切り詰める。

```python
compressed = doc if len(doc) <= 400 else (doc[:400] + "\n...[truncated]")
```

しかし生成される8 familyの最大documentは `sparse_anomaly` の397文字である。従って全caseでpayloadはrawと同一になる。

その結果、比較しているのはほぼ次だけである。

```text
Document:
```

対

```text
Compressed document:
```

#### 影響

- `mean(T_raw - T_comp) = -2`
- compressedがtokenを減らしたcase = 0

という結果を、compressionやBITEの失敗とは解釈できない。

#### 修正

- pilot生成時に、各documentが本当に変換されたかを `assert transformed_payload != raw_payload` で検査する
- `payload_chars_before/after`、`payload_tokens_before/after`、`wrapper_tokens`を別々に保存する
- rawとcandidateで同一prompt templateを使い、method名はAPIへ送らないmetadataに置く
- no-op transformationは `status=no_op` とし、C1/C3の主解析対象から分ける

---

### P0-2. `Q_baseline` が実際のraw model performanceではない

threshold lockでは、`Q_baseline` は同一task・同一target model・同一effortのraw full context条件とされている。

ところが実装は、gold answerをそのまま評価してbaselineを作っている。

```python
gold = str(packet.get("gold_answer", ""))
m_base = metrics_from_instance(packet, vis, answer=gold)
Q_baseline = float(m_base["quality"])
```

exact matchなので、goldをgoldと比較すれば `Q_baseline=1.0` になる。

#### 影響

現行constraintは、

> candidateの品質が、実際のraw model結果から5pp以内か

ではなく、

> candidateの答えがほぼ完全正答か

を判定している。これは非劣性比較の定義と異なる。

#### 修正

1. 同じ `instance_id × model × effort × seed` のraw callを先に記録する
2. `Q_baseline = raw_result.Q` とする
3. candidate / length-only / other baselinesを同じraw rowへpaired joinする
4. raw callが失敗・timeoutなら、そのpairを「欠測」として明示し、gold=1.0で代替しない
5. gold accuracy自体は `Q_oracle_reference` など別名で保持する

---

### P0-3. visible evidence recallが、実際に見せたpromptを測っていない

`_visible_for_method()` はmethodによらず、packetへあらかじめ入った `visible_evidence` IDを返す。

一方、target modelへ送るdocumentは `_build_messages()` 内で別に加工される。documentを切り詰めても、どのevidence IDが切れたかが更新されない。

#### 影響

将来、重要な証拠を圧縮で落としても、packetのIDが残っていれば `Recall_vis` が高いままになる可能性がある。

#### 修正

transformation outputを一つの型へ統一する。

```text
TransformedPacket
  payload_text
  visible_unit_ids
  recovery_index
  provenance
  operator_trace
  loss_ledger
  accounting
```

target prompt、visible recall、recoverable recall、provenance scoreは、**すべて同じTransformedPacketから算出**する。

---

### P0-4. C2は `true` ではなく `not_evaluated` と記録すべき

現行 `analysis/hypothesis-tests.json` は、C2を `true` としつつ、「placeholderでありlength-only比較ではない」と注意書きしている。

この形式は危険である。後にtableやabstractへ自動抽出されたとき、caveatだけ落ちて `C2=true` が独り歩きし得る。

#### 修正

```json
{
  "C2_morphology_beats_length_only": null,
  "C2_status": "not_evaluated",
  "reason": "length-only arm not connected to billed pilot"
}
```

にする。

PR #8の設計方向は正しいが、設計だけでまだ実装されていない。加えて、単なるlength bin比較では不十分で、**同じ意味内容を保ち、入力長を揃え、textureだけを変えたmatched pair**が必要である。

参照: [PR #8](https://github.com/nyattoh/bite-ingestion/pull/8)

---

### P0-5. actual BITE candidateを有料pilotへ接続していない

repositoryには、

- `rule_pi`
- `length_pi`
- `universal_reduce`
- `rule_pi_rebite`
- CUT / UNTANGLE / REDUCE / INTEGRATE

などが既にある。offline smoke matrixにも登録されている。

しかし billed pilotは `raw_full` と `compressed_passthrough` の2条件のみである。従って、今のpaid resultはactual candidateの性能を含んでいない。

#### 修正

次のpaid pilotへ進む前に、offlineで少なくとも次の行が同一interfaceから出ることを確認する。

| arm | 必須 |
|---|---|
| raw_full | yes |
| length_pi | yes |
| rule_pi | yes |
| rule_pi_rebite | yes |
| fixed_chunk_topk | yes |
| universal_reduce | yes |
| oracle_pi | diagnostic only |

各armが本当に異なる `payload_text / visible_unit_ids / R / τ` を生成したことをartifactへ保存する。

---

### P0-6. `dependency_chain` 修正は妥当だが、主結果を置き換えてはいけない

v2 full pilotの46 failureの大半は、goldが `100` なのにmodelが `K00=100` と返したexact-match mismatchである。Path Bでは質問を「数字だけ」と明示して48/48へ改善した。

これはtask specification修正として妥当。しかし、修正後のPath Bだけを元の384-call primary resultと混ぜてはいけない。現在の文書はこの分離を守っており、そこは正しい。

次にfull rerunする場合は、新しいbenchmark versionとして、例えば `BITEBench-pilot-v0.2` のように別manifestへ固定する。

---

## 評価設計上の次の課題

### 1. baseline名と実装忠実度を分ける

`hyve_like`、`contextsniper_like`、`adaptive_chunk_like`、`query_aware_compress_like` は、文書上も本物の再実装ではなくoffline stubである。

stubを比較用heuristicとして置くのは問題ない。ただし、論文で「HYVEやContextSniperを上回った」とは書けない。

#### 推奨する分類

- **Reference heuristics**: 現在の `-like` stubs
- **Reproduced baselines**: 公式code / paper条件を再現したもの
- **Native BITE arms**: `length_pi`, `rule_pi`, `rule_pi_rebite`
- **Oracle diagnostics**: `oracle_pi`

### 2. BITEBenchをmaterialiseする

現在は8 familyをprocedural generatorで生成している。これは開発に便利だが、査読用benchmarkとしては次が必要である。

- 全instanceをJSONL等でmaterialise
- generator commit、seed、schema version、checksumを保存
- source factsとrendered textureを分離
- same-facts / same-answerを検査するvalidator
- length-matched counterfactual pair ID
- evidence span / unit IDを実text位置へ対応付け
- train / calibration / pilot / held-out testを分離
- generatorを修正したらbenchmark versionを上げる

### 3. synthetic short QAだけではtoken効率を判定しにくい

現行documentは22〜397文字で、long-context problemになっていない。BITEの価値は、反復・入れ子・cross-reference・壊れた構造が大きくなったときに出るはずである。

必要なのは、例えば次のscale sweepである。

```text
0.5k / 2k / 8k / 32k / 100k tokens
```

ただし、いきなり全条件へ課金するのではなく、offline rendererとtokeniserで事前にpayload差を確認してからsmall pilotへ進む。

### 4. 統計はactual contrastが出来てから

現時点でCIやHolmが未計算なのは問題ではない。actual morphology-vs-length contrastがまだないため、先に統計を足しても意味が薄い。

actual pairが出来た後は、

- paired token differenceのbootstrap CI
- paired accuracyのMcNemarまたはexact test
- family別effectと全体effectを分離
- model / effort / scaleとのinteraction
- recovery回数とnet savingのbreak-even
- no-op / overflow / abstentionを欠測から分離

を報告する。

---

## 外部研究との位置関係

BITEの方向は面白いが、近接領域は2026年時点でかなり混み合っている。

| 近接研究 | BITEと近い点 | BITEが差分にすべき点 |
|---|---|---|
| [HYVE](https://arxiv.org/abs/2604.05400) | machine dataをschema-aware hybrid viewへ変換し、datastoreから省略情報を回収 | prose / JSON / log / codeを跨ぐcounterfactual texture benchmark、length-only isolation |
| [ContextSniper](https://arxiv.org/abs/2607.01916) | compact evidence packet、recoverable source context、code task | code専用ではない統一morphology policyとoperator trace |
| [IterCOMP](https://arxiv.org/abs/2608.13588) | multi-hop evidenceを反復的に追加・圧縮 | ingestion時に作ったbounded `R`だけから回復するcontract、full-cost ledger |
| [LongLLMLingua](https://arxiv.org/abs/2310.06839) | query-aware long-prompt compression | token importanceではなく、data morphologyに応じたoperator selection |
| [LLMLingua-2](https://arxiv.org/abs/2403.12968) | faithful task-agnostic prompt compression | surface texture interventionとrecoverabilityの評価 |
| [Cache-Aware Prompt Compression](https://arxiv.org/abs/2607.15516) | compression overheadとcache economicsを含むcost model | cacheを含むfull-cost accountingをBITEにも導入する必要性 |
| [Lost in the Middle](https://arxiv.org/abs/2307.03172) | context位置による性能劣化 | same factを異なるtexture・位置へ置くstress testの根拠 |

### 新規性の安全な置き場所

現状、最も安全なのは次の主張である。

> BITEBench is a morphology-controlled evaluation framework that holds task semantics and answer identity constant while varying representation texture, and measures whether morphology-aware ingestion adds value beyond length-only routing under matched-quality, full-cost accounting.

まだ安全でない主張は次。

- BITEは一般にtokenを減らす
- BITEはHYVE / ContextSniper / prompt compressionより優れる
- 歯の役割分担が最適なoperator taxonomyである
- recovery付きarchitectureがproductionで省電力になる

---

## 次にやる順番

### Phase 0 — 追加課金なしで評価器を直す

#### EVAL-01: paired baseline契約の修正

- `Q_baseline` をactual `raw_full` responseから取得
- raw/candidate rowをpair IDでjoin
- missing pair、timeout、rate limitを明示
- gold referenceとraw baselineを別fieldにする

#### EVAL-02: promptとevidence IDを一体化

- transformation resultを `TransformedPacket` へ統一
- prompt bodyとvisible IDsを同じobjectから生成
- truncation / dedupe / quarantineで消えたunitを `R` へ移す
- recallとprovenanceをtransformed packetから再計算

#### EVAL-03: C2を `not_evaluated` に変更

- `hypothesis-tests.json`、summary、handoverを修正
- `true + caveat` を廃止

#### EVAL-04: prompt parity test

- rawと各armでwrapperを同一化
- empty payloadを使った固定overhead test
- payload tokenとtotal tokenを別計測
- no-opを検出

#### EVAL-05: CIを追加

- GitHub Actionsで `ruff`, `mypy`, `pytest`, schema/artifact validation
- `main` protectionは公開前に設定

### Phase 1 — 本当の中心仮説をofflineで試す

1. PR #8のlength-only armを実装
2. actual `rule_pi` pipelineをbilled runnerと同一harnessへ接続
3. same-facts / same-answer / length-matched texture pairsをmaterialise
4. `raw_full / length_pi / rule_pi / rule_pi_rebite` のoffline matrixを生成
5. 各armのpayloadが本当に違うことを機械検査
6. 期待方向がない場合はpaid pilotへ進まない

### Phase 2 — small paid pilot

最初は小さく、次の順で進める。

1. 2 family × 3 instance × 4 arms のsmoke
2. output / usage / pair join / recovery ledgerを人手確認
3. 問題がなければ `N_pilot=24/family`
4. 一つ目のmodelで評価契約を固定した後、別model・effortへ拡張

### Phase 3 — 論文化条件

少なくとも以下が揃ってから、architecture superiorityを検討する。

- morphology-aware armがlength-only armを、長さmatched条件で上回る
- quality constraintをactual raw baselineに対して満たす
- router / operator / recovery / outputを含めてもnet token savingが正
- 一つのfamilyだけではなく、事前指定した複数textureで再現
- real workloadまたは現実的なlong-context proxyで再現
- failure atlasとnegative familiesを同じ粒度で報告

満たさない場合でも、BITEBench / evaluation paperとして価値は残る。

---

## Repository運用上の改善

### READMEを現在地へ更新する

READMEはまだ「Gate B scaffold」「Next: BITE-06」となっているが、実際にはGate C billed pilotとanalysisまで進んでいる。初見の読者には大きな混乱になる。

最低限、READMEの先頭に次を置く。

- current stance: Pivot-to-bench
- current authoritative result: v2 pilot = pivot
- current central limitation: BITE candidate未評価
- quick start: offline gate / smoke / artifact validation
- repository map: `bite_ingestion` vs `bite_eval`
- claim boundary

### release metadataを整える

現在 `pyproject.toml` は、

- version `0.0.0`
- licence `TBD`
- author `TBD`

である。公開前には少なくとも次が必要。

- LICENSE
- author / ORCID
- `CITATION.cff`
- semantic version
- reproducibility environment lock
- release tag
- dataset licence cards

### rootを整理する

- `_fix_bite12.py` は一時scriptに見えるため、削除または `scripts/migrations/` へ移す
- task-pack ZIPと展開済みtask packは、研究codeと分離し、release assetまたは `docs/archive/` へ移す
- 大きなpilot JSONをGitで維持する方針を決める。Git LFS、release asset、Zenodo artifactなどを検討

### CIとbranch protection

現在のmain commitにはGitHub status checkが付いていない。local gate scriptがあっても、第三者には毎commit通っているか分からない。

公開前には、

- test / lint / typecheck / schema validation
- artifact checksum validation
- secret scan
- no paid API in CI

を必須checkにする。

---

## 論文としての見せ方

### 推奨ストーリー

#### Figure 1

同じfactsを、prose / table / JSON / log / codeへrenderする。長さが同じでも、最適な処理routeが違うことを一枚で見せる。

#### Figure 2

```text
Raw source
   ↓ morphology profiler
CUT / UNTANGLE / REDUCE / INTEGRATE
   ↓
Evidence Packet (E, R, τ)
   ↓
Target model
   ↘ bounded re-bite
```

#### Figure 3

x軸 `T_total`、y軸 quality、点の形をtexture family、色をarmとしたPareto plot。raw、length-only、morphology-aware、oracleを並べる。

#### Figure 4

failure atlas。どのtextureで、

- evidence omission
- over-quarantine
- under-reduction
- dependency break
- recovery overhead

が起きたかを示す。

### タイトル候補

1. **Length Is Not Texture: A Morphology-Controlled Benchmark for LLM Context Ingestion**
2. **BITEBench: Testing Structure-Aware Ingestion Beyond Length-Only Prompt Compression**
3. **What Should an LLM Bite First? Full-Cost Evaluation of Morphology-Aware Context Ingestion**
4. 負の結果が中心になる場合: **Why Truncation Is Not Ingestion: A Failure-Aware Benchmark for LLM Context Preparation**

歯の比喩は記憶に残る。ただし、本文の新規性は「歯に例えたこと」ではなく、**textureを操作変数として固定し、length-onlyとの差を反証可能にしたこと**へ置く。

---

## 最終判定

このrepositoryは、失敗しているわけではない。むしろ、短期間でここまで実装しながら、誤った `Go` を出さなかった点が強い。

ただし、現行pilotをそのまま論文結果へ使うと、査読者には次のように指摘される可能性が高い。

> “Your billed experiment does not evaluate the proposed morphology-aware ingestion system. The compressed arm is effectively a no-op on the supplied synthetic inputs, the quality baseline is an oracle gold answer rather than the raw model condition, and evidence recall is not derived from what the model actually received.”

これは直せる。しかも、architectureを作り直す必要はない。主に **evaluation glueとdata contractの修正**である。

したがって、次の判断はこうなる。

- **研究継続:** Yes
- **追加の有料full rerun:** まだNo
- **最優先:** evaluator semanticsの修正とactual BITE armsの接続
- **論文方針:** Pivot-to-benchを維持
- **最も有望な貢献:** morphology-controlled benchmark + evidence recoverability + full-cost accounting

---

## Evidence map

| 論点 | 主なrepo資料 |
|---|---|
| Current stance / README | [`README.md`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/README.md) |
| Authoritative pilot | [`analysis/main-results.md`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/analysis/main-results.md) |
| Recomputed metrics | [`analysis/bite15b_pilot_recompute_v2.json`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/analysis/bite15b_pilot_recompute_v2.json) |
| Failure analysis | [`analysis/error-atlas.md`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/analysis/error-atlas.md) |
| Hypothesis status | [`analysis/hypothesis-tests.json`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/analysis/hypothesis-tests.json) |
| Paid runner | [`src/bite_eval/pilot/billed_runner.py`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/src/bite_eval/pilot/billed_runner.py) |
| Synthetic families | [`src/bite_eval/pilot/families.py`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/src/bite_eval/pilot/families.py) |
| Constraints | [`src/bite_eval/pilot/constraints.py`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/src/bite_eval/pilot/constraints.py) |
| Operator design | [`docs/03-operator-taxonomy.md`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/docs/03-operator-taxonomy.md) |
| Evidence contract | [`docs/04-evidence-packet-contract.md`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/docs/04-evidence-packet-contract.md) |
| Recovery contract | [`docs/05-bounded-rebite.md`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/docs/05-bounded-rebite.md) |
| Baseline parity | [`docs/baseline-parity.md`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/docs/baseline-parity.md) |
| Threshold lock | [`docs/d2-threshold-lock-2026-09-16.md`](https://github.com/nyattoh/bite-ingestion/blob/6b7b574ba5c7855e7eaf672df02628c3c3720ade/docs/d2-threshold-lock-2026-09-16.md) |
| Latest length-only design | [PR #8](https://github.com/nyattoh/bite-ingestion/pull/8) |

