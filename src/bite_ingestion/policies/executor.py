"""Thin helper: apply a proposed sequence via bite_ingestion.operators.apply_operator.

Optional; records τ.policy_name on the packet. Soft-imports operators so
policies package remains usable without the operator library present.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from copy import deepcopy
from typing import Any

from bite_ingestion.interfaces.operator import OperatorId

from .grammar import validate_sequence


def apply_sequence(
    sequence: Sequence[OperatorId | str],
    packet: Mapping[str, object],
    *,
    policy_name: str | None = None,
    context: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Apply operators in order; write τ.policy_name when possible.

    Raises ImportError if operators package is unavailable.
    """
    seq = validate_sequence(sequence)
    from bite_ingestion.operators import apply_operator  # local import

    current: dict[str, Any] = deepcopy(dict(packet))
    for op in seq:
        current = dict(apply_operator(op, current, context))

    tau = current.get("tau")
    if not isinstance(tau, MutableMapping):
        tau = {}
        current["tau"] = tau
    if policy_name is not None:
        tau["policy_name"] = policy_name
    tau["sequence"] = [o.value for o in seq]
    return current


__all__ = ["apply_sequence"]
