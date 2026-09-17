"""Operator-sequence policies: rule-Π, length-Π, fixed-Π, oracle-Π."""

from __future__ import annotations

from .decision import PolicyDecision, RuleFire
from .fixed_policy import DEFAULT_SEQUENCE, FixedPolicy
from .grammar import (
    NORMAL_ORDER,
    GrammarError,
    drop_later_ops,
    enumerate_legal_sequences,
    is_normal_form,
    normalize_sequence,
    validate_sequence,
)
from .leak_guard import (
    OracleLeakError,
    assert_no_oracle_leak,
    check_leak,
    find_forbidden_keys,
)
from .length_policy import LengthOnlyPolicy
from .oracle_policy import OracleEvalForbiddenError, OraclePolicy
from .rule_policy import MorphologyRequiredError, RulePolicy
from .thresholds import TBD_CALIBRATE, TBDCalibrate

try:
    from .executor import apply_sequence
except ImportError:  # pragma: no cover - optional
    apply_sequence = None  # type: ignore[assignment]

__all__ = [
    "DEFAULT_SEQUENCE",
    "NORMAL_ORDER",
    "TBD_CALIBRATE",
    "FixedPolicy",
    "GrammarError",
    "LengthOnlyPolicy",
    "MorphologyRequiredError",
    "OracleEvalForbiddenError",
    "OracleLeakError",
    "OraclePolicy",
    "PolicyDecision",
    "RuleFire",
    "RulePolicy",
    "TBDCalibrate",
    "apply_sequence",
    "assert_no_oracle_leak",
    "check_leak",
    "drop_later_ops",
    "enumerate_legal_sequences",
    "find_forbidden_keys",
    "is_normal_form",
    "normalize_sequence",
    "validate_sequence",
]
