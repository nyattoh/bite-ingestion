"""oracle-Π: eval-only gold-route lookup by task_id.

Never used by the profiler. Requires allow_eval_use=True (or
evaluation_mode=True) at construction; propose() also checks context.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from bite_ingestion.interfaces.operator import OperatorId

from .decision import PolicyDecision, RuleFire
from .grammar import validate_sequence

POLICY_NAME = "oracle-Π"


class OracleEvalForbiddenError(RuntimeError):
    """Raised when oracle-Π is used without eval permission."""


class OraclePolicy:
    """Eval-only policy: looks up gold route by task_id from budget/context."""

    policy_name: str = POLICY_NAME

    def __init__(
        self,
        route_table: Mapping[str, Sequence[OperatorId | str]] | None = None,
        *,
        allow_eval_use: bool = False,
        evaluation_mode: bool = False,
    ) -> None:
        self.allow_eval_use = bool(allow_eval_use or evaluation_mode)
        self._routes: dict[str, tuple[OperatorId, ...]] = {}
        if route_table:
            for tid, seq in route_table.items():
                self._routes[str(tid)] = validate_sequence(seq)
        self._last_decision: PolicyDecision | None = None

    @property
    def last_decision(self) -> PolicyDecision | None:
        return self._last_decision

    def set_route(self, task_id: str, sequence: Sequence[OperatorId | str]) -> None:
        self._routes[str(task_id)] = validate_sequence(sequence)

    def propose(
        self,
        morphology: Mapping[str, float],
        budget: Mapping[str, object] | None = None,
    ) -> Sequence[OperatorId]:
        return self.explain_propose(morphology, budget).sequence

    def explain_propose(
        self,
        morphology: Mapping[str, float],
        budget: Mapping[str, object] | None = None,
    ) -> PolicyDecision:
        _ = morphology  # oracle does not use transparent m for routing
        if not self.allow_eval_use:
            raise OracleEvalForbiddenError(
                "oracle-Π requires allow_eval_use=True or evaluation_mode=True "
                "(eval-only; never for profiler / transparent path)"
            )

        task_id = None
        if budget:
            task_id = budget.get("task_id")
            # Also allow nested context
            ctx = budget.get("context")
            if task_id is None and isinstance(ctx, Mapping):
                task_id = ctx.get("task_id")
            # evaluation_mode override in budget for session flags
            if budget.get("evaluation_mode") is False and not self.allow_eval_use:
                raise OracleEvalForbiddenError("evaluation_mode=False in budget")

        if task_id is None:
            raise KeyError("oracle-Π requires budget['task_id'] (or context.task_id)")

        tid = str(task_id)
        if tid not in self._routes:
            raise KeyError(f"oracle-Π: no gold route for task_id={tid!r}")

        seq = self._routes[tid]
        decision = PolicyDecision(
            policy_name=self.policy_name,
            sequence=seq,
            rules_fired=[
                RuleFire(
                    rule_id="ORACLE-LOOKUP",
                    feature="task_id",
                    comparison="route_table[task_id]",
                    effect="include",
                    observed={"task_id": tid, "sequence": [o.value for o in seq]},
                    threshold=None,
                )
            ],
            notes=["eval-only", "gold route by task_id"],
        )
        self._last_decision = decision
        return decision


__all__ = ["POLICY_NAME", "OracleEvalForbiddenError", "OraclePolicy"]
