"""Versioned gold-free conditional texture policy v4 (Phase 3T).

Does not rewrite v3. Gate uses exact-reference v3 features. Sequence comes
from unchanged projected_actionability_plan_v1. T_high=4 is carry-forward.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from bite_ingestion.interfaces.operator import OperatorId
from bite_ingestion.operators.integrate import IntegrateOperator
from bite_ingestion.operators.reduce_v2 import LogicalReduceOperatorV2
from bite_ingestion.operators.untangle import UntangleOperator
from bite_ingestion.policies.projected_actionability_plan_v1 import plan as project_plan
from bite_ingestion.profilers.dependency_dispersion_v3 import measure as measure_dispersion

from .decision import PolicyDecision, RuleFire
from .leak_guard import assert_no_oracle_leak

POLICY_NAME = "conditional_texture_policy_v4"
LOCKED_T_HIGH_REFERENCE = 4.0
POLICY_LEAK_KEYS = frozenset(
    {
        "texture",
        "expected_sequence",
        "operator",
        "route",
        "answer",
        "expected_route",
        "duplicate_groups",
        "anomaly_unit_ids",
        "explicit_join_groups",
    }
)


class PolicyLeakError(ValueError):
    """Raised when gold / texture / route labels reach the policy."""


def _payload_of(packet: Mapping[str, Any]) -> str:
    document = packet.get("document")
    if isinstance(document, str) and document:
        return document
    units = packet.get("units") or []
    if isinstance(units, Sequence) and not isinstance(units, (str, bytes)):
        return "\n".join(str(unit.get("text", "")) for unit in units if isinstance(unit, Mapping))
    return ""


def assert_policy_gold_isolated(
    packet: Mapping[str, Any],
    context: Mapping[str, Any] | None = None,
) -> None:
    assert_no_oracle_leak(packet, context, where=POLICY_NAME)
    found = sorted(key for key in packet if str(key) in POLICY_LEAK_KEYS)
    if context:
        found.extend(sorted(key for key in context if str(key) in POLICY_LEAK_KEYS))
    if found:
        raise PolicyLeakError(
            f"gold/texture leak into {POLICY_NAME}: forbidden keys {sorted(set(found))}"
        )


def _op(name: str) -> OperatorId:
    if name == "UNTANGLE":
        return OperatorId.UNTANGLE
    if name == "REDUCE_v2":
        return OperatorId.REDUCE_V2
    if name == "INTEGRATE":
        return OperatorId.INTEGRATE
    raise PolicyLeakError(f"{POLICY_NAME} forbids {name}")


class ConditionalTexturePolicyV4:
    policy_name: str = POLICY_NAME

    def __init__(self) -> None:
        self._last_decision: PolicyDecision | None = None
        self._last_plan: dict[str, Any] | None = None

    @property
    def last_decision(self) -> PolicyDecision | None:
        return self._last_decision

    @property
    def last_plan(self) -> dict[str, Any] | None:
        return self._last_plan

    def propose(
        self,
        packet: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
    ) -> tuple[OperatorId, ...]:
        return self.explain_propose(packet, context=context).sequence

    def explain_propose(
        self,
        packet: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
    ) -> PolicyDecision:
        assert_policy_gold_isolated(packet, context)
        if context and ("dependency_edges" in context or "edges" in context):
            raise PolicyLeakError(f"{POLICY_NAME} forbids v1 edges as INTEGRATE context")
        payload = _payload_of(packet)
        dispersion = measure_dispersion({"payload": payload, "text": payload})
        n_edges = float(dispersion.features.get("n_reference_edges") or 0.0)
        mean = float(dispersion.features.get("mean_reference_edge_distance") or 0.0)
        fires: list[RuleFire] = []
        notes: list[str] = []
        self._last_plan = None
        if n_edges == 0.0:
            notes.append("no_reference_dispersion_contribution")
            fires.append(
                RuleFire(
                    rule_id="gate.n_reference_edges",
                    feature="n_reference_edges",
                    comparison="==",
                    effect="omit",
                    observed=n_edges,
                    threshold=0,
                )
            )
            decision = PolicyDecision(
                policy_name=POLICY_NAME, sequence=(), rules_fired=fires, notes=notes
            )
            self._last_decision = decision
            return decision

        gated = (not dispersion.fail_closed) and n_edges > 0.0 and mean >= LOCKED_T_HIGH_REFERENCE
        fires.append(
            RuleFire(
                rule_id="gate.high_reference_dispersion",
                feature="mean_reference_edge_distance",
                comparison=">=",
                effect="include" if gated else "omit",
                observed=mean,
                threshold=LOCKED_T_HIGH_REFERENCE,
            )
        )
        if not gated:
            notes.append("conditional_map_not_gated")
            decision = PolicyDecision(
                policy_name=POLICY_NAME, sequence=(), rules_fired=fires, notes=notes
            )
            self._last_decision = decision
            return decision

        projected = project_plan(packet, context)
        self._last_plan = projected
        chosen = tuple(_op(name) for name in projected["projected_sequence"])
        for step in projected["actionability_before_each_step"]:
            fires.append(
                RuleFire(
                    rule_id=f"plan.{step['op']}",
                    feature="projected_actionability",
                    comparison="actionable",
                    effect="include" if step["included"] else "omit",
                    observed=step["actionable"],
                )
            )
        if not chosen:
            notes.append("high_reference_dispersion_alone_does_not_select_operator")
        for row in projected["suppressed_actions"]:
            notes.append(f"suppressed:{row['op']}:{row['reason']}")
        decision = PolicyDecision(
            policy_name=POLICY_NAME, sequence=chosen, rules_fired=fires, notes=notes
        )
        self._last_decision = decision
        return decision

    def apply(
        self,
        packet: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        sequence = self.propose(packet, context=context)
        out = deepcopy(dict(packet))
        ctx = context or {}
        for op in sequence:
            if op is OperatorId.UNTANGLE:
                out = dict(UntangleOperator().apply(out, ctx))
            elif op is OperatorId.REDUCE_V2:
                out = dict(LogicalReduceOperatorV2().apply(out, ctx))
            elif op is OperatorId.INTEGRATE:
                out = dict(IntegrateOperator().apply(out, ctx))
            else:
                raise PolicyLeakError(f"{POLICY_NAME} forbids {op}")
        tau = out.get("tau")
        if not isinstance(tau, dict):
            tau = {}
            out["tau"] = tau
        tau["policy_name"] = POLICY_NAME
        tau["sequence"] = [op.value for op in sequence]
        if self._last_plan is not None:
            tau["projected_plan"] = self._last_plan
        return out
