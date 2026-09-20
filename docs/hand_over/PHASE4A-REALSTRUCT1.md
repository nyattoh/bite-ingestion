# PHASE4A-REALSTRUCT1 引き継ぎ

- 担当: Grok
- 前提: `PHASE3T_EXACT_REFERENCE_VALIDATED`
- ブランチ: `feat/phase4a-realstruct1-corpus-freeze`
- A0 protocol freeze: `3e5d2d7c9cd0a07346e90401496df042aa956bf7`
- A0 freeze blob: `6e009fb6cf1cb239b8449e402301be15ffd7ed86`
- 実行日: 2026-09-19
- 有料 API: **未使用**
- p3f evaluation replica 2/3: **未開封**
- Phase 3T / 3S / 3Q artifact / verdict: **未変更**
- BITE sensor / policy / planner / operator: **未実行**
- baseline: **未実行**
- XFER-3: **未作成**

---

## 判定

```text
PHASE4A_REAL_CORPUS_FROZEN
```

REALSTRUCT-1 は 12 文書の convenience sample。public な line-oriented key=value 設定ファイルだけ。representative / real-world generalization / BITE superiority ではない。

```text
Phase3S remains FAILED
Phase3Q remains FAILED
```

---

## 何を固定したか

- A0 で family / 件数 / natural vs enriched / eligibility / split / annotation grammar / claim boundary を source 取得前に freeze
- 3 family × 4 文書。family 内 2 natural + 2 explicit-reference-enriched
- enrichment は raw `${NAME}` が同一文書の assignment key と case-sensitive exact 一致するときだけ。BITE sensor は見ていない
- 1 repository につき 1 文書。1 URI = 1 document
- SPDX は MIT / Apache-2.0 のみ採用。GPL/AGPL などは manifest の exclusions に理由を残して置換
- split は family 内 raw SHA256 の lexicographic 順。先頭 1 件が development（3）、残り 9 が evaluation。入替禁止
- scorer annotation は `bite_ingestion.policies` / `profilers` を import しない独立コード。first `=` が assignment。comment / section / blank / other は `unsupported` であり negative example ではない
- gold は `${NAME}` のみ。`$NAME` / substring / `${NAME:-x}` / section-qualified `${colors.background}` は gold にしない。missing annotation を非 reference と解釈しない

---

## 成果物

- `benchmarks/spec/phase4a-realstruct1-freeze.json`
- `corpora/realstruct-1/raw/`（12 ファイル、改行・encoding 未改変）
- `corpora/realstruct-1/manifest.json`
- `corpora/realstruct-1/licenses.json`
- `corpora/realstruct-1/split.json`
- `corpora/realstruct-1/annotations.json`
- `artifacts/phase4a/realstruct-1.json`

---

## 次

FROZEN なので次は Phase 4B で同じ evaluation 9 文書の bytes を BITE と baseline に使う。4A では baseline も BITE も走らせない。source 差し替えは禁止。p3f evaluation は開けない。main へ merge しない。Phase 3S / 3Q を CONFIRMED に書き換えない。XFER-3 は作らない。
