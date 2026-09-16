"""rule_pi_rebite — RulePolicy sequence + empty re-bite hook stub.

Actual RecoverEngine is an optional import; if missing, still expose
rebite_enabled=True with no-op until called.
"""

from __future__ import annotations

from collections.abc import Mapping

from bite_eval.interface import (
    empty_accounting,
    extract_budget,
    extract_morphology,
    extract_text,
    make_output,
)


def _try_recover_engine():
    try:
        from bite_ingestion.recovery import RecoverEngine  # type: ignore[attr-defined]

        return RecoverEngine
    except ImportError:  # pragma: no cover
        try:
            from bite_ingestion.recovery.engine import RecoverEngine  # type: ignore

            return RecoverEngine
        except ImportError:
            return None


class RulePiRebiteBaseline:
    baseline_id: str = "rule_pi_rebite"

    def __init__(self, policy: object | None = None) -> None:
        self._policy = policy
        self.rebite_enabled: bool = True
        self._recover_cls = _try_recover_engine()

    def rebite(
        self,
        packet: Mapping[str, object],
        request: Mapping[str, object] | None = None,
        **kwargs: object,
    ) -> Mapping[str, object]:
        """Optional re-bite hook. No-op if RecoverEngine or store/state missing."""
        eng_cls = self._recover_cls
        if eng_cls is None:
            return {
                "status": "ok",
                "rebite_enabled": True,
                "noop": True,
                "reason": "RecoverEngine not importable; empty re-bite hook stub",
                "request": dict(request or {}),
            }
        source_store = kwargs.get("source_store")
        state = kwargs.get("state")
        if source_store is None or state is None:
            return {
                "status": "ok",
                "rebite_enabled": True,
                "noop": True,
                "reason": "source_store/state not provided; empty re-bite hook stub",
                "request": dict(request or {}),
            }
        engine = eng_cls() if callable(eng_cls) else eng_cls
        recover = getattr(engine, "recover", None)
        if recover is None:
            return {
                "status": "failed",
                "rebite_enabled": True,
                "reason": "RecoverEngine has no recover()",
            }
        try:
            return recover(packet, request or {}, source_store, state)  # type: ignore[misc]
        except TypeError as exc:
            return {
                "status": "failed",
                "rebite_enabled": True,
                "reason": f"recover() signature mismatch: {exc}",
                "request": dict(request or {}),
            }

    def run(
        self,
        packet: Mapping[str, object],
        context: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        try:
            from bite_ingestion.policies import RulePolicy
        except ImportError as exc:
            return make_output(
                baseline_id=self.baseline_id,
                status="failed",
                visible_evidence="",
                accounting=empty_accounting(),
                reason=f"rule_pi_rebite requires bite_ingestion.policies: {exc}",
            )

        try:
            policy = self._policy or RulePolicy()
            morphology = extract_morphology(packet, context)
            budget = extract_budget(packet, context)
            explain = getattr(policy, "explain_propose", None)
            decision = explain(morphology, budget) if callable(explain) else None
            if decision is None:
                raise RuntimeError("policy explain_propose unavailable")
            seq = [o.value if hasattr(o, "value") else str(o) for o in decision.sequence]
            text = extract_text(packet)
            recover_available = self._recover_cls is not None
            return make_output(
                baseline_id=self.baseline_id,
                status="ok",
                visible_evidence=text,
                accounting=empty_accounting(extra={"rebite_tokens": 0}),
                tau=[
                    {"op": "POLICY", "policy": "rule-Π", "sequence": seq},
                    {"op": "REBITE_HOOK", "enabled": True, "engine_bound": recover_available},
                ],
                baseline_trace={
                    "policy_name": "rule-Π",
                    "sequence": seq,
                    "rebite_enabled": True,
                    "recover_engine_available": recover_available,
                    "decision": decision.as_dict() if hasattr(decision, "as_dict") else None,
                },
                extra={
                    "proposed_sequence": seq,
                    "rebite_enabled": True,
                },
            )
        except Exception as exc:  # noqa: BLE001 — baseline fail-closed
            return make_output(
                baseline_id=self.baseline_id,
                status="failed",
                visible_evidence="",
                accounting=empty_accounting(),
                reason=f"rule_pi_rebite failed: {exc}",
            )


__all__ = ["RulePiRebiteBaseline"]
