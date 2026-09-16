"""oracle_pi — wrap OraclePolicy (eval-only; requires flag)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from bite_eval.interface import (
    empty_accounting,
    extract_budget,
    extract_morphology,
    extract_text,
    make_output,
)


def _eval_flag(packet: Mapping[str, object], context: Mapping[str, object] | None) -> bool:
    for src in (context or {}, packet):
        if not isinstance(src, Mapping):
            continue
        if src.get("allow_eval_use") is True or src.get("evaluation_mode") is True:
            return True
        budget = src.get("budget")
        if isinstance(budget, Mapping) and (
            budget.get("allow_eval_use") is True or budget.get("evaluation_mode") is True
        ):
            return True
    return False


def _route_table(packet: Mapping[str, object], context: Mapping[str, object] | None) -> dict:
    for src in (context or {}, packet):
        if not isinstance(src, Mapping):
            continue
        rt = src.get("oracle_route_table") or src.get("route_table")
        if isinstance(rt, Mapping):
            return dict(rt)
        budget = src.get("budget")
        if isinstance(budget, Mapping):
            rt2 = budget.get("oracle_route_table") or budget.get("route_table")
            if isinstance(rt2, Mapping):
                return dict(rt2)
    return {}


class OraclePiBaseline:
    baseline_id: str = "oracle_pi"

    def __init__(
        self,
        policy: object | None = None,
        route_table: Mapping[str, Sequence[str]] | None = None,
        *,
        allow_eval_use: bool = False,
    ) -> None:
        self._policy = policy
        self._route_table = dict(route_table) if route_table else None
        self._allow_eval_use = allow_eval_use

    def run(
        self,
        packet: Mapping[str, object],
        context: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        try:
            from bite_ingestion.policies import OracleEvalForbiddenError, OraclePolicy
        except ImportError as exc:
            return make_output(
                baseline_id=self.baseline_id,
                status="failed",
                visible_evidence="",
                accounting=empty_accounting(),
                reason=f"oracle_pi requires bite_ingestion.policies: {exc}",
            )

        allow = self._allow_eval_use or _eval_flag(packet, context)
        if not allow:
            return make_output(
                baseline_id=self.baseline_id,
                status="failed",
                visible_evidence="",
                accounting=empty_accounting(),
                baseline_trace={"eval_flag_required": True},
                reason=(
                    "oracle_pi requires eval flag: context/packet "
                    "allow_eval_use=True or evaluation_mode=True"
                ),
            )

        try:
            routes = self._route_table or _route_table(packet, context)
            policy = self._policy or OraclePolicy(
                route_table=routes or None,
                allow_eval_use=True,
            )
            # If policy was pre-built without routes, try inject from packet
            if routes and hasattr(policy, "set_route"):
                for tid, seq in routes.items():
                    policy.set_route(str(tid), seq)  # type: ignore[attr-defined]

            morphology = extract_morphology(packet, context)
            budget = extract_budget(packet, context)
            if "task_id" not in budget:
                for src in (packet, context or {}):
                    if isinstance(src, Mapping) and "task_id" in src:
                        budget["task_id"] = src["task_id"]
                        break
            budget["evaluation_mode"] = True
            decision = policy.explain_propose(morphology, budget)  # type: ignore[attr-defined]
            seq = [o.value if hasattr(o, "value") else str(o) for o in decision.sequence]
            text = extract_text(packet)
            return make_output(
                baseline_id=self.baseline_id,
                status="ok",
                visible_evidence=text,
                accounting=empty_accounting(),
                tau=[{"op": "POLICY", "policy": "oracle-Π", "sequence": seq}],
                baseline_trace={
                    "policy_name": "oracle-Π",
                    "sequence": seq,
                    "eval_only": True,
                    "decision": decision.as_dict() if hasattr(decision, "as_dict") else None,
                },
                extra={"proposed_sequence": seq},
            )
        except OracleEvalForbiddenError as exc:
            return make_output(
                baseline_id=self.baseline_id,
                status="failed",
                visible_evidence="",
                accounting=empty_accounting(),
                reason=f"oracle_pi eval forbidden: {exc}",
            )
        except Exception as exc:  # noqa: BLE001
            return make_output(
                baseline_id=self.baseline_id,
                status="failed",
                visible_evidence="",
                accounting=empty_accounting(),
                reason=f"oracle_pi failed: {exc}",
            )


__all__ = ["OraclePiBaseline"]
