"""raw_full — pass-through full visible context (no compression)."""

from __future__ import annotations

from collections.abc import Mapping

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
            return make_output(
                baseline_id=self.baseline_id,
                status="ok",
                visible_evidence=text,
                accounting=empty_accounting(),
                tau=[{"op": "RAW_FULL", "status": "ok"}],
                baseline_trace={"char_len": len(text), "pass_through": True},
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
