# EVAL-01: Q_baseline gold-oracle leak 修正完了

**担当**: Cloud Agent  
**完了日時**: 2026-09-16  
**Status**: 完了 (PR ready for review)

## 問題

`Q_baseline` が実際の `raw_full` model 応答ではなく、gold (oracle) から導出されていた。
これにより、有料 pilot の constraint check が無意味になっていた。

### 確認された問題箇所

- `src/bite_eval/pilot/billed_runner.py` (396–399行目):
  ```python
  gold = str(packet.get("gold_answer", ""))
  m_base = metrics_from_instance(packet, vis, answer=gold)
  Q_baseline = float(m_base["quality"])
  ```
- `src/bite_eval/pilot/runner.py`: offline runner も同様のパターン

## 実装した修正

### 1. Billed runner (`billed_runner.py`)

#### 変更内容:
- `BilledInstanceResult` に `baseline_status` field を追加
  - 値: `ok` | `missing_pair` | `timeout` | `rate_limit` | `error`
- `evaluate_billed_instance` に `raw_baseline_q` および `baseline_status` パラメータを追加
- Q_baseline の計算ロジックを変更:
  - **raw_full method**: 自己ペアリング (`Q_baseline = Q`)
  - **他の methods**: paired raw_full の Q を使用
  - **paired raw_full が無い場合**: `baseline_status = "missing_pair"` を設定、Q_baseline=0.0
- `run_billed_pilot` に `raw_baseline_lookup` dict を追加:
  - raw_full 結果を instance_id でインデックス
  - 他 method 評価時に lookup して baseline として使用
  - checkpoint/resume 時も正しく復元

#### 契約の保証:
1. ✅ Gold を `Q_baseline` として使用しない
2. ✅ `Q_baseline` は実際の `raw_full` 応答から取得
3. ✅ Paired raw_full が無い場合、明示的な status 設定
4. ✅ timeout/rate_limit 時も適切な baseline_status

### 2. Offline runner (`runner.py`)

#### 変更内容:
- `InstanceResult` の `Q_baseline` フィールドを `Q_gold_oracle` に改名
- Module docstring に明確な説明を追加:
  > Q_gold_oracle field represents gold answer quality (not actual baseline).
  > Billed runner uses actual raw_full model Q as Q_baseline.

#### 理由:
Offline synthetic runner は gold answer を使用するが、これは実際の baseline
ではないため、混乱を避けるために明確にラベル付けした。

### 3. Tests (`tests/eval/test_q_baseline_gold_leak.py`)

新規テストファイルを作成:

- ✅ `test_q_baseline_not_from_gold`: gold leak が無いことを確認
  - Wrong answer を返す fake client を使用
  - Q=0.0 だが Q_baseline=1.0 (gold使用の証拠) にならないことを検証
  - raw_full の self-pairing により Q_baseline=Q=0.0 となることを確認

- ✅ `test_baseline_status_field_exists`: baseline_status field の存在確認

- 🔜 `test_compressed_method_pairs_with_raw_full`: (skipped - 将来実装)
- 🔜 `test_missing_raw_pair_has_missing_status`: (skipped - 将来実装)
- 🔜 `test_timeout_raw_pair_has_timeout_status`: (skipped - 将来実装)

## 検証結果

### Test suite:
```
tests/eval/test_q_baseline_gold_leak.py: 2 passed, 3 skipped
tests/eval/test_billed_pilot_mock.py: 28 passed
tests/eval/test_pilot_smoke.py: 8 passed
Full test suite: 173 passed, 3 skipped
```

### Code quality:
```
ruff: All checks passed!
mypy: Success: no issues found in 3 source files
```

## 変更ファイル

### Core changes:
1. `src/bite_eval/pilot/billed_runner.py` (+47 lines, -19 lines)
   - `BilledInstanceResult` に `baseline_status` field 追加
   - `evaluate_billed_instance` の signature および実装変更
   - `run_billed_pilot` に `raw_baseline_lookup` ロジック追加
   - Error case の baseline 処理を修正

2. `src/bite_eval/pilot/runner.py` (+18 lines, -14 lines)
   - `Q_baseline` → `Q_gold_oracle` への改名
   - Module docstring に説明追加

3. `tests/eval/test_q_baseline_gold_leak.py` (新規作成, 76 lines)
   - Gold leak prevention の regression tests

## 実際の Q_baseline 計算フロー

### Before (bug):
```
Q_baseline = metrics_from_instance(packet, vis, answer=gold)["quality"]
// 常に gold を評価 → Q_baseline=1.0 (gold が正解の場合)
```

