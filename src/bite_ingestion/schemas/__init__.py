from __future__ import annotations

import json
from pathlib import Path

_SCHEMA_DIR = Path(__file__).resolve().parent


def load_schema(name: str) -> dict:
    with (_SCHEMA_DIR / name).open(encoding="utf-8") as f:
        return json.load(f)
