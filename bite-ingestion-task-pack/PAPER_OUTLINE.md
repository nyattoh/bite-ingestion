# BITE 論文骨子 v0.1

作成日時: 2026-09-13 22:48:37 JST

## 0. 仮称と一行フック

### 第一候補

**BITE Before You Think: Morphology-Aware Ingestion for Token-Efficient Language Models**

### 正式な展開

**BITE: Boundary-, Interdependency-, Texture-, and Evidence-Aware Ingestion**

### 一行フック

> **長さだけが問題なのではない。同じ情報でも、データの「食感」が違えば、最適な食べ方も違う。**

BITE は、異種データをそのまま長い token 列へ変換する前に、データの境界、反復、依存関係、異常密度、構造規則性、証拠の局在性を調べ、処理 operator の列を選ぶ外部 ingestion architecture です。

咬合・歯種は着想と説明のための対応表として使います。生体模倣の忠実性は主張せず、技術的な貢献は **query-conditioned morphology profiling、operator routing、provenance-preserving evidence construction、bounded evidence recovery** として定義します。

## 1. なぜ独立研究にするか

TopoLoad は、処理が目標方向へ進むか、横へ逸れるかを見て計算経路を制御する研究です。BITE は、その前段で **何を model-visible context に変換するか**を扱います。

```text
Raw heterogeneous data
        |
        v
BITE morphology-aware ingestion
        |
        v
Compact, recoverable evidence packet
        |
        v
Any model / router / agent, including TopoLoad
```

したがって、BITE は Topo シリーズに依存せず単独で評価でき、後から adapter で接続できます。

## 2. 問題設定

長い入力へ対する既存策には、prompt compression、RAG、adaptive chunking、database-like hybrid views、code-specific context gates、model-internal conditional computationがあります。しかし、次の問いは独立に検証する価値があります。

> **入力長ではなくデータ形態を観測し、複数の可逆・準可逆 operator から処理列を選ぶことで、単一の chunking／compression 戦略よりも、総 model-visible token を減らしながら品質と証拠追跡性を保てるか。**

重要なのは「巨大データなら大臼歯」という単純な size router にしないことです。大きくても反復の多い log は小さく集約でき、短くても依存関係の強い契約条項や code は高密度の統合を必要とします。

## 3. BITE の操作的対応

| 着想上の歯種 | 正式 operator family | 主なデータ特性 | 典型処理 |
|---|---|---|---|
| 前歯 | `CUT` | 境界が明確、局所的、切り分け可能 | 行、段落、page、record、function、AST node 単位の切断 |
| 犬歯 | `UNTANGLE` | 依存、異常、例外、壊れた構造、注入候補 | rare event 抽出、dependency trace、cycle 分離、malformed region 隔離 |
| 小臼歯 | `REDUCE` | 反復、規則性、集約可能性 | dedupe、canonicalise、cluster、aggregate、schema normalise |
| 大臼歯 | `INTEGRATE` | 部分間結合が強い、cross-unit reasoning が必要 | join、multi-hop evidence assembly、frontier model synthesis |

正式な method と実装では `CUT / UNTANGLE / REDUCE / INTEGRATE` を使います。歯の名称は図・導入・説明上の mnemonic に限定します。

## 4. 最小形式モデル

### 4.1 入力

- 生データ集合: \(D = \{u_1, \ldots, u_n\}\)
- 問いまたは task: \(q\)
- token budget: \(B\)
- operator library: \(\mathcal{O}\)
- target model configuration: \(M\)

各 \(u_i\) は source location、version、type、optional relation を持つ source unit とします。

### 4.2 Morphology vector

\[
\mathbf{m}(D,q) = [b, r, s, k, a, l, p, u]
\]

- \(b\): boundary clarity — 自然な切断境界の明確さ
- \(r\): redundancy / compressibility — 反復・圧縮可能性
- \(s\): structural regularity — schema、record、syntax の規則性
- \(k\): cross-unit coupling — 部分同士の依存・結合度
- \(a\): anomaly sparsity / entanglement — rare evidence、異常、壊れた領域
- \(l\): evidence locality — 正答根拠が局所に集まる程度
- \(p\): provenance sensitivity — 行番号、原文、version を失えない程度
- \(u\): uncertainty about sufficient evidence — 現在の evidence で十分かの不確実性

v0.1 は transparent features と oracle labels を中心にし、learned profiler は ablation または v0.2 とします。

### 4.3 Operator policy

policy \(\Pi\) は operator sequence を選びます。

\[
\pi = \Pi(\mathbf{m}(D,q), B), \qquad \pi=(o_1,\ldots,o_j),\; o_i\in\mathcal{O}
\]

出力は model-visible evidence packet \(E_0\) と source recovery index \(R\) です。

\[
(E_0, R, \tau) = \pi(D,q)
\]

\(\tau\) は operator trace で、何を残し、何を外に置き、どこから復元できるかを記録します。

### 4.4 Bounded re-bite

最初の evidence が不足する場合、target model は自由な探索を続けず、許可された schema で追加 evidence を要求します。

\[
E_{t+1}=E_t \cup \operatorname{Recover}(R, request_t)
\]

