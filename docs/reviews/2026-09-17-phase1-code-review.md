# Phase 1 Code Review

- 対象リポジトリ: [`nyattoh/bite-ingestion`](https://github.com/nyattoh/bite-ingestion)
- レビュー対象 commit: **`origin/main` = `801b40d`**（PR #14 `cursor/eval-05-add-ci-b554` マージ後）
- レビュー実施日: 2026-09-17
- 目的: Phase 1 offline comparative experiment 着手前の妥当性審査
- 前提文書: [`docs/reviews/2026-09-17-external-evaluation.md`](./2026-09-17-external-evaluation.md)（先に通読済み）
- 本レビューでのコード変更: **なし**（read-only。PR / merge / push / 有料API呼び出し / threshold 変更なし）

## 検証方法

静的読解に加えて、**offline のみ**で以下を実行し挙動を実測した（有料API未使用）。

- `pytest`（`origin/main`, Python 3.11）: **213 passed / 3 skipped** — CI green は再現できた
- 各 arm の `run()` を 8 family の packet に対して直接実行し、payload 長・proposed sequence・policy が受け取る morphology/budget を実測
- `apply_sequence()` を pilot packet に直接適用し、`visible_evidence` / `R` / `loss_ledger` の遷移を実測
- `bite_bench` の全 renderer を実行し、surface への gold 漏洩を実測

> **注記（未確認事項ではなく手続き上の注意）**: レビュー開始時点で、ローカル作業ツリーは `origin/main` より **19 commit 遅れ**ており、EVAL-01 / 02 / 04 / 05（PR #11–#14）が入っていなかった。本レビューは `origin/main` を隔離 worktree に取得して実施している。作業ツリーの同期は未実施（こちらでは変更しない）。

---

## Executive Summary

1. **Phase 1 で比較予定の 4 arm のうち 3 つが、payload をまったく変換していない。** `raw_full` / `length_pi` / `rule_pi` / `rule_pi_rebite` はいずれも `visible_evidence = 元documentそのもの` を返す。policy は operator sequence を **提案するだけ**で、CUT / UNTANGLE / REDUCE / INTEGRATE は一度も実行されない。8 family 全てで 4 arm の payload 長が完全一致することを実測で確認した。この状態で Phase 1 を回すと「差が出なかった」のか「変換していないから差が出ようがなかった」のかを事後に区別できない。

2. **morphology profiler が評価経路に一度も接続されていない。** `DeterministicMorphologyProfiler` は定義・export されているだけで、`src/` 配下のどこからも呼ばれていない。`rule_pi` が受け取る morphology は全 packet で `{}`（実測）。結果、`rule_pi` の出力は全 family で定数 `['CUT']` になり、**length_pi より差別化されていない**。「morphology-aware が length-only を上回るか」という C2 の中心仮説を、現状のコードは原理的に評価できない。

3. **BITEBench の renderer 6 種すべてが、surface text に gold answer と required evidence ID を埋め込んでいる。** `answer = 'E42'` / `INFO gold_answer=E42` / `# answer: E42` / JSON の `"answer"` と `"required_evidence_ids"` など。BITEBench surface を target model 入力に使った瞬間、全 arm の Q が飽和し比較が無意味になる。既存の漏洩テストは `OPTIMAL_ROUTE=` / `route_label=` しか見ておらず、この漏洩を検出しない。

4. **evidence recall が payload から算出されていない。** EVAL-02 で `TransformedPacket` は導入されたが、truncation 時に「可視 ID は保持する」と明示的に決め打ちしており（`billed_runner.py:410-421`）、その evidence が実際に payload 内に残っているかの検査がない。さらにこの挙動は `test_bug1_truncation_preserves_visible_evidence_recall` が `recall_vis == 1.0` として**固定してしまっている**。これは本レビュー依頼 1 の「IDはvisibleだが実体はpayload外」という false-positive recall そのものである。

5. **operator を pilot packet 形式に適用すると、evidence が 100% 消えたうえで R にも loss ledger にも記録されない。** `CUT` 適用後の実測値は `visible_evidence: []`, `R: {"entries": []}`, `irreversible_loss_ledger: []`。operator 層は `units` / Mapping 形式の evidence を前提とするのに対し、pilot packet の `visible_evidence` は文字列 ID のリストであるため、`synthesize_units_from_evidence` が全要素を silently skip する。silent data loss の定義そのものに該当する。

6. **`T_total` という同名フィールドが、リポジトリ内で 2 つの異なる意味で使われている。** `docs/token-accounting.md` は「full cost、**決して** target-input-only ではない」と定義するが、billed 経路の `BilledInstanceResult.T_total` は target 1コールの provider usage のみで、profiler / router / operator / re-bite bucket を一切持たない。現状は決定論変換で各 bucket が 0 のため数値上は一致するが、re-bite を含む Phase 1 では必ず食い違う。

---

## Readiness

# **BLOCKED**

総合点や完成度で判断していない。**上記 1 / 2 / 3 / 4 / 5 はいずれも単独で Phase 1 の比較結果を無効化する**ため、この判定になる。

- 1・2 が残ったまま Phase 1 を回すと、出てくる数値は「4 arm が同一入力を処理した結果」であり、morphology の効果とは無関係である。
- 3 が残ったまま BITEBench surface を使うと、Q はすべて 1.0 付近に張り付き、arm 間比較が成立しない。
- 4・5 が残ったまま operator を接続すると、evidence integrity 指標が現実と逆方向にずれる（消えた証拠を visible と報告する／消えた証拠をどこにも記録しない）。

逆に言えば、**アーキテクチャの作り直しは不要**である。operator 層・recovery 層・token ledger・grammar・leak guard の設計品質は高く、欠けているのは「packet 形式の統一」と「pipeline の実接続」である。P0 は 7 件、いずれも局所修正で閉じられる範囲にある。

---

## P0 — Phase 1 開始前に必須

### P0-1. 比較対象の 4 arm が同一 payload を出力する（operator が実行されない）

**問題**
`length_pi` / `rule_pi` / `rule_pi_rebite` は policy から operator sequence を受け取るが、それを適用せず `visible_evidence` に元の document をそのまま入れて返す。`raw_full` も同じ document を返すため、4 arm の payload は同一。

**該当ファイル・関数**

- [`src/bite_eval/baselines/rule_pi.py:42-56`](../../src/bite_eval/baselines/rule_pi.py) — `RulePiBaseline.run()`：`text = extract_text(packet)` → `visible_evidence=text`
- [`src/bite_eval/baselines/length_pi.py:42-55`](../../src/bite_eval/baselines/length_pi.py) — `LengthPiBaseline.run()`（同型）
- [`src/bite_eval/baselines/rule_pi_rebite.py:111-133`](../../src/bite_eval/baselines/rule_pi_rebite.py) — `RulePiRebiteBaseline.run()`（同型）
- [`src/bite_eval/baselines/raw_full.py:51-58`](../../src/bite_eval/baselines/raw_full.py)
- `apply_sequence` の呼び出し元は [`src/bite_eval/baselines/universal_reduce.py:56-63`](../../src/bite_eval/baselines/universal_reduce.py) **のみ**

**なぜ結果を歪めるか**
`EvalHarness.run_smoke()` は `T_target_in = estimate_tokens_char4(visible_evidence)` を計上する（[`eval_harness.py:148-162`](../../src/bite_eval/harness/eval_harness.py)）。payload が同一なら `T_target_in` も同一になり、**C1（token 改善）と C3（net saving）は構造的に必ず「差なし」になる**。これは仮説の反証ではなく測定の不在であり、しかも両者は artifact 上で区別できない。

実測（8 family × 1 instance、`visible_evidence` の文字数）:

| family | doc chars | raw_full | length_pi | rule_pi | rule_pi_rebite |
|---|---:|---:|---:|---:|---:|
| clean_local | 91 | 91 | 91 | 91 | 91 |
| repeated_records | 278 | 278 | 278 | 278 | 278 |
| sparse_anomaly | 397 | 397 | 397 | 397 | 397 |
| dependency_chain | 65 | 65 | 65 | 65 | 65 |
| malformed_mixed | 77 | 77 | 77 | 77 | 77 |
| dense_cross_reference | 57 | 57 | 57 | 57 | 57 |
| adversarial_omission | 339 | 339 | 339 | 339 | 339 |
| texture_swap | 22 | 22 | 22 | 22 | 22 |

**最小修正案**
各 baseline の `run()` で `decision.sequence` を `apply_sequence()` に通し、その出力 packet の `visible_evidence` / `R` / `tau` を返す。`raw_full` のみ従来どおり無変換。ただし P0-3 を先に直さないと `apply_sequence` は evidence を消すので、**P0-3 とセットで実施する**。

**修正確認方法**
`assert` 相当の機械検査を artifact 生成時に入れる：同一 packet に対する `length_pi` と `rule_pi` の `sha256(payload_text)` が少なくとも 1 family で異なること、かつ `raw_full` の payload と `rule_pi` の payload が一致する場合は行に `status=no_op` が立つこと。

---

### P0-2. morphology profiler が評価経路に接続されていない（rule_pi が morphology-blind）

**問題**
`DeterministicMorphologyProfiler` は `src/` 内のどこからも呼ばれていない。`rule_pi` は `extract_morphology(packet, context)` で morphology を取りに行くが、これは `packet["morphology"]` / `packet["m"]` を探すだけで、pilot packet にも BITEBench bundle にもそのキーは存在しない。

**該当ファイル・関数**

- [`src/bite_ingestion/profilers/deterministic.py`](../../src/bite_ingestion/profilers/deterministic.py) — 呼び出し元ゼロ
- [`src/bite_eval/interface.py:124-137`](../../src/bite_eval/interface.py) — `extract_morphology()`：見つからなければ `{}` を返す（fallback も警告もなし）
- [`src/bite_ingestion/policies/rule_policy.py:84-104`](../../src/bite_ingestion/policies/rule_policy.py) — `_f(morphology, "b")` 等はすべて `default=0.0`

**なぜ結果を歪めるか**
morphology が `{}` なら `b=a=r=k=l=u=0.0` となり、`rule_policy` の分岐は CUT のみ include、UNTANGLE / REDUCE / INTEGRATE は全 omit に固定される。実測でも 8 family すべてで `rule_pi → ['CUT']`。一方 `length_pi` は char 長で 3 バンドに分かれる。つまり **現状の「morphology-aware arm」は length-only arm より情報量が少ない**。この状態の C2 は、どちらに転んでも morphology の効果を示さない。

さらに `extract_morphology` が黙って `{}` を返すため、profiler の未接続が artifact のどこにも現れない。

**最小修正案**
harness（または各 baseline の入口）で `DeterministicMorphologyProfiler().profile_report()` を呼び、`packet["morphology"]` に注入してから policy へ渡す。同時に `extract_morphology` が空を返したら `status=failed` / `reason=morphology_missing` にして fail-closed にする（黙って 0 ベクトルで進ませない）。profiler は deterministic なので token は 0 だが、`cpu_ms` は ledger の `profiler` 行に載せる。

**修正確認方法**
`rule_pi` の `proposed_sequence` が family 間で 2 種類以上に分かれること、および `baseline_trace.decision.rules_fired` に実測 morphology 値（`observed`）が記録されていることを test で固定する。`morphology={}` を渡したら例外/failed になる negative test も置く。

---

### P0-3. operator を pilot packet に適用すると evidence が全消失し、R にも loss ledger にも残らない

**問題**
operator 層は `packet["units"]`、なければ `visible_evidence` の **Mapping 要素**から unit を合成する。pilot packet の `visible_evidence` は `["repeated_records-e0"]` のような**文字列 ID のリスト**なので、`synthesize_units_from_evidence` の `if not isinstance(item, Mapping): continue` で全要素が捨てられ、`units = []` になる。operator は「入力が空だった」として正常終了する。

**該当ファイル・関数**

- [`src/bite_ingestion/operators/base.py:94-129`](../../src/bite_ingestion/operators/base.py) — `synthesize_units_from_evidence()`（非 Mapping を silently skip）
- [`src/bite_ingestion/operators/base.py:132-140`](../../src/bite_ingestion/operators/base.py) — `ensure_units()`
- [`src/bite_eval/pilot/families.py:38-53`](../../src/bite_eval/pilot/families.py) — `_base()` が `visible_evidence: list[str]` を生成
- operator 層は `packet["document"]` を一切参照しない

**なぜ結果を歪めるか**
実測（`repeated_records` packet に `apply_sequence([CUT])`）:

```
入力:  visible_evidence = ['repeated_records-e0']   document = 278 chars
出力:  visible_evidence = []
       R                = {"entries": []}
       irreversible_loss_ledger = []
       tau.steps[0].omitted_ref = []
```

`universal_reduce` は実際にこの経路を通るため、その payload は実測 **2 文字**（`[]` の JSON 表現）。`T_target_in ≈ 0` となり、**損失ゼロで 100% の token 削減**という artifact が生成される。Phase 1 にこの arm を含めれば、Pareto plot 上で universal_reduce が圧勝する偽の結果が出る。加えて「omitted evidence は必ず R か loss ledger へ移る」という [`docs/03-operator-taxonomy.md`](../03-operator-taxonomy.md) の不変条件が、検出されないまま破れている。

**最小修正案**
2 点セット。
1. pilot / BITEBench packet を operator の入力契約に合わせる：`document` を unit 化し（`unit_id`, `text`, `span`, `source_uri` を持つ Mapping）、`gold_evidence_ids` を実 span に紐づける。
2. `ensure_units()` を fail-closed にする：`visible_evidence` が非空なのに合成 unit が 0 件なら例外を投げる（現在の silent skip をやめる）。

**修正確認方法**
「非空入力 → 空出力」で例外になる test を追加。さらに全 operator に対して `len(visible_units) + len(R.entries) + len(loss_ledger.unit_ids) >= len(input_units)` を検証する property test を置く。

---

### P0-4. BITEBench の全 renderer が gold answer と required evidence ID を surface に埋め込んでいる

**問題**
6 renderer すべてで、正解が本文に literal で出現する。required evidence ID も同様。

**該当ファイル・関数**（[`src/bite_bench/renderers.py`](../../src/bite_bench/renderers.py)）

| renderer | 行 | 漏洩箇所 |
|---|---|---|
| `render_prose_narrative` | `:33` | `f"Canonical answer label: {case.answer}"` |
| `render_table_csv` | `:43` | `f"# answer: {case.answer}"` |
| `render_nested_json` | `:50`, `:55` | `"answer": case.answer`、**`"required_evidence_ids"` も丸ごと** |
| `render_event_logs` | `:67` | `f"INFO gold_answer={case.answer}"` |
| `render_code_config` | `:76` | `f"answer = {case.answer!r}"` |
| `render_mixed_payload` | `:80-84` | 上記 3 種を連結（全部継承） |

加えて全 renderer が `case.question` も本文に埋めている（`:25`, `:43`, `:48`, `:61`, `:73`）。

**なぜ結果を歪めるか**
実測で全 family について `answer in surface == True`、`required_evidence_ids ⊂ surface == True`。target model は推論せずに読み取るだけで正答できるため、**Q が全 arm で飽和し、matched-quality 制約（`Q >= Q_baseline - delta`）が全 arm で自明に成立する**。「どの arm も品質を落とさずに token を減らせた」という誤結論に直結する。required evidence ID の漏洩は、evidence 選択タスクとしての妥当性も壊す。

なお [`src/bite_bench/generator.py:109`](../../src/bite_bench/generator.py) のコメント `# Explicit non-leakage: route labels are metadata only, never embedded as answers.` は、現状のコードに対して事実と異なる。

**最小修正案**
`answer` / `required_evidence_ids` / `question` を surface から除去し、`CanonicalCase.identity_payload()` 側のメタデータにのみ保持する。question は prompt wrapper 側で 1 回だけ与える（現在は本文と wrapper で二重になり token も膨らむ）。

**修正確認方法**
`test_route_label_not_in_surface_as_instruction` を拡張し、全 renderer・全 seed について `case.answer not in text`、`all(eid not in text for eid in case.required_evidence_ids)`、`case.question not in text` を assert する。

---

### P0-5. visible evidence ID が payload の実体と結びついていない（false-positive recall）

**問題**
`_transform_packet()` は truncation 時に「元の visible ID をそのまま残す」と明示的に決め打ちしている。切り落とされた部分に gold evidence があったかどうかは検査されない。切り落とし分は `stable_id()` で作った**新規の合成 ID** で R に入るため、`gold_evidence_ids` とは決して交差しない。

**該当ファイル・関数**

- [`src/bite_eval/pilot/billed_runner.py:410-421`](../../src/bite_eval/pilot/billed_runner.py) — `# BUG 1 FIX: Keep original visible evidence IDs if content still appears in the truncated prefix (which it typically does for synthetic packets).`
- [`src/bite_eval/pilot/billed_runner.py:424-435`](../../src/bite_eval/pilot/billed_runner.py) — 切り落とし分に合成 `unit_id` を採番して `add_r_entry`
- [`src/bite_eval/pilot/billed_runner.py:634-648`](../../src/bite_eval/pilot/billed_runner.py) — `combined_rec_ids = original_rec_ids | r_unit_ids`
- [`src/bite_eval/pilot/constraints.py:101-108`](../../src/bite_eval/pilot/constraints.py) — `metrics_from_instance()` は ID 集合の積しか見ない
- [`tests/eval/test_eval02_unified_transform.py:294-328`](../../tests/eval/test_eval02_unified_transform.py) — **この挙動を `recall_vis == 1.0` として固定している**

**なぜ結果を歪めるか**
双方向に壊れている。

- **visible 側（false positive）**: 400 文字以降に gold evidence があっても、ID は visible に残る → `Recall_vis` が過大。該当 test は `doc = "A" * 500` という、evidence の所在を検証しようがない入力で `recall_vis == 1.0` を要求しており、コメントの `(which it typically does for synthetic packets)` という仮定がそのまま regression として凍結されている。
- **recoverable 側（false negative）**: 失われた本文は合成 ID で R に入るので、`gold_evidence_ids` との積に寄与しない → 本当に回復可能になったかを `Recall_rec` は測れない。

結果、「消えた証拠を visible と報告し、かつ R に入ったとも認識しない」状態になる。EVAL-02 の目的（prompt と visible ID を同一オブジェクトから出す）は形式上達成されているが、**意味上の整合（ID ↔ 実テキスト）は未達**である。

**最小修正案**
evidence ID に span を持たせ（P0-3 の unit 化と同じ作業）、`visible_unit_ids` は「span が `payload_text` 内に残っている unit」だけを含める。payload から消えた unit は、**元の unit_id のまま** R へ移す（合成 ID を新規採番しない）。

**修正確認方法**
`test_bug1_truncation_preserves_visible_evidence_recall` を、evidence を 400 文字境界の前後に置いた 2 ケースに差し替える。前にあるケースは `recall_vis=1.0` かつ R 空、後ろにあるケースは `recall_vis=0.0` かつ `R` に**同じ gold ID**が入り `recall_rec=1.0` になること。さらに「`visible_unit_ids` の全 unit の text が `payload_text` の部分文字列である」を全 arm で検査する共通 assertion を入れる。

---

### P0-6. texture_swap の counterfactual pair が「同一 facts / 同一 answer」を満たしていない

**問題**
`facts_id = f"facts-{i // 2}"` で隣接 index をペアにしているが、隣接 index は codeword も値も gold evidence ID も異なる。

**該当ファイル・関数**
[`src/bite_eval/pilot/families.py:204-220`](../../src/bite_eval/pilot/families.py) — `texture_swap` 分岐

**なぜ結果を歪めるか**
実測:

| instance | facts_id | texture | gold_answer | gold_evidence_ids | doc chars |
|---|---|---|---|---|---:|
| texture_swap-000 | facts-0 | json | **100** | `['texture_swap-e0']` | 22 |
| texture_swap-001 | facts-0 | prose | **101** | `['texture_swap-e1']` | 42 |
| texture_swap-002 | facts-1 | json | **102** | `['texture_swap-e2']` | 22 |
| texture_swap-003 | facts-1 | prose | **103** | `['texture_swap-e3']` | 42 |

同じ `facts_id` のペアで、事実・質問・正解・必要 evidence・長さの**すべて**が異なる。`facts_id` で group by して texture 効果を推定すると、実際には「別問題どうしの難易度差」を texture 効果として読むことになる。長さも 22 vs 42 で ~2 倍あり、token-length matched 条件になっていない。

**最小修正案**
`i // 2` で決まる 1 つの `(code, val)` から 2 つの surface を生成する（現在は `i` ごとに `code`/`val` が動いている）。長さは padding ではなく、tokenizer ベースで揃えるか、揃わない場合は `length_matched: false` を明示して主解析から外す。

**修正確認方法**
「同一 `facts_id` の全 instance について `gold_answer` / `gold_evidence_ids` / `query` が一致する」ことを検査する validator を追加し、benchmark 生成時に必ず通す。

---

### P0-7. `T_total` の定義が 2 つ併存している（full-cost 契約と billed 行の乖離）

**問題**
[`docs/token-accounting.md:26`](../token-accounting.md) は `T_total` を「Full cost — **never** target-input-only」と定義し、`T_profiler + T_router + Σ(T_in + T_out)` の式を置いている。一方 billed 経路の `BilledInstanceResult.T_total` は target 1 コールの provider `total_tokens` のみで、profiler / router / operator / re-bite の bucket を持たない。

**該当ファイル・関数**

- [`src/bite_eval/pilot/billed_runner.py:121-126, 693`](../../src/bite_eval/pilot/billed_runner.py) — `T_total` = provider usage のみ
- [`src/bite_eval/accounting/ledger.py:97-126`](../../src/bite_eval/accounting/ledger.py) — こちらは契約どおりの bucket 合算
- 両者を突き合わせる検査は存在しない

**なぜ結果を歪めるか**
現状は変換がすべて決定論（token 0）なので数値が偶然一致しているが、Phase 1 で `rule_pi_rebite` を入れると re-bite コストが billed 側の `T_total` に**入らない**。同じ `T_total` という名前の列を Phase 1 の集計で比較すると、re-bite ありの arm だけコストが過少計上される。

**最小修正案**
billed 行のフィールドを `T_target_call` にリネームし、`T_total` は `TokenLedger.totals()` の合算値のみに使う。両経路を同じ ledger に集約し、`validate_ledger_totals()` を Phase 1 の集計前に必ず通す。

**修正確認方法**
`rule_pi_rebite` を含む offline 行について `T_total == T_profiler + T_router + T_target_in + T_target_out + T_rebite + T_baseline + T_calls_other` が成立し、かつ `T_rebite > 0` の行が存在することを test で固定する。

---

## P1 — 本実験前に修正推奨

### P1-1. re-bite コストが ledger に届かない

`RecoverEngine._finish()` は回復コストを `packet["accounting"]["rebite_tokens"]` に書き込む（[`engine.py:140-149`](../../src/bite_ingestion/recovery/engine.py)、`rebite_tokens_in_T_total: True` というフラグまで付けている）。しかし `TokenLedger.merge_baseline_accounting()` は `baseline_router_tokens` と `baseline_compressor_tokens` **の 2 キーしか読まない**（[`ledger.py:186-211`](../../src/bite_eval/accounting/ledger.py)）。`rule_pi_rebite` が返す `empty_accounting(extra={"rebite_tokens": 0})` も同様に捨てられる。

harness 側で `T_rebite` に計上されるのは `ctx["stub_rebite_tokens"]` だけで、既定値は 0（[`eval_harness.py:163-176`](../../src/bite_eval/harness/eval_harness.py)）。つまり **`rule_pi_rebite` は追加情報を token コスト 0 で得る**。レビュー依頼 6 の「rule_pi_rebite だけが不公平に追加情報を得ていないか」に対する答えは、現状 **Yes**。

修正: `merge_baseline_accounting` に `rebite_tokens` → `category="rebite"` の行を追加する。

### P1-2. 失敗行が constraints_ok_rate から黙って消える

`measured_rows` は `baseline_status in ("rate_limit","timeout","error","missing_pair","unknown")` と `error is not None` を除外する（[`billed_runner.py:1113-1123`](../../src/bite_eval/pilot/billed_runner.py)）。除外自体は `Q_baseline=0.0` による vacuous pass を防ぐ正しい対処だが、**summary に除外件数を示すフィールドがない**（`n_measured` / `n_excluded` / `n_missing_pair` のいずれも存在しない）。90% が timeout し 10% が完璧でも `constraints_ok_rate = 1.0` / `systematic_fail = False` になる。

[`docs/token-accounting.md:52`](../token-accounting.md) の「Averages must not silently exclude failures without an explicit, documented rule」に反している。

修正: summary に `n_measured` / `n_excluded_by_status`（status 別内訳）を追加し、`decide_gate_c` に除外率を渡す。

### P1-3. C1 / C3 が paired でなく、C2 の母集団が quality 側と食い違う

`_estimate_c123()` は `mean(T_total | raw_full)` と `mean(T_total | compressed)` を**非対応の平均**で比較する（[`billed_runner.py:729-735`](../../src/bite_eval/pilot/billed_runner.py)）。instance_id による join がないため、raw だけ成功した instance と comp だけ成功した instance が混ざる。

さらに `_estimate_c123` の行フィルタは `T_total is None or r.error` のみで、`baseline_status` を見ない。つまり **`measured_rows` から除外された行が C1 / C3 には寄与する**。「品質は測れていないがトークンは改善した」行が confirmatory に入る。

修正: `instance_id` で inner join した paired difference を使い、C1/C3/C2 と constraints を同一の行集合で評価する。

### P1-4. raw_full の Q_baseline 自己参照により、arm 間で制約の厳しさが非対称

`raw_full` は `Q_baseline = 自分の Q` となり（[`billed_runner.py:654-657`](../../src/bite_eval/pilot/billed_runner.py)）、品質制約 `Q >= Q_baseline - delta` を**常に自明に満たす**。一方 compressed 側は raw の Q に対して評価される。両者の `constraints_ok` を `C2: comp_ok >= raw_ok` で比較しているため、compressed 側に一方的に不利なバイアスが入る。

修正: raw_full 行の品質制約を `null`（not_applicable）として記録し、constraint rate の比較から除く。または C2 を「品質制約下での token 差」として定義し直す。

### P1-5. quality 以外の 3 制約が arm と無関係な定数

実測（全 family、`answer` を意図的に不正解にしても不変）:

| family | recall_vis | recall_rec | provenance |
|---|---:|---:|---:|
| adversarial_omission | 0.50 | 1.00 | 1.00 |
| 上記以外の 7 family | 1.00 | 1.00 | 1.00 |

- `recall_rec` は `recoverable_evidence_ids` が既定で `gold_evidence_ids` と同一のため（[`families.py:47-49`](../../src/bite_eval/pilot/families.py)）、**常に 1.0**。実際の recovery を一度も要求しない。
- `provenance` は `packet["provenance_complete_rate"]`（生成時に 1.0 固定）をそのまま返すだけで（[`constraints.py:113-118`](../../src/bite_eval/pilot/constraints.py)）、`TransformedPacket.provenance` は metric に使われない。レビュー依頼 8 の「provenance score が自己申告値だけになっていないか」は **Yes**。
- `recall_vis` は packet に事前記入された値で決まり、arm によらない。

結果、`constraints_ok` は実質 Q の検査のみに退化している。`rho_recoverable=0.90` / `eta=0.95` は現状どんな実装欠陥でも発火しない。

修正: `provenance` は `TransformedPacket.provenance` の実測完全性（span/source_uri が埋まっている visible unit の割合）から算出する。`recall_rec` は実際に R から回復した ID に基づかせる。

### P1-6. `adversarial_omission` の「隠された証拠」は実際には prompt に入っている

`document` に `HIDDEN: {code}={val}` が平文で含まれるのに、`visible_evidence` は半分だけ（[`families.py:183-202`](../../src/bite_eval/pilot/families.py)）。model は全文を読めるので、`recall_vis=0.5` は fiction であり、H4（R 経由の回復）を一度も検証していない。この family を recovery の証拠に使うと誤った主張になる。

### P1-7. INTEGRATE の provenance 規約が他 operator と不整合

`rebuild_visible_from_units()` は `unit_ids = [新しい unit_id]` を入れる（[`base.py:276-282`](../../src/bite_ingestion/operators/base.py)）が、INTEGRATE は `unit_ids = joined_from`（結合元 ID）を入れる（[`integrate.py:192-202`](../../src/bite_ingestion/operators/integrate.py)）。同時に `units[].unit_id` は新 ID のまま。**どのフィールドを読むかで visible unit ID が変わる**ため、operator 順序（INTEGRATE を含む／含まない）で recall の意味がずれる。

### P1-8. CUT は unit_id を毎回振り直すため、arm 間で ID が比較不能

`CutOperator` は分割した各セグメントに `stable_id("u_", packet_id, parent_unit_id, span, seg)` で**新 ID**を採番する（[`cut.py:69-87`](../../src/bite_ingestion/operators/cut.py)）。分割が実質 no-op（1 セグメント）でも ID は変わる。`parent_unit_id` は残るが、metric 層はこの親子鎖を辿らない。結果、CUT を含む arm と含まない arm で `visible_unit_ids` の名前空間が異なり、`gold_evidence_ids` との積が取れない。

修正: metric 計算時に `parent_unit_id` 鎖を root まで解決してから gold と突き合わせる。

### P1-9. no-op が artifact に記録されない

EVAL-04 で no-op 検出の test は入った（`test_no_op_transformation_detection`）が、`TransformedPacket.transformation_note` は `BilledInstanceResult` にも summary にも書き出されない。`status=no_op` フィールドも存在しない。検出はテスト内だけで、**実行 artifact からは no-op かどうか分からない**。

現状 8 family の document は最大 397 文字（`sparse_anomaly`）で 400 文字の閾値に届かないため、`compressed_passthrough` は**全 case で no-op**。かつ EVAL-04 の wrapper 統一により raw と compressed の prompt は完全一致する。つまり今の minimal billed 設定は、**同一 prompt を 2 回課金する**構成になっている。Phase 2 に進む際は要注意。

### P1-10. BITEBench の canonical case が 2 件しかなく、長さ整合が char ベース

- `make_synthetic_case(seed)` は `seed % 2` でしか分岐しないため、seed 0..9 で得られる case は `{syn-case-000, syn-case-001}` の 2 種のみ（実測）。Phase 1 の N を確保できない。
- `length_matched` は `len(text)` の一致で判定（[`generator.py:106`](../../src/bite_bench/generator.py)）。tokenizer ベースではないため、repetitive logs と dense prose の token 数は一致しない。レビュー依頼 7 の「token-length matched 条件を作れるか」は現状 **No**。
- `_pad_to_length` が `"\n# pad ..."` を挿入する（[`generator.py:51-59`](../../src/bite_bench/generator.py)）。`#` 始まりの行は profiler の `s`（構造規則性）特徴を +0.2 する（[`deterministic.py:125-127`](../../src/bite_ingestion/profilers/deterministic.py)）ため、padding が morphology を汚染する。
- `bundle_fingerprint()` は surface text を含まない（[`generator.py:133-141`](../../src/bite_bench/generator.py)）ので、renderer を書き換えても fingerprint が変わらない。benchmark version 管理として機能しない。

### P1-11. length_pi の char / token バンドが暗黙に切り替わる

`extract_budget()` は `n_tokens` が無ければ `char_len = len(text)` を補う（[`interface.py:140-156`](../../src/bite_eval/interface.py)）。`LengthOnlyPolicy` は `n_tokens` があれば `LENGTH_*_MAX`（64 / 256）、無ければ `CHAR_*_MAX`（256 / 1024）を使う（[`length_policy.py:78-89`](../../src/bite_ingestion/policies/length_policy.py)）。**どちらの尺度が使われたかは packet の内容次第**で、混在すると instance 間でバンド定義が変わる。`RuleFire.feature` に `"char_len"` / `"n_tokens"` が残るので監査は可能だが、混在自体を止める仕組みはない。

また `CHAR_SHORT_MAX = 256` は pilot document の長さ範囲（22–397 文字）のほぼ中央にあり、この 1 つの数字で family のバンド割り当てが決まる。`TBD_CALIBRATE` は「synthetic / tests only、not empirical」と明記されており（[`thresholds.py:1-6`](../../src/bite_ingestion/policies/thresholds.py)）**意図的に有利化されてはいない**が、Phase 1 で使うなら calibration set を分離して事前に固定し、sensitivity を報告する必要がある。

レビュー依頼 3 の「threshold が暗黙に有利な値になっていないか」については、**有利化の形跡は見つからなかった**（値は data を見る前にコミットされ、TBD と明示されている）。ただし未較正であること自体が Phase 1 のリスクである。

---

## P2 — 論文化・公開前の改善

- **P2-1**: `UntangleOperator` の被覆不変条件が `assert`（[`untangle.py:178-179`](../../src/bite_ingestion/operators/untangle.py)）。`python -O` で消える。明示的な例外に変える。
- **P2-2**: `_classify_unit` は `ERROR|FATAL|EXCEPTION|TRACEBACK|PANIC` と `ref:` / `#see` を検出したら quarantine する。実ログ・実コードでは大半の unit が隔離されうる（over-quarantine）。閾値・比率の上限が必要。
- **P2-3**: `CutOperator` は `context["max_units"]` が無いと一切 omit しない（[`cut.py:92-94`](../../src/bite_ingestion/operators/cut.py)）。`rule_pi` の現行 sequence は `['CUT']` のみなので、operator を接続しても **token は原理的に減らない**。Phase 1 の期待値設定に影響する。
- **P2-4**: CI（[`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)）に secret scan と「有料API を呼ばないこと」の明示 guard がない。`validate_artifacts` も `artifacts/runs` があるときだけ動く条件付き。
- **P2-5**: `-like` baseline（`hyve_like` 等）の命名は外部評価どおり「Reference heuristics」へ分類し直す。
- **P2-6**: `pyproject.toml` の version `0.0.0` / licence `TBD` / author `TBD`、`_fix_bite12.py` の root 残置、task-pack ZIP の同梱は外部評価の指摘のまま未対応。
- **P2-7**: `dependency_chain` だけ query に出力形式の指示（`example format: 42`）が入っている（[`families.py:138-143`](../../src/bite_eval/pilot/families.py)）。arm 間では同一なので公平性は保たれるが、family 間の prompt engineering 量が不均一。

---

## Fairness Audit

同一 packet・同一 offline harness 経路での比較（`raw_full` / `length_pi` / `rule_pi` / `rule_pi_rebite`）。

| 条件 | 状態 | 根拠 |
|---|---|---|
| 同一 query | ✅ OK | `packet["query"]` を全 arm が共有。BITEBench 側は本文にも question が入る（P0-4） |
| 同一 target model | ✅ OK | billed 経路は 1 つの `ZaiClient` インスタンスを全 method で使用 |
| 同一 system / user wrapper | ✅ OK | EVAL-04 で統一。`_build_messages()` は method を参照しない（`billed_runner.py:474-504`）。`"Compressed document:"` は除去済み |
| 同一 output constraint | ✅ OK | `"Answer with only the final value/string, no explanation."` を全 arm 共通 |
| 同一 timeout / retry | ✅ OK | `timeout_s` / `retry_max` は client 属性で arm 非依存（`zai_client.py:192-260`）。429 は no-retry で統一 |
| 同一 token accounting | ❌ **NG** | billed `T_total` は target のみ、offline `T_total` は full bucket（P0-7）。re-bite は ledger に届かない（P1-1） |
| 同一 recovery budget | ⚠️ **未成立** | `rule_pi_rebite` は `RecoverEngine` を**結線していない**（`recover()` は `source_store`/`state` 未提供時に no-op を返す）。re-bite なしの arm との差が「情報量ゼロ・コストゼロ」なので比較が定義されていない |
| router / operator / recovery コストの単一計上 | ⚠️ 部分的 | `DC-1`（`call_id` 重複検出）は `validate_ledger_totals()` に実装あり。ただし profiler は未接続で常に 0、operator は決定論で 0、re-bite は未計上。**二重計上は現状なし、未計上が問題** |
| length_pi と rule_pi 以外の差が混入しないか | ❌ **NG** | 両 arm とも payload が同一（P0-1）、かつ rule_pi の morphology が `{}`（P0-2）。**そもそも 2 arm の間に差が存在しない** |

**結論**: prompt / model / 実行条件レベルの parity は EVAL-04 で確立された。しかし **arm の中身（payload・routing 情報・recovery）が実装されていない**ため、公平な比較以前に比較すべき対象が存在しない。

---

## Evidence Integrity Audit

`visible → omitted → recoverable → provenance` の遷移。

| 遷移 | 期待 | 実際 | 判定 |
|---|---|---|---|
| truncation で消えた本文 → visible から除外 | 除外される | **除外されない**（元 ID を保持、`billed_runner.py:410-421`） | ❌ P0-5 |
| truncation で消えた本文 → R へ | 元 unit_id で R へ | **合成 ID** で R へ。gold と交差しない（`:424-435`） | ❌ P0-5 |
| CUT / REDUCE / UNTANGLE の omit → R | R + loss ledger に記録 | operator 単体の実装は**正しい**（`cut.py:96-109`, `reduce.py:95-146`, `untangle.py:163-182`） | ✅ 実装は妥当 |
| 上記を pilot packet に適用したとき | 同上 | **全 evidence が消え、R も loss ledger も空**（実測） | ❌ P0-3 |
| visible ID の実体が payload 内に存在するか検証 | 検証あり | **検証なし**。span も部分文字列検査も存在しない | ❌ P0-5 |
| source span / provenance の維持 | 維持 | operator 内では `span` / `parent_unit_id` / `source_uri` を維持。ただし CUT は ID を振り直し（P1-8）、INTEGRATE は規約が異なる（P1-7） | ⚠️ 部分的 |
| provenance score の算出元 | transformed packet | **`packet["provenance_complete_rate"]` の自己申告固定値 1.0**（`constraints.py:113-118`） | ❌ P1-5 |
| recoverable recall の算出元 | 実際の R | `recoverable_evidence_ids` の既定値が `gold_evidence_ids` のため**常に 1.0** | ❌ P1-5 |
| operator の no-op と実変換の区別 | 区別可能 | `transformation_note` はあるが artifact に出力されない。`status=no_op` なし | ❌ P1-9 |

**false-positive recall の有無**: **発生する**。しかも `test_bug1_truncation_preserves_visible_evidence_recall` によって仕様として固定されている。これは本レビューで最も優先度の高い修正対象の 1 つ。

---

## Token Accounting Audit

契約式（[`docs/token-accounting.md`](../token-accounting.md)）:
`T_total = T_profiler + T_router + Σ_c (T_in_c + T_out_c)`

| 項目 | 計上状況 | 備考 |
|---|---|---|
| profiler | 常に 0 | profiler 未接続（P0-2）。決定論なら 0 で正しいが、接続後も `cpu_ms` のみで token 0 を維持すること |
| router（policy） | 常に 0 | 決定論 policy なので DC-2 上は正しい |
| operator / compressor | **未計上** | operator が実行されていない（P0-1）。実行後も token 0（決定論）だが、`T_baseline` bucket は用意済み |
| target input / output | 計上あり | billed は provider usage、offline は char/4 proxy。混在なし（`estimate_source` で区別） |
| re-bite | **未計上** | `accounting["rebite_tokens"]` が ledger に届かない（P1-1） |
| recovery target call | **未計上** | 回復後の再問い合わせ自体が実装されていない |

**二重計上の候補**

- `EvalHarness.run_smoke()` のコメント `# Only count target if not already counted via baseline accounting`（[`eval_harness.py:145-146`](../../src/bite_eval/harness/eval_harness.py)）は**実装されていない**。target 行は無条件に記録される。現在の baseline はすべて `baseline_router_tokens` / `baseline_compressor_tokens` しか返さないため実害はないが、将来 target 相当を accounting に含む baseline を足すと二重計上になる。
- `DC-1`（同一 `call_id` の重複行）は `validate_ledger_totals()` で検出される。現状の違反は検出されなかった。
- `T_logical_char4_proxy` は **変換後ではなく元の document** から計算されている（[`billed_runner.py:663-664`](../../src/bite_eval/pilot/billed_runner.py) の `text = str(packet.get("document"))`）。二重計上ではないが、offline での payload 差分検出には使えない値になっている。Phase 1 は offline なのでここは実害が出る。

**結論**: 二重計上は現時点で検出されなかった。問題は **未計上（re-bite / recovery）と、`T_total` の定義二重化（P0-7）** にある。

---

## Leakage Audit

| 漏洩源 | 経路 | 状態 |
|---|---|---|
| gold answer → target prompt（pilot） | `families.py` の query | ✅ なし。`dependency_chain` の gold 埋め込みは commit `938eaab` で修正済み。全 family の query を確認し、gold value の literal 混入なし |
| gold answer → target prompt（BITEBench） | `renderers.py` の surface | ❌ **全 6 renderer で漏洩**（P0-4） |
| gold evidence ID → surface | `render_nested_json` の `required_evidence_ids` | ❌ **漏洩**（P0-4） |
| gold answer → routing 判断 | `rule_pi` の morphology / budget | ✅ なし。`assert_no_oracle_leak()` が `gold_` / `oracle_` / `eval_` 接頭辞と 11 個の完全一致キーを拒否（[`leak_guard.py:13-45`](../../src/bite_ingestion/policies/leak_guard.py)）。`extract_budget()` が budget へ写すキーは `n_tokens` / `char_len` / `task_id` / `pre_segmented` / `malformed` / `max_chars` に限定 |
| family 名 → routing 判断 | — | ✅ なし。`extract_budget` / `extract_morphology` のどちらも `family` を渡さない |
| oracle route → 透過 policy | `oracle_pi` | ✅ 隔離されている。`allow_eval_use` / `evaluation_mode` フラグ必須で、既定は `status=failed`（[`oracle_pi.py:75-87`](../../src/bite_eval/baselines/oracle_pi.py)） |
| gold answer → Q_baseline | EVAL-01 | ✅ 修正済み。`Q_baseline` は paired `raw_full` 応答から取得。gold 由来の `m_base` は削除されている。`test_q_baseline_gold_leak.py` が回帰を防いでいる |
| 既存の漏洩テストの網羅性 | `test_texture_invariance.py:47-53` | ❌ `OPTIMAL_ROUTE=` / `route_label=` のみ検査。gold answer を検出しない |

**注**: `leak_guard` は mapping の**トップレベルキーのみ**を検査し、ネストした dict の中は見ない。`extract_budget` が `packet["budget"]` を 1 段フラット化するため実用上はほぼ覆えているが、2 段以上のネストは素通りする。

---

## Required Regression Tests

Phase 1 開始前に追加すべき test を、対応する P0/P1 とともに列挙する。

### Evidence integrity（P0-3 / P0-5）

1. `test_visible_ids_are_substrings_of_payload` — 全 arm・全 family で、`visible_unit_ids` の各 unit の `text` が `payload_text` の部分文字列であること。
2. `test_evidence_after_cutpoint_moves_to_R_with_original_id` — gold evidence を truncation 境界の**後ろ**に置いたとき、`recall_vis == 0.0` かつ R に**元の gold ID** が入り `recall_rec == 1.0` になること。既存の `test_bug1_truncation_preserves_visible_evidence_recall` はこの形へ差し替える。
3. `test_evidence_before_cutpoint_stays_visible` — 境界の**前**に置いたときは `recall_vis == 1.0` かつ R が空。
4. `test_operator_conservation_property` — 全 operator について `len(visible_units) + len(R.entries) + len(loss_ledger unit_ids) >= len(input_units)`。
5. `test_nonempty_input_never_yields_empty_output` — 非空 packet に operator を適用して `visible_evidence == []` になったら fail。
6. `test_ensure_units_fails_closed_on_string_evidence` — `visible_evidence` が文字列リストのとき例外を投げること（silent skip の禁止）。
7. `test_cut_unit_ids_resolve_to_gold_via_parent_chain` — CUT 後の unit から `parent_unit_id` を辿って gold ID に到達できること（P1-8）。

### Arm differentiation（P0-1 / P0-2）

8. `test_arms_produce_distinct_payloads` — 少なくとも 1 family で `sha256(length_pi.payload) != sha256(rule_pi.payload)`。
9. `test_rule_pi_sequence_varies_across_families` — `rule_pi` の `proposed_sequence` が 2 種類以上になること。
10. `test_morphology_is_populated_before_policy` — policy に渡る morphology が空でなく、8 特徴キーを持つこと。
11. `test_empty_morphology_fails_closed` — `morphology={}` を渡したら `status=failed` / `reason=morphology_missing`。
12. `test_no_op_recorded_in_artifact` — payload が入力と同一なら行に `status=no_op` が立ち、summary に集計されること。

### Leakage（P0-4 / P0-6）

13. `test_no_gold_answer_in_any_surface` — 全 renderer × 全 seed で `case.answer not in text`。
14. `test_no_required_evidence_ids_in_surface` — 同上で evidence ID も不在。
15. `test_no_question_duplicated_in_surface` — question は wrapper のみに存在。
16. `test_counterfactual_pair_identity` — 同一 `facts_id` の全 instance で `gold_answer` / `gold_evidence_ids` / `query` が一致。
17. `test_counterfactual_pair_token_matched` — ペアの **token 長**（char ではなく）が許容誤差内、または `length_matched: false` が明示されること。
18. `test_bundle_fingerprint_changes_on_renderer_change` — renderer 出力を変えたら fingerprint が変わること（P1-10）。

### Token accounting（P0-7 / P1-1 / P1-2）

19. `test_rebite_tokens_reach_ledger` — `RecoverEngine` が計上した `rebite_tokens` が `TokenLedger.totals()["T_rebite"]` に反映されること。
20. `test_rebite_arm_costs_more_than_non_rebite` — 同一 packet で `rule_pi_rebite` の `T_total > rule_pi` の `T_total`（回復が発生した場合）。
21. `test_t_total_equals_bucket_sum_for_all_arms` — 全 arm で `validate_ledger_totals()` が違反 0。
22. `test_no_duplicate_call_id_across_buckets` — DC-1 の明示的検査。
23. `test_summary_reports_excluded_row_counts` — summary に `n_measured` / `n_excluded_by_status` が存在し、`n_measured + n_excluded == n_instance_rows`。
24. `test_logical_proxy_uses_transformed_payload` — `T_logical_char4_proxy` が変換後 payload から計算されること。

### Pairing / metrics（P1-3 / P1-4 / P1-5）

25. `test_c1_c3_use_paired_join` — raw と candidate が `instance_id` で inner join され、片側のみの instance が除外されること。
26. `test_confirmatory_and_constraints_use_same_rows` — C1/C2/C3 の母集団と `measured_rows` が一致。
27. `test_provenance_derived_from_transformed_packet` — `provenance_complete_rate` を packet から消しても provenance が算出され、provenance 欠損を注入すると値が下がること。
28. `test_recoverable_recall_requires_actual_recovery` — R に入っていない gold ID は `recall_rec` に寄与しないこと。

---

## Recommended Next Step

Phase 1 に進む前の**最小作業**のみを示す。順序に依存関係がある。

1. **packet 契約の統一（P0-3 の前半）** — `document` を `unit_id` / `text` / `span` / `source_uri` を持つ unit 列へ変換し、`gold_evidence_ids` を実 span に紐づける。pilot families と BITEBench の両方を同じ契約に寄せる。**これが他のすべての前提**になる。

2. **fail-closed 化（P0-3 の後半 / P0-2）** — `ensure_units()` と `extract_morphology()` が空を返したら例外にする。黙って 0 ベクトル・空 unit で先に進む経路を塞ぐ。

3. **profiler の結線（P0-2）** — harness 入口で `DeterministicMorphologyProfiler` を呼び `packet["morphology"]` に注入する。この時点で `rule_pi` の sequence が family 間で分かれることを確認する。

4. **operator の実行（P0-1）** — `length_pi` / `rule_pi` / `rule_pi_rebite` の `run()` から `apply_sequence()` を呼ぶ。4 arm の payload hash が実際に分かれることを機械検査で確認する。

5. **BITEBench の gold 除去（P0-4）** — 6 renderer から answer / required_evidence_ids / question を除去し、テスト 13–15 を追加する。

6. **counterfactual pair の修正（P0-6）** — `texture_swap` の `facts_id` を実際の同一 facts に対応させ、テスト 16 を追加する。

7. **`T_total` の一本化（P0-7 / P1-1）** — billed 行を `T_target_call` にリネームし、`T_total` は ledger 合算のみにする。`rebite_tokens` を ledger に通す。

8. **上記 1–7 のあとで**、P0-5 の evidence integrity テスト（1–7 番）を追加し、全部 green にしてから Phase 1 の offline matrix を初回実行する。この時点で「4 arm の payload が本当に違う」「evidence ID が payload の実体に対応している」「T_total が全コストを含む」の 3 点が機械検査で保証されている状態になる。

**やらないこと（Phase 1 前）**: threshold の較正、有料 pilot の再実行、統計検定の追加、architecture superiority に関する主張。P1-11 の calibration は Phase 1 の結果を見る**前**に calibration set を分離して固定する必要があるが、値そのものの変更は本レビューの範囲外とした。

---

## 未確認事項

以下は本レビューで確認していない。断定していない箇所として明記する。

- GitHub 上の Actions 実行結果（green であることはユーザー申告。ローカルでは `pytest` 213 passed / 3 skipped と `ruff` / `mypy` 相当の構成を確認したが、Actions のログ自体は未参照）
- skip された 3 件の test の内容と skip 理由
- `benchmarks/frozen-v0.1/*.json` の中身が現行 renderer 出力と一致するか（`test_frozen_fixture_if_present` は `identity_sha256` と `generator_version` のみ比較し、surface text を比較しない）
- `artifacts/pilot/*.json` の既存 billed 結果を、EVAL-01/02/04 適用後のコードで再計算した場合の数値変化（有料 API を使わない再計算は可能だが、本レビューでは未実施）
- `configs/baselines/*.json` / `configs/policies/*.json` の内容が実装と整合しているか
- `harness/bitebench_hook.py` の実配線状況
- Phase 1 で `EvalHarness` を使う前提で書いているが、別の runner を新設する計画がある場合、P1-5（metric が placeholder）の評価は変わる。現行 `EvalHarness.run_smoke()` は quality / recall / provenance を `ctx` から受け取るだけで**計算しない**ため、そのままでは Phase 1 の品質比較に使えない。
