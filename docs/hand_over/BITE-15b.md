# BITE-15b handover — billed N_pilot（v2 = **pivot**）

- **Date**: 2026-09-17 (UTC+9)
- **Phase**: Gate C billed N_pilot（checkpoint / resume → thinking 修正 → v2 再課金）
- **Tone**: Pivot-to-bench; no Survive; **Go 捏造禁止**
- **Standing**: 有料はローカル（raytrek / Path B）。Cloud は mock / 文書のみ。Cloud 移行は hold。
- **Authoritative Gate C record**: **v2 @ [`967ec0b`](https://github.com/nyattoh/bite-ingestion/commit/967ec0b)** → **`pivot`**

## 権威ある結果（v2）

| 項目 | 値 |
| --- | --- |
| コミット | [`967ec0b`](https://github.com/nyattoh/bite-ingestion/commit/967ec0b) |
| summary | `artifacts/pilot/bite15b_billed_summary_v2.json` |
| partial | `artifacts/pilot/bite15b_billed_partial_v2.json` |
| checkpoint | 未コミット（`bite15b_checkpoint_v2.jsonl`） |
| 規模 | 384/384 billed rows |
| empty answers | **0/384**（minimal 0/12） |
| T_completion | min 2 / max 5 / mean ≈ 2.86 |
| **decision** | **`pivot`**（`c1=False c2=True c3=False`）— **Go ではない** |
| constraints_ok_rate | **0.880208**（338/384） |
| 弱点 family | `dependency_chain` ≈ 0.0417；他 7 family = 1.0 |
| 429 / timeout | なし |

再計算: `analysis/bite15b_pilot_recompute_v2.json`

## v1（履歴・非最終）

| 項目 | 値 |
| --- | --- |
| コミット | [`e44b5bd`](https://github.com/nyattoh/bite-ingestion/commit/e44b5bd) |
| decision | `stop`（empty-answer confounder 付き） |
| empty / T_completion | 354/384 empty；T_completion 常に 64 |

v1 は thinking/抽出バグ込み。科学的最終判定には使わない。

## なぜ BITE-15b があったか

初回フルランが `TimeoutError` で集計喪失 → checkpoint/resume/timeout 硬化。その後 v1 完走が empty×64 で汚染 → thinking disabled + 抽出 fallback + max_tokens=256 で v2 再課金。

## Fix summary（main に含まれる）

| Area | Change |
| --- | --- |
| `zai_client.py` | timeout retry；`thinking: disabled`；`reasoning_content` fallback |
| `billed_runner.py` | checkpoint/resume；pilot `max_tokens=256` |
| CLI / config | bite15b パス・retry・thinking 注記 |
| Tests | mock（thinking disabled / reasoning fallback 含む） |
| `scripts/run_billed_pilot.py` | executable bit（Cloud verify PR） |

## Resume policy

- Skip `ok`；retry `timeout`/`error` once；skip `rate_limit`
- v2 再課金は `--no-resume` + 新パス。以降の再開は **v2 checkpoint のみ**

## CLI（親機 / raytrek — 有料のみ）

```powershell
cd D:\develop\works\bite-ingestion
# Inject ZAI_API_KEY via bw-env (human finger) — do not echo the value

# Example: resume on v2 paths (prefer these over v1 filenames)
python scripts/run_billed_pilot.py --no-minimal --n-per-family 24 `
  --families clean_local repeated_records sparse_anomaly dependency_chain `
             malformed_mixed dense_cross_reference adversarial_omission texture_swap `
  --checkpoint artifacts/pilot/bite15b_checkpoint_v2.jsonl `
  --partial-out artifacts/pilot/bite15b_billed_partial_v2.json `
  --out artifacts/pilot/bite15b_billed_summary_v2.json `
  --resume
```

`--resume` is the default; use `--no-resume` only for a clean slate (will re-bill).

## Checkpoint record shape (JSONL)

One object per line:

```json
{
  "family": "clean_local",
  "instance_id": "...",
  "method": "raw_full",
  "status": "ok|error|timeout|rate_limit",
  "error_type": null,
  "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2, "cached_tokens": 0},
  "ts": "2026-09-17T00:00:00Z",
  "row": { }
}
```

## Verify (box / Cloud — mocks only)

```bash
cd /workspace
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest tests/eval/test_billed_pilot_mock.py -q
# KEY_ABSENT path (exit 2):
env -u ZAI_API_KEY .venv/bin/python scripts/run_billed_pilot.py --minimal ; echo exit=$?
```

## Cloud verification (2026-09-16 UTC・有料なし)

PR #1（`cursor/bite-15b-cloud-verify-1ee6`）時点の記録。有料フル実行は後にローカル v2 で完了（上表）。Cloud 側の方針は不変。

| Check | Result |
| --- | --- |
| `pytest tests/eval/test_billed_pilot_mock.py` | **26 passed**（当時；現行 suite は追加テストあり） |
| `pytest tests/eval/` | **54 passed**（当時） |
| `compileall src/bite_eval` | OK |
| CLI `ZAI_API_KEY` absent | exit **2** + `KEY_ABSENT` |
| Env key presence | **ABSENT**（length 非公開） |
| Egress | unrestricted（到達確認はキー注入後） |
| 有料実行 | **Cloud では行わない**（ローカル Path B） |

**ブロッカー（Cloud）**: `ZAI_API_KEY` 無し。有料 N_pilot は人間 / Path B のローカル実行。Cloud 移行 hold。

## 未解決 / 次

1. Gate C 記録は **pivot**（確定）。Go ではない
2. BITE-16: `dependency_chain` 失敗の記述、C2 placeholder の限界明記
3. full matrix 実施可否は人間判断

## Do-not

- Go / Survive 捏造禁止
- checkpoint JSONL・キー値をコミットしない
- Cloud から再課金しない / Cloud 移行 hold
- No Gemini ingest; no push/publish of secrets
- post-hoc で閾値を動かして Go にしない
- キー値は PRESENT/ABSENT（+任意 length）のみ
