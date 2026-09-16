# Codex model × effort policy for BITE

作成日時: 2026-09-13 22:48:37 JST

## 1. 二種類の model × effort を分ける

この計画では次を混同しません。

1. **BITEを作るCodexのmodel × effort** — 調査、設計、実装、査読の担当。
2. **BITEを評価するtarget model × effort** — 論文実験の独立変数。

CodexでAstraを使ったこと自体を研究結果にはしません。

## 2. Codex作業profile

2026-09-13時点のOpenAI公式案内では、GPT-6 Astraはcoding、research、analysis、complex problem-solving向けの最上位、Solは能力と効率の強い均衡、Terraは日常実装、Lunaは反復的なfocused task向けです。reasoning levelはmodel choiceと独立で、Astra LowがSol Highを上回る場合もあるため、単純にeffortを最大化しません。

| Profile | 役割 | BITEでの利用 |
|---|---|---|
| Astra / Low | 高レバレッジの批判、研究境界、設計review | scope、preregistration、pilot判定、最終abstract |
| Astra / Medium | 新規性統合、形式モデル、claim audit、reviewer simulation | Gate AとGate Dに限定 |
| Astra / High | 通常は使わない | Mediumで解けない形式矛盾が残る場合のみ人の承認後 |
| Sol / High | architecture、実験設計、統計解釈、paper draft | 研究実務の主力 |
| Sol / Medium | 限定された設計・文書化 | subtaskへ分割できる場合 |
| Terra / High | 複数module実装、benchmark、integration、実験harness | 実装の主力 |
| Terra / Medium | scaffold、adapter、dataset preparation、release automation | 明確なacceptance criteriaのtask |
| Luna / Medium | fixture生成、index、schema check、formatting | 仕様判断を伴わない作業 |
| Luna / Low | 小修正、整形、一覧生成 | claimや数理には使わない |

## 3. 使い分け原則

- Astraは「失敗すると後工程全体を無駄にする判断」に集中させる。
- Astra Highへ上げる前に、入力不足、権限不足、task分割不足を確認する。
- 実装はTerra、研究判断はSol、研究全体の反証と最終監査はAstraを基本とする。
- makerとcheckerはmodelまたはeffortを変える。
- 同じmodelに発案と最終査読を閉じない。
- Fast modeは速度優先の明示的なrunだけにし、research gateでは既定OFFとする。

## 4. BITE task別の主担当

| Task group | Maker | Checker |
|---|---|---|
| Scope、name、attention boundary | Astra Low | Sol High |
| Prior art、novelty kill gate | Astra Medium | Sol High |
| Formal morphology model | Astra Medium | Sol High |
| Operator contract、preregistration | Sol High | Astra Low |
| Scaffold、dataset adapters | Terra Medium | Luna Medium / Sol High |
| Benchmark、profiler、operators、router | Terra High | Sol High |
| Pilot go/no-go | Sol High | Astra Low |
| Full experiments | Terra High | Sol High |
| Statistics、error atlas | Sol High | Astra Medium |
| Paper、figures | Sol High | Astra Medium |
| Independent claim audit | Astra Medium | Sol High |
| Demo、release automation | Terra Medium/High | Sol High |

## 5. 研究実験のtarget model matrix

主比較では、baselineごとにtarget modelとeffortを固定します。BITEだけ強いmodelや高いeffortを使いません。

### Main matrix

| Role | Representative profile | 目的 |
|---|---|---|
| economical target | Terra / Medium | token節約が日常modelで効くか |
| strong target | Sol / Medium | model strengthが上がっても効果が残るか |
| frontier spot-check | Astra / Low | 小さいsubsampleで長context性能が高いmodelにもselection効果があるか |
| optional open model | fixed local model / fixed decoding | provider依存性の確認 |

### Router matrix

| Router | Token accounting | 位置付け |
|---|---|---|
| deterministic profiler | model token 0 | v0.1 primary |
| Luna Low classifier | 全入出力を加算 | semantic gate ablation |
| length-only rule | model token 0 | 必須baseline |
| oracle route | model token 0 | upper bound、実運用主張は禁止 |

### Effort discipline

- Main matched-quality comparisonはMedium effort固定を基本とする。
- Astra spot-checkはLowから開始する。
- effort可変routingはsecondary studyに隔離する。
- providerがreasoning tokenを非公開にする場合、観測可能tokenとbilling/usage fieldsを分けて報告する。
- model version、date、client、temperature、tool permission、context limitをrun manifestへ固定する。

## 6. 代替profile

利用可能modelはplan、workspace、rolloutで異なります。

- Astra unavailable → Sol High maker + 別runのSol High adversarial checker
- Sol unavailable → Terra Highでdraftし、Astra Lowでreview
- Terra unavailable → Sol Medium、またはtaskを小分けしてLuna Medium
- Luna unavailable → Terra Low/Medium

置換時は `runs/model-substitutions.jsonl` に実際のmodel、effort、理由を記録します。

## 7. Astraを使う箇所、使わない箇所

### 使う

- HYVE／ContextSniper等との実質差分が残るか
- morphology vectorが装飾でなく測定可能か
- benchmarkにtarget leakageがないか
- pilotが失敗したときに続行かpivotか
- paper claimがartifactを超えていないか

### 使わない

-大量fixtureの生成
- file rename、index、formatting
- 単純parser実装
- baseline runの繰り返し
- chart dataの整形

## 8. 公式案内の扱い

OpenAIの現行案内は、Astraを最も高性能なWork/Codex model、Solを強い均衡、Terraを日常work、Lunaをfocused/repetitive workとして説明し、low effortから始めることを勧めています。model提供状況は変化し得るため、実行時に再確認してください。
