# PHASE1-FOUNDATION-CLAUDE 引き継ぎ

- 担当: Claude（packet契約 / evidence integrity / BITEBench integrity / token accounting contract）
- 基準 commit: `origin/main` = `801b40d`（PR #14 マージ後）
- 作業ブランチ: `fix/phase1-foundation-packet-contract`（**未 push / 未 merge / PR 未作成**）
- 実行日: 2026-09-17
- 有料 API: **未使用**（AGENTS.md「Irreversible は human / Path B」に従う）
- 参照: `docs/reviews/2026-09-17-external-evaluation.md`, `docs/reviews/2026-09-17-phase1-code-review.md`

---

## 1. 修正した P0

| # | 問題 | 状態 |
|---|---|---|
| P0-3 | operator に pilot packet を渡すと evidence が全消失し、R にも loss ledger にも残らない | **修正** |
| P0-4 | BITEBench renderer 6 種すべてが gold answer / required evidence ID を surface に埋め込む | **修正** |
| P0-5 | truncation で本文が消えても visible evidence ID が残る（false-positive recall） | **修正** |
| P0-6 | `texture_swap` の counterfactual pair が同一 facts / answer を満たさない | **修正** |
| P0-7 | `T_total` が billed 経路と ledger で別意味 | **修正** |
| P0-2（一部） | morphology profiler 未接続 → rule-Π が morphology-blind | **fail-closed 化のみ**（profiler 配線は scope 外 = Grok 担当） |
| P0-1 | 4 arm が同一 payload（operator 未実行） | **scope 外**（Grok 担当）。ただし実行の前提となる packet 契約・fail-closed は整備済み |

あわせて対応した P1: re-bite コストが ledger に届かない（P1-1）、provenance が自己申告値（P1-5 の一部）、no-op が artifact に出ない（P1-9）、benchmark fingerprint が renderer 変更を検出しない（P1-10 の一部）。

---

## 2. 変更ファイル

### 新規

| ファイル | 役割 |
|---|---|
| `src/bite_ingestion/packet_contract.py` | unit 契約の単一の正本。生成・検証・span 分割・provenance 計測 |
| `tests/test_phase1_foundation.py` | 4 契約の regression（41 test） |
| `benchmarks/frozen-v0.2/syn-case-{000,001}.json` | 漏洩除去後の frozen fixture |

### 変更

| ファイル | 変更内容 |
|---|---|
| `src/bite_ingestion/operators/base.py` | `synthesize_units_from_evidence` / `ensure_units` を fail-closed 化 |
| `src/bite_eval/pilot/families.py` | 全 packet に span 付き unit graph。`texture_swap` の pair 修正 |
| `src/bite_eval/pilot/billed_runner.py` | `_transform_packet` を span ベースへ。`T_target_call` / `T_total` 分離 |
| `src/bite_eval/pilot/runner.py` | offline も unit graph から visible を導出 |
| `src/bite_eval/accounting/ledger.py` | `T_operator` bucket 追加、`rebite_tokens` を bucket へ |
| `src/bite_eval/accounting/dc_validators.py` | `T_operator` を合計検証へ追加 |
| `src/bite_eval/harness/eval_harness.py` | adapter 申告分の二重計上を抑止（DC-1） |
| `src/bite_ingestion/policies/rule_policy.py` | `MorphologyRequiredError` 追加、空 morphology を拒否 |
| `src/bite_ingestion/policies/__init__.py` | 例外を export |
| `src/bite_eval/baselines/rule_pi.py` | `reason_code=morphology_missing` を返す |
| `src/bite_eval/baselines/rule_pi_rebite.py` | recovery コストを累積し accounting へ |
| `src/bite_bench/renderers.py` | 漏洩除去 + `RenderedSurface`（span 付き unit） |
| `src/bite_bench/generator.py` | 漏洩 guard / counterfactual validator / 長さ表示の是正 / fingerprint |
| `output/eval-fixtures/prose_smoke.json` | 文字列 evidence → Mapping 形式 |
| `docs/token-accounting.md`, `docs/04-evidence-packet-contract.md` | 契約の追記 |
| `tests/eval/test_eval02_unified_transform.py` | **誤仕様を撤回し span ベースへ全面書き換え** |
| `tests/eval/test_eval04_prompt_parity.py` | no-op 判定を構造化フラグへ |
| `tests/test_texture_invariance.py` | 漏洩 / pair identity / fingerprint / 長さ表示の検査を追加 |