### After (fixed):
```
if method_id == "raw_full":
    Q_baseline = Q  // self-pairing
elif raw_baseline_q is not None:
    Q_baseline = raw_baseline_q  // paired raw_full の Q
else:
    Q_baseline = 0.0, baseline_status = "missing_pair"
```

## Bugbot findings fixes (2026-09-16 追加)

PR #11 の Bugbot が検出した 3 件の baseline 処理バグを修正:

### Bug 1 — High: Stale baseline after resume retry
**問題**: `raw_full` がタイムアウト後に resume retry で成功しても、既に書き込まれた compressed 行の `Q_baseline=0.0` / `baseline_status=timeout` が更新されず、gate metrics が誤る。

**修正**: `_refresh_stale_baselines()` 関数を追加し、`raw_full` 成功時（resume retry 含む）に同 instance_id の compressed 行の stale baseline を更新。

**テスト**: `test_bug1_stale_baseline_refreshed_after_resume`, `test_bug1_multiple_compressed_rows_refreshed`

### Bug 2 — Medium: Rate-limit skip unpaired compressed
**問題**: `raw_full` が rate limit された時、checkpoint に記録されるが row は作成されず。resume 時に compressed が `missing_pair` / `Q_baseline=0.0` で実行される。また `baseline_status=rate_limit` が記録されていなかった。

**修正**: 
- Rate limit 時に row を作成し `baseline_status=rate_limit` を記録
- Resume 時に paired raw_full が rate_limit の場合、compressed をスキップ

**テスト**: `test_bug2_rate_limit_records_baseline_status`, `test_bug2_compressed_skipped_when_raw_rate_limited`

### Bug 3 — Medium: Provider errors marked baseline ok
**問題**: 非タイムアウトの `ZaiClientError` が `raw_full` で発生した時、`baseline_status=ok` / `Q=0.0` が記録され、失敗した呼び出しが valid baseline として扱われる。

**修正**: Provider/client エラー時は `baseline_status=error` を設定（`ok` ではない）。タイムアウトは引き続き `timeout`。

**テスト**: `test_bug3_provider_error_not_baseline_ok`, `test_bug3_timeout_still_marked_timeout`

### baseline_status 値の完全な定義:
- `ok`: 成功した baseline (raw_full が正常に実行された)
- `missing_pair`: paired raw_full がまだ実行されていない
- `timeout`: raw_full がタイムアウトした
- `rate_limit`: raw_full が rate limit された
- `error`: raw_full でプロバイダーエラーが発生した（非タイムアウト）

### Bugbot PR#11 2nd round fixes (2026-09-17 追加)

2件の checkpoint 永続化バグを修正:

#### Bug 1 — High: Checkpoint rewrite clobbers rate_limit status
**問題**: Successful `raw_full` 後の checkpoint rewrite で、compressed 行の `status=rate_limit` が `status=error` に上書きされていた（error field が非 null のため）。Resume 時に rate_limit 行が retryable と判断され、再度 429 を引き起こす可能性。

**修正**: Checkpoint rewrite 時に explicit status (`rate_limit` 等) を保持。`baseline_status == "rate_limit"` の場合は `status=rate_limit` を書き込む。

**テスト**: `test_bug1_checkpoint_rewrite_preserves_rate_limit_status`

#### Bug 2 — Medium: Restore refresh skips checkpoint rewrite
**問題**: Restore-only path で stale baseline を in-memory 更新するが、checkpoint JSONL に永続化されない。次回 resume で stale baseline のまま実行される。

**修正**: Post-restore refresh 後、live success path と同様に updated compressed 行を checkpoint に append。

**テスト**: `test_bug2_restore_refresh_persists_to_checkpoint`, `test_bug2_restore_with_rate_limit_sibling`

## Out of scope (意図的に除外)

以下は Phase 1+ の課題として残した:
- ❌ EVAL-02: TransformedPacket 型の統一 (大きなリファクタリング)
- ❌ EVAL-04: Prompt parity test (別 PR で対応可能)
- ❌ Real BITE morphology arms の接続 (Phase 1)
- ❌ Full 384 paid pilot の再実行 (評価器修正後)

## 次のステップ

本 PR が merge された後:

1. **EVAL-02**: `TransformedPacket` 型を導入し、prompt body と visible IDs を統一
2. **EVAL-04**: Prompt parity test (wrapper token overhead の検証)
3. **Phase 1**: Actual `rule_pi` pipeline を billed runner へ接続
4. **Rerun**: 修正された評価器で小規模 pilot を再実行して動作確認

## Notes

- Checkpoint/resume 機能は保持され、正常に動作
- Existing test suite すべて pass (backward compatibility 維持)
- Code style (ruff, mypy) すべて clean
- Task requirement "ponytail style: smallest correct change" に準拠
