# PHASE1-WIRING-GROK 引き継ぎ

- 担当: Grok（profiler / operator 実行 / 4 arm / bounded re-bite / offline matrix）
- 前提: `FOUNDATION_READY_FOR_WIRING`（Claude foundation）
- ブランチ: `fix/phase1-foundation-packet-contract`（**未 push / 未 merge**）
- 実行日: 2026-09-17
- 有料 API: **未使用**
- `TBD_CALIBRATE`: **未変更**
- 本 matrix は **配線検証**。研究結論ではない。

---

## 判定

```text
PHASE1_OFFLINE_READY
```

| # | 条件 | 状態 |
|---|---|---|
| 1 | 4 arm 実装済み | yes |
| 2 | morphology-aware が実測 morphology を使う | yes |
| 3 | operators が実行される | yes |
| 4 | evidence integrity | yes（conservation + parent chain） |
| 5 | re-bite cost が計上される | yes（情報追加時 T_rebite>0） |
| 6 | T_total が一意 | yes（bucket 合計のみ） |
| 7 | offline matrix green | yes（n_failed=0, artifact validation OK） |

---

## profiler 接続箇所

- `bite_eval.arm_runtime.attach_morphology` — payload + query のみ
- `EvalHarness.run_smoke` 入口（全 method）
- `run_phase1_matrix` が各 case で 1 回計測し、4 arm に同じ vector を渡す
- 空 `morphology={}` は adapter が `status=failed` / `reason_code=morphology_missing`
- gold / oracle / family は profiler 入力に入れない

## arm 別 pipeline

| arm | 経路 |
|---|---|
| `raw_full` | 無変換。matrix `status=pass_through` |
| `length_pi` | `LengthOnlyPolicy({})` → `apply_sequence()`。morphology は記録するが読まない |
| `rule_pi` | 実測 morphology → `RulePolicy` → `apply_sequence()` |
| `rule_pi_rebite` | **`RulePiBaseline.run()` のあと bounded Recover だけ**。sequence は rule_pi と同一 |

fairness（4 arm 共通）: 同一 query、同一 wrapper、同一 output constraint、同一 `local_char4_proxy`、timeout/retry は offline で n/a。評価集合は `case_id` inner join。

`length_pi` と `rule_pi` の差は policy 入力と routing のみ。

## operator 実行経路

`execute_sequence` → `bite_ingestion.policies.apply_sequence` → CUT / UNTANGLE / REDUCE / INTEGRATE。

CUT 子は `parent_unit_id`。INTEGRATE visible ID は `units[].unit_id`。metric は `root_ids_of()`。

## recovery 経路

`bounded_rebite`:

- 上限 `J=3`, `B_r=512`（TBD）
- 同一 `unit_id` は再取得しない（engine dedupe + fetched set）
- R `locator` を step に残す
- recovered unit は provenance（`source_uri`, `byte_or_token_span`）を持つ
- 情報が増えて `T_rebite=0` なら fail-closed
- 追加 target call は offline では無い。回収後 payload の `T_target_in` が増える

query が visible に無く R にあるときだけ動く。gold ID は使わない。

## token accounting

```
T_total = T_profiler + T_router + T_operator + T_target_in + T_target_out + T_rebite
```

決定論 profiler/router は token 0。`T_target_in` は最終 payload の char/4。`call_id` は `{method}:{case_id}:{bucket}` で一意。

## regression tests

`tests/test_phase1_wiring.py` ほか。

profiler connected / morphology fail-closed / arm payload diff / conservation / parent lineage / re-bite bounded / re-bite token accounting / no-op artifact / T_total == bucket sum / no duplicate call_id / failed rows counted / paired same rows。

すべて offline。

## offline matrix summary

artifact:

- `artifacts/phase1/arm_differentiation.json`
- `artifacts/phase1/arm_summary.md`

再生成: `python scripts/run_offline_arm_matrix.py`

実測（8 family × 1 × 4 arm = 32 行、結論ではない）:

| 項目 | 値 |
|---|---|
| n_total | 32 |
| n_measured | 32 |
| n_excluded | 0 |
| n_failed | 0 |
| n_no_op | 8 |
| no_op_rate | 0.25 |
| failure_rate | 0.0 |
| rule_pi sequence | `['CUT']`, `['CUT','UNTANGLE']` |
| length_pi ≠ rule_pi | 少なくとも 1 case（CUT+REDUCE vs CUT など） |

payload hash と sequence の全表は `arm_summary.md`。

## no-op / failure

- `pass_through`: raw_full
- `no_op`: candidate が R 空かつ payload が原文と同じ
- `transformed`: payload または R が動いた
- `failed`: adapter 失敗
- timeout / missing_pair / rate_limit は schema のみ（offline 0）
- 平均の分母は n_total。失敗を黙って消さない

## 未解決

- billed / 有料 runner への 4 arm 接続（scope 外）
- token-length matching、canonical case pool 拡張（Claude §10）
- 現行 synthetic では `rule_pi_rebite` が `rule_pi` と同じ payload の case が多い（R に query 不足が無い）。能力は接続済み。H4 の本検証は evidence が本当に R へ落ちる family が要る
- `frozen-v0.1` 残置
- threshold 較正はしない

## 検証コマンド（実施済み）

```
ruff check src tests
mypy src
pytest
schema files (source_unit, evidence_packet, phase1-offline-matrix)
scripts/checksums.py
scripts/validate_artifacts.py
```
