# BITE-08 — deterministic morphology profilerを実装する

## Assignment

- Phase: `Gate B`
- Maker: `gpt-5.6-terra / High`
- Checker: `gpt-5.6-sol / High`
- Depends on: `BITE-05, BITE-06, BITE-07`

## Objective

raw data全体をLLMへ送らずにmorphology featuresを計算し、calibrated profileとevidenceを返す。

## Read first

- docs/morphology-feature-contract.md
- spec/morphology.schema.json
- benchmarks/spec/

## Deliverables

- src/bite_ingestion/profilers/
- tests/test_profiler.py
- docs/profiler-evidence.md
- output/calibration/profiler-baseline.json

## Acceptance criteria

- length、boundary、redundancy、regularity、coupling proxy、anomaly、locality proxy、provenance sensitivityを返す
- 各featureにmeasurement evidenceがある
- file typeだけでrouteを決めない
- malformed inputでfail closedまたはuncertainを返す
- profiling CPU timeとmemoryを測る
- ground-truth routeを参照しない

## Do not

- target answerをfeatureに使わない
- 全入力をsemantic LLM classifierへ送らない
- uncertaintyを0に固定しない

## Verify

- synthetic monotonicity tests
- texture-pair leakage test
- checkerがfeature failure casesを追加する

## Completion record

`docs/hand_over/BITE-08.md` に、変更、検証結果、failure、未解決点、次taskが読むartifactを記録する。
