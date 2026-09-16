from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable


@runtime_checkable
class MorphologyProfiler(Protocol):
    def profile(self, source_unit: Mapping[str, object]) -> Mapping[str, float]:
        """Return transparent morphology features for a source unit."""