---

## 3. 新しい packet contract

### unit の必須形状

```text
unit_id         packet 内で一意
text            document の正確な部分文字列
span            {"start": int, "end": int, "unit": "char"}
source_uri      provenance root
parent_unit_id  派生元（source unit は None）
provenance      {unit_id, source_uri, byte_or_token_span, renderer_id}
```

### 強制される規則（`bite_ingestion.packet_contract`）

1. **evidence ID には実体が必要。** `gold_evidence_ids` / `required_evidence_ids` が
   unit に解決できなければ `PacketContractError`。
2. **span は解決可能でなければならない。** `document[start:end] == unit.text` を検証。
3. **silent empty output 禁止。** evidence を宣言しているのに unit が 0 件なら例外。
4. **visibility は導出であって宣言ではない。** payload に span 全体が残った unit だけが visible。

### resolve 順序（`resolve_packet_units`）

```text
packet["units"] があれば         → document と突き合わせて検証
なければ gold_evidence_ids あり  → PacketContractError（アンカー無しの ID は不可）
どちらも無く document のみ       → document 全体を 1 unit として合成（legacy 互換）
```

### pilot packet

- `units` / `gold_evidence_ids`（unit_id）/ `visible_evidence`（operator 向け描画）を保持
- `recoverable_evidence_ids` は **空で出荷**。回復可能性は R に入って初めて成立する
- `provenance_complete_rate` は unit graph から**実測**
- document 文字列は従来と **byte-identical**（検証済み）

---

## 4. evidence 遷移規則

```text
span が payload 内に完全に収まる
    → visible_unit_ids に残る
    → R には入らない

span が cut point を跨ぐ / 越える
    → visible_unit_ids から除外
    → 元の unit_id のまま R へ（新しい synthetic ID は採番しない）
    → recoverable なら recall_rec に寄与
```

**部分生存は omission 扱い。**「たぶん前半に証拠がある」という仮定は禁止した。

`_transform_packet` は送信直前に `assert_units_in_payload` で自己検査する。
ID が visible なのに本文が payload に無い状態は例外になる。

`TransformedPacket` の追加フィールド:

| フィールド | 意味 |
|---|---|
| `omitted_unit_ids` | payload から落ちた unit（R の unit_id と一致） |
| `is_no_op` | 何も削られず payload が原文と同一 |
| `provenance_complete_rate` | visible unit から実測した provenance 完全性 |

行（`BilledInstanceResult`）には `transformation_status`（`no_op` / `transformed` /
`failed`）と `omitted_unit_ids` が載るので、artifact だけで no-op を判別できる。

---

## 5. T_total 定義

```text
T_target_call = provider が返した 1 target call の usage

T_total =
    T_profiler
  + T_router
  + T_operator
  + T_target_in
  + T_target_out
  + T_rebite
  + T_baseline
  + T_calls_other
```

- `T_total` は **ledger の bucket 合計のみ**。target call の別名にしない
- billed 行は決定論段階（profiler / router / operator）を 0 token として**明示的に記録**するので、`T_total` は常に合計として成立する
- 旧 checkpoint は `T_total` に target call を入れていた。`_legacy_target_call` が
  `T_target_call` へ写すので、resume しても意味が入れ替わらない
- 同一 call の二重計上は `DC-1`（`call_id` 重複）で検出
- `RecoverEngine._finish` → `accounting["rebite_tokens"]` →
  `merge_baseline_accounting` → `T_rebite` の経路を接続した
- `EvalHarness` は adapter が申告した target / rebite token がある場合、stub 行を記録しない

---

## 6. BITEBench integrity

### 除去したもの（全 6 renderer）

| renderer | 旧 漏洩 |
|---|---|
| `prose_narrative` | `Canonical answer label: E42` |
| `table_csv` | `# answer: E42` / `# question: ...` |
| `nested_json` | `"answer": "E42"` / **`"required_evidence_ids"`** |
| `event_logs` | `INFO gold_answer=E42` |
| `code_config` | `answer = 'E42'` / `query = '...'` |
| `mixed_payload` | 上記 3 種を継承 |

加えて `fact_id`（`syn-e1` 等）も surface から除去した。評価専用の識別子であり
shortcut feature になりうるため。unit は span で紐づく。

