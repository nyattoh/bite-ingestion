from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[2] / "output" / "operator-fixtures"


def load_fixture(name: str) -> dict:
    with open(FIXTURES / name, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def cut_paragraph():
    return load_fixture("cut_paragraph.json")


@pytest.fixture
def cut_lines():
    return load_fixture("cut_lines.json")


@pytest.fixture
def untangle_mixed():
    return load_fixture("untangle_mixed.json")


@pytest.fixture
def reduce_dupes():
    return load_fixture("reduce_dupes.json")


@pytest.fixture
def integrate_keys():
    return load_fixture("integrate_keys.json")


@pytest.fixture
def minimal_packet():
    return load_fixture("minimal_scaffold.json")
