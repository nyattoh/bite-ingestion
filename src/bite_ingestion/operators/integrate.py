"""INTEGRATE operator — deterministic join only (no LM calls)."""

from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from typing import Any

from bite_ingestion.interfaces.operator import OperatorId

from .base import (
    append_tau_step,
    deep_copy_packet,
    ensure_units,
    sort_units,
    stable_id,
)

_ID_FIELD = re.compile(r"\b(?:id|key)\s*=\s*([A-Za-z0-9_\-.]+)", re.IGNORECASE)
_REF_FIELD = re.compile(r"(?:ref:|#see\s+)([A-Za-z0-9_\-./]+)", re.IGNORECASE)


def _extract_join_keys(text: str) -> list[str]:
    keys = [m.group(1) for m in _ID_FIELD.finditer(text)]
    return keys


def _context_dep_edges(context: Mapping[str, object]) -> list[tuple[str, str]]:
    """Pull dependency edges from context (e.g. prior UNTANGLE output)."""
    edges: list[tuple[str, str]] = []
    raw = context.get("dependency_edges")
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        for e in raw:
            if isinstance(e, Mapping) and "from" in e and "to" in e:
                edges.append((str(e["from"]), str(e["to"])))
            elif isinstance(e, Sequence) and len(e) == 2:
                edges.append((str(e[0]), str(e[1])))
    # Also accept untangle-shaped blob
    unt = context.get("untangle")
    if isinstance(unt, Mapping):
        for e in unt.get("dependency_edges") or []:
            if isinstance(e, Mapping) and "from" in e and "to" in e:
                edges.append((str(e["from"]), str(e["to"])))
    return edges


class IntegrateOperator:
    """Deterministic INTEGRATE: join on shared keys / dependency edges; never LM."""

    id = OperatorId.INTEGRATE

    def apply(
        self,
        packet: Mapping[str, object],
        context: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        ctx = dict(context or {})
        mode = str(ctx.get("integrate_mode", "deterministic_join"))
        if mode != "deterministic_join":
            # Soft fail: no LM path in this library
            out = deep_copy_packet(packet)
            ensure_units(out)
            out["op_status"] = "failed"
            out["integrate"] = {
                "integrate_mode": mode,
                "join_plan": [],
                "used_evidence_ids": [],
                "error": "only deterministic_join supported in BITE-09 library",
            }
            append_tau_step(
                out,
                op=OperatorId.INTEGRATE,
                inputs_ref=[str(u.get("unit_id", "")) for u in out.get("units") or []],
                outputs_ref=[],
                omitted_ref=[],
                errors=[out["integrate"]["error"]],
                extra={"integrate_mode": mode},
            )
            out["op_last_touch"] = OperatorId.INTEGRATE.value
            return out

        out = deep_copy_packet(packet)
        units_in = sort_units(ensure_units(out))
        input_ids = [str(u.get("unit_id", "")) for u in units_in]
        id_to_unit = {str(u.get("unit_id", "")): u for u in units_in}

        # Groups by explicit id=/key= fields
        groups: OrderedDict[str, list[str]] = OrderedDict()
        unkeyed: list[str] = []
        for u in units_in:
            uid = str(u.get("unit_id", ""))
            keys = _extract_join_keys(str(u.get("text", "")))
            if not keys:
                unkeyed.append(uid)
                continue
            # primary join key = first key occurrence (deterministic)
            jk = keys[0]
            groups.setdefault(jk, []).append(uid)

        # Merge via dependency edges from context / packet.untangle
        edges = _context_dep_edges(ctx)
        if isinstance(out.get("untangle"), Mapping):
            edges.extend(_context_dep_edges({"untangle": out["untangle"]}))
        edges = sorted(set(edges))

        # Union-find over units linked by same join key or dependency edge
        parent: dict[str, str] = {uid: uid for uid in input_ids}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            if a not in parent or b not in parent:
                return
            ra, rb = find(a), find(b)
            if ra == rb:
                return
            # deterministic: prefer lexicographically smaller root
            if ra < rb:
                parent[rb] = ra
            else:
                parent[ra] = rb

        for jk, members in groups.items():
            for m in members[1:]:
                union(members[0], m)

        for a, b in edges:
            if a in parent and b in parent:
                union(a, b)

        # Also union units that share the same extracted key string across groups already handled

        clusters: OrderedDict[str, list[str]] = OrderedDict()
        for uid in input_ids:
            root = find(uid)
            clusters.setdefault(root, []).append(uid)
        for root in clusters:
            clusters[root] = sorted(set(clusters[root]))

        join_plan: list[dict[str, Any]] = []
        integrated_units: list[dict[str, Any]] = []
        used: list[str] = []

        # Emit integrated units for clusters with size >= 2; pass through singles
        for root in sorted(clusters.keys()):
            members = clusters[root]
            if len(members) < 2:
                continue
            # Join key: prefer explicit key from first member text, else root
            texts_keys: list[str] = []
            for mid in members:
                texts_keys.extend(_extract_join_keys(str(id_to_unit[mid].get("text", ""))))
            join_key = texts_keys[0] if texts_keys else f"dep:{root}"
            method = "key_field" if texts_keys else "dependency_edge"
            join_plan.append({"join_key": join_key, "unit_ids": members, "method": method})
            used.extend(members)
            joined_text = "\n".join(str(id_to_unit[m].get("text", "")) for m in members)
            new_id = stable_id("u_", out.get("packet_id", ""), "join", join_key, *members)
            first = id_to_unit[members[0]]
            integrated_units.append(
                {
                    "unit_id": new_id,
                    "text": joined_text,
                    "span": first.get("span"),
                    "source_uri": first.get("source_uri"),
                    "version": first.get("version"),
                    "media_type": first.get("media_type"),
                    "joined_from": members,
                    "join_key": join_key,
                }
            )

        # Pass-through units not consumed by a multi-join
        used_set = set(used)
        for u in units_in:
            uid = str(u.get("unit_id", ""))
            if uid not in used_set:
                integrated_units.append(dict(u))

        integrated_units = sort_units(integrated_units)
        # Stable sort join_plan
        join_plan = sorted(join_plan, key=lambda j: (str(j["join_key"]), ",".join(j["unit_ids"])))
        used_evidence_ids = sorted(set(used))

        out["units"] = integrated_units
        # Visible items keep provenance pointers to input unit_ids
        visible: list[dict[str, Any]] = []
        for u in integrated_units:
            src_ids = list(u.get("joined_from") or [u.get("unit_id")])
            visible.append(
                {
                    "text": str(u.get("text", "")),
                    "role": None,
                    "unit_ids": [str(x) for x in src_ids],
                }
            )
        out["visible_evidence"] = visible
        out["integrate"] = {
            "integrate_mode": "deterministic_join",
            "join_plan": join_plan,
            "used_evidence_ids": used_evidence_ids,
        }
        out["op_status"] = "ok"
        append_tau_step(
            out,
            op=OperatorId.INTEGRATE,
            inputs_ref=input_ids,
            outputs_ref=[str(u["unit_id"]) for u in integrated_units],
            omitted_ref=[],
            extra={
                "integrate_mode": "deterministic_join",
                "join_plan": join_plan,
                "used_evidence_ids": used_evidence_ids,
            },
        )
        return out