### answer leakage test の意味（2026-09-17 合意済み）

`case.answer not in rendered_surface` は**文字どおりの禁止ではない**。禁止すべきは
gold answer が「それが答えである」ことを示すメタ情報・ラベルとして surface に出る
ことであって、値そのものの存在ではない。`answer="E42"` は required evidence
`Fact("syn-e2","error_code","E42")` の値そのものなので、文字どおり除去すると
extractive QA として解答不能になる。

したがって test は次の 2 点を検査する:

> 1. **answer が許可された evidence span の外側に出現しないこと**
> 2. **answer を正解としてラベル付けする構造が存在しないこと**
>    （`answer=` / `gold_answer=` / `Canonical answer label:` / `# answer:` /
>    正解を特別扱いする JSON field / answer を直接指示・強調する marker）

| 出現の仕方 | 判定 |
|---|---|
| required evidence の自然な本文・値として存在 | OK |
| 上記のラベル・専用 field・強調 marker として存在 | NG |

`assert_no_surface_leakage()` が生成時にこれを強制する。あわせて
**required evidence ID は surface に出さず metadata / provenance 側にのみ保持**し、
**question も surface 本文へ重複させず wrapper から 1 回だけ渡す**。
test は全 renderer × seed 0–5 で実行している。

### counterfactual pair

- `assert_counterfactual_identity()` を追加。同一 `facts_id` について
  `answer` / `question` / `required_evidence_ids` / `facts` の一致を機械検査
- pilot の `texture_swap` は `i // 2` で decode した 1 組の事実から 2 surface を生成。
  同一 `facts_id` のペアは code / value / answer / gold evidence ID が一致する
  （旧実装は `facts-0` に `K00=100` と `K01=101` を入れていた）

### 長さ表示

```text
length_matched      : False          （token 一致は未実装）
length_match_basis  : "char_only_not_token"
char_len_matched    : True/False     （padding の結果）
padding_applied     : True/False
padding_note        : padding は '# pad' 行を挿入し morphology を動かす
```

char length を token length と呼ばない。主解析へ紛れ込ませないため
`length_matched` は常に `False`。

### versioning

- `GENERATOR_VERSION` `0.1.0-synthetic` → **`0.2.0-synthetic`**
- `bundle_fingerprint` に surface hash を含めた。renderer を変えると fingerprint が動く
- `benchmarks/frozen-v0.2/` を再生成。**`frozen-v0.1/` は gold を漏洩しているので使用禁止**
  （削除はしていない。test で「現行 generator と一致しないこと」を固定）

---

## 7. 撤回した既存 test とその理由

指示どおり「新仕様へ合わせて弱める」ことはしていない。誤仕様を固定していた test は
撤回し、理由を test ファイルの docstring にも残した。

### `test_bug1_truncation_preserves_visible_evidence_recall`（撤回）

```python
doc = "A" * 500
assert transformed.visible_unit_ids == ["gold-ev-1", "gold-ev-2"]
assert recall_vis == 1.0
```

**なぜ誤りか:** 入力は全文が `A` で、evidence が 400 文字の前後どちらにあるか検証
しようがない。コード側のコメントも
`(which it typically does for synthetic packets)` と仮定を明記していた。
「ID は visible だが実体は payload 外」という false-positive recall を仕様として
固定していた。さらに切り落とし分に新しい synthetic ID を振っていたため、
`gold_evidence_ids` と交差せず recoverable recall でも救えなかった。

**置換:** span ベースの 3 ケース（cut point より前 / 後 / 跨ぎ）+
「visible unit の text が payload に実在する」検査。

### `test_length_matched_contrast_pair`（撤回）

```python
assert pair["length_matched"] is True
```

**なぜ誤りか:** char padding の結果を length matching と呼んでいた。token 長は
一致していないので、token-matched 解析へそのまま入ると長さ交絡が残る。

**置換:** `length_matched is False` + `char_len_matched is True` + basis 文字列。

### `test_no_op_transformation_detection` / `test_no_op_detection_with_truncation`（強化）

`transformation_note` の部分文字列一致を、構造化フラグ `is_no_op` と
`omitted_unit_ids == R の unit_id` 検査へ置換した（弱化ではなく強化）。

### `test_route_label_not_in_surface_as_instruction`（強化）

