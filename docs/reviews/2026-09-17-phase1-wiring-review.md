# Phase 1 wiring レビュー（Grok 差分）

- レビュー対象: `docs/hand_over/PHASE1-WIRING-GROK.md` が示す Phase 1 配線差分
- ベース: `fix/phase1-foundation-packet-contract` @ `5ecf1a0`（Claude foundation）
- レビュー実施日: 2026-09-17
- レビュー種別: read-only レビュー → 指摘事項を修正 → 本書へ記録
- 有料 API: **未使用**。`TBD_CALIBRATE`: **未変更**
- 修正後 commit: `a145bf5`

---

## 総評

**配線そのものは本物である。** profiler は実接続され、operator は実行され、payload は実際に変化する。
Claude foundation §11 で引き継いだ `parent_unit_id` 鎖の解決も `root_ids_of()` で正しく実装されている。

ただし初回 `PHASE1_OFFLINE_READY` は**時期尚早**だった。arm 間比較を歪める欠陥が 3 件（うち 1 件は P0）あり、
報告されていた matrix 数値のうち「差別化」を示す指標は実態の 4 倍に膨らんでいた。

修正後は判定を支持できる。

---

## 検証済み（問題なし）

| 項目 | 確認方法 |
|---|---|
| profiler 接続 | `run_phase1_matrix` が case ごとに 1 回計測し 4 arm へ同一 vector を配布。`profiler_source_unit` は payload+query のみ |
| operator 実行 | `malformed_mixed` rule_pi が UNTANGLE で T_total 20→12、`sparse_anomaly` length_pi が REDUCE で 100→54 |
| parent chain | `root_ids_of` / `lineage_parent_ids` が CUT 子・REDUCE 集約・INTEGRATE 結合をすべて root へ解決（foundation P1-8 解消） |
| INTEGRATE ID 規約 | `rebuild_visible_from_units` へ統一。他 operator と一致（foundation P1-7 解消） |
| `recoverable_evidence_ids` | `constraints.py` の既定が `gold_ids` → `[]` に修正され、R 由来 ID が union される |
| T_total 一意性 | `validate_matrix_doc` が行単位で bucket 合計と `call_id` 重複を検査 |
| 失敗行の扱い | 分母に残り、`n_excluded` を明示 |
| ゲート | ruff / mypy / pytest / schema / artifact validation すべて green |

---

## 修正した指摘

### P0 — raw_full だけ provenance=0.0（比較を無効化していた）

**問題**
`raw_full` の adapter 出力に `units` が無いため、`metrics_from_transformed` が `units=[]` を受け取り
`vis_units` が空・`vis` が非空となって `elif vis: prov = 0.0` に落ちていた。

```
修正前 provenance by arm:
  raw_full [0.0]   length_pi [1.0]   rule_pi [1.0]   rule_pi_rebite [1.0]
```

**なぜ結果を歪めるか**
ロック済み制約は `Prov ≥ η = 0.95`。この指標を制約判定へ回すと **baseline である raw_full が 100% 失格し、
候補 arm は全通過**する。arm の性質ではなく「adapter がどのフィールドを埋めたか」で決まっており、
fairness audit が防ぐべき類型そのもの。現 matrix は `constraints_ok` を計算していないため即座には
発火しないが、`mean_provenance=0.75` は既に無意味な数値だった。

**該当**: `src/bite_eval/baselines/raw_full.py`

**修正**: `extra` に `units` を追加。全 arm が同一の unit graph を公開する。

**確認**: `test_provenance_is_arm_independent`（全 arm の provenance 集合が一致すること）、
`test_raw_full_exposes_the_same_unit_graph_as_candidates`。修正後は全 arm で `1.0`。

---

### P0 — 全 unit を quarantine しても payload に本文が残っていた

**問題**
`payload_text_from_packet` の最終 fallback が `extract_text(packet)`（＝元 document）だった。
UNTANGLE が全 unit を R へ隔離すると `units=[]` / `visible_evidence=[]` になり、fallback が発火して
**隔離したはずの本文をそのまま payload として返していた**。

```
修正前 rule_pi:
  visible_unit_ids = []          ← 何も可視でない
  R entries        = 1           ← 隔離済み
  payload_text     = 'ERROR: secret_token=ZZ9 value=42'   ← 隔離した本文がそのまま
```

