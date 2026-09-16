# BITE-08 handover

## 変更

- `src/bite_ingestion/profilers/__init__.py`
- `src/bite_ingestion/profilers/deterministic.py` — transparent features `b,r,s,k,a,l,p,u`; evidence; fail-closed on NUL; ignores answer/route; CPU/memory in ProfileReport
- `tests/test_profiler.py`
- `docs/morphology-feature-contract.md`, `docs/profiler-evidence.md`
- `spec/morphology.schema.json`
- `output/calibration/profiler-baseline.json`

## 検証（raytrek / D:\develop\works\bite-ingestion）

- `ruff check src tests`: All checks passed
- `mypy src`: Success (20 source files)
- `pytest`: **23 passed**
- `scripts/gate.ps1`: **PASS**
- no push / no publish / no paid API

## 次

BITE-09: operator library（CUT / UNTANGLE / REDUCE / INTEGRATE）へ進めてよい状態。
