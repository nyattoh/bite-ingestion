# PHASE1-NEGATIVE-CONTROLS 引き継ぎ

- 担当: Claude
- ベース: `main` = `353c0c0`（PR #15 マージ後）
- ブランチ: `feat/negative-control-families`（**未 push / 未 merge**）
- 実行日: 2026-09-18
- 有料 API: **未使用**
- `TBD_CALIBRATE` / profiler feature / routing rule: **未変更**
- 既存 workload family: **未変更**

---

## 目的

**BITE を有利に見せることではない。** 測定器が「失敗を失敗として検出できる」ことを証明する。

Phase 1 wiring レビュー時点で、offline matrix 全 32 行の `recall_vis` / `recall_rec` /
`provenance` はすべて 1.00 の定数だった。つまり指標は「発火しなかった」ことしか示せておらず、
**必要な証拠が失われたときに実際に数字が下がるのかは未検証**だった。

本作業はその穴だけを埋める。benchmark 全体の拡張や threshold 調整には進んでいない。

---

## 設計方針

負例は `SYNTHETIC_FAMILIES` に入れず、独立した `NEGATIVE_FAMILIES` として追加した。

| 理由 | |
|---|---|
| 既存 workload を汚さない | `run_pilot` / billed runner / 既存テストは 8 family のまま |
| 「結果に合わせた改造」を防ぐ | 既存 family の document は byte-identical（テストで固定） |
| それでも同じ matrix に入る | 同一 4 arm・同一 wrapper・同一 estimator を通る `case_kind=negative_control` の行 |

**期待値は測定前に設計から書き下ろした**（`NEGATIVE_FAMILY_INTENT` → `NEGATIVE_EXPECTATIONS`）。
初回実測で全件一致したため、後から期待値を実測に合わせる操作は発生していない。

---

## 追加した負例 3 件

### 1. `neg_gold_quarantined` — 証拠が隔離され、re-bite で戻る

```text
{"audit": [                                    <- 文書全体を malformed JSON にする
INFO service=alpha region=lab-only slot=0      <- gold A（残る）
ERROR service=alpha code=K00 value=100         <- gold B（ERROR行 → 隔離される）
INFO trailing heartbeat ok=1
```

**人間が見て失敗すべき理由**: 答えを含む唯一の行が ERROR 行であり、UNTANGLE は anomaly 行を
隔離する。よって morphology-aware arm は必然的に答えを視界から外す。

機構（すべて既存ルール）: 先頭 `{` + `json.loads` 失敗 → profiler `a=0.80` →
`a >= HIGH(0.66)` → rule-Π が UNTANGLE を含む → `ERROR` が `anomaly_candidate` に分類され R へ。
query の語（`code` / `value` / `K00`）は隔離された行にしか無いので、bounded re-bite が
request を組み立てられる。

| arm | recall_vis | recall_rec | T_rebite | 期待 | 実測 |
|---|---:|---:|---:|---|---|
| raw_full | 1.00 | 1.00 | 0 | 全部見える | ✅ 一致 |
| length_pi | 1.00 | 1.00 | 0 | UNTANGLE しないので無傷 | ✅ 一致 |
| rule_pi | **0.50** | 1.00 | 0 | 半分失う / R には在る | ✅ 一致 |
| rule_pi_rebite | **1.00** | 1.00 | **10** | 取り戻す / 課金される | ✅ 一致 |

### 2. `neg_unrecoverable_gold` — R に在っても回収されない

```text
{"audit": [
INFO code=K00 status lookup requested          <- gold A（残る。query の語を全部含む）
ERROR code=K00 status=100                      <- gold B（隔離される）
INFO trailing heartbeat ok=1
```

**人間が見て失敗すべき理由**: 生き残った行が query と同じ語（`code` / `status` / `K00`）を
反復しているため、語ベースの bounded recovery は「何かが欠けている」という信号を得られない。
証拠は R に在るが、取りに行けない。

| arm | recall_vis | recall_rec | T_rebite | 期待 | 実測 |
|---|---:|---:|---:|---|---|
| rule_pi | **0.50** | 1.00 | 0 | 半分失う | ✅ 一致 |
| rule_pi_rebite | **0.50** | 1.00 | **0** | 回収できず、課金も無い | ✅ 一致 |

**1 と 2 の対比が本作業の核心**である。同じ損失・同じ R 記録でありながら、
実際に回収したかどうかで `recall_vis` と `T_rebite` が分かれる。
**「R に在る」と「取り戻した」は別物であり、数字がそれを区別する。**

### 3. `neg_missing_provenance` — 出自不明の断片

```text
Section A. The codeword K00 equals 100. Section B was pasted from an unrecorded source.
                                        ^^^^^^^^^^^^^^ source_uri="" の unit
```

**人間が見て失敗すべき理由**: 貼り付け元が記録されていない断片は provenance を完成させようがない。

| arm | provenance | recall_vis | 期待 | 実測 |
|---|---:|---:|---|---|
| raw_full | **0.50** | 1.00 | 全 arm で 1.0 未満 | ✅ 一致 |
| length_pi | **0.50** | 1.00 | 同上 | ✅ 一致 |
| rule_pi | **0.50** | 1.00 | 同上 | ✅ 一致 |
| rule_pi_rebite | **0.50** | 1.00 | 同上 | ✅ 一致 |

provenance の欠損が recall の欠損として誤報告されないこと（recall は 1.00 のまま）も
テストで固定した。

---

## offline matrix 実データ

