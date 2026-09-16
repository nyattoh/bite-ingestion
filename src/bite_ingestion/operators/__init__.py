"""Provenance-preserving deterministic operator library (CUT/UNTANGLE/REDUCE/INTEGRATE)."""

from __future__ import annotations

from collections.abc import Mapping

from bite_ingestion.interfaces.operator import Operator, OperatorId

from .cut import CutOperator
from .integrate import IntegrateOperator
from .loss_ledger import assert_no_undeclared_loss, audit_undeclared_visible_loss
from .reduce import ReduceOperator
from .untangle import UntangleOperator

__all__ = [
    "OPERATOR_REGISTRY",
    "CutOperator",
    "IntegrateOperator",
    "OperatorId",
    "ReduceOperator",
    "UntangleOperator",
    "apply_operator",
    "assert_no_undeclared_loss",
    "audit_undeclared_visible_loss",
    "get_operator",
]

OPERATOR_REGISTRY: dict[OperatorId, Operator] = {
    OperatorId.CUT: CutOperator(),
    OperatorId.UNTANGLE: UntangleOperator(),
    OperatorId.REDUCE: ReduceOperator(),
    OperatorId.INTEGRATE: IntegrateOperator(),
}


def get_operator(op_id: OperatorId | str) -> Operator:
    """Return a registered operator instance by id."""
    key = OperatorId(op_id) if not isinstance(op_id, OperatorId) else op_id
    if key not in OPERATOR_REGISTRY:
        raise KeyError(f"unknown operator: {op_id!r}")
    return OPERATOR_REGISTRY[key]


def apply_operator(
    op_id: OperatorId | str,
    packet: Mapping[str, object],
    context: Mapping[str, object] | None = None,
) -> Mapping[str, object]:
    """Apply a registered operator; always deterministic mode."""
    return get_operator(op_id).apply(packet, context)
