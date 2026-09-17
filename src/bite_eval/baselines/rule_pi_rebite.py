"""rule_pi_rebite — identical to rule_pi plus bounded recovery.

The only added capability is Recover against R. Operator sequence, policy,
and packet contract match rule_pi. Extra visible text is never free:
T_rebite plus the post-recovery T_target_in must move.
"""

from __future__ import annotations

from collections.abc import Mapping

from bite_eval.arm_runtime import (
    bounded_rebite,
    ensure_operator_packet,
    output_fields_from_transformed,
    payload_text_from_packet,
)
from bite_eval.baselines.rule_pi import RulePiBaseline
from bite_eval.interface import (
    empty_accounting,
    extract_query,
    extract_text,
    make_output,
)
from bite_ingestion.packet_contract import visible_evidence_from_units

try:  # pragma: no cover - import shape only
    from bite_ingestion.policies import MorphologyRequiredError
except ImportError:  # pragma: no cover

    class MorphologyRequiredError(ValueError):  # type: ignore[no-redef]
        """Fallback when bite_ingestion.policies is unavailable."""


def _as_list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


def _as_map(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}


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
        #: Cumulative recovery cost observed via :meth:`rebite`. Reported in
        #: ``accounting["rebite_tokens"]`` so the ledger can bill T_rebite —
        #: a re-bite arm must never get its extra evidence for free.
        self.rebite_tokens: int = 0

    def _record_rebite_cost(self, result: object) -> None:
        tokens = getattr(result, "estimated_tokens", None)
        if tokens is None and isinstance(result, Mapping):
            tokens = result.get("estimated_tokens")
        try:
            self.rebite_tokens += int(tokens or 0)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            pass

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
            result = recover(packet, request or {}, source_store, state)  # type: ignore[misc]
            self._record_rebite_cost(result)
            return result
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
            inner = RulePiBaseline(policy=self._policy)
            base = dict(inner.run(packet, context))
            if str(base.get("status")) != "ok":
                base["baseline_id"] = self.baseline_id
                return base
            seq = _as_list(base.get("proposed_sequence"))
            text = extract_text(packet)
            recover_available = self._recover_cls is not None
            original_units = list(ensure_operator_packet(packet).get("units") or [])
            units_out = _as_list(base.get("units"))
            unit_maps = [u for u in units_out if isinstance(u, Mapping)]
            transformed = {
                # The source document must travel with the packet: payload
                # reconstruction re-slices it so the arm emits the document's
                # own separators, exactly like rule_pi.
                "document": text,
                "units": units_out,
                "R": _as_map(base.get("R")) or {"entries": []},
                "visible_evidence": visible_evidence_from_units(unit_maps),
                "irreversible_loss_ledger": _as_list(base.get("irreversible_loss_ledger")),
                "tau": _as_map(base.get("operator_tau")),
                "packet_id": packet.get("instance_id") or packet.get("packet_id") or "pkt",
            }
            rebite_steps: list = []
            if recover_available:
                transformed, rebite_tok, rebite_steps = bounded_rebite(
                    transformed,
                    query=extract_query(packet, context),
                    original_units=[u for u in original_units if isinstance(u, Mapping)],
                )
                self.rebite_tokens += int(rebite_tok)
                after = payload_text_from_packet(transformed)
                before = str(base.get("payload_text") or base.get("visible_evidence") or "")
                if after != before and int(rebite_tok) <= 0:
                    raise RuntimeError("recovered evidence added with T_rebite=0")
            fields = output_fields_from_transformed(transformed, original_text=text)
            tau = _as_list(base.get("tau"))
            tau.append(
                {
                    "op": "REBITE",
                    "enabled": True,
                    "engine_bound": recover_available,
                    "steps": rebite_steps,
                }
            )
            trace = _as_map(base.get("baseline_trace"))
            trace.update(
                {
                    "rebite_enabled": True,
                    "recover_engine_available": recover_available,
                    "rebite_steps": rebite_steps,
                    "transformation_status": fields["transformation_status"],
                }
            )
            return make_output(
                baseline_id=self.baseline_id,
                status="ok",
                visible_evidence=fields["payload_text"],
                accounting=empty_accounting(extra={"rebite_tokens": self.rebite_tokens}),
                tau=tau,
                baseline_trace=trace,
                extra={
                    "proposed_sequence": seq,
                    "rebite_enabled": True,
                    **fields,
                },
            )
        except MorphologyRequiredError as exc:
            return make_output(
                baseline_id=self.baseline_id,
                status="failed",
                visible_evidence="",
                accounting=empty_accounting(),
                baseline_trace={"reason_code": "morphology_missing"},
                reason=f"rule_pi_rebite morphology_missing: {exc}",
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
