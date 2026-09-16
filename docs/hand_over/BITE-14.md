# BITE-14 handover — D-2 lock apply + offline synthetic pilot (Gate C first stage)

- **Date**: 2026-09-16 (UTC+9)
- **Phase**: Gate C first stage (threshold lock applied; offline pilot only)
- **Tone**: Pivot-to-bench; name plan B; **no Survive architecture claims**
- **Artifact**: `bite14-dist.zip` overlays onto `D:\develop\works\bite-ingestion`
- **Authority**: `/workspace/path-a/bite-ingestion/d2-threshold-lock-2026-09-16.md` (copied to `research/` and `docs/`)
- **Standing**: Antigravity irrelevant (desktop Path A). Synthetic + offline ONLY.

## Gate status

| Gate | Status | Note |
| --- | --- | --- |
| Gate B (05–13) | Assumed overlaid on raytrek | harness + baselines present |
| **Gate C / BITE-14** | **Offline pilot scaffold** | D-2 lock v0.1 numbers applied; decision=`insufficient_offline` under proxy tokens |
| Confirmatory Go | **Not claimed** | C1–C3 need billed `T_total`; offline `local_char4_proxy` cannot support Go |

## Lock pointer (values used — no extras invented)

| Symbol | Value |
| --- | --- |
| Q | task accuracy in [0,1]; Q_baseline = Raw full same task/model/effort |
| δ | 0.05 |
| ρ_visible | 0.50 |
| ρ_recoverable | 0.90 |
| η | 0.95 |
| J | 3 |
| B_r | min(4096, floor(0.5 · T_in(raw))) |
| N_pilot | 24 / synthetic family |
| N_full | 100 (recorded; pilot uses 24) |
| α | 0.05; confirmatory Holm; C1/C2/C3 |
| Oracle | max 15 T_total evals / instance |
| Cache | primary billed/provider; offline pilot **labels** `local_char4_proxy`; DC-3 still offline-proxy |

## Change list (repo-relative)

| Path | Role |
| --- | --- |
| `research/metric-contract.json` | scaffold → `d2_locked_v0.1`; formula/buckets kept; policy_thresholds filled |
| `research/d2-threshold-lock-2026-09-16.md` | content-identical lock reference |
| `docs/d2-threshold-lock-2026-09-16.md` | same lock copy |
| `configs/d2_lock_v0.1.json` | lock values only |
| `configs/pilot_bite14.json` | pilot wiring; proxy limitation labeled |
| `src/bite_eval/pilot/` | families (8), constraints, `decide_gate_c`, runner |
| `src/bite_eval/__init__.py` | soft-exports pilot helpers; version bite14 |
| `scripts/run_pilot.py` | offline CLI; writes summary JSON |
| `tests/eval/test_metric_contract_lock.py` | contract/config load |
| `tests/eval/test_pilot_smoke.py` | families + decide + small pilot smoke |
| `docs/hand_over/BITE-14.md` | this file |

### Overlay safety

- Does **not** ship `src/bite_ingestion/__init__.py` (no clobber).
- Does **not** replace baseline adapters; reuses soft-import pattern from BITE-13.
- Re-includes `accounting/` / `harness/` / `artifacts/` from BITE-13 for package coherence (idempotent with prior overlay).

## Pilot summary (box)

- Families: **8** (`clean_local`, `repeated_records`, `sparse_anomaly`, `dependency_chain`, `malformed_mixed`, `dense_cross_reference`, `adversarial_omission`, `texture_swap`)
- N target: **24 / family**; all 8 generable offline → **N actual = 24 / family**
- Methods: `raw_full`, `synthetic_passthrough` (deterministic offline; no LLM)
- `paid_api=false`; `estimate_source=local_char4_proxy`
- **Decision: `insufficient_offline`**
- Reason: confirmatory C1–C3 require billed `T_total` improvement / morphology increment / net savings; proxy smoke cannot honestly support **Go**

## `decide_gate_c` predicates (code comments mirror lock)

- `insufficient_offline` if `paid_api=false` OR estimate is `local_char4_proxy` OR any of C1–C3 is `None`
- `stop` if systematic constraint failure, or billed path with all C1–C3 false
- `go` only if paid + billed + constraints hold + C1∧C2∧C3
- `pivot` for partial confirmatory / scope triggers (standing remains Pivot-to-bench)

## Limitations

1. Offline char/4 proxy ≠ provider billed tokens (DC-3 still offline-proxy labeled).
2. No Gemini `local_only` auto-ingest into eval.
3. No paid API / Z.ai / keys / push / publish / purchase.
4. Morphology vs length-only (C2) not statistically tested offline.
5. Constraint smoke uses deterministic gold-matched answers — not a model eval.

## Verify (box)

```bash
cd /workspace/path-a/bite-ingestion
PYTHONPATH=bite14-dist/src \
  .venv-bite09/bin/python -m compileall -q bite14-dist/src/bite_eval
PYTHONPATH=bite14-dist/src \
  .venv-bite09/bin/python -m pytest bite14-dist/tests/eval/test_metric_contract_lock.py bite14-dist/tests/eval/test_pilot_smoke.py -q
PYTHONPATH=bite14-dist/src \
  .venv-bite09/bin/python bite14-dist/scripts/run_pilot.py --n-per-family 24 --slim \
  --out bite14-dist/artifacts/pilot/bite14_pilot_summary.json
```

## Verify (Windows parent after overlay)

```powershell
cd D:\develop\works\bite-ingestion
# Expand-Archive .\bite14-dist.zip -DestinationPath . -Force
python -m compileall src/bite_eval/pilot
python -m pytest tests/eval/test_metric_contract_lock.py tests/eval/test_pilot_smoke.py -q
python scripts/run_pilot.py --n-per-family 24 --slim --out artifacts/pilot/bite14_pilot_summary.json
# Expect decision insufficient_offline; paid_api False; local_char4_proxy labeled
```

## Do-not reminders

- No Survive claims; Pivot-to-bench
- No inventing calibrated numbers beyond D-2 lock
- Prefer `insufficient_offline` over Go on proxy/smoke
- No auto-ingest of Gemini local_only into eval

## Verify (raytrek, UTC+9 ~2026-09-16 19:45)
- Selective overlay (did not clobber BITE-13 accounting/harness)
- python -m ruff check src tests: All checks passed
- mypy src: Success
- pytest: **142 passed**
- run_pilot: 8 families × 24; decision=**insufficient_offline** (paid_api=false; T_total=local_char4_proxy; C1–C3 unevaluable)
- scripts/gate.ps1: **PASS**
- No Z.ai/keys/Gemini eval ingest/push/publish/Survive claims
