# PHASE4H-REALSTRUCT2 引き継ぎ

- 担当: Grok
- 前提: `PHASE4G_COMPARISON_ACCOUNTING_VALIDATED`
- ブランチ: `feat/phase4h-realstruct2-corpus-freeze`
- H0 protocol freeze: `29dd6c91d02edcca6b486e74bac9bdf50259b149`
- H0 freeze blob: `4c48c198456babe2f5d0e652aefe831f8dacd3bc`
- H1 candidate pool: `b50e36d2916ff8de7eaae37055fef6bf114d2008`
- H1 pool blob: `7f45295f0ffe2880516f9f8ccbfa2c20b942a002`
- Phase 4G HEAD: `be0248c972d9136ae6c39c57bf7e6a756e815aa9`
- 実行日: 2026-09-21
- 有料 API: **未使用**
- p3f: **未開封**
- Phase 4F / 4G artifacts: **未変更**
- BITE v5 / length_pi_v1 / tokenizer: **未実行・未変更**
- 4 arms: **未実行**

---

## 判定

```text
PHASE4H_REALSTRUCT2_PARTIAL
```

prospectively acquired convenience sample for a later frozen comparison。BITE evidence / baseline evidence / comparison result / generalization / superiority ではない。

H0 を変えずに 18/18 primary を埋められなかった。family 内 first-6 は MIT/Apache-2.0 かつ 60 unique repo/path の凍結プールでは 4+3+3 件まで。

```text
dotenv-like primary 4
properties primary 3
ini_cfg primary 3
secondary 0
```

主な不足理由は GitHub license metadata が MIT/Apache-2.0 でないこと（None / NOASSERTION / GPL 等）と、first `=` 文法で assignment が 10 未満であること。プール拡大や license 推定の後付けは H0 改変になるのでしていない。

---

## 何を固定したか

- H0 で queries / pool size 60 / eligibility / SHA256 選択順 / primary 非条件付き / secondary 分離 / 注釈文法 / Phase4I 要約契約を探索前に freeze
- H1 で family あたり 60 unique repo/path。file contents 未開封。以降の追加・並べ替えなし
- H2 は selection_key 昇順のみ。手選びなし
- scorer は two-pass `${NAME}`。expected route / operator / BITE edge / arm winner は保存しない
- secondary は primary に混ぜない。今回 0 件

---

## 成果物

- `benchmarks/spec/phase4h-realstruct2-freeze.json`
- `artifacts/phase4h/candidate-pool.json`
- `corpora/realstruct-2/raw/`（受理 10）
- `corpora/realstruct-2/manifest.json`
- `corpora/realstruct-2/primary.json`
- `corpora/realstruct-2/secondary.json`
- `corpora/realstruct-2/licenses.json`
- `corpora/realstruct-2/annotations.json`
- `corpora/realstruct-2/rejections.json`
- `artifacts/phase4h/realstruct-2.json`

---

## 次

H0 を書き換えない。4 arms / tokenizer はまだ走らせない。p3f は開けない。main へ merge しない。quota を埋めるなら別 phase で discovery 契約を先に freeze し直す。
