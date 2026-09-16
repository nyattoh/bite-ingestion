"""rule_pi — wrap RulePolicy (rule-Π / morphology-aware candidate)."""

from __future__ import annotations

from collections.abc import Mapping

from bite_eval.interface import (
    empty_accounting,
    extract_budget,
    extract_morphology,
    extract_text,
    make_output,
)


def _policy(**kwargs: object):
    from bite_ingestion.policies import RulePolicy

    return RulePolicy(**kwargs)  # type: ignore[arg-type]


class RulePiBaseline:
    baseline_id: str = "rule_pi"

    def __init__(self, policy: object | None = None, **kwargs: object) -> None:
        self._policy = policy
        self._kwargs = kwargs

    def run(
        self,
        packet: Mapping[str, object],
        context: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        try:
            policy = self._policy or _policy(**self._kwargs)
            morphology = extract_morphology(packet, context)
            budget = extract_budget(packet, context)
            explain = getattr(policy, "explain_propose", None)
            decision = explain(morphology, budget) if callable(explain) else None
            if decision is None:
                raise RuntimeError("policy explain_propose unavailable")
            seq = [o.value if hasattr(o, "value") else str(o) for o in decision.sequence]
            text = extract_text(packet)
            return make_output(
                baseline_id=self.baseline_id,
                status="ok",
                visible_evidence=text,
                accounting=empty_accounting(),
                tau=[{"op": "POLICY", "policy": "rule-Π", "sequence": seq}],
                baseline_trace={
                    "policy_name": getattr(decision, "policy_name", "rule-Π"),
                    "sequence": seq,
                    "decision": decision.as_dict() if hasattr(decision, "as_dict") else None,
                },
                extra={"proposed_sequence": seq},
            )
        except ImportError as exc:
            return make_output(
                baseline_id=self.baseline_id,
                status="failed",
                visible_evidence="",
                accounting=empty_accounting(),
                reason=f"rule_pi requires bite_ingestion.policies: {exc}",
            )
        except Exception as exc:  # noqa: BLE001
            return make_output(
                baseline_id=self.baseline_id,
                status="failed",
                visible_evidence="",
                accounting=empty_accounting(),
                reason=f"rule_pi failed: {exc}",
            )


__all__ = ["RulePiBaseline"]
