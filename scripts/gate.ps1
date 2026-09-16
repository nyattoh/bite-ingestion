$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
python -m pip install -e '.[dev]' -q
python -m ruff check src tests
python -m mypy src
python -m pytest
python -c "from pathlib import Path; import json; root=Path('src/bite_ingestion/schemas'); [json.loads((root/n).read_text(encoding='utf-8')) for n in ('source_unit.schema.json','evidence_packet.schema.json')]; print('schema files: ok')"
python scripts/checksums.py
Write-Output 'gate: PASS'
