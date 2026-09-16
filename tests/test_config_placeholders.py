from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_default_config_marks_tbd() -> None:
    text = (ROOT / "configs" / "default.toml").read_text(encoding="utf-8")
    assert "TBD" in text
    assert "allow_network = false" in text
    assert "allow_paid_api = false" in text