**なぜ結果を歪めるか**
foundation P0-5（ID は visible だが実体は payload 外）の**裏返し**である。
「R へ移した」と記録しながら本文は target model へ送られる。evidence integrity の主張が成立しない。

**該当**: `src/bite_eval/arm_runtime.py::payload_text_from_packet`

**修正**: packet が unit graph を持つ場合（`units` キーが存在、または `visible_evidence` が list）は、
graph が空なら payload も空を返す。document への fallback は unit graph を持たない legacy packet のみ。

**確認**: 修正後は `rule_pi` payload=`''`、`rule_pi_rebite` が回復して payload 復元＋`T_rebite=8`。
`test_rule_pi_rebite_recovers_query_relevant_omission`。

> **補足（2 つのバグが相殺していた）**: 下記 P1-1 の修正で `rule_pi_rebite` の packet に `document` を
> 載せた結果、この fallback が発火するようになり本欠陥が表面化した。逆に言えば、re-bite が
> 発火していたのは「packet に document が無く payload が空に見えた」ためであり、
> 設計どおりの理由ではなかった。

---

### P1-1 — payload 再構成で空白が変わり、no_op 判定が壊れていた

**問題**
候補 arm は visible unit の text を `"\n"` 連結して payload を作る一方、`raw_full` は document を
そのまま送っていた。

```
clean_local  raw    : 'Section A. ... equals 100. Section B filler...'
             rule_pi: 'Section A. ... equals 100.\nSection B filler...'
             R=0  loss=0  status=transformed   ← 何も削っていない
```

`clean_local` / `dependency_chain` / `dense_cross_reference` の 3 family が
**R 空・loss ledger 空・unit 除去ゼロなのに `transformed`** と記録されていた。

**なぜ結果を歪めるか**
- `n_transformed` と `raw_vs_candidate_diff_payload` が過大（実測 4 倍）
- `is_no_op` が `payload == original_text` 比較のため信頼できない
- billed run へ持ち込むと、同一内容なのに raw と候補で prompt が異なる。
  EVAL-04 が wrapper で潰したのと同じ交絡

**該当**: `src/bite_eval/arm_runtime.py`, `src/bite_eval/baselines/rule_pi_rebite.py`

**修正**: `_reconstruct_from_document()` を追加。unit が document の逐語スライスである場合
（CUT / UNTANGLE のような text-preserving 経路）は document を再スライスし、**元の separator を保持**する。
REDUCE / INTEGRATE のように text を書き換える operator では `None` を返して従来の join に fall back。
除去された span が挟まる gap は出力しない（削除済み本文の再混入防止）。
`rule_pi_rebite` の再構成 packet にも `document` を載せ、`rule_pi` と同一経路にした。

**確認**: `test_no_op_arm_payload_is_byte_identical_to_raw`（R と loss ledger が空なら payload hash は
raw と一致し `status=no_op` であること）、`test_arm_differentiation_is_backed_by_real_removal`
（payload が raw と異なるなら R か loss ledger に記録があること）。

---

### P1-2 — re-bite テストがガードで空回りしていた

**問題**

| test | 症状 |
|---|---|
| `test_rebite_token_accounting_in_matrix` | `if payload差分あり:` でガード。現 matrix では **一度も if 節に入らない**（完全に空回り） |
| `test_rule_pi_rebite_recovers_query_relevant_omission` | `or "secret_token" in payload` の逃げ道＋`>= 0`（恒真）。厳格な検査は `if` の中 |
| `test_rebite_bounded_and_no_repeat_fetch` | 同上 |

実際に走らせると recovery は発火していた（capability 自体は本物）が、**退行しても静かに空回りへ変わる**。

**修正**:
- 2 つの fixture テストを無条件アサーションへ。`steps` 非空、`outcome=="success"` 存在、
  `rebite_tokens > 0`、回復 unit が payload に到達、を必ず検査
- matrix テストは双方向の不変条件へ変更（payload 一致 ⇔ `T_rebite == 0`）。
  片方向だけだと現 matrix で空回りするため

---

### P2 — gold / family ラベルが operator packet に同乗していた

