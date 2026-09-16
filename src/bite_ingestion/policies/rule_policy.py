"""Transparent rule-Π: morphology + budget → normal-form operator sequence.

Decision direction follows BITE-02 §3.2 omit rules. Thresholds live under
TBD_CALIBRATE (synthetic placeholders — not empirical).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from bite_ingestion.interfaces.operator import OperatorId

from .decision import PolicyDecision, RuleFire
from .grammar import GrammarError, drop_later_ops, validate_sequence
from .leak_guard import assert_no_oracle_leak
from .thresholds import TBD_CALIBRATE, TBDCalibrate

POLICY_NAME = "rule-Π"


def _f(morphology: Mapping[str, float], key: str, default: float = 0.0) -> float:
    v = morphology.get(key, default)
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _budget_flag(budget: Mapping[str, object] | None, key: str, default: Any = None) -> Any:
    if not budget:
        return default
    return budget.get(key, default)


class RulePolicy:
    """Deterministic transparent operator-sequence policy (rule-Π)."""

    policy_name: str = POLICY_NAME

    def __init__(
        self,
        *,
        query_conditioned: bool = True,
        thresholds: TBDCalibrate | None = None,
        empty_fallback: OperatorId = OperatorId.CUT,
    ) -> None:
        self.query_conditioned = query_conditioned
        self.thresholds = thresholds or TBD_CALIBRATE
        # If all ops omitted: prefer CUT (segmentation baseline) unless
        # budget says pre_segmented and length suggests REDUCE — see docs.
        self.empty_fallback = empty_fallback
        self._last_decision: PolicyDecision | None = None

    @property
    def last_decision(self) -> PolicyDecision | None:
        return self._last_decision

    def propose(
        self,
        morphology: Mapping[str, float],
        budget: Mapping[str, object] | None = None,
    ) -> Sequence[OperatorId]:
        decision = self.explain_propose(morphology, budget)
        return decision.sequence

    def explain_propose(
        self,
        morphology: Mapping[str, float],
        budget: Mapping[str, object] | None = None,
    ) -> PolicyDecision:
        # Hard leak check — raise if oracle/eval keys present.
        assert_no_oracle_leak(morphology, budget, where="rule-Π morphology/budget")

        thr = self.thresholds
        fires: list[RuleFire] = []
        include: dict[OperatorId, bool] = {
            OperatorId.CUT: False,
            OperatorId.UNTANGLE: False,
            OperatorId.REDUCE: False,
            OperatorId.INTEGRATE: False,
        }

        b = _f(morphology, "b")
        a = _f(morphology, "a")
        r = _f(morphology, "r")
        k = _f(morphology, "k")
        # Query-conditioned features: accept but zero-out when disabled.
        if self.query_conditioned:
            l = _f(morphology, "l")
            u = _f(morphology, "u")
        else:
            l = 0.0
            u = 0.0
            fires.append(
                RuleFire(
                    rule_id="QC-OFF",
                    feature="l,u",
                    comparison="query_conditioned=False → zero",
                    effect="ignore",
                    observed={"l": _f(morphology, "l"), "u": _f(morphology, "u")},
                    threshold=None,
                )
            )

        pre_segmented = bool(_budget_flag(budget, "pre_segmented", False))
        malformed = bool(
            _budget_flag(budget, "malformed", False)
            or _budget_flag(budget, "malformed_flag", False)
        )

        # --- CUT: include if b low OR not pre-segmented; omit if b high AND pre_segmented
        if b >= thr.HIGH and pre_segmented:
            include[OperatorId.CUT] = False
            fires.append(
                RuleFire(
                    rule_id="CUT-OMIT",
                    feature="b,pre_segmented",
                    comparison=f"b≥HIGH({thr.HIGH}) AND pre_segmented=True",
                    effect="omit",
                    observed={"b": b, "pre_segmented": pre_segmented},
                    threshold=thr.HIGH,
                )
            )
        else:
            include[OperatorId.CUT] = True
            reason = "b<HIGH" if b < thr.HIGH else "pre_segmented=False"
            fires.append(
                RuleFire(
                    rule_id="CUT-IN",
                    feature="b,pre_segmented",
                    comparison=f"{reason} → include CUT",
                    effect="include",
                    observed={"b": b, "pre_segmented": pre_segmented},
                    threshold=thr.HIGH,
                )
            )

        # --- UNTANGLE: include if a high OR malformed; omit if a low and no malformed
        if a >= thr.HIGH or malformed:
            include[OperatorId.UNTANGLE] = True
            fires.append(
                RuleFire(
                    rule_id="UNTANGLE-IN",
                    feature="a,malformed",
                    comparison=f"a≥HIGH({thr.HIGH}) OR malformed",
                    effect="include",
                    observed={"a": a, "malformed": malformed},
                    threshold=thr.HIGH,
                )
            )
        else:
            include[OperatorId.UNTANGLE] = False
            fires.append(
                RuleFire(
                    rule_id="UNTANGLE-OMIT",
                    feature="a,malformed",
                    comparison=f"a<HIGH({thr.HIGH}) AND malformed=False",
                    effect="omit",
                    observed={"a": a, "malformed": malformed},
                    threshold=thr.HIGH,
                )
            )

        # --- REDUCE: include if r high; omit if r low
        if r >= thr.HIGH:
            include[OperatorId.REDUCE] = True
            fires.append(
                RuleFire(
                    rule_id="REDUCE-IN",
                    feature="r",
                    comparison=f"r≥HIGH({thr.HIGH})",
                    effect="include",
                    observed={"r": r},
                    threshold=thr.HIGH,
                )
            )
        else:
            include[OperatorId.REDUCE] = False
            fires.append(
                RuleFire(
                    rule_id="REDUCE-OMIT",
                    feature="r",
                    comparison=f"r<HIGH({thr.HIGH})",
                    effect="omit",
                    observed={"r": r},
                    threshold=thr.HIGH,
                )
            )

        # --- INTEGRATE: if query_conditioned: k high AND l low; else k high only
        if self.query_conditioned:
            if k >= thr.HIGH and l <= thr.LOW:
                include[OperatorId.INTEGRATE] = True
                fires.append(
                    RuleFire(
                        rule_id="INTEGRATE-IN-QC",
                        feature="k,l",
                        comparison=f"k≥HIGH({thr.HIGH}) AND l≤LOW({thr.LOW})",
                        effect="include",
                        observed={"k": k, "l": l},
                        threshold={"HIGH": thr.HIGH, "LOW": thr.LOW},
                    )
                )
            else:
                include[OperatorId.INTEGRATE] = False
                fires.append(
                    RuleFire(
                        rule_id="INTEGRATE-OMIT-QC",
                        feature="k,l",
                        comparison="NOT (k≥HIGH AND l≤LOW)",
                        effect="omit",
                        observed={"k": k, "l": l},
                        threshold={"HIGH": thr.HIGH, "LOW": thr.LOW},
                    )
                )
        else:
            if k >= thr.HIGH:
                include[OperatorId.INTEGRATE] = True
                fires.append(
                    RuleFire(
                        rule_id="INTEGRATE-IN-NOQC",
                        feature="k",
                        comparison=f"k≥HIGH({thr.HIGH}) (query_conditioned=False)",
                        effect="include",
                        observed={"k": k, "l_ignored": _f(morphology, "l")},
                        threshold=thr.HIGH,
                    )
                )
            else:
                include[OperatorId.INTEGRATE] = False
                fires.append(
                    RuleFire(
                        rule_id="INTEGRATE-OMIT-NOQC",
                        feature="k",
                        comparison=f"k<HIGH({thr.HIGH}) (query_conditioned=False)",
                        effect="omit",
                        observed={"k": k},
                        threshold=thr.HIGH,
                    )
                )

        # Build sequence in normal order
        seq_list = [op for op in (
            OperatorId.CUT,
            OperatorId.UNTANGLE,
            OperatorId.REDUCE,
            OperatorId.INTEGRATE,
        ) if include[op]]

        fallback_reason: str | None = None
        notes: list[str] = []
        if u > 0 and self.query_conditioned:
            notes.append(f"u={u:.3f} accepted but unused for routing in v0.1")

        # Always ≥1 op
        if not seq_list:
            # Fallback choice: if pre_segmented and length/budget suggests
            # compression need, use REDUCE; else CUT (document in hand_over).
            n_tokens = _budget_flag(budget, "n_tokens", None)
            use_reduce = False
            if pre_segmented:
                try:
                    if n_tokens is not None and int(n_tokens) > thr.LENGTH_SHORT_MAX:
                        use_reduce = True
                except (TypeError, ValueError):
                    pass
            fb = OperatorId.REDUCE if use_reduce else self.empty_fallback
            seq_list = [fb]
            fallback_reason = (
                f"all_ops_omitted→{fb.value}"
                + (";pre_segmented_long→REDUCE" if use_reduce else ";default→CUT")
            )
            fires.append(
                RuleFire(
                    rule_id="EMPTY-FALLBACK",
                    feature="all_omit",
                    comparison="no op included → fallback ≥1",
                    effect="fallback",
                    observed={"chosen": fb.value, "pre_segmented": pre_segmented},
                    threshold=None,
                )
            )

        # Budget fallback: max_ops / token_budget too small → drop later ops
        max_ops = _budget_flag(budget, "max_ops", None)
        if max_ops is not None:
            try:
                mo = int(max_ops)
                if mo >= 1 and len(seq_list) > mo:
                    before = list(seq_list)
                    seq_list = list(drop_later_ops(seq_list, mo))
                    reason = f"budget.max_ops={mo} truncated {before}→{seq_list}"
                    fallback_reason = (
                        f"{fallback_reason};{reason}" if fallback_reason else reason
                    )
                    fires.append(
                        RuleFire(
                            rule_id="BUDGET-MAX-OPS",
                            feature="budget.max_ops",
                            comparison=f"len>{mo} → drop later ops",
                            effect="fallback",
                            observed={"before": [o.value for o in before], "after": [o.value for o in seq_list]},
                            threshold=mo,
                        )
                    )
            except (TypeError, ValueError, GrammarError):
                pass

        # token_budget: coarse heuristic — if very small, force max_ops=1
        token_budget = _budget_flag(budget, "token_budget", None)
        if token_budget is not None:
            try:
                tb = int(token_budget)
                # Synthetic: if token_budget < LENGTH_SHORT_MAX, keep only first op
                if tb < thr.LENGTH_SHORT_MAX and len(seq_list) > 1:
                    before = list(seq_list)
                    seq_list = list(drop_later_ops(seq_list, 1))
                    reason = f"budget.token_budget={tb}<SHORT→keep1"
                    fallback_reason = (
                        f"{fallback_reason};{reason}" if fallback_reason else reason
                    )
                    fires.append(
                        RuleFire(
                            rule_id="BUDGET-TOKEN",
                            feature="budget.token_budget",
                            comparison=f"token_budget<{thr.LENGTH_SHORT_MAX} → max 1 op",
                            effect="fallback",
                            observed={"before": [o.value for o in before], "after": [o.value for o in seq_list]},
                            threshold=thr.LENGTH_SHORT_MAX,
                        )
                    )
            except (TypeError, ValueError, GrammarError):
                pass

        sequence = validate_sequence(seq_list)
        decision = PolicyDecision(
            policy_name=self.policy_name,
            sequence=sequence,
            rules_fired=fires,
            fallback_reason=fallback_reason,
            query_conditioned=self.query_conditioned,
            notes=notes,
        )
        self._last_decision = decision
        return decision


__all__ = ["POLICY_NAME", "RulePolicy"]
