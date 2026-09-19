"""Versioned gold-free conditional texture policy v2 (Phase 3P).

Does not rewrite v1, RulePolicy, gate, UNTANGLE, or INTEGRATE predicates.
REDUCE uses structural_redundancy_v2 and LogicalReduceOperatorV2.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from bite_ingestion.interfaces.operator import OperatorId
from bite_ingestion.operators.integrate import IntegrateOperator
from bite_ingestion.operators.preflight import (
    explicit_join_clusters,
    routing_untangle_reasons,
)
from bite_ingestion.operators.reduce_v2 import LogicalReduceOperatorV2
from bite_ingestion.operators.untangle import UntangleOperator
from bite_ingestion.profilers.dependency_dispersion_v1 import measure as measure_dispersion
from bite_ingestion.profilers.structural_redundancy_v2 import measure as measure_redundancy

from .decision import PolicyDecision, RuleFire
from .leak_guard import assert_no_oracle_leak

POLICY_NAME = "conditional_texture_policy_v2"
LOCKED_T_HIGH = 4.0
POLICY_LEAK_KEYS = frozenset(
    {
        "texture",
        "expected_sequence",
        "operator",
        "route",
        "answer",
        "expected_route",
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


def _units_of(packet: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = packet.get("units") or []
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return [unit for unit in raw if isinstance(unit, Mapping)]
    return []


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


class ConditionalTexturePolicyV2:
    policy_name: str = POLICY_NAME

    def __init__(self) -> None:
        self._last_decision: PolicyDecision | None = None

    @property
    def last_decision(self) -> PolicyDecision | None:
        return self._last_decision

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
        source = {"payload": payload, "text": payload}
        dispersion = measure_dispersion(source)
        redundancy = measure_redundancy(source)
        n_edges = float(dispersion.features.get("n_edges") or 0.0)
        mean = float(dispersion.features.get("mean_edge_distance") or 0.0)
        ratio = float(redundancy.features.get("duplicate_unit_ratio") or 0.0)
        fires: list[RuleFire] = []
        notes: list[str] = []
        if n_edges == 0.0:
            notes.append("no_dependency_dispersion_contribution")
            fires.append(
                RuleFire(
                    rule_id="gate.n_edges",
                    feature="n_edges",
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

        gated = (not dispersion.fail_closed) and n_edges > 0.0 and mean >= LOCKED_T_HIGH
        fires.append(
            RuleFire(
                rule_id="gate.high_dispersion",
                feature="mean_edge_distance",
                comparison=">=",
                effect="include" if gated else "omit",
                observed=mean,
                threshold=LOCKED_T_HIGH,
            )
        )
        if not gated:
            notes.append("conditional_map_not_gated")
            decision = PolicyDecision(
                policy_name=POLICY_NAME, sequence=(), rules_fired=fires, notes=notes
            )
            self._last_decision = decision
            return decision

        untangle = any(
            routing_untangle_reasons(str(unit.get("text", ""))) for unit in _units_of(packet)
        )
        reduce = (not redundancy.fail_closed) and ratio > 0.0
        integrate = bool(explicit_join_clusters(_units_of(packet)))
        fires.append(
            RuleFire(
                rule_id="pred.UNTANGLE",
                feature="routing_untangle_reasons",
                comparison="any",
                effect="include" if untangle else "omit",
                observed=untangle,
            )
        )
        fires.append(
            RuleFire(
                rule_id="pred.REDUCE_v2",
                feature="duplicate_unit_ratio",
                comparison=">",
                effect="include" if reduce else "omit",
                observed=ratio,
                threshold=0,
            )
        )
        fires.append(
            RuleFire(
                rule_id="pred.INTEGRATE",
                feature="explicit_id_key_join",
                comparison="cluster>=2",
                effect="include" if integrate else "omit",
                observed=integrate,
            )
        )
        chosen: list[OperatorId] = []
        if untangle:
            chosen.append(OperatorId.UNTANGLE)
        if reduce:
            chosen.append(OperatorId.REDUCE_V2)
        if integrate:
            chosen.append(OperatorId.INTEGRATE)
        if not chosen:
            notes.append("high_dispersion_alone_does_not_select_operator")
        decision = PolicyDecision(
            policy_name=POLICY_NAME, sequence=tuple(chosen), rules_fired=fires, notes=notes
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
        return out