**問題**
`execute_sequence` は context から `gold_*` / `oracle_*` / `family` を除去していたが、
**packet には `gold_answer` / `gold_evidence_ids` / `family` が残ったまま** `apply_sequence` へ渡っていた。
コード内コメントは「Operators must not see gold / oracle / family」と主張していた。

現在どの operator も読んでいない（grep 確認済み）ため潜在的だが、主張と実態が食い違っていた。

**修正**: `scrub_eval_only_keys()` を追加し `ensure_operator_packet` / `execute_sequence` の双方へ適用。
**unit 解決（＝ gold ID の実体検証）を済ませてから** scrub するので、evidence-id 契約は維持される。

**確認**: `test_operator_packet_carries_no_gold_or_family_labels`。

---

### P2 — matrix runner が Windows コンソールで落ちていた

`scripts/run_offline_arm_matrix.py` が markdown summary を stdout へ echo しており、
含まれる em dash が cp932 で `UnicodeEncodeError` を起こす。**例外により後続の self-check
（`raw_vs_candidate_diff_payload <= 0` などの FAIL 判定）が丸ごとスキップ**されていた。
handover の再生成コマンドが著者環境で失敗する状態。

**修正**: markdown の echo を削除し、要約数値の print に置換。self-check が必ず走る。

---

## matrix 数値の訂正

配線検証であり研究結論ではない。8 family × 1 instance × 4 arm = 32 行。

| 指標 | Grok 報告 | 修正後 | 備考 |
|---|---:|---:|---|
| n_total | 32 | 32 | — |
| n_failed | 0 | 0 | — |
| n_pass_through | 8 | 8 | raw_full |
| **n_transformed** | **16** | **4** | 空白差を transformed と誤判定していた |
| **n_no_op** | **8** | **20** | 同上 |
| **raw_vs_candidate_diff_payload** | **16** | **4** | 同上 |
| **mean_provenance** | **0.75** | **1.0** | raw_full の 0.0 が混入していた |
| rule_pi_sequences | `['CUT']`, `['CUT','UNTANGLE']` | 同左 | 変化なし |
| length_pi ≠ rule_pi | 3 family | 3 family | 変化なし |
| pytest | 372 passed / 3 skipped | **377 passed / 3 skipped** | — |

修正後に実際に変換が起きている 4 行（すべて R 非空）:

| case | arm | sequence | R | T_total（raw 比） |
|---|---|---|---:|---|
| sparse_anomaly-000 | length_pi | CUT, REDUCE | 12 | 54（raw 100） |
| adversarial_omission-000 | length_pi | CUT, REDUCE | 1 | 48（raw 85） |
| malformed_mixed-000 | rule_pi | CUT, UNTANGLE | 1 | 12（raw 20） |
| malformed_mixed-000 | rule_pi_rebite | CUT, UNTANGLE | 1 | 12（raw 20） |

---

## handover の記述訂正（修正していない／記録のみ）

### rule-Π の差別化は、同じ差分で追加された profiler ルール 1 本に依存している

実測 morphology（`HIGH=0.66`）:

| family | a | r | k | 発火 |
|---|---:|---:|---:|---|
| malformed_mixed | **0.80** | 0.00 | 0.00 | UNTANGLE |
| sparse_anomaly | 0.00 | 0.48 | 0.00 | — |
| 他 6 family | 0.00 | ≤0.25 | 0.00 | — |

`a=0.80` は `src/bite_ingestion/profilers/deterministic.py` にこの差分で新規追加された
`malformed_json` 判定の **`+0.8`** が唯一の発生源である。これが無ければ全 family で `a=0.0` となり、
rule_pi は 8/8 で `['CUT']` 固定 — morphology 由来の差別化はゼロになる。

handover の「`TBD_CALIBRATE`: **未変更**」は字義どおりには正しい（`TBDCalibrate` dataclass は無傷）が、
**threshold ではなく feature 側を編集して routing 挙動を変えている**ため、そのままでは誤解を招く。
`+0.8` は `HIGH=0.66` を 1 手で跨ぐ値である。

malformed JSON の検出自体は morphology 信号として妥当なので**ルールは変更していない**。
ただし以下は Phase 1 の結果を読む際の前提として明記する必要がある。

