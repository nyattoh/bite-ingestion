# BITE research and Codex task pack

作成日時: 2026-09-13 22:48:37 JST

## 目的

「人が食べ物の形や硬さに応じて前歯、犬歯、小臼歯、大臼歯を使い分けるように、AIへ渡す前のdataも形態に応じて異なる処理を通せないか」という着想を、独立した反証可能な研究へ落としたtask packです。

仮称は **BITE: Boundary-, Interdependency-, Texture-, and Evidence-Aware Ingestion**。論文候補題は **BITE Before You Think: Morphology-Aware Ingestion for Token-Efficient Language Models** です。

## 研究の核

単なる「大きいdataを圧縮する」ではありません。

- 同じ情報をprose、table、JSON、logs、codeへ変換する。
- 内容と正解は固定し、表面形態だけを変える。
- morphologyに応じて `CUT / UNTANGLE / REDUCE / INTEGRATE` のoperator sequenceを変える。
- modelへ見せないsourceは捨てず、recoverable indexへ置く。
- 不足時はbounded re-biteで必要箇所だけ追加する。
- routerを含む総tokenで比較する。

この **counterfactual texture benchmark** が、比喩を研究へ変える中心です。

## 推奨repository

Gate A承認後の既定案: `nyattoh/bite-ingestion`

既存Topo系へ直接混ぜず、将来adapterで接続します。

## ファイル

- `PAPER_OUTLINE.md` — 論文骨子、形式モデル、benchmark、hypotheses、claim境界
- `MODEL_EFFORT_POLICY.md` — Codex作業と研究実験のmodel/effort割当
- `PRIOR_ART_SEEDS.md` — 近接研究とnovelty hazard
- `EXCITEMENT_STRATEGY.md` — 覚えやすいが誇張しない見せ方
- `TASK_MATRIX.md` — 全20taskの一覧と依存関係
- `tasks/BITE-00.md`〜`tasks/BITE-19.md` — Codexへ個別投入できるtask
- `task-manifest.json` — 機械可読task定義
- `CODEX_RUNBOOK.md` — gate、実行順、共通prompt、stop rule
- `VALIDATION_REPORT.md` — pack生成時の整合検査
- `SHA256SUMS.txt` — 配布ファイルchecksum

## 最初に人が確認する事項

1. 仮称BITEを名称調査へ進めてよいか。
2. architecture paperではなく、近接研究次第でbenchmark/evaluation paperへpivotしてよいか。
3. headline benchmarkを「same facts, different texture」に置いてよいか。
4. v0.1でenergy reductionを主張しない方針でよいか。
5. Gate Aが通るまでfull implementationを始めない方針でよいか。

## 重要な近接研究

- HYVE, arXiv:2604.05400
- ContextSniper, arXiv:2607.01916
- Adaptive Chunking, arXiv:2603.25333
- LongLLMLingua, arXiv:2310.06839
- Byte Latent Transformer, arXiv:2412.09871
- Mixture-of-Depths, arXiv:2404.02258
- Data-centric compression perspective, arXiv:2505.19147

これらは開始点であり、新規性調査の完了を意味しません。
