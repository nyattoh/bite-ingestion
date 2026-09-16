# BITE-15b handover — billed runner checkpoint / resume / timeout fix

- **Date**: 2026-09-17 (UTC+9)
- **Phase**: Gate C billed N_pilot hardening (after BITE-15 overlay)
- **Tone**: Pivot-to-bench; no Survive claims; no Go invention
- **Artifact**: `bite15b-fix-dist.zip` overlays onto `D:\develop\works\bite-ingestion`
- **Standing**: Box builds/tests with mocks only. Parent (raytrek) resumes billed with key via bw-env.

## Failure mode (why this fix)

Full `N_pilot` billed run failed with:

```text
TimeoutError: The read operation timed out
```

after ~51 minutes and wrote **no** `bite15b` summary/partial — measured call counts were lost.

Root causes:

1. Bare `TimeoutError` from `urllib` / socket read was not mapped to a caught client error, so it bubbled out of the runner uncaught.
2. No per-call checkpoint — a crash mid-run left zero durable tallies.
3. No resume path — a restart would have re-billed already-successful calls.

## Fix summary

| Area | Change |
| --- | --- |
| `zai_client.py` | `ProviderTimeoutError`; catch TimeoutError / URL timeout; finite exponential backoff retries; 429 never retried; no key logging |
| `billed_runner.py` | JSONL checkpoint after every attempt + atomic partial rewrite; resume skips `ok`; retries prior `timeout`/`error` once; skips prior `rate_limit` |
| `run_billed_pilot.py` | `--checkpoint`, `--resume/--no-resume` (default True), bite15b default paths, config-driven timeout/retry |
| `pilot_bite15_billed.json` | `retry.*` + `checkpoint.*` documented defaults |
| Tests | checkpoint write, resume skips ok, timeout retries then fail, 429 stops without retry storm |

## Retry defaults (config)

| Field | Default | Meaning |
| --- | --- | --- |
| `timeout_s` | **120** | Per-call read timeout |
| `retry_max` | **3** | Retries after first attempt → **4 attempts total** |
| `retry_backoff_base_s` | **2.0** | First backoff sleep |
| `retry_backoff_factor` | **2.0** | Sleeps: 2s, 4s, 8s between attempts |

429: immediate stop + flush checkpoint/partial → decision `pivot` / `rate_limit_partial`. **No retry storm.**

## Resume policy (documented choice)

- **Skip** `(family, instance_id, method)` whose latest checkpoint status is `ok` — **no duplicate billing**.
- **Retry once** prior `timeout` / `error` under the **new run's** client retry budget.
- **Skip** prior `rate_limit` keys (avoid immediate 429 storm). Delete those JSONL lines (or use `--no-resume`) to force a later re-attempt after cooling down.

## CLI (parent / raytrek — resume full N_pilot)

```powershell
cd D:\develop\works\bite-ingestion
# Expand-Archive .\bite15b-fix-dist.zip -DestinationPath . -Force
# Inject ZAI_API_KEY via bw-env (human finger) — do not echo the value

python scripts/run_billed_pilot.py --no-minimal --n-per-family 24 `
  --families clean_local repeated_records sparse_anomaly dependency_chain `
             malformed_mixed dense_cross_reference adversarial_omission texture_swap `
  --checkpoint artifacts/pilot/bite15b_checkpoint.jsonl `
  --partial-out artifacts/pilot/bite15b_billed_partial.json `
  --out artifacts/pilot/bite15b_billed_summary.json `
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

## Verify (box — mocks only)

```bash
cd /workspace/path-a/bite-ingestion
PYTHONPATH=bite15-dist/src \
  .venv-bite09/bin/python -m pytest bite15-dist/tests/eval/test_billed_pilot_mock.py -q
```

## Do-not reminders

- No real Z.ai from box; parent runs billed
- No Gemini ingest; no push/publish
- No key values in artifacts/logs (presence/length only)
- Do not invent Go numbers