- rule-Π の差別化は **1/8 family** でのみ発火する
- `k=0.00` が全 family のため **INTEGRATE は一度も発火しない**
- `r` の最大が 0.48 < 0.66 のため **REDUCE も rule_pi では一度も発火しない**
- rule_pi が実行した operator は CUT と UNTANGLE(1 case) のみ。
  REDUCE / INTEGRATE の配線は unit test でしか覆われていない

### rule-Π が length-Π より「何もしない」ケースがある

`sparse_anomaly` / `adversarial_omission` では rule_pi が `no_op`、length_pi が `CUT+REDUCE` で
実際に圧縮している（100→54, 85→48）。差別化はしているが、方向としては
**morphology-aware が length-only より少なく動いている**。サマリの書き方には注意が要る。

### matrix 上で re-bite は一度も発火しない

全 32 行で `T_rebite=0`、`rule_pi_rebite` の payload は 8 case すべて `rule_pi` と同一。
handover の未解決欄に正直に記載されている。re-bite の課金経路は専用 fixture テストでのみ覆われる。

---

## 指標が定数である件（未解決）

修正後も matrix 全 32 行で `recall_vis = recall_rec = 1.00` である。
matrix には evidence integrity 検出が**失敗しうる case が 1 つも無い**ため、
「検出が働く」ことではなく「発火しない」ことしか示せていない。

対処として `test_recall_can_fail_when_evidence_is_lost` を追加し、
`metrics_from_transformed` が以下を返すことを固定した。

- gold unit が R 無しで消失 → `recall_vis=0.5`, `recall_rec=0.5`
- 同じ消失が R 経由 → `recall_vis=0.5`, `recall_rec=1.0`

ただし **matrix 自体に負例 family を入れるべき**であり、これは未着手。

---

## 追加した regression test

`tests/test_phase1_wiring.py`

| test | 目的 |
|---|---|
| `test_provenance_is_arm_independent` | 全 arm の provenance が同一基準（P0-1 の回帰防止） |
| `test_raw_full_exposes_the_same_unit_graph_as_candidates` | baseline が unit graph を公開する |
| `test_no_op_arm_payload_is_byte_identical_to_raw` | 何も除去していないなら payload hash が raw と一致し `no_op` |
| `test_arm_differentiation_is_backed_by_real_removal` | payload 差分は必ず R か loss ledger で説明できる |
| `test_recall_can_fail_when_evidence_is_lost` | recall が 1.0 以外も返せる（指標が定数でない） |
| `test_operator_packet_carries_no_gold_or_family_labels` | gold / family の scrub |

既存テストの強化（弱化ではない）:

- `test_rule_pi_rebite_recovers_query_relevant_omission` — 逃げ道と恒真アサーションを除去し無条件化
- `test_rebite_bounded_and_no_repeat_fetch` — 成功・課金・provenance を無条件化
- `test_rebite_token_accounting_in_matrix` — 双方向の不変条件へ（空回り解消）

---

## 実行した検証

```text
pytest                          377 passed, 3 skipped   （修正前 372 passed, 3 skipped）
ruff check src tests            All checks passed
mypy src                        Success: no issues found in 82 source files
schema (source_unit / evidence_packet / phase1-offline-matrix)   ok
scripts/validate_artifacts.py   Validated 5 artifacts; failures=0
scripts/run_offline_arm_matrix.py   exit=0（self-check 通過）
```

**注意**: `scripts/checksums.py` は working tree の未追跡 artifact も
`artifacts/SHA256SUMS.txt` へ取り込む（既知・Claude foundation §9 と同じ）。
ローカル実行後の差分は commit していない。

---

## 判定

```text
PHASE1_OFFLINE_READY
```

修正後は支持できる。ただし以下を Phase 1 の結果解釈の前提として明示すること。

1. rule-Π の差別化は `malformed_json` (+0.8) 由来で **1/8 family** のみ
2. **REDUCE / INTEGRATE は rule_pi では未発火**（unit test のみ）
3. **re-bite は matrix 上で未発火**（fixture test のみ）
4. 全行で recall が 1.00 の定数。負例 family が必要
5. canonical case pool は 2 件のまま、token-length matching は未実装
   （Claude foundation §10 から継続）

**この判定は「offline matrix の配線が正しく動く」であって、
「morphology-aware が length-only を上回る」ではない。**
上記 1–4 が残る限り、本 matrix から architecture superiority は一切主張できない。
