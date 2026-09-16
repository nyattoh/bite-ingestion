# BITE-11 handover

## 変更（raytrek: D:\\develop\\works\\bite-ingestion）

- `src/bite_ingestion/recovery/` — RecoverEngine, guards, budget, audit, source_store, dedupe, types
- `docs/05-bounded-rebite.md`, `docs/recovery-security.md`, `docs/hand_over/BITE-11.md`
- `spec/rebite-request.schema.json`
- `tests/test_rebite.py`, `tests/recovery/conftest.py`
- `output/rebite-fixtures/*`

## 検証

- `ruff check src tests`: All checks passed
- `mypy src`: Success (45 source files)
- `pytest`: **98 passed**
- `scripts/gate.ps1`: **PASS**
- no push / no publish / no paid API / no real-data DL

## 契約メモ（D-2 拘束）

- Q_req 6種のみ。Escalate 不使用。R/handles 外は fail-closed
- J/Br は TBD_CALIBRATE（DEFAULT_J=3, DEFAULT_BR_TOKENS=512）— 確認的実験／Go判定には使わない
- token 見積は char/4 proxy（tokenizer 主張なし）
- Survive 断定なし。synthetic のみ

## 次

BITE-12: 公平な baseline adapters。投入可（D-1〜D-5b 拘束継続）。
