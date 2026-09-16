from __future__ import annotations

import json
from pathlib import Path

import pytest

from bite_ingestion.recovery import RecoverEngine, SourceStore
from bite_ingestion.recovery.budget import RecoverBudget

FIXTURES = Path(__file__).resolve().parents[1].parent / "output" / "rebite-fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def base_packet(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "packet_base.json").read_text(encoding="utf-8"))


@pytest.fixture
def source_store(fixtures_dir: Path) -> SourceStore:
    data = json.loads((fixtures_dir / "source_store.json").read_text(encoding="utf-8"))
    return SourceStore.from_dict(data)


@pytest.fixture
def engine() -> RecoverEngine:
    return RecoverEngine(RecoverBudget(max_calls=3, token_ceiling=512))
