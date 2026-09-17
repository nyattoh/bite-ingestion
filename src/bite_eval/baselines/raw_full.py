"""raw_full — pass-through full visible context (no compression)."""

from __future__ import annotations

from collections.abc import Mapping

from bite_eval.arm_runtime import payload_hash
from bite_eval.interface import (
    _coerce_int,
    empty_accounting,
    extract_budget,
    extract_text,
    make_output,
)


class RawFullBaseline:
    """Pass-through: visible_evidence = full document; overflow if max_chars exceeded."""

    baseline_id: str = "raw_full"

    def run(
        self,
        packet: Mapping[str, object],
        context: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        try:
            text = extract_text(packet)
            budget = extract_budget(packet, context)
            max_chars = budget.get("max_chars")
            if max_chars is None and context and "max_chars" in context:
                max_chars = context["max_chars"]
            if max_chars is not None:
                try:
                    limit = _coerce_int(max_chars, 0)
                except (TypeError, ValueError):
                    limit = None
                if limit is not None and len(text) > limit:
                    return make_output(
                        baseline_id=self.baseline_id,
                        status="overflow",
                        visible_evidence=text[:limit],
                        accounting=empty_accounting(),
                        tau=[{"op": "RAW_FULL", "status": "overflow"}],
                        baseline_trace={
                            "char_len": len(text),
                            "max_chars": limit,
                            "truncated": True,
                        },
                        reason=f"context overflow: char_len={len(text)} > max_chars={limit}",
                    )
            raw_units = packet.get("units")
            units = [
                dict(u)
                for u in (raw_units if isinstance(raw_units, list) else [])
                if isinstance(u, Mapping) and u.get("unit_id")
            ]
            unit_ids = [str(u["unit_id"]) for u in units]
            return make_output(
                baseline_id=self.baseline_id,
                status="ok",
                visible_evidence=text,
                accounting=empty_accounting(),
                tau=[{"op": "RAW_FULL", "status": "ok"}],
                baseline_trace={"char_len": len(text), "pass_through": True},
                extra={
                    "proposed_sequence": [],
                    "payload_text": text,
                    "payload_hash": payload_hash(text),
                    "transformation_status": "pass_through",
                    "is_no_op": True,
                    "visible_unit_ids": unit_ids,
                    # The baseline must expose the same unit graph as the
                    # candidate arms. Omitting it made provenance score 0.0
                    # for raw_full and 1.0 for every candidate — an arm
                    # difference caused by adapter fields, not by the arm.
                    "units": units,
                    "R": {"entries": []},
                    "irreversible_loss_ledger": [],
                },
            )
        except Exception as exc:  # noqa: BLE001 — surface as failed, never silent
            return make_output(
                baseline_id=self.baseline_id,
                status="failed",
                visible_evidence="",
                accounting=empty_accounting(),
                baseline_trace={"error": type(exc).__name__},
                reason=f"raw_full failed: {exc}",
            )


__all__ = ["RawFullBaseline"]