`OPTIMAL_ROUTE=` / `route_label=` のみ検査していたため gold answer 漏洩を
検出できなかった。全 renderer × 全 seed の漏洩検査へ拡張。

---

## 8. 追加した regression test

`tests/test_phase1_foundation.py`（41 test）

| 区分 | test |
|---|---|
| packet 契約 | 全 family の unit graph が解決する / gold evidence の text が document に実在する / unit が provenance を持つ / recoverable を事前宣言しない |
| fail-closed | 文字列 evidence list を silent skip しない / 非空入力が silent empty output にならない / 宙に浮いた evidence ID を拒否 / 解決不能 span を拒否 / rule-Π が空 morphology を拒否 / `rule_pi` が `reason_code` を返す |
| evidence integrity | span ベース分割 / 部分生存は omission / visible と R が disjoint |
| token accounting | `T_total == bucket sum` / `rebite_tokens` が ledger へ届く / RecoverEngine → accounting → `T_rebite` の end-to-end / `rule_pi_rebite` が recovery コストを申告 / DC-1 重複検出 |
| operator 保存則 | visible + R + loss ledger が入力 unit を覆う |

`tests/eval/test_eval02_unified_transform.py`（書き換え）

- cut point 前 → `recall_vis == 1.0`、R 空
- cut point 後 → `recall_vis == 0.0`、**同じ gold ID が R**、`recall_rec == 1.0`
- cut point 跨ぎ → visible から除外
- 全 visible unit の text が payload に実在（start を 6 通り parametrize）
- prompt と visible ID が同一オブジェクト由来 / 落ちた本文が prompt に無い
- provenance が実測であること（provenance を剥がすと 0.0 に落ちる）
- fail-closed 4 種

`tests/test_texture_invariance.py`（拡張、99 test）

- 全 renderer × seed 0–5 の漏洩検査
- 漏洩 guard 自体が発火することの検査（answer ラベル / question 混入）
- unit span 解決 / required evidence の解決
- counterfactual identity（一致 + 3 種の不一致検出）
- 長さ表示 / fingerprint 変化 / frozen v0.2 一致 / v0.1 が現行でないこと

---

## 9. 実行した検証

```text
pytest        349 passed, 3 skipped   （基準 main: 213 passed, 3 skipped）
ruff  src tests                       All checks passed
mypy  src                             Success: no issues found in 80 source files
schema 検証                           source_unit / evidence_packet: ok
scripts/validate_artifacts.py         Validated 4 manifests; failures=0
scripts/checksums.py                  実行可（下記の注意あり）
```

追加で offline 実測した内容:

- 8 family の `document` が変更前と **byte-identical**
- 全 family の unit span が解決し、gold evidence ID が実体へ解決する
- cut point 前後の recall 遷移が仕様どおり（1.0/空 → 0.0/R/1.0）
- 全 renderer で `question` / evidence ID が不在、answer は evidence span 内のみ

**注意:** `scripts/checksums.py` は working tree の未追跡 artifact も
`artifacts/SHA256SUMS.txt` へ取り込む。ローカル実行後の差分は commit していない
（CI のクリーンな環境では発生しない）。

---

## 10. 未解決事項

1. **`bite_bench` の canonical case は依然 2 件のみ**（`make_synthetic_case` は
   `seed % 2`）。Phase 1 の N 確保には case pool の拡張が必要。今回は integrity
   修正に限定したため未着手。
2. **token-length matching 未実装。** tokenizer ベースの matcher が無いため
   `length_matched=False` を明示する対処に留めた。
3. **`frozen-v0.1/` を残置**（2026-09-17 合意: 今は削除しない）。gold を漏洩しているが、
   legacy / superseded として現行 generator から隔離されていれば十分。test で
   「現行 generator と一致しないこと」を固定済み。削除・archive は Grok 側の作業か
   公開整理の段階で判断する。
4. **`adversarial_omission` の意味変更**（2026-09-17 合意済み）。旧実装は
   `visible_evidence=[eid]` で `recall_vis=0.5` を宣言していたが、`HIDDEN:` 本文は
   document に平文で入っており raw_full では実際に可視だった。raw_full で本文に
   存在するものを "hidden" と見なすのはやめ、新契約では `recall_vis=1.0` が正しい値。
   H4（R 経由の回復）は、**Grok 側で実際に evidence を R へ落とす変換経路を接続した後**
   に検証する。family 定義自体は変えていない。
