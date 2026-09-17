# EVAL-05 引き継ぎ

## タスク概要

**Phase 0 EVAL-05**: GitHub Actions CI の追加

- 仕様書: `docs/reviews/2026-09-17-external-evaluation.md` § Phase 0 / EVAL-05
- PR: [#14](https://github.com/nyattoh/bite-ingestion/pull/14)
- ブランチ: `cursor/eval-05-add-ci-b554`
- ベース: `main` (`7772219` / PR #13 EVAL-04 merge後)

## 実施内容

### 1. GitHub Actions ワークフロー追加

新規ファイル `.github/workflows/ci.yml` を作成し、以下のチェックを実装:

1. **ruff** - `src/` と `tests/` の lint
2. **mypy** - `src/` の型チェック
3. **pytest** - テストスイート実行
4. **スキーマ検証** - `source_unit.schema.json` と `evidence_packet.schema.json` の読み込み確認
5. **チェックサム検証** - `scripts/checksums.py` 実行
6. **アーティファクト検証** (条件付き) - `artifacts/runs` が存在する場合 `scripts/validate_artifacts.py` 実行

### 2. 既存の型エラー修正

CI 導入時に検出された既存の mypy 型エラーを修正:

- ファイル: `src/bite_eval/providers/zai_client.py`
- 問題: 変数 `text` の再定義
- 対処: legacy text field 用に別変数 `legacy_text` を使用

## コミット履歴

```
dbcc9d0 fix(types): use different variable name for legacy text field
ea499da fix(types): resolve mypy type error in zai_client
680710f feat(ci): add GitHub Actions CI for Phase 0 EVAL-05
```

## 検証結果

### CI 実行結果

- **Status**: ✅ SUCCESS
- **Run ID**: 35195145729
- **実行時刻**: 2026-09-17 07:33:46 - 07:34:06 (約20秒)
- **詳細**: https://github.com/nyattoh/bite-ingestion/actions/runs/35195145729

### チェック内容

全てのチェックが成功:

- ✅ ruff linting
- ✅ mypy type checking (79 source files checked)
- ✅ pytest test suite
- ✅ Schema file validation
- ✅ Checksum verification
- ✅ Artifact validation (条件分岐により実行されず、正常)

## 設計方針

### オフライン/決定論的

仕様に従い、CI は完全にオフラインかつ決定論的:

- シークレット不要
- 有料 API 呼び出し無し
- LLM 呼び出し無し
- 外部サービス依存無し

### 既存ツールとの一致

`scripts/gate.sh` と同じチェックを実行し、開発環境と CI の一貫性を確保。

### Python 3.11

`pyproject.toml` の要件に合わせて Python 3.11 を使用。

### パイプ最適化

`pip` キャッシュを有効化し、ビルド時間を短縮。

## スコープ外

仕様書に従い、以下は実施せず:

- ✗ ブランチ保護設定の変更 (public release 前に手動設定予定)
- ✗ コードやテストの変更 (型エラー修正を除く)
- ✗ Phase 1/2 の作業

## 残存課題

### なし

CI は期待通り動作しており、残存課題はありません。

### 将来的な改善候補 (optional)

- カバレッジレポート追加
- マトリクスビルド (複数 Python バージョン)
- アーティファクトアップロード (テスト結果等)
- キャッシュ戦略の最適化

## 成果物

### PR 情報

- **URL**: https://github.com/nyattoh/bite-ingestion/pull/14
- **タイトル**: Phase 0 EVAL-05: Add GitHub Actions CI
- **Status**: Draft → Ready for review (推奨)
- **Base**: main
- **Head SHA**: `dbcc9d0`

### ファイル変更

```
.github/workflows/ci.yml                     | 56 ++++++++++++++++++
src/bite_eval/providers/zai_client.py        |  2 +-
```

- 新規: 1 ファイル
- 変更: 1 ファイル
- 合計: +57 行, -1 行

## 次のステップ

1. PR をレビュー
2. 必要に応じてフィードバック対応
3. main へマージ
4. 公開前にブランチ保護設定を追加:
   - 必須チェック: `test (3.11)`
   - レビュー要件等は project policy に従う

## 参照

- 仕様書: `docs/reviews/2026-09-17-external-evaluation.md`
- PR: https://github.com/nyattoh/bite-ingestion/pull/14
- CI 実行: https://github.com/nyattoh/bite-ingestion/actions/runs/35195145729
- 関連 PR: #11 (EVAL-01), #12 (EVAL-02), #13 (EVAL-04)

---

**作成日時**: 2026-09-17 07:35 UTC  
**作成者**: Cloud Agent (Cursor)  
**タスク**: Phase 0 EVAL-05
