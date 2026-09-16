# Excitement strategy — memorable without overclaiming

## 原則

注目されることは保証できません。BITEでは、比喩を入口にし、中心結果を誰でも追試できるbenchmarkへ置きます。

## 1. 読者が10秒で掴める対比

```text
Old question: How many tokens can the model swallow?
BITE question: What shape should the evidence take before the model sees it?
```

日本語では「長さではなく食感」と表現できます。

## 2. Hero figure

左に同一canonical factsの6表現、中央にmorphology profileと4 operator、右に同じanswer-supporting evidence packetを置きます。

- prose -> CUT
- nested JSON -> CUT + REDUCE
- repetitive logs -> REDUCE + UNTANGLE
- code/config -> CUT + UNTANGLE + INTEGRATE
- dense cross-reference -> INTEGRATE
- omitted clue -> re-bite

図だけで「同じ内容でも処理を変える」が伝わることをacceptance criteriaにします。

## 3. 一枚で強い結果図

- X軸: total model-visible tokens
- Y軸: task quality
- point shape: workload texture
- line: method Pareto frontier

BITEが右上ではなく左上へ移動するかを示します。結果が出なければ図を隠さずnegative resultにします。

## 4. Memorability assets

- system name: BITE
- benchmark: BITEBench
- source-grounded output: evidence packet（図では evidence bolus を補助表現として使用可）
- additional evidence request: bounded re-bite
- slogan: Length is not texture.

## 5. 発表前のtitle test

技術者3名以上に、title、abstract、hero figureだけを見せ、次を匿名で答えてもらいます。

1. 何が新しいと思ったか
2. 既存RAG/compressionと何が違うか
3. 誇張に見える箇所
4. 30秒後に覚えている語

反応が「歯の比喩だけ」に集中する場合は、formal subtitleとbenchmarkを前へ出します。

## 6. Demo

browser-onlyまたはlocal-firstで次を見せます。

- raw input token estimate
- morphology vector
- selected operator trace
- visible evidence
- omitted but recoverable evidence index
- re-bite requests
- baselineとのtoken差

paperの主張と同じoffline fixturesを使い、demo専用の成功例を作らないこと。

## 7. Release package

- paper source
- BITEBench generator
- frozen benchmark split
- raw run manifests
- error gallery
- interactive demo
- 90秒説明script
- note/Medium向け一般解説
- claim/evidence matrix

## 8. やらないこと

- 未実測のenergy削減をtitleへ入れない
- 「human-like」「biologically optimal」と言わない
- best-case compression ratioだけをheadlineにしない
- router tokenを除外しない
- accuracy低下を平均で隠さない
- close workを小さく扱わない
