"""bite_eval — baselines (12) + harness (13) + pilot/Gate-C labels (14).

Name plan B / Pivot-to-bench. No Survive claims. Synthetic/offline only.
D-2 lock v0.1 applied for thresholds; offline proxy → insufficient_offline.
"""

from __future__ import annotations

from bite_eval.accounting import TokenLedger
from bite_eval.artifacts import ArtifactLedger
from bite_eval.harness import EvalHarness

# Soft re-export of BITE-12 baselines when present (overlay-safe)
try:
    from bite_eval.baselines import BASELINE_IDS, get_baseline, list_baselines
    from bite_eval.interface import STATUS_VALUES, BaselineAdapter

    _HAS_BASELINES = True
except ImportError:
    BASELINE_IDS = ()  # type: ignore[assignment]
    get_baseline = None  # type: ignore[assignment]
    list_baselines = None  # type: ignore[assignment]
    BaselineAdapter = None  # type: ignore[assignment,misc]
    STATUS_VALUES = frozenset()  # type: ignore[assignment]
    _HAS_BASELINES = False

# Soft re-export of BITE-14 pilot helpers (always present in this overlay)
try:
    from bite_eval.pilot import (
        SYNTHETIC_FAMILIES,
        ConstraintResult,
        DecisionLabel,
        check_constraints,
        decide_gate_c,
        generate_family_instances,
    )

    _HAS_PILOT = True
except ImportError:
    SYNTHETIC_FAMILIES = ()  # type: ignore[assignment]
    ConstraintResult = None  # type: ignore[assignment,misc]
    DecisionLabel = None  # type: ignore[assignment,misc]
    check_constraints = None  # type: ignore[assignment]
    decide_gate_c = None  # type: ignore[assignment]
    generate_family_instances = None  # type: ignore[assignment]
    _HAS_PILOT = False

__all__ = [
    "BASELINE_IDS",
    "STATUS_VALUES",
    "SYNTHETIC_FAMILIES",
    "ArtifactLedger",
    "BaselineAdapter",
    "ConstraintResult",
    "DecisionLabel",
    "EvalHarness",
    "TokenLedger",
    "check_constraints",
    "decide_gate_c",
    "generate_family_instances",
    "get_baseline",
    "list_baselines",
]

__version__ = "0.1.0-bite14-synthetic"
