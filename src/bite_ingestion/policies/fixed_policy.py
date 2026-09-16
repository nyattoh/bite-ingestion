"""fixed-Π: same legal sequence for every task (H5 counterfactual)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from bite_ingestion.interfaces.operator import OperatorId

from .decision import PolicyDecision, RuleFire
from .grammar import validate_sequence

POLICY_NAME = "fixed-Π"

DEFAULT_SEQUENCE: tuple[OperatorId, ...] = (OperatorId.CUT, OperatorId.REDUCE)


class FixedPolicy:
    """Always propose the same configurable normal-form sequence."""

    policy_name: str = POLICY_NAME

    def __init__(
        self,
        sequence: Sequence[OperatorId | str] | None = None,
    ) -> None:
        self._sequence = validate_sequence(sequence if sequence is not None else DEFAULT_SEQUENCE)
        self._last_decision: PolicyDecision | None = None

    @property
    def sequence(self) -> tuple[OperatorId, ...]:
        return self._sequence

    @property
    def last_decision(self) -> PolicyDecision | None:
        return self._last_decision

    def propose(
        self,
        morphology: Mapping[str, float],
        budget: Mapping[str, object] | None = None,
    ) -> Sequence[OperatorId]:
        _ = morphology, budget
        return self.explain_propose(morphology, budget).sequence

    def explain_propose(
        self,
        morphology: Mapping[str, float],
        budget: Mapping[str, object] | None = None,
    ) -> PolicyDecision:
        _ = morphology, budget
        decision = PolicyDecision(
            policy_name=self.policy_name,
            sequence=self._sequence,
            rules_fired=[
                RuleFire(
                    rule_id="FIXED",
                    feature="none",
                    comparison="constant sequence",
                    effect="include",
                    observed={"sequence": [o.value for o in self._sequence]},
                    threshold=None,
                )
            ],
            notes=["morphology and budget ignored (fixed-Π)"],
        )
        self._last_decision = decision
        return decision


__all__ = ["DEFAULT_SEQUENCE", "POLICY_NAME", "FixedPolicy"]
