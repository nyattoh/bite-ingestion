from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable


@runtime_checkable
class TargetModel(Protocol):
    model_id: str

    def complete(self, prompt: str, *, effort: str | None = None) -> Mapping[str, object]:
        """Scaffold implementations must stay offline."""
