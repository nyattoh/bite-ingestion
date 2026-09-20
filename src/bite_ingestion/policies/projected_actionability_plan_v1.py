"""Projected actionability planner v1 (Phase 3R).

Does not change operators or policy v2. Projects UNTANGLE → REDUCE_v2 →
INTEGRATE on a scratch packet and keeps only currently actionable steps.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from bite_ingestion.logical_record import LogicalRecordError, identity_of_text
from bite_ingestion.operators.integrate import IntegrateOperator
from bite_ingestion.operators.preflight import (
    explicit_join_clusters,
    routing_untangle_reasons,
)
from bite_ingestion.operators.reduce_v2 import LogicalReduceOperatorV2
from bite_ingestion.operators.untangle import UntangleOperator
from bite_ingestion.policies.leak_guard import assert_no_oracle_leak

PLANNER_NAME = "projected_actionability_plan_v1"
OPERATOR_ORDER = ("UNTANGLE", "REDUCE_v2", "INTEGRATE")
PLANNER_LEAK_KEYS = frozenset(
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
        "required_evidence_ids",
        "intended_dispersion",
    }
)


class PlannerLeakError(ValueError):
    """Raised when scorer / gold labels reach the planner."""


def _units(packet: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = packet.get("units") or []
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return [unit for unit in raw if isinstance(unit, Mapping)]
    return []


def _has_logical_dups(units: Sequence[Mapping[str, Any]]) -> bool:
    counts: Counter[tuple[str, str]] = Counter()
    for unit in units:
        try:
            ident = identity_of_text(str(unit.get("text", "")))
        except LogicalRecordError:
            ident = None
        if ident is not None:
            counts[ident] += 1
    return any(count >= 2 for count in counts.values())


def actionable(packet: Mapping[str, Any], op: str) -> bool:
    units = _units(packet)
    if op == "UNTANGLE":
        return any(routing_untangle_reasons(str(unit.get("text", ""))) for unit in units)
    if op == "REDUCE_v2":
        return _has_logical_dups(units)
    if op == "INTEGRATE":
        return bool(explicit_join_clusters(units))
    return False


def apply_operator(packet: Mapping[str, Any], op: str) -> dict[str, Any]:
    if op == "UNTANGLE":
        return dict(UntangleOperator().apply(packet))
    if op == "REDUCE_v2":
        return dict(LogicalReduceOperatorV2().apply(packet))
    if op == "INTEGRATE":
        return dict(IntegrateOperator().apply(packet))
    raise PlannerLeakError(f"{PLANNER_NAME} forbids {op}")


def _assert_gold_free(packet: Mapping[str, Any], context: Mapping[str, Any] | None) -> None:
    assert_no_oracle_leak(packet, context, where=PLANNER_NAME)
    found = sorted(key for key in packet if str(key) in PLANNER_LEAK_KEYS)
    if context:
        found.extend(sorted(key for key in context if str(key) in PLANNER_LEAK_KEYS))
    if found:
        raise PlannerLeakError(
            f"gold/texture leak into {PLANNER_NAME}: forbidden keys {sorted(set(found))}"
        )


def _suppress_reason(op: str, *, quarantined: bool, reduced: bool) -> str:
    if op == "INTEGRATE" and reduced:
        return "subsumed_by_reduce"
    if quarantined:
        return "blocked_by_quarantine"
    return "no_longer_actionable"


def plan(
    packet: Mapping[str, Any],
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    _assert_gold_free(packet, context)
    initial = {op: actionable(packet, op) for op in OPERATOR_ORDER}
    scratch = deepcopy(dict(packet))
    sequence: list[str] = []
    steps: list[dict[str, Any]] = []
    suppressed: list[dict[str, str]] = []
    quarantined = False
    reduced = False
    for op in OPERATOR_ORDER:
        is_actionable = actionable(scratch, op)
        included = is_actionable
        steps.append({"op": op, "actionable": is_actionable, "included": included})
        if included:
            if op == "UNTANGLE":
                quarantined = True
            if op == "REDUCE_v2":
                reduced = True
            sequence.append(op)
            scratch = apply_operator(scratch, op)
        elif initial[op]:
            suppressed.append(
                {
                    "op": op,
                    "reason": _suppress_reason(op, quarantined=quarantined, reduced=reduced),
                }
            )
    return {
        "planner_name": PLANNER_NAME,
        "initial_actionability": initial,
        "actionability_before_each_step": steps,
        "projected_sequence": sequence,
        "suppressed_actions": suppressed,
    }