5. **`constraints_ok_rate` の除外件数が summary に出ない**（review P1-2）。
   `measured_rows` は失敗行を除外するが `n_measured` / `n_excluded` が無い。
   metric 集計の範囲なので今回の担当外。
6. **C1/C3 が paired join でない**（review P1-3）。同上。
7. **CUT が unit_id を振り直す**（review P1-8）、**INTEGRATE の provenance 規約が
   他 operator と不整合**（review P1-7）。operator 配線時に顕在化するので、
   Grok 側で `parent_unit_id` 鎖の解決が必要になる。

---

## 11. Grok へ渡す前提条件

配線作業に入る前に、以下が成立していることを前提にしてよい。

| 前提 | 根拠 |
|---|---|
| packet は span 付き unit graph を持つ | `resolve_packet_units` / `validate_units` |
| evidence ID は必ず実体を持つ | `assert_evidence_ids_resolve`（未解決なら例外） |
| 空 unit / 文字列 evidence は例外になる | `ensure_units` fail-closed |
| visible ID は payload の実体と一致する | `assert_units_in_payload` |
| 落ちた unit は元 ID のまま R に入る | `_transform_packet` |
| BITEBench surface に gold / question / evidence ID は無い | `assert_no_surface_leakage`（生成時強制） |
| counterfactual pair は同一 facts/answer/question/evidence | `assert_counterfactual_identity` |
| `T_total` は ledger 合計のみ | `TokenLedger.totals()` / `validate_ledger_totals` |
| re-bite コストは `T_rebite` へ到達する | `merge_baseline_accounting` |

配線時に **必ず踏む**こと:

1. **profiler を接続する。** 現在 `rule_pi` / `rule_pi_rebite` は morphology が空だと
   `status=failed` / `reason_code=morphology_missing` を返す。
   `DeterministicMorphologyProfiler().profile_report()` の結果を
   `packet["morphology"]` へ入れてから policy を呼ぶ。profiler は決定論なので
   token は 0、`cpu_ms` のみ ledger へ。
2. **operator を実行する。** `apply_sequence()` は pilot packet の unit graph を
   そのまま受ける。`visible_evidence` は Mapping 形式で出荷済み。
3. **arm の payload が実際に違うことを機械検査する。**
   `sha256(payload)` が family 単位で分岐することを artifact に残す。
   分岐しない場合は `transformation_status=no_op` が立つ。
4. **CUT 後の ID 解決。** CUT は unit_id を振り直す。metric 側で
   `parent_unit_id` 鎖を root まで辿ってから `gold_evidence_ids` と突き合わせること。
   未対応のまま CUT を含む arm を評価すると recall が 0 になる。
5. **threshold は触らない。** `TBD_CALIBRATE` は未較正のまま。

---

## 12. 判定

```text
FOUNDATION_READY_FOR_WIRING
```

根拠:

| 条件 | 状態 | 根拠 |
|---|---|---|
| evidence ID と payload が対応 | ✅ | span ベース導出 + `assert_units_in_payload` + 全 family/seed の test |
| silent evidence loss がない | ✅ | `ensure_units` / `synthesize_units_from_evidence` の fail-closed、保存則 test |
| BITEBench gold leakage がない | ✅ | 全 6 renderer から除去、生成時 guard、全 renderer × seed 0–5 の test |
| counterfactual identity が成立 | ✅ | `assert_counterfactual_identity` + `texture_swap` 修正 |
| `T_total` 契約が一意 | ✅ | `T_target_call` / `T_total` 分離、bucket 合計検証、legacy checkpoint の写像 |

§6 の answer leakage 解釈、§10 の (3) `frozen-v0.1` 残置、(4)
`adversarial_omission` の意味変更は **2026-09-17 に合意済み**。
残る判断待ちは §10 の (1) case pool 2 件、(2) token-length matching 未実装、
(5)–(7) の metric 集計・operator 配線時の課題。特に (1) は Phase 1 の N 確保に
直接効く。

**この判定は「配線してよい」であって「Phase 1 の比較が成立する」ではない。**
P0-1（operator 未実行）と P0-2（profiler 未接続）が残っている限り、4 arm は
依然として同一 payload を出力する。
