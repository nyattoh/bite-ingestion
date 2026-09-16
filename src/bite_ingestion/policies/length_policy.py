"""length-Π: length-only baseline — ignores morphology.

Uses budget.n_tokens or budget.char_len (synthetic). Cutpoints are
TBD_CALIBRATE placeholders, not empirical.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from bite_ingestion.interfaces.operator import OperatorId

from .decision import PolicyDecision, RuleFire
from .grammar import validate_sequence
from .thresholds import TBD_CALIBRATE, TBDCalibrate


def _coerce_int(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"budget.{field} must be numeric")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"budget.{field} must be numeric")

POLICY_NAME = "length-Π"


class LengthOnlyPolicy:
    """Deterministic length-only operator-sequence policy."""

    policy_name: str = POLICY_NAME

    def __init__(self, *, thresholds: TBDCalibrate | None = None) -> None:
        self.thresholds = thresholds or TBD_CALIBRATE
        self._last_decision: PolicyDecision | None = None

    @property
    def last_decision(self) -> PolicyDecision | None:
        return self._last_decision

    def propose(
        self,
        morphology: Mapping[str, float],
        budget: Mapping[str, object] | None = None,
    ) -> Sequence[OperatorId]:
        # morphology intentionally ignored
        _ = morphology
        return self.explain_propose(morphology, budget).sequence

    def explain_propose(
        self,
        morphology: Mapping[str, float],
        budget: Mapping[str, object] | None = None,
    ) -> PolicyDecision:
        _ = morphology
        thr = self.thresholds
        n_tokens = None
        char_len = None
        source = "default_short"
        if budget:
            if "n_tokens" in budget and budget["n_tokens"] is not None:
                try:
                    n_tokens = _coerce_int(budget["n_tokens"], "n_tokens")
                    source = "n_tokens"
                except (TypeError, ValueError):
                    n_tokens = None
            if n_tokens is None and "char_len" in budget and budget["char_len"] is not None:
                try:
                    char_len = _coerce_int(budget["char_len"], "char_len")
                    source = "char_len"
                except (TypeError, ValueError):
                    char_len = None

        if n_tokens is not None:
            length_val = n_tokens
            short_max = thr.LENGTH_SHORT_MAX
            med_max = thr.LENGTH_MEDIUM_MAX
        elif char_len is not None:
            length_val = char_len
            short_max = thr.CHAR_SHORT_MAX
            med_max = thr.CHAR_MEDIUM_MAX
        else:
            length_val = 0
            short_max = thr.LENGTH_SHORT_MAX
            med_max = thr.LENGTH_MEDIUM_MAX

        seq: Sequence[OperatorId]
        if length_val <= short_max:
            seq = (OperatorId.CUT,)
            band = "short"
        elif length_val <= med_max:
            seq = (OperatorId.CUT, OperatorId.REDUCE)
            band = "medium"
        else:
            seq = (OperatorId.CUT, OperatorId.REDUCE, OperatorId.INTEGRATE)
            band = "long"

        seq = validate_sequence(seq)
        fires = [
            RuleFire(
                rule_id=f"LENGTH-{band.upper()}",
                feature=source,
                comparison=f"{source}={length_val} → band={band} (TBD cutpoints)",
                effect="include",
                observed={"length": length_val, "band": band},
                threshold={"short_max": short_max, "medium_max": med_max},
            )
        ]
        decision = PolicyDecision(
            policy_name=self.policy_name,
            sequence=seq,
            rules_fired=fires,
            fallback_reason=None,
            query_conditioned=None,
            notes=["morphology ignored (length-Π)", "thresholds=TBD_CALIBRATE"],
        )
        self._last_decision = decision
        return decision


__all__ = ["POLICY_NAME", "LengthOnlyPolicy"]