最大回数 \(J\)、追加 token budget \(B_r\)、許可 request type を事前固定します。これは無制限 agent loop ではありません。

### 4.5 評価目的

単一の恣意的 aggregate score だけで結論を出さず、Pareto frontier を主に報告します。補助的には次を定義します。

\[
T_{total} = T_{profiler} + T_{router} + \sum_{c \in calls}(T^{in}_c + T^{out}_c)
\]

\[
\min_{\pi} \; T_{total}(\pi)
\quad\text{subject to}\quad
Q(\pi) \ge Q_{baseline}-\delta,
\; Recall_{evidence}(\pi)\ge\rho,
\; Prov(\pi)\ge\eta
\]

router に LLM を使った場合、その token も必ず \(T_{total}\) に含めます。通常 code による parser、dedupe、aggregation は token 0 として扱いますが、CPU time と wall-clock は測定します。

## 5. 中心的な新規性候補

新規性は Gate A の文献調査が終わるまで確定しません。候補は次です。

1. **Cross-domain morphology vector**: 長さや document type だけでなく、切断可能性、反復、結合度、異常密度、証拠局在性を同時に扱う。
2. **Operator sequence routing**: 一つの compression method を選ぶのではなく、`CUT -> UNTANGLE -> REDUCE -> INTEGRATE` の順序と省略を task ごとに変える。
3. **Counterfactual Texture Benchmark**: 同じ underlying facts と正解を、prose、CSV、nested JSON、logs、code/config、mixed payload に変換し、表面形態だけを変える。
4. **Evidence packet contract**: visible context、omitted source index、coverage、operator trace、version をまとめて評価する。
5. **Bounded evidence recovery**: irreversibly summarise せず、足りない根拠だけを定型 request で追加する。
6. **Full-cost accounting**: target prompt だけでなく profiler、router、re-bite、output token を総計する。

HYVE、ContextSniper、Adaptive Chunking、LongLLMLingua 等との比較でこの差分が消えた場合は、問いを縮小または中止します。

## 6. 主仮説

### H1 — Texture matters beyond length

長さと domain を統制しても、morphology features は最適 operator sequence の予測に増分情報を持つ。

### H2 — Matched-quality token reduction

BITE は raw full-context、fixed chunking、single universal compressor、adaptive chunking、domain-specific context systemsに対し、task qualityを許容差内に保ちながら総model-visible tokenを減らす。

### H3 — Counterfactual texture robustness

同一 facts を異なる表現へ変換した texture-paired tasks で、BITE は固定戦略より operator choice regret が小さく、正答と evidence recall を安定させる。

### H4 — Recoverability prevents catastrophic omission

source recovery index と bounded re-bite は、不可逆 compression に比べ、重要証拠を初回 context から落とした場合の回復率を改善する。

### H5 — No universal tooth

全 workload で同じ operator sequence が最良にはならない。もし同じ戦略がほぼ全てで勝つなら、morphology router の必要性は否定される。

### H6 — Routing overhead must pay for itself

profiler／router／recovery の時間・token overhead を含めても、節約が残る。overhead が節約を相殺する場合は失敗と判定する。

## 7. BITEBench

### 7.1 Counterfactual texture pairs — headline benchmark

一つの canonical fact graph から、内容を変えずに次を生成します。

- narrative prose
- Markdown table / CSV
- deeply nested JSON
- repetitive event logs
- code + configuration
- mixed text / table / log payload

質問、正解、必要 evidence unit は同一に保ちます。これにより、content difficulty ではなく surface morphology の効果を検査できます。

### 7.2 Synthetic task families

| Family | 主な texture | 想定最適 route |
|---|---|---|
| clean_local | 明確な境界、局所 evidence | CUT |
| repeated_records | 反復 schema | CUT -> REDUCE |
| sparse_anomaly | 大量反復中の少数異常 | REDUCE -> UNTANGLE |
| dependency_chain | cross-unit dependency | CUT -> UNTANGLE -> INTEGRATE |
| malformed_mixed | 壊れた JSON と自然文の混在 | UNTANGLE -> CUT -> REDUCE |
| dense_cross_reference | 短いが強結合 | INTEGRATE |
| adversarial_omission | relevant item が圧縮で落ちやすい | route + re-bite |
| texture_swap | facts 固定、表現のみ変更 | morphology-dependent |

### 7.3 Real workload families

dataset は licence、再配布可否、PII、安全性を BITE-07 で確認して固定します。

- observability logs / telemetry
- tabular and nested machine data
- repository-level code and test output
- long technical or legal documents
- mixed agent tool outputs

特定 dataset 名は調査前に必須化しません。

## 8. 比較条件

必須 baseline:

1. Raw full context
2. Length-only router
3. Fixed-size chunk + top-k retrieval
4. Semantic or adaptive chunking
5. One universal reduction operator
6. Query-aware prompt compression
7. Domain-specific systems where fair: HYVE-like structured view, ContextSniper-like code evidence gate
8. BITE rule policy
9. BITE + bounded re-bite
10. Oracle operator route

