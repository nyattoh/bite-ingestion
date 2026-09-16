# BITE-15 handover — billed pilot overlay (Path A / Z.ai)

- **Date**: 2026-09-16 (UTC+9)
- **Phase**: Gate C billed smoke (after BITE-14 `insufficient_offline` on proxy)
- **Tone**: Pivot-to-bench; no Survive claims; no Go on minimal N
- **Artifact**: `bite15-dist.zip` overlays onto `D:\develop\works\bite-ingestion`
- **Standing**: Box builds/tests with mocks only. Parent (raytrek) runs billed with key via bw-env.

## Why BITE-15

BITE-14 decided `insufficient_offline` because `T_total` was `local_char4_proxy`.  
D-2 lock / DC-3: primary `T_total` = **billed provider usage**. This overlay adds a thin Z.ai client + billed runner so confirmatory C1–C3 can be assessed with real usage (parent machine).

## Change list (repo-relative)

| Path | Role |
| --- | --- |
| `src/bite_eval/providers/zai_client.py` | Thin chat client; env key; usage parse; RateLimitError on 429; redacted traces |
| `src/bite_eval/providers/__init__.py` | Package exports |
| `src/bite_eval/pilot/billed_runner.py` | Synthetic families + billed target calls; T_total from usage only |
| `src/bite_eval/pilot/decide.py` | Extended: `provider_usage_billed`, `sample_meets_n_pilot`, `rate_limit_partial` |
| `scripts/run_billed_pilot.py` | CLI; `--minimal` default; KEY_ABSENT exit 2; partial on 429 |
| `configs/pilot_bite15_billed.json` | Model, minimal sizes, lock refs, `paid_api=true` |
| `tests/eval/test_billed_pilot_mock.py` | Mocked HTTP; key absent; usage parse; decide_gate_c billed |
| `docs/hand_over/BITE-15.md` | This file |

Reuses BITE-14 pilot families/constraints and BITE-13 accounting (logical char4 kept **separate**).

## Model choice

- **Selected**: `glm-4.5-flash`
- **Base URL**: `https://api.z.ai/api/paas/v4/`
- **Rationale**: Documented on Z.ai chat-completion model enum as a cheap/flash tier; preferred over `glm-4.5` / larger series for pilot cost. If parent docs differ, override with `--model`.

## Minimal-set rationale (default)

| Knob | Value |
| --- | --- |
| Families | `clean_local`, `adversarial_omission` (2) |
| Instances / family | 3 |
| Methods | `raw_full`, `compressed_passthrough` |
| Target calls | **12** |

Rationale: first billed smoke must not explode cost/rate-limit budget. Expand toward lock `N_pilot=24` / family later:

```bash
python scripts/run_billed_pilot.py --no-minimal --n-per-family 24 \
  --families clean_local repeated_records sparse_anomaly dependency_chain \
             malformed_mixed dense_cross_reference adversarial_omission texture_swap
```

## How billed `T_total` is computed

1. Each target call → Z.ai `chat/completions`.
2. Read `response.usage`: `prompt_tokens`, `completion_tokens`, `total_tokens`, `cached_tokens`.
3. Row field **`T_total`** = `total_tokens` (or prompt+completion if total missing).
4. Label: `estimate_source=provider_usage_billed`.
5. **`T_logical_char4_proxy`** may be stored alongside for diagnostics — **never** written into `T_total`.
6. Mixing proxy into billed `T_total` is forbidden (fail / insufficient).

## Decision policy (encoded + documented)

| Condition | Label |
| --- | --- |
| No billed usage on paid path | `insufficient_offline` |
| Rate-limited mid-run (partial saved) | `pivot` (reason `rate_limit_partial`) |
| Systematic constraint failure | `stop` |
| Minimal 2×3 (or n ≪ N_pilot) even if C1–C3 look good | **`pivot`** (need full N_pilot billed) |
| All C1–C3 false under billed | `stop` |
| `go` | Only if paid + `provider_usage_billed` + C1∧C2∧C3 + constraints hold + **`sample_meets_n_pilot`** — **minimal set will NOT fire go** |

C2 in the minimal runner is a **placeholder** (compressed constraints not worse than raw); true morphology-vs-length-only needs a length-only arm — treat minimal C2 as provisional.

## Go / Pivot / Stop predicates (summary)

- **Go**: confirmatory C1–C3 + N_pilot billed + constraints — not claimed on minimal.
- **Pivot**: default for minimal billed; also rate-limit partial; partial confirmatory.
- **Stop**: systematic constraint fail, or billed all-C false.
- **insufficient_offline**: no billed usage / proxy-only / C unevaluable without rate-limit path.

## Security / limits

- Key: env `ZAI_API_KEY` only. Presence: PRESENT/ABSENT (+ optional length). **Never** print/log/write key values.
- HTTP traces: Authorization redacted (`***REDACTED***`).
- No Gemini `local_only` ingest. No push/publish/purchase.
- Box pytest uses **mocks only** — do not call real Z.ai from the box.
- Parent injects key via bw-env/Bitwarden finger; CLI exit 2 if absent:

  `KEY_ABSENT: need human finger to inject via bw-env/Bitwarden`

## CLI usage (parent / raytrek)

```powershell
cd D:\develop\works\bite-ingestion
# Expand-Archive .\bite15-dist.zip -DestinationPath . -Force
# Inject ZAI_API_KEY via bw-env (human finger) — do not echo the value
python scripts/run_billed_pilot.py --minimal --out artifacts/pilot/bite15_billed_summary.json
# On 429: artifacts/pilot/bite15_billed_partial.json + decision pivot
```

## Verify (box — mocks only)

```bash
cd /workspace/path-a/bite-ingestion
PYTHONPATH=bite15-dist/src \
  .venv-bite09/bin/python -m compileall -q bite15-dist/src/bite_eval
PYTHONPATH=bite15-dist/src \
  .venv-bite09/bin/python -m pytest bite15-dist/tests/eval/test_billed_pilot_mock.py bite15-dist/tests/eval/test_pilot_smoke.py -q
# KEY_ABSENT path (no network):
env -u ZAI_API_KEY PYTHONPATH=bite15-dist/src \
  .venv-bite09/bin/python bite15-dist/scripts/run_billed_pilot.py --minimal ; echo exit=$?
# Expect exit 2 and KEY_ABSENT message
```

## Do-not reminders

- No Survive claims; Pivot-to-bench
- No Go on minimal n ≪ N_pilot
- No mixing `local_char4_proxy` into billed `T_total`
- No key values in artifacts/logs
- No real Z.ai from box; parent runs billed


## BITE-15b follow-up (2026-09-17 UTC+9)

Full N_pilot billed run initially hit `TimeoutError` with no summary. Checkpoint/resume: **`docs/hand_over/BITE-15b.md`**.

**v1** [`e44b5bd`](https://github.com/nyattoh/bite-ingestion/commit/e44b5bd): `stop` but empty-answer confounder.  
**v2** [`967ec0b`](https://github.com/nyattoh/bite-ingestion/commit/967ec0b): thinking-disabled rebill → **`pivot`** (`c1=False c2=True c3=False`). **Not Go.** Artifacts: `bite15b_billed_summary_v2.json`. Next: BITE-16 (`docs/hand_over/BITE-16.md`).
