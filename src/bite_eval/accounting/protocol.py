"""TokenMeter Protocol (from bite_ingestion.interfaces / BITE-13 readpack)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable


@runtime_checkable
class TokenMeter(Protocol):
    def record(self, event: Mapping[str, object]) -> None: ...

    def totals(self) -> Mapping[str, int | float | str]: ...


__all__ = ["TokenMeter"]
