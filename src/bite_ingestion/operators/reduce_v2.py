"""Logical REDUCE v2 — dedupe by logical_record_identity_v2.

Does not change ReduceOperator. Does not rewrite unit IDs for whitespace.
Keep first source-exact representative. Omitted units are R-recoverable.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
from typing import Any

from bite_ingestion.interfaces.operator import OperatorId
from bite_ingestion.logical_record import LogicalRecordError, identity_of_text

from .base import (
    LOSS_DEDUPE,
    REASON_DEDUPE_COLLAPSE,
    add_loss_ledger_entry,
    add_r_entry,
    add_recovery_handle,
    append_tau_step,
    deep_copy_packet,
    ensure_units,
    rebuild_visible_from_units,
    sort_units,
    unit_locator,
)


class LogicalReduceOperatorV2:
    """Dedupe supported logical records; leave unsupported units untouched."""

    id = OperatorId.REDUCE_V2

    def apply(
        self,
        packet: Mapping[str, object],
        context: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        _ = context
        out = deep_copy_packet(packet)
        units_in = sort_units(ensure_units(out))
        input_ids = [str(u.get("unit_id", "")) for u in units_in]
        seen: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()
        kept: list[dict[str, Any]] = []
        omit_map: dict[str, str] = {}
        r_ids: list[str] = []

        for unit in units_in:
            text = str(unit.get("text", ""))
            try:
                ident = identity_of_text(text)
            except LogicalRecordError:
                ident = None
            if ident is None:
                kept.append(dict(unit))
                continue
            if ident in seen:
                kept_unit = seen[ident]
                kept_id = str(kept_unit.get("unit_id", ""))
                uid = str(unit.get("unit_id", ""))
                rid = add_r_entry(
                    out,
                    unit_id=uid,
                    reason=REASON_DEDUPE_COLLAPSE,
                    recoverable=True,
                    locator=unit_locator(unit),
                    aggregate_parent=kept_id,
                    extra={
                        "original_text": text,
                        "source_span": dict(unit.get("span") or {}),
                        "provenance": dict(unit.get("provenance") or {}),
                        "duplicate_of": kept_id,
                        "parent_unit_id": unit.get("parent_unit_id") or uid,
                    },
                )
                r_ids.append(rid)
                add_loss_ledger_entry(
                    out,
                    op=OperatorId.REDUCE_V2,
                    kind=LOSS_DEDUPE,
                    unit_ids=[uid],
                    note=f"logical duplicate collapsed into {kept_id}",
                    declared=True,
                )
                omit_map[uid] = kept_id
            else:
                seen[ident] = unit
                kept.append(dict(unit))

        if r_ids:
            add_recovery_handle(out, r_ids=sorted(set(r_ids)), op=OperatorId.REDUCE_V2)
        out["units"] = sort_units(kept)
        out["visible_evidence"] = rebuild_visible_from_units(out["units"])
        out["reduce"] = {"omit_map": {key: omit_map[key] for key in sorted(omit_map)}}
        out["op_status"] = "ok"
        append_tau_step(
            out,
            op=OperatorId.REDUCE_V2,
            inputs_ref=input_ids,
            outputs_ref=[str(u["unit_id"]) for u in out["units"]],
            omitted_ref=sorted(omit_map),
            extra={"reduce.omit_map": out["reduce"]["omit_map"]},
        )
        return out
