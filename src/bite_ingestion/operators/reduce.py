"""REDUCE operator — dedupe / aggregate / canonicalise with declared loss."""

from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import Mapping
from typing import Any

from bite_ingestion.interfaces.operator import OperatorId

from .base import (
    LOSS_AGGREGATE,
    LOSS_DEDUPE,
    LOSS_WHITESPACE,
    REASON_AGGREGATE_COUNT,
    REASON_CANONICALISE_WHITESPACE,
    REASON_DEDUPE_COLLAPSE,
    add_loss_ledger_entry,
    add_r_entry,
    add_recovery_handle,
    append_tau_step,
    deep_copy_packet,
    ensure_units,
    rebuild_visible_from_units,
    sort_units,
    stable_id,
    unit_locator,
)

_KV_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


def _canonical_ws(text: str) -> str:
    """Collapse internal whitespace runs to single space; strip ends."""
    return re.sub(r"\s+", " ", text.strip())


def _parse_kv(text: str) -> tuple[str, str] | None:
    m = _KV_LINE.match(text.strip())
    if not m:
        return None
    return m.group(1), m.group(2).strip()


def _parse_csv_row(text: str) -> tuple[str, ...] | None:
    s = text.strip()
    if "," not in s:
        return None
    # No quoted-field parser beyond simple split — synthetic fixtures only
    parts = tuple(p.strip() for p in s.split(","))
    if len(parts) < 2:
        return None
    return parts


