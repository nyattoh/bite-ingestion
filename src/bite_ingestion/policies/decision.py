"""Structured policy decision record (explainability; optional richer return)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bite_ingestion.interfaces.operator import OperatorId


@dataclass
class RuleFire:
    """One decision-table row that fired."""

    rule_id: str
    feature: str
    comparison: str
    effect: str  # include|omit|fallback|ignore
    observed: Any = None
    threshold: Any = None


@dataclass
class PolicyDecision:
    """Explainable outcome of a propose() call."""

    policy_name: str
    sequence: tuple[OperatorId, ...]
    rules_fired: list[RuleFire] = field(default_factory=list)
    fallback_reason: str | None = None
    query_conditioned: bool | None = None
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "policy_name": self.policy_name,
            "sequence": [o.value for o in self.sequence],
            "rules_fired": [
                {
                    "rule_id": r.rule_id,
                    "feature": r.feature,
                    "comparison": r.comparison,
                    "effect": r.effect,
                    "observed": r.observed,
                    "threshold": r.threshold,
                }
                for r in self.rules_fired
            ],
            "fallback_reason": self.fallback_reason,
            "query_conditioned": self.query_conditioned,
            "notes": list(self.notes),
        }


__all__ = ["PolicyDecision", "RuleFire"]