`artifacts/phase1/arm_differentiation.json`（再生成: `python scripts/run_offline_arm_matrix.py`）

```text
n_total = 44   (workload 32 + negative_control 12)
negative_control_report: n_checked = 12, violations = none
workload means: recall_vis=1.0  recall_rec=1.0  provenance=1.0   ← 汚染なし
```

負例は **workload の平均や arm 差別化指標に混ぜていない**。
`summarize_rows` の means と `length_vs_rule_diff_families` / `rule_pi_sequences` は
workload 行のみで計算する。負例の実測値は `negative_control_report.observed` に全行掲載される
（隠していない）。

`validate_matrix_doc` は以下を artifact レベルで強制する。

- `negative_control_report.n_checked > 0`
- `violations` が空でなければ **検証エラー**（測定器が報告すべき失敗を報告しなかった、という意味）
- schema 側でも `violations` を `maxItems: 0` にした

---

## 変更していないもの

| | |
|---|---|
| `TBD_CALIBRATE` | 未変更 |
| profiler の feature 定義 | 未変更（`malformed_json` +0.8 もそのまま） |
| rule-Π / length-Π の routing rule | 未変更 |
| operator の実装 | 未変更 |
| 既存 8 workload family の document | byte-identical（`test_workload_documents_were_not_modified` で固定） |
| 有料 runner / billed 経路 | 未変更 |

`_Seg` に `source_uri` の任意上書きを 1 つ足しただけが、既存コードへの唯一の変更である
（デフォルト `None` = 従来どおり）。

---

## 作業中に確認した挙動（注意点）

**gold unit id は lineage 経由でしか残らない。** CUT が子 unit に新しい id を振るため、
`visible_unit_ids` や R の `unit_id` を gold id と直接比較しても一致しない。
metric 層（`metrics_from_transformed`）は `root_ids_of` で `parent_unit_id` を辿って解決しており、
これが正しく効いているからこそ `recall_vis=0.50` が出る。

最初に書いたテストは raw id 一致を仮定していて落ちた。テスト側を metric と同じ解決方法へ直した。
**今後 R や visible の id を gold と突き合わせるコードを書くときは、必ず `root_ids_of` を通すこと。**

---

## 未カバーの領域（正直な限界）

**`recall_rec` が 1.0 未満になるケースは作れていない。**

現行 operator は省略した unit を必ず R へ記録する（CUT の budget 省略、UNTANGLE の隔離、
REDUCE の dedupe / aggregate / whitespace、すべて `add_r_entry`）。
`recoverable=False` を立てる経路も存在しない。したがって **arm 経由で「R にも残らない消失」を
発生させることは、operator を変更しない限り不可能**である。

- 本作業の範囲では operator を変更しないため、未カバーのまま残す
- 指標側が `recall_rec < 1.0` を返せること自体は
  `test_recall_can_fail_when_evidence_is_lost`（`metrics_from_transformed` 直接呼び出し）で
  既に固定済み
- arm 経由で検証したい場合は「R に記録しない省略」を行う operator か、
  `recoverable=False` を立てる経路が必要。これは別タスク

---

## 追加したテスト

`tests/test_negative_controls.py`（21 test、すべて無条件アサーション）

| 区分 | test |
|---|---|
| 分離 | 負例が workload set に入っていない / 既存 document が byte-identical / 負例が packet 契約を満たす |
| 同一 matrix | 4 arm 揃っている / `case_kind` が付く / workload 平均を汚さない |
| 証拠喪失 | `recall_vis` が 0.5 へ落ちる / 落ちた unit が lineage 経由で R に解決する |
| R vs 回収 | re-bite が回収して `T_rebite>0` / 回収できない場合は 0.5 のまま `T_rebite==0` / 2 例の対比 |
| provenance | 全 arm で 0.50 / recall として誤報告されない |
| artifact | report が出る・validation を通る / **改竄検知**（負例が失敗を報告しなくなったら validation が落ちる） |
| その他 | 決定性 / 各負例が人間可読な理由を持つ / matrix を介さない直接呼び出しでも同じ数字 |

既存テスト 1 件を更新: `test_provenance_is_arm_independent` は
「raw_full の provenance 集合 == {1.0}」を要求していたが、`neg_missing_provenance` で
raw_full が**正しく 0.5 を出す**ようになったため衝突した。
arm 間の独立性（全 arm で同一）は全行に対して維持し、`{1.0}` の要求は workload 行に限定した。
弱化ではなく、適用範囲の明確化である。

---

## 実行した検証

```text
pytest                          398 passed, 3 skipped   （base: 377 passed, 3 skipped）
ruff check src tests            All checks passed
mypy src                        Success: no issues found in 82 source files
scripts/run_offline_arm_matrix.py   exit=0, rows=44
scripts/validate_artifacts.py   Validated 5 artifacts; failures=0
```

テストだけでなく **offline matrix の実データ**（`artifacts/phase1/arm_differentiation.json`）
上でも全 12 行の負例が期待どおりの値を出していることを確認済み。

---

## 判定

```text
NEGATIVE_CONTROLS_GREEN
```

- 証拠を失ったケースで数字が実際に 1.0 未満になる ✅
- R へ移した場合と re-bite で取り戻した場合の違いが数字に現れる ✅
- provenance 欠損が 1.0 から下がる ✅
- offline matrix の実データで確認済み ✅
- 期待値は測定前に宣言し、後から結果に合わせていない ✅

**ここで停止する。** benchmark 全体の拡張、canonical case pool の追加、
token-length matching、threshold 較正には進んでいない。