class ReduceOperator:
    """Deterministic REDUCE: never silent-drop; declare every omit/merge in R + ledger."""

    id = OperatorId.REDUCE

    def apply(
        self,
        packet: Mapping[str, object],
        context: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        ctx = dict(context or {})
        # Optional flags; defaults enable all three structural paths
        do_dedupe = bool(ctx.get("dedupe", True))
        do_aggregate = bool(ctx.get("aggregate", True))
        do_canonicalise = bool(ctx.get("canonicalise_whitespace", True))

        out = deep_copy_packet(packet)
        units_in = sort_units(ensure_units(out))
        input_ids = [str(u.get("unit_id", "")) for u in units_in]

        omit_map: dict[str, str] = {}  # omitted_unit_id -> kept_or_aggregate_id
        r_ids: list[str] = []
        working = [dict(u) for u in units_in]

        # 1) Canonicalise whitespace (preserve original via R; declared recoverable)
        if do_canonicalise:
            next_units: list[dict[str, Any]] = []
            for u in working:
                raw = str(u.get("text", ""))
                canon = _canonical_ws(raw)
                if canon != raw:
                    new_id = stable_id("u_", out.get("packet_id", ""), "ws", u.get("unit_id", ""), canon)
                    new_u = {
                        **u,
                        "unit_id": new_id,
                        "text": canon,
                        "derived_from": u.get("unit_id"),
                    }
                    rid = add_r_entry(
                        out,
                        unit_id=str(u.get("unit_id", "")),
                        reason=REASON_CANONICALISE_WHITESPACE,
                        recoverable=True,
                        locator=unit_locator(u),
                        aggregate_parent=new_id,
                        extra={"original_text": raw, "canonical_text": canon},
                    )
                    r_ids.append(rid)
                    add_loss_ledger_entry(
                        out,
                        op=OperatorId.REDUCE,
                        kind=LOSS_WHITESPACE,
                        unit_ids=[str(u.get("unit_id", ""))],
                        note="whitespace canonicalised; original recoverable via R",
                        declared=True,
                    )
                    omit_map[str(u.get("unit_id", ""))] = new_id
                    next_units.append(new_u)
                else:
                    next_units.append(u)
            working = next_units

        # 2) Exact-text dedupe (keep first by span/unit_id order)
        if do_dedupe:
            seen: OrderedDict[str, dict[str, Any]] = OrderedDict()
            next_units = []
            for u in sort_units(working):
                key = str(u.get("text", ""))
                if key in seen:
                    kept = seen[key]
                    kept_id = str(kept.get("unit_id", ""))
                    uid = str(u.get("unit_id", ""))
                    rid = add_r_entry(
                        out,
                        unit_id=uid,
                        reason=REASON_DEDUPE_COLLAPSE,
                        recoverable=True,
                        locator=unit_locator(u),
                        aggregate_parent=kept_id,
                        extra={"duplicate_of": kept_id, "text": u.get("text")},
                    )
                    r_ids.append(rid)
                    add_loss_ledger_entry(
                        out,
                        op=OperatorId.REDUCE,
                        kind=LOSS_DEDUPE,
                        unit_ids=[uid],
                        note=f"exact duplicate collapsed into {kept_id}",
                        declared=True,
                    )
                    omit_map[uid] = kept_id
                else:
                    seen[key] = u
                    next_units.append(u)
            working = next_units

        # 3) Aggregate identical schema-ish key=value or CSV rows by counting
        if do_aggregate:
            buckets: OrderedDict[str, dict[str, Any]] = OrderedDict()
            # bucket_key -> {repr_unit, members: [unit_ids], count, kind}
            passthrough: list[dict[str, Any]] = []
            for u in sort_units(working):
                text = str(u.get("text", ""))
                kv = _parse_kv(text)
                csv = _parse_csv_row(text) if kv is None else None
                if kv is not None:
                    bkey = f"kv:{kv[0]}={kv[1]}"
                    kind = "kv"
                    display = f"{kv[0]}={kv[1]}"
                elif csv is not None:
                    bkey = "csv:" + ",".join(csv)
                    kind = "csv"
                    display = ",".join(csv)
                else:
                    passthrough.append(u)
                    continue
                if bkey not in buckets:
                    buckets[bkey] = {
                        "repr": u,
                        "members": [str(u.get("unit_id", ""))],
                        "count": 1,
                        "kind": kind,
                        "display": display,
                    }
                else:
                    buckets[bkey]["members"].append(str(u.get("unit_id", "")))
                    buckets[bkey]["count"] += 1

            next_units = list(passthrough)
            for bkey in buckets:
                info = buckets[bkey]
                members: list[str] = list(info["members"])
                count = int(info["count"])
                repr_u = dict(info["repr"])
                if count == 1:
                    next_units.append(repr_u)
                    continue
                agg_text = f"{info['display']} | count={count}"
                agg_id = stable_id("u_", out.get("packet_id", ""), "agg", bkey, count)
                agg_unit = {
                    "unit_id": agg_id,
                    "text": agg_text,
                    "span": repr_u.get("span"),
                    "source_uri": repr_u.get("source_uri"),
                    "version": repr_u.get("version"),
                    "media_type": repr_u.get("media_type"),
                    "aggregate_members": sorted(members),
                    "aggregate_count": count,
                }
                next_units.append(agg_unit)
                for mid in members:
                    rid = add_r_entry(
                        out,
                        unit_id=mid,
                        reason=REASON_AGGREGATE_COUNT,
                        recoverable=True,
                        locator={},
                        aggregate_parent=agg_id,
                        extra={"bucket": bkey, "count": count},
                    )
                    r_ids.append(rid)
                    omit_map[mid] = agg_id
                add_loss_ledger_entry(
                    out,
                    op=OperatorId.REDUCE,
                    kind=LOSS_AGGREGATE,
                    unit_ids=members,
                    note=f"aggregated {count} identical rows into {agg_id}",
                    declared=True,
                )
            working = next_units

        working = sort_units(working)
        if r_ids:
            add_recovery_handle(out, r_ids=sorted(set(r_ids)), op=OperatorId.REDUCE)

        out["units"] = working
        out["visible_evidence"] = rebuild_visible_from_units(working)
        # Deterministic omit_map key order
        omit_sorted = {k: omit_map[k] for k in sorted(omit_map.keys())}
        out["reduce"] = {"omit_map": omit_sorted}
        out["op_status"] = "ok"
        append_tau_step(
            out,
            op=OperatorId.REDUCE,
            inputs_ref=input_ids,
            outputs_ref=[str(u["unit_id"]) for u in working],
            omitted_ref=sorted(omit_map.keys()),
            extra={"reduce.omit_map": omit_sorted},
        )
        return out
