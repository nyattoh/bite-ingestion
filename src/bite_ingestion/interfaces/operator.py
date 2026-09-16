from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Protocol, runtime_checkable


class OperatorId(str, Enum):
    CUT = "CUT"
    UNTANGLE = "UNTANGLE"
    REDUCE = "REDUCE"
    INTEGRATE = "INTEGRATE"


@runtime_checkable
class Operator(Protocol):
    id: OperatorId

    def apply(
        self,
        packet: Mapping[str, object],
        context: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        """Transform an evidence packet; preserve provenance."""
