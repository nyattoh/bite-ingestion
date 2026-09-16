# BITE-05 handover

## 変更

- Offline scaffold under `D:\develop\works\bite-ingestion`（既存 task-pack は残置）
- `src/bite_ingestion`：interfaces 分離 + JSON Schemas + offline stubs
- `tests/`：schema / offline smoke / TBD config
- `configs/default.toml`：TBD・network/paid API 禁止
- `bitebench/`（BITE-06 枠）、`harness/`（BITE-13 枠）
- `scripts/gate.sh` / `gate.ps1` / `checksums.py`
- `.gitignore`

## 検証（raytrek・venv）

- `ruff check src tests`：PASS
- `mypy src`：PASS
- `pytest`：6 passed
- schema load：ok
- `scripts/checksums.py`：ok（seeds/artifacts 空）

## 未解決

- 名称案 B 人間承認
- 数値・dataset・API・予算は TBD
- BITE-06 は統括の次指示待ち

## BITE-06 投入可否

scaffold として投入可（`bitebench/` 枠あり）。実装開始は統括指示後。
