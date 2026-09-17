# EVAL-04 ハンドオーバー

**タスクID:** EVAL-04  
**日付:** 2026-09-17  
**ステータス:** 完了 ✅  
**PR:** [#13](https://github.com/nyattoh/bite-ingestion/pull/13)

## 概要

Phase 0 / EVAL-04「プロンプトパリティテスト」を実装。プロンプトラッパーを統一し、BITE-15b pilotの系統的な2トークンバイアス(delta=-2)を解消。

## 実装内容

### 1. コア修正: ラッパー統一

**ファイル:** `src/bite_eval/pilot/billed_runner.py`

**変更箇所:** `_build_messages()` 関数 (474-504行目)

**Before:**
- raw_full: `"Document:"` プレフィックス
- compressed_passthrough: `"Compressed document:"` プレフィックス
- 結果: 系統的2トークン差 (compressed が raw より2トークン多い)

**After:**
- 全arm共通: `"Document:"` プレフィックス
- wrapper bias = 0 (ペイロードが同一の場合)

**変更統計:**
- 29行変更 (+13, -16)
- method_id条件分岐を削除し、単一の統一テンプレートへ

### 2. 新規テスト: EVAL-04回帰テスト群

**ファイル:** `tests/eval/test_eval04_prompt_parity.py` (新規作成)

**テストケース (7件, 全パス):**

1. `test_wrapper_parity_raw_vs_compressed`
   - raw と compressed のラッパーが同一であることを検証
   - "Compressed document:" の存在を禁止

2. `test_empty_payload_overhead`
   - 空ペイロードで固定オーバーヘッド(wrapper token)を測定
   - arm間でオーバーヘッドが同一であることを確認

3. `test_payload_vs_total_token_separation`
   - total_tokens = wrapper_tokens + payload_tokens の分離測定
   - 各成分が独立して測定可能であることを検証

4. `test_no_op_transformation_detection`
   - no-op変換(ペイロード不変)の検出
   - 短いドキュメント(400字未満)で no-op を確認

5. `test_no_op_detection_with_truncation`
   - 実際の変換(truncation)と no-op の区別
   - 長いドキュメント(400字超)でtruncation発生を確認

6. `test_wrapper_overhead_is_measurable_artifact`
   - artifact出力用のオーバーヘッド報告構造
   - wrapper/payload/total の3成分を artifact として記録可能

7. `test_regression_bite15b_wrapper_bias`
   - **BITE-15b回帰ガード**
   - delta=-2 バイアスの再発防止
   - 同一ペイロード → delta=0 を保証

**テストコード統計:**
- 329行 (新規)
- char/4 proxy による token 推定使用(オフラインのみ)
- 実際の production 関数を呼び出し(コピーロジックなし)

## 検証結果

### テスト実行

```bash
# EVAL-04 テスト
$ pytest tests/eval/test_eval04_prompt_parity.py -v
7 passed in 0.04s ✅

# 全 eval テスト
$ pytest tests/eval/ -v
96 passed, 3 skipped in 0.51s ✅
```

### Linter

```bash
# ruff
$ ruff check src/ tests/
All checks passed! ✅

# mypy
$ mypy src/ tests/
Success: no issues found ✅
```

### 影響範囲確認

**既存テストへの影響:** なし  
- 全96テスト引き続きパス
- 既存の EVAL-02 テスト含め、回帰なし

**変更の最小性:** 最小正確変更(smallest correct change)を遵守  
- 既存ハーネス拡張(並列スタック作成なし)
- production 関数呼び出し(合成フィクスチャのみ、有料API呼び出しなし)

## EVAL-04 要件達成状況

仕様書: `docs/reviews/2026-09-17-external-evaluation.md` (444-450行目)

- [x] ✅ **要件1:** ラッパー統一 (raw と各arm が同一ラッパー使用)
- [x] ✅ **要件2:** 固定オーバーヘッドテスト(空ペイロード使用)
- [x] ✅ **要件3:** payload token と total token の分離測定
- [x] ✅ **要件4:** no-op 検出(wrapper無意味 / arm が raw と同一)

## PR 情報

- **URL:** https://github.com/nyattoh/bite-ingestion/pull/13
- **ブランチ:** `cursor/eval-04-prompt-parity-9f23`
- **ベースブランチ:** `main`
- **ステータス:** Draft (Bugbot レビュー待ち、マージしない)
- **Tip SHA:** `0d19f4fb076b9e5da819c4a2e7f04a81e8e4d118`

## 変更ファイル

```
src/bite_eval/pilot/billed_runner.py    |  29 ++-
tests/eval/test_eval04_prompt_parity.py | 329 +++++++++++++++++++++++
2 files changed, 342 insertions(+), 16 deletions(-)
```

## 影響評価

### Before (BITE-15b v2 pilot)

```
mean(T_raw - T_comp) = -2
compressed が raw より低token だったケース = 0 / 192
原因: "Document:" (1 token) vs "Compressed document:" (3 tokens)
```

### After (本PR)

```
同一ペイロードの場合:
  mean(T_raw - T_comp) = 0 (wrapper 同一のため)

no-op 変換の検出:
  payload_before == payload_after → no-op フラグ
  
token 分解追跡:
  total_tokens = wrapper_tokens + payload_tokens
  (個別測定可能、artifact 出力対応)
```

## スコープ外項目(確認済み)

以下はタスク指示により明示的にスコープ外:

- ❌ EVAL-05 (CI追加) — 別PR
- ❌ Phase 1/2 (実際の BITE arm 接続、有料pilot) — 別フェーズ
- ❌ PRマージ — Bugbotレビュー待ち、手動マージ不可
- ❌ 有料API / full-384 / live billing — コアテストはオフラインのみ

## 残存ギャップ

**なし。** EVAL-04 要件は完全に満たされている。

次のフェーズ(EVAL-05 または Phase 1)は別タスクとして実施。

## コミット情報

**Author:** Cursor Agent (cursoragent@cursor.com)  
**Message:**
```
fix(eval): EVAL-04 - unify prompt wrappers and add parity tests

Phase 0 / EVAL-04: prompt parity test to eliminate wrapper bias.

Changes:
- Unified wrapper: all arms (raw_full, compressed_passthrough) now use
  identical 'Document:' prefix instead of 'Compressed document:'
- Fixed BITE-15b systematic 2-token bias (delta=-2 in v2 pilot)
- Added comprehensive EVAL-04 regression tests:
  * Empty payload overhead measurement
  * Payload vs total token separation
  * No-op transformation detection
  * Wrapper parity verification
  * BITE-15b wrapper bias regression guard

All tests pass (96 passed, 3 skipped). Ruff and mypy clean.

Closes: Phase 0 EVAL-04 requirement from 2026-09-17-external-evaluation.md
Out of scope: EVAL-05, paid pilots, billing
```

## 検証手順(再現用)

```bash
# 1. ブランチ取得
git fetch origin cursor/eval-04-prompt-parity-9f23
git checkout cursor/eval-04-prompt-parity-9f23

# 2. 依存関係インストール
pip3 install -e .[dev]

# 3. EVAL-04 テスト実行
pytest tests/eval/test_eval04_prompt_parity.py -v

# 4. 全テスト実行
pytest tests/eval/ -v

# 5. Linter 実行
ruff check src/ tests/
mypy src/ tests/

# 期待結果:
# - pytest: 7 passed (EVAL-04), 96 passed (全体)
# - ruff: All checks passed
# - mypy: Success: no issues found
```

## 次のアクション

1. **Bugbot レビュー待機**
   - PR #13 は draft 状態
   - レビュー完了後、必要に応じて修正

2. **EVAL-05 (CI追加)** — 別タスク
   - GitHub Actions で ruff/mypy/pytest/schema validation
   - main protection は公開前に設定

3. **Phase 1 (実際の中心仮説オフラインテスト)** — 別フェーズ
   - PR #8 の length-only arm 実装
   - actual `rule_pi` pipeline を billed runner と同一ハーネスへ接続

---

**完了条件達成:**
- ✅ 1つのPR open (EVAL-04 prompt parity tests + minimal harness wiring)
- ✅ 報告: PR URL, tip SHA, 変更ファイル, 検証実行方法, 残存ギャップ
- ✅ 有料API / full-384 / live billing 未使用(Phase 0 要件遵守)

**タスク完了。** 🎉
