"""BITE-14 offline synthetic pilot + Gate C decision labels (D-2 lock v0.1).

Pivot-to-bench only. No Survive claims. Offline proxy cannot alone support Go.
"""

from __future__ import annotations

from bite_eval.pilot.constraints import ConstraintResult, check_constraints
from bite_eval.pilot.decide import DecisionLabel, decide_gate_c
from bite_eval.pilot.families import SYNTHETIC_FAMILIES, generate_family_instances

__all__ = [
    "SYNTHETIC_FAMILIES",
    "ConstraintResult",
    "DecisionLabel",
    "check_constraints",
    "decide_gate_c",
    "generate_family_instances",
]
