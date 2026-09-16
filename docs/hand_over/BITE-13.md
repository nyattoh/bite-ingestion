# BITE-13 handover — total-token evaluation harness + artifact ledger

- **Date**: 2026-09-16 (UTC+9)
- **Phase**: Gate B
- **Tone**: Pivot-to-bench; name plan B; no Survive claims; thresholds TBD only
- **Artifact**: `bite13-dist.zip` overlays onto `D:\develop\works\bite-ingestion`
- **Zip**: `bite13-dist.zip` (overlay; SHA256 reported by maker after pack)
- **Standing locks**: D-1..D-5b honored (synthetic/offline; no keys; no non-NF mapping; no trademark infringement)

## Gate status (explicit)

| Gate | Status | Note |
| --- | --- | --- |
| **Gate B (05–13)** | **Completion candidate** | Harness + ledger + schemas + smoke tests landed under `bite_eval` overlay |
| **Gate C (BITE-14+)** | **Blocked** | Blocked until **numeric thresholds locked (D-2)**. No Go/Pivot/Stop judgments in this task |

Do **not** treat smoke `T_total` values as calibrated scientific results or pilot success.

## Changes

### New under `src/bite_eval/`

| Path | Role |
| --- | --- |
| `accounting/` | `TokenLedger` (TokenMeter); DC-1..6 validators; char/4 proxy labeled `local_char4_proxy` |
| `harness/` | `EvalHarness.run_smoke` — offline synthetic; buckets + placeholders; soft baseline import |
| `artifacts/` | `ArtifactLedger` — manifests under `artifacts/runs/<run_id>/`; hash/redact; digest idempotency |
| `__init__.py` | Extends exports; soft-reexports BITE-12 baselines when present |

### Scripts / schemas / tests / docs / research

- `scripts/run_matrix.py` — CLI smoke over fixtures / baseline ids
- `scripts/validate_artifacts.py` — schema + ledger sum + secret-key scan
- `spec/run-manifest.schema.json` **and** `schemas/run-manifest.schema.json` (same content)
- `tests/eval/` — ledger sums, schema, reproducibility, DC-1, failed-run retention
- `docs/token-accounting.md` — formula + DC + provider vs local
- `docs/hand_over/BITE-13.md` — this file
- `research/statistical-analysis-plan.md` — stub → TBD
- `research/metric-contract.json` — T_total buckets + DC ids; numbers still TBD
- `output/eval-fixtures/` — synthetic packets

### Overlay notes

- Does **not** clobber `src/bite_ingestion/__init__.py` or operator interfaces.
- Prefer merging atop BITE-12 `bite_eval` (baselines remain). Overlay only adds accounting/harness/artifacts + updates `__init__.py`.

## API summary

```text
from bite_eval import EvalHarness, TokenLedger, ArtifactLedger

h = EvalHarness(artifact_root=".", persist=True)
manifest = h.run_smoke("raw_full", packet, context)
# manifest: status, T_total, token_buckets, metrics{quality,...}, ledger_rows, gates

ledger = TokenLedger()
ledger.record({"category":"target","kind":"api","call_id":"c1","tokens_in":10,"tokens_out":2})
ledger.totals()["T_total"]  # profiler+router+sum_c
```

## Verify (box)

- `compileall`: OK
- `pytest bite13-dist/tests/eval`: **16 passed, 1 skipped** (baseline soft-import skip without merge)
- merged with bite12 baselines: **33 passed** (16 eval + 17 baseline contract)
- `run_matrix.py` + `validate_artifacts.py`: smoke manifests OK

```bash
cd /workspace/path-a/bite-ingestion
PYTHONPATH=bite13-dist/src:bite12-dist/src:bite10-dist/src:bite09-dist/src:bite11-dist/src \
  .venv-bite09/bin/python -m compileall -q bite13-dist/src/bite_eval
PYTHONPATH=bite13-dist/src:bite12-dist/src:bite10-dist/src:bite09-dist/src:bite11-dist/src \
  .venv-bite09/bin/python -m pytest bite13-dist/tests/eval -q
```

## Verify (Windows parent after overlay)

```powershell
cd D:\develop\works\bite-ingestion
# Expand-Archive .\bite13-dist.zip -DestinationPath . -Force
python -m compileall src/bite_eval/accounting src/bite_eval/harness src/bite_eval/artifacts
python -m pytest tests/eval -q
python scripts/run_matrix.py --methods raw_full synthetic_passthrough
python scripts/validate_artifacts.py --root .
```

## Open / blockers

1. **D-2**: Numeric Go/Pivot/Stop thresholds remain TBD → **Gate C (BITE-14) blocked**.
2. Local char/4 is proxy only; provider usage wiring awaits real (still offline-stubbable) meters.
3. Cache policy (DC-3) label only — provider cache billing behavior 【未確認】.
4. Smoke does not average; later stats must not silently drop failures.
5. No paid API / no keys / no real-data download in this task.

## Do-not reminders

- No push / publish / buy / messaging / API keys / real dataset download
- No target-input-only labeled as `T_total`
- No inventing calibrated Go criteria or claiming pilot success
- Pivot-to-bench; no Survive claims

## Artifacts for next task

- Run manifest schema + `ArtifactLedger` resume-by-digest
- `TokenLedger` + DC validators
- `EvalHarness.run_smoke` offline path
- Updated `research/metric-contract.json` (still TBD numbers)

## Verify (raytrek, UTC+9 ~2026-09-16 18:50)
- ruff (python -m ruff check src tests): clean after auto-fix (I001/RUF022/RUF019/UP017)
- mypy src: Success
- pytest: **131 passed**
- run_matrix + validate_artifacts: OK (4 manifests)
- scripts/gate.ps1: **PASS**
- paid_api=False; no push/publish/keys; Gate C blocked until D-2 thresholds locked
