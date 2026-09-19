# PHASE3A-PROFILER-MECHANISM-AUDIT 引き継ぎ

- 担当: Grok
- 前提: Phase 2D `PHASE2D_OFFLINE_NO_SIGNAL`（0/48、PR #23）
- ブランチ: `feat/phase3a-profiler-mechanism-audit`
- 実行日: 2026-09-19
- 有料 API: **未使用**
- profiler feature / threshold / routing / operator: **未変更**
- Phase 2 evaluation: **spent holdout**。再評価していない。

これは confirmatory result ではない。結果を見たあとの mechanism analysis。

---

## 判定

```text
PHASE3A_DISPERSION_UNOBSERVABLE
```

現 profiler では Phase 2 の dispersion 操作を routing feature として観測できない。

Phase 2D の 0/48 を「直す」目的ではない。holdout で threshold を動かしていない。

---

## なぜ 0/48 だったか

Phase 2A の dispersion は、同じ fact 行の**並べ替え**だけをする。required evidence の char-span 位置は 48/48 pair で変わる（clustered では隣接、dispersed では文書に散らす）。

rule-Π が使う `b, a, r, k, l, u` は、その並べ替えを見る設計になっていない。

| feature | routing? | dispersion で動く設計か | 実装 |
|---|---|---|---|
| b | yes | no | 全文の改行密度と separator 文字レート |
| a | yes | no | 全文 anomaly / 全体 JSON parse |
| r | yes | no | 重複 stripped-line 比（行の multiset） |
| k | yes | no | 全文の ref-like token 数 / line_count |
| l | yes | no | query-token の行内 substring hit を降順ソートし、上位 min(3,n) / 合計。**行順と行間距離を捨てる** |
| u | listed, unused | no | a と (1-l) から派生。rule-Π は記録するだけで route しない |
| s, p | no | no | 全文 heuristics |

Phase 2D 48 pair の clustered vs dispersed profiler ベクトルは **8 feature すべて abs delta = 0**。Phase 2D に保存されていた morphology と、今の profiler の再計算は 48/48 一致。

policy が差を「使わなかった」のではない。差が vector に乗っていない。

---

## `l` について

`l` は「位置的な evidence locality」ではない。

- 入力は payload 行と query だけ。gold / required_evidence_id は見ない
- 各 stripped line について query token の substring ヒット数を数える
- `sorted(hits, reverse=True)` のあと top-k mass / total
- したがって line order / distance に対して **permutation-invariant**

行を並べ替えても `l`（および他の全 feature）は変わらない。同じ並べ替えで、ヒット行の first–last index span は変わり得る。テストで固定している。

このベンチの question は `value` などを含み、distractor 行 `neutral_value_*` にも部分一致する。query-hit の行 index span は 24/48 しか動かない。dispersion の設計軸の代理には使えない。代理は required-evidence span spread（48/48 で差あり、routing feature ではない）。

---

## 測ったもの / 測っていないもの

測った:

- 現行 profiler の式
- 48 pair の feature 別 abs delta
- 行順列不変
- required-evidence span spread（audit diagnostic）

測っていない / やっていない:

- profiler の変更
- HIGH/LOW の再校正
- Phase 2 evaluation の再走行
- paid API
- 「BITE が dispersion を処理できない」という製品主張

---

## 成果物

- `artifacts/phase3a/profiler-mechanism-audit.json`
- `artifacts/phase3a/profiler-mechanism-audit.md`
- `src/bite_eval/phase3a_audit.py`
- `scripts/run_phase3a_audit.py`
- `tests/test_phase3a_profiler_mechanism.py`
- `spec/phase3a-profiler-mechanism-audit.schema.json`

---

## 次にやらないこと

spent holdout で `l` を位置 feature に書き換えて Phase 2D を再採点しない。
main へ merge しない（この作業の範囲）。
