from __future__ import annotations

from collections.abc import Mapping, Sequence

from bite_ingestion.interfaces.operator import OperatorId


class OfflineTargetModel:
    model_id = "offline-stub"

    def complete(self, prompt: str, *, effort: str | None = None) -> Mapping[str, object]:
        raise RuntimeError("OfflineTargetModel refuses network/paid calls (BITE-05 scaffold).")


class NullTokenMeter:
    def __init__(self) -> None:
        self._events: list[Mapping[str, object]] = []

    def record(self, event: Mapping[str, object]) -> None:
        self._events.append(dict(event))

    def totals(self) -> Mapping[str, int | float | str]:
        return {"events": len(self._events), "T_total": "TBD"}


class FixedPolicy:
    def propose(
        self,
        morphology: Mapping[str, float],
        budget: Mapping[str, object] | None = None,
    ) -> Sequence[OperatorId]:
        return ()