可能なら learned policy を secondary experiment に置きます。BITE だけ高性能 model、高 effort、追加 call を使わないよう統制します。

## 9. Primary metrics

- task accuracy / rubric score
- total model-visible input token
- total output / reasoning token where observable
- total LLM call count
- first-pass evidence sufficiency
- visible evidence recall / precision
- recoverable evidence recall
- provenance completeness
- compression ratio
- operator selection regret against oracle
- re-bite count and recovery success
- end-to-end latency
- deterministic preprocessing time
- context construction failure rate
- matched-quality cost-token Pareto frontier

Energy、carbon、GPU power は直接測定しない限り claim しません。

## 10. Ablations

- morphology featuresなし、lengthのみ
- query conditioningなし
- `UNTANGLE`なし
- `REDUCE`なし
- `INTEGRATE`を常時使用
- source recovery indexなし
- bounded re-biteなし
- fixed operator order
- domain labelのみ
- learned profiler vs deterministic profiler
- target model別、effort固定／可変
- texture-pair trainingあり／なし

## 11. 論文構成

### Abstract

1. 問題: long context対策が入力を均質なtoken列として扱いがち。
2. 着想: lengthではなくmorphologyに応じてoperator sequenceを変える。
3. 方法: BITE profiler、four operator families、recoverable evidence packet、bounded re-bite。
4. benchmark: BITEBench と counterfactual texture pairs。
5. baselines: full context、chunking、compression、domain-specific context systems。
6. results: 実験後にのみ記入。
7. limits: representation dependence、router overhead、dataset scope、energy未測定。

### 1. Introduction

- context window拡大だけでは selection problem は消えない。
- 同じ長さでも、反復logと密結合契約条項では必要な処理が違う。
- “Length is not texture.”
- BITEの研究問い、貢献候補、主張境界。

### 2. Related Work

- prompt / retrieval compression
- adaptive and semantic chunking
- structured machine-data views
- code context and tool-output gating
- data-centric token compression
- model-internal adaptive computation
- iterative / active retrieval
- dentition as design inspiration only

### 3. Problem Formulation

- source units、query、budget
- morphology vector
- operator sequence
- evidence packet、recoverability
- total-token accounting

### 4. Method

- profiler
- CUT
- UNTANGLE
- REDUCE
- INTEGRATE
- gate policy
- bounded re-bite
- provenance and freshness contract

### 5. BITEBench

- canonical fact graph
- texture renderers
- ground-truth evidence spans
- synthetic and real workloads
- licence and privacy boundary

### 6. Experiments

- target models and effort
- baseline parity
- primary metrics
- statistical protocol
- budget and stopping rule

### 7. Results

- matched-quality token Pareto
- texture-pair robustness
- operator selection matrix
- evidence omission and recovery
- overhead breakdown
- cross-domain transfer

### 8. Ablations and Error Atlas

- features、operators、recovery、model strength
- false reductions
- over-integration
- dependency misses
- malformed input failures

### 9. Discussion

- “chewing” metaphor vs formal architecture
- when fixed compression is enough
- when morphology routing is unnecessary
- relationship to database systems、RAG、conditional computation

### 10. Limitations and Safety

- operator-induced omission
- prompt injection in retained evidence
- source freshness
- privacy and access control
- hidden bias in morphology labels
- provider-specific tokenisation

### 11. Conclusion

結果が支持した範囲だけを述べます。

## 12. 注目を集めるための、研究として正当な見せ場

1. **Title hook**: “BITE Before You Think” と正式副題を併記する。
2. **Hero figure**: 同一 facts が prose / JSON / log / code へ変わり、別 operator route で同じ compact evidence へ収束する図。
3. **Headline result**: matched qualityでの総token削減と、texture swap時の安定性を一文で示す。結果前に数字を置かない。
4. **BITEBench release**: canonical facts と renderer を公開し、研究者が新しいtextureを追加できるようにする。
5. **Interactive demo**: 入力のmorphology profile、operator trace、残した証拠、外に置いた証拠、token差を可視化する。
6. **Failure gallery**: BITEが噛み損ねたケースも公開し、比喩だけの論文に見せない。

注目・採択・引用は保証できません。目的は「一目で理解できるが、検証すると厳密」という構成にすることです。

## 13. Go / Pivot / Stop

### Go

- morphologyがlength/domainを越えてoperator choiceを予測する。
- 3つ以上の異なるworkload familyでmatched-quality token Paretoが改善する。
- total accounting後も節約が残る。
- texture-pair benchmarkで固定戦略より安定する。

### Pivot

- cross-domain差分は弱いが、一つのdomainで明確に効く。
- operator routingよりevidence recovery contractが主貢献になる。
- morphology taxonomyよりcounterfactual benchmark自体が主貢献になる。

### Stop / Negative result paper

- length-onlyまたは単一adaptive strategyがほぼ同等。
- router overheadが節約を相殺する。
- evidence omissionが品質を一貫して損なう。
-近接研究と実質的差分が成立しない。

negative resultでも、BITEBenchとfull-cost evaluationが有用なら、architecture superiorityを主張せずbenchmark／evaluation paperへ切り替えます。
