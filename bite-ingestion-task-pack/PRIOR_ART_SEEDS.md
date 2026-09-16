# Prior-art seed map and novelty hazards

作成日時: 2026-09-13 22:48:37 JST

これは文献調査の完了版ではなく、BITE-01で必ず再検索する開始点です。

## 最も近い研究

| Work | Identifier | BITEへの脅威 | BITEが残すべき差分仮説 |
|---|---|---|---|
| HYVE: Hybrid Views for LLM Context Engineering over Machine Data | arXiv:2604.05400 | structured machine dataをdatabase-like viewへ変換し、full dataをrecoverable datastoreに保持。token 50–90%減を報告 | machine dataだけでなくcross-domain morphology、operator sequence、counterfactual texture pairs、full-cost route regret |
| ContextSniper: Token-Efficient Code Memory for Repository-Level Program Repair | arXiv:2607.01916 | code/runtime evidenceをcompact packet化し、sourceをprompt外に保持。token削減を報告するがrepair rateは僅かに低下 | code特化でないtexture model、same-facts/different-form benchmark、operator taxonomy、bounded re-bite |
| Adaptive Chunking | arXiv:2603.25333 | documentごとにchunking methodを選択 | chunker choiceだけでなくheterogeneous operator chainとprovenance recovery |
| LongLLMLingua | arXiv:2310.06839 | query-aware prompt compressionでtoken・cost・latencyを削減 | token deletion/compressionだけでなくstructure-specific transformation、exact source recovery、cross-texture route |
| Byte Latent Transformer | arXiv:2412.09871 | predictabilityに応じdynamic patching、model内部でcomputeを配分 | model外部のingestion、既存modelへplug-in、source-level provenance |
| Mixture-of-Depths | arXiv:2404.02258 | tokenごとのmodel内部compute routing | model-visible token constructionとは別層 |
| Data-centric compression survey/position | arXiv:2505.19147 | input compressionを広い研究軸として整理 | generic compressionとの差を具体的benchmarkとoperator routingで示す必要 |
| CompAct | arXiv:2407.09014 | retrieved documentをquery依存に圧縮 | retrieval後の文書圧縮より前のraw heterogeneous ingestionとsource recovery |

## Novelty hazard checklist

BITE-01は少なくとも次のquery familyを別々に検索します。

- morphology-aware / structure-aware context routing
- multi-operator preprocessing selection
- adaptive chunking and parser selection
- prompt / retrieval compression
- machine-data hybrid views and database-backed context
- code context gates and tool-output filters
- active / iterative retrieval and sufficiency detection
- provenance-preserving summarisation/compression
- content-invariant representation or counterfactual formatting benchmarks
- model-internal token routing and dynamic compute
- information bottleneck and sufficient statistics for LLM context

## 新規性が消える条件

次を全て含む先行研究が見つかった場合、architecture claimを縮小します。

1. query-conditioned morphology features
2. multiple heterogeneous operator families and sequence selection
3. same facts rendered into multiple surface textures
4. recoverable omitted evidence with bounded additional requests
5. full model-token accounting
6. cross-domain evaluation

architecture差分が弱い場合は、`BITEBench` または `evidence packet contract` を主貢献へpivotします。

## 生体側の扱い

人の歯は切断、裂断、粉砕を含む異なる役割を持つという一般的な解剖学的説明を着想に使えます。ただし、AI operatorの最適性を歯の解剖から導出したとは書きません。biology sectionは導入の短い段落とappendixのsource noteに限定します。
