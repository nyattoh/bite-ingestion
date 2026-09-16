"""universal_reduce — always APPLY / propose REDUCE only (FixedPolicy)."""

from __future__ import annotations

from collections.abc import Mapping

from bite_eval.interface import (
    empty_accounting,
    extract_budget,
    extract_morphology,
    extract_text,
    make_output,
)


class UniversalReduceBaseline:
    """One universal reduction operator baseline (H5 counterfactual)."""

    baseline_id: str = "universal_reduce"

    def run(
        self,
        packet: Mapping[str, object],
        context: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        try:
            from bite_ingestion.interfaces.operator import OperatorId
            from bite_ingestion.policies import FixedPolicy
        except ImportError as exc:
            # Offline fallback without policies: still propose REDUCE in trace
            text = extract_text(packet)
            return make_output(
                baseline_id=self.baseline_id,
                status="ok",
                visible_evidence=text,
                accounting=empty_accounting(),
                tau=[{"op": "REDUCE", "universal": True}],
                baseline_trace={
                    "sequence": ["REDUCE"],
                    "note": f"policies unavailable ({exc}); stub REDUCE proposal",
                },
                extra={"proposed_sequence": ["REDUCE"]},
            )

        try:
            policy = FixedPolicy(sequence=(OperatorId.REDUCE,))
            morphology = extract_morphology(packet, context)
            budget = extract_budget(packet, context)
            decision = policy.explain_propose(morphology, budget)
            seq = [o.value for o in decision.sequence]
            text = extract_text(packet)
            # Optional: try apply REDUCE if operators available
            applied = False
            visible = text
            try:
                from bite_ingestion.policies import apply_sequence

                if apply_sequence is not None:
                    out_pkt = apply_sequence((OperatorId.REDUCE,), packet, policy_name="universal_reduce", context=context)
                    if isinstance(out_pkt, Mapping):
                        ve = out_pkt.get("visible_evidence", text)
                        visible = ve
                        applied = True
            except (ImportError, TypeError, ValueError, AttributeError):
                applied = False

            return make_output(
                baseline_id=self.baseline_id,
                status="ok",
                visible_evidence=visible,
                accounting=empty_accounting(),
                tau=[{"op": "REDUCE", "universal": True, "applied": applied}],
                baseline_trace={
                    "sequence": seq,
                    "applied": applied,
                    "policy_name": "fixed-Π(REDUCE)",
                },
                extra={"proposed_sequence": seq},
            )
        except Exception as exc:  # noqa: BLE001
            return make_output(
                baseline_id=self.baseline_id,
                status="failed",
                visible_evidence="",
                accounting=empty_accounting(),
                reason=f"universal_reduce failed: {exc}",
            )


__all__ = ["UniversalReduceBaseline"]
