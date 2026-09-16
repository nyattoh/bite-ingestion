# BITE task matrix

## 一覧

| ID | Task | Phase | Maker | Checker | Depends on |
|---|---|---|---|---|---|
| BITE-00 | 研究境界、名称、注目フックを固定する | Gate A | gpt-6-astra / Low | gpt-5.6-sol / High | — |
| BITE-01 | 近接研究を再現可能に調べ、novelty kill gateを実行する | Gate A | gpt-6-astra / Medium | gpt-5.6-sol / High | BITE-00 |
| BITE-02 | データmorphologyとoperator selectionの形式モデルを確定する | Gate A | gpt-6-astra / Medium | gpt-5.6-sol / High | BITE-00, BITE-01 |
| BITE-03 | 四operatorとevidence packet contractを設計する | Gate A | gpt-5.6-sol / High | gpt-6-astra / Low | BITE-02 |
| BITE-04 | 仮説、benchmark、統計、kill criteriaを事前登録する | Gate A | gpt-5.6-sol / High | gpt-6-astra / Low | BITE-01, BITE-02, BITE-03 |
| BITE-05 | offline reproducible repository scaffoldを作る | Gate B | gpt-5.6-terra / Medium | gpt-5.6-luna / Medium | BITE-04 |
| BITE-06 | BITEBench counterfactual texture generatorを作る | Gate B | gpt-5.6-terra / High | gpt-5.6-sol / High | BITE-05 |
| BITE-07 | real workload、licence、privacy、dataset adaptersを固定する | Gate B | gpt-5.6-terra / Medium | gpt-5.6-sol / High | BITE-05, BITE-01 |
| BITE-08 | deterministic morphology profilerを実装する | Gate B | gpt-5.6-terra / High | gpt-5.6-sol / High | BITE-05, BITE-06, BITE-07 |
| BITE-09 | CUT / UNTANGLE / REDUCE / INTEGRATE operator libraryを実装する | Gate B | gpt-5.6-terra / High | gpt-5.6-sol / High | BITE-05, BITE-06, BITE-07 |
| BITE-10 | transparent operator-sequence policyとoracleを実装する | Gate B | gpt-5.6-terra / High | gpt-6-astra / Low | BITE-08, BITE-09 |
| BITE-11 | bounded re-biteとsource recoveryを実装する | Gate B | gpt-5.6-terra / High | gpt-5.6-sol / High | BITE-09, BITE-10 |
| BITE-12 | 公平なbaseline adaptersを実装する | Gate B | gpt-5.6-terra / High | gpt-5.6-sol / High | BITE-05, BITE-06, BITE-07 |
| BITE-13 | total-token evaluation harnessとartifact ledgerを実装する | Gate B | gpt-5.6-terra / High | gpt-5.6-sol / High | BITE-10, BITE-11, BITE-12 |
| BITE-14 | pilotを実行し、Go / Pivot / Stopを判定する | Gate C | gpt-5.6-sol / High | gpt-6-astra / Low | BITE-06, BITE-08, BITE-09, BITE-10, BITE-11, BITE-12, BITE-13 |
| BITE-15 | 事前登録matrixでfull experimentsとablationsを実行する | Gate C | gpt-5.6-terra / High | gpt-5.6-sol / High | BITE-14 |
| BITE-16 | 統計解析、Pareto分析、error atlasを作る | Gate C | gpt-5.6-sol / High | gpt-6-astra / Medium | BITE-15 |
| BITE-17 | 結果拘束型の論文、hero figure、abstractを作る | Gate D | gpt-5.6-sol / High | gpt-6-astra / Medium | BITE-16 |
| BITE-18 | 独立再現、claim audit、adversarial reviewer simulationを行う | Gate D | gpt-6-astra / Medium | gpt-5.6-sol / High | BITE-17 |
| BITE-19 | demo、artifact、publication packageを仕上げる | Gate D | gpt-5.6-terra / Medium | gpt-5.6-sol / High | BITE-18 |

## Gate別

- Gate A: BITE-00〜04 — idea survival、novelty、formal model、operator contract、preregistration
- Gate B: BITE-05〜13 — offline core、BITEBench、real adapters、profiler、operators、policy、recovery、baselines、evaluation
- Gate C: BITE-14〜16 — pilot、full experiments、statistics/error atlas
- Gate D: BITE-17〜19 — paper、independent audit、demo/release

## クリティカルパス

```text
BITE-00 -> BITE-01 -> BITE-02 -> BITE-03 -> BITE-04
                                             |
                                             v
BITE-05 -> (BITE-06 || BITE-07) -> BITE-08
                    |               |
                    +-> BITE-09 ----+
                              |
                              v
                          BITE-10 -> BITE-11
                              |         |
                              +-> BITE-12
                                      |
                                      v
                                   BITE-13
                                      |
                                      v
                                   BITE-14 -> BITE-15 -> BITE-16
                                                          |
                                                          v
                                                       BITE-17 -> BITE-18 -> BITE-19
```

## 高価なmodelを使う関門

- Astra Medium: BITE-01、02、16 checker、17 checker、18
- Astra Low: BITE-00、03 checker、04 checker、10 checker、14 checker
- Sol High: architecture、benchmark review、experiment design、paper
- Terra High: implementationとexperiment execution
- Luna: mechanical validationのみ

Astraを全taskへ使わず、research directionを誤ると全工程が無駄になる箇所へ限定します。
