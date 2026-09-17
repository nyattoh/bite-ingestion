"""CUT operator — split on natural boundaries; preserve source spans."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bite_ingestion.interfaces.operator import OperatorId

from .base import (
    REASON_BUDGET_TRUNCATED,
    absolute_span,
    add_r_entry,
    add_recovery_handle,
    append_tau_step,
    deep_copy_packet,
    ensure_units,
    rebuild_visible_from_units,
    sort_units,
    split_lines,
    split_paragraphs,
    split_records,
    stable_id,
    unit_locator,
)


class CutOperator:
    """Deterministic CUT: paragraph / line / record boundaries with span provenance."""

    id = OperatorId.CUT

    def apply(
        self,
        packet: Mapping[str, object],
        context: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        ctx = dict(context or {})
        out = deep_copy_packet(packet)
        units_in = ensure_units(out)
        boundary = str(ctx.get("boundary", "paragraph")).lower()
        if boundary not in {"paragraph", "line", "record"}:
            boundary = "paragraph"
        max_units = ctx.get("max_units")
        max_n: int | None = (
            int(max_units)
            if isinstance(max_units, int)
            or (isinstance(max_units, str) and str(max_units).isdigit())
            else None
        )
        if isinstance(max_units, float) and max_units == int(max_units):
            max_n = int(max_units)

        split_fn = {
            "paragraph": split_paragraphs,
            "line": split_lines,
            "record": split_records,
        }[boundary]

        produced: list[dict[str, Any]] = []
        input_ids = [str(u.get("unit_id", "")) for u in units_in]

        for parent in units_in:
            text = str(parent.get("text", ""))
            parent_span = (
                parent.get("span")
                if isinstance(parent.get("span"), Mapping)
                else {"start": 0, "end": len(text), "unit": "char"}
            )
            segments = split_fn(text)
            for local_start, local_end, seg in segments:
                # Skip pure empty segments from leading/trailing blank splits unless sole content
                if seg == "" and len(segments) > 1:
                    continue
                span = absolute_span(parent_span, local_start, local_end)
                uid = stable_id(
                    "u_",
                    out.get("packet_id", ""),
                    parent.get("unit_id", ""),
                    span["start"],
                    span["end"],
                    seg,
                )
                parent_prov = (
                    parent.get("provenance")
                    if isinstance(parent.get("provenance"), Mapping)
                    else {}
                )
                produced.append(
                    {
                        "unit_id": uid,
                        "text": seg,
                        "span": span,
                        "source_uri": parent.get("source_uri"),
                        "version": parent.get("version"),
                        "media_type": parent.get("media_type"),
                        "parent_unit_id": parent.get("unit_id"),
                        "provenance": {
                            "unit_id": uid,
                            "source_uri": parent.get("source_uri")
                            or (
                                parent_prov.get("source_uri")
                                if isinstance(parent_prov, Mapping)
                                else None
                            ),
                            "byte_or_token_span": f"char:{span['start']}-{span['end']}",
                            "renderer_id": (
                                parent_prov.get("renderer_id")
                                if isinstance(parent_prov, Mapping)
                                else None
                            ),
                        },
                    }
                )

        produced = sort_units(produced)
        omitted: list[dict[str, Any]] = []
        selected = produced
        if max_n is not None and max_n >= 0 and len(produced) > max_n:
            selected = produced[:max_n]
            omitted = produced[max_n:]

        r_ids: list[str] = []
        for om in omitted:
            rid = add_r_entry(
                out,
                unit_id=str(om["unit_id"]),
                reason=REASON_BUDGET_TRUNCATED,
                recoverable=True,
                locator=unit_locator(om),
                extra={
                    "text": om.get("text"),
                    "boundary": boundary,
                    "parent_unit_id": om.get("parent_unit_id"),
                },
            )
            r_ids.append(rid)

        if r_ids:
            add_recovery_handle(out, r_ids=r_ids, op=OperatorId.CUT)

        out["units"] = selected
        out["visible_evidence"] = rebuild_visible_from_units(selected)
        # Update top-level provenance to first selected unit when present
        if selected:
            first = selected[0]
            prov = (
                dict(out.get("provenance") or {})
                if isinstance(out.get("provenance"), Mapping)
                else {}
            )
            prov["unit_id"] = first["unit_id"]
            if first.get("source_uri") is not None:
                prov["source_uri"] = first.get("source_uri")
            span = first.get("span") or {}
            if isinstance(span, Mapping):
                prov["byte_or_token_span"] = f"char:{span.get('start')}-{span.get('end')}"
            out["provenance"] = prov

        out["cut"] = {
            "boundary": boundary,
            "max_units": max_n,
            "n_produced": len(produced),
            "n_selected": len(selected),
            "n_omitted": len(omitted),
        }
        out["op_status"] = "ok"
        append_tau_step(
            out,
            op=OperatorId.CUT,
            inputs_ref=input_ids,
            outputs_ref=[str(u["unit_id"]) for u in selected],
            omitted_ref=[str(u["unit_id"]) for u in omitted],
            extra={"boundary": boundary, "max_units": max_n},
        )
        return out
