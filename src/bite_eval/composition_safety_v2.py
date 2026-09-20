"""Lineage-aware composition safety v2 (Phase 3P).

Does not change phase3m_eval.composition_safety. Join/overmerge compare
root lineage sets, not current unit IDs.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from bite_eval.accounting.estimate import estimate_tokens_char4
from bite_ingestion.logical_record import identity_of_text
from bite_ingestion.operators.loss_ledger import audit_undeclared_visible_loss
from bite_ingestion.operators.preflight import (
    explicit_join_clusters,
    extract_explicit_join_keys,
)
from bite_ingestion.packet_contract import (
    conservation_untraced,
    lineage_parent_ids,
    provenance_completeness,
    root_ids_of,
)


def _units(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = packet.get("units") or []
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return [dict(unit) for unit in raw if isinstance(unit, Mapping)]
    return []


def _r_entries(packet: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    blob = packet.get("R")
    if not isinstance(blob, Mapping):
        return []
    raw = blob.get("entries") or []
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return [row for row in raw if isinstance(row, Mapping)]
    return []


def _ledger(packet: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = packet.get("irreversible_loss_ledger") or []
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return [row for row in raw if isinstance(row, Mapping)]
    return []


def _isolated_ids(packet: Mapping[str, Any]) -> list[str]:
    blob = packet.get("untangle")
    if not isinstance(blob, Mapping):
        return []
    out: list[str] = []
    for row in blob.get("isolated") or []:
        if isinstance(row, Mapping) and row.get("unit_id"):
            out.append(str(row["unit_id"]))
    return out


def _join_plans(packet: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    blob = packet.get("integrate")
    if not isinstance(blob, Mapping):
        return []
    raw = blob.get("join_plan") or []
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return [row for row in raw if isinstance(row, Mapping)]
    return []


def _lineage_index(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for unit in _units(before) + _units(after):
        uid = str(unit.get("unit_id", ""))
        if uid:
            by_id[uid] = unit
    extra_units = before.get("lineage_units") or after.get("lineage_units") or []
    if isinstance(extra_units, Sequence) and not isinstance(extra_units, (str, bytes)):
        for unit in extra_units:
            if isinstance(unit, Mapping) and unit.get("unit_id"):
                by_id.setdefault(str(unit["unit_id"]), dict(unit))
    for row in _r_entries(after):
        uid = str(row.get("unit_id") or "")
        extra_raw = row.get("extra")
        extra: Mapping[str, Any] = extra_raw if isinstance(extra_raw, Mapping) else {}
        if not uid:
            continue
        by_id.setdefault(
            uid,
            {
                "unit_id": uid,
                "text": extra.get("original_text", ""),
                "span": extra.get("source_span") or {},
                "provenance": extra.get("provenance") or {},
                "parent_unit_id": extra.get("parent_unit_id"),
            },
        )
    return by_id


def _parents_of(uid: str, unit: Mapping[str, Any], r_entries: Sequence[Mapping[str, Any]]) -> list[str]:
    parents = list(lineage_parent_ids(unit))
    for row in r_entries:
        extra_raw = row.get("extra")
        extra: Mapping[str, Any] = extra_raw if isinstance(extra_raw, Mapping) else {}
        if str(row.get("unit_id")) == uid:
            for key in ("duplicate_of", "parent_unit_id"):
                val = extra.get(key) or row.get("aggregate_parent")
                if val:
                    parents.append(str(val))
    seen: set[str] = set()
    out: list[str] = []
    for parent in parents:
        if parent and parent not in seen:
            seen.add(parent)
            out.append(parent)
    return out


def resolve_root_ids(
    uids: Sequence[str],
    by_id: Mapping[str, Mapping[str, Any]],
    r_entries: Sequence[Mapping[str, Any]],
) -> set[str]:
    roots: set[str] = set()
    for start in uids:
        if not start:
            continue
        seen: set[str] = set()
        stack = [str(start)]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            unit = by_id.get(cur)
            if unit is None:
                roots.add(cur)
                continue
            parents = _parents_of(cur, unit, r_entries)
            if not parents:
                roots.add(cur)
                continue
            stack.extend(parents)
    return roots


def _text_of(uid: str, by_id: Mapping[str, Mapping[str, Any]]) -> str:
    unit = by_id.get(uid)
    if unit is None:
        return ""
    return str(unit.get("text", ""))


def composition_safety_v2(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    gold_ids: Sequence[str],
    sequence: Sequence[str],
) -> dict[str, Any]:
    visible = _units(after)
    input_units = _units(before)
    input_ids = [str(unit["unit_id"]) for unit in input_units]
    gold = {str(uid) for uid in gold_ids}
    r_entries = _r_entries(after)
    by_id = _lineage_index(before, after)
    roots = root_ids_of([str(unit["unit_id"]) for unit in visible], visible) | resolve_root_ids(
        [str(unit["unit_id"]) for unit in visible], by_id, r_entries
    )
    recoverable = {
        str(row["unit_id"])
        for row in r_entries
        if row.get("unit_id") and row.get("recoverable") is True
    }
    lineage_recall = 1.0 if not gold else len(gold & (roots | recoverable)) / len(gold)
    completeness = provenance_completeness(visible)
    untraced = conservation_untraced(
        input_ids,
        visible_units=visible,
        r_entries=r_entries,
        loss_ledger=_ledger(after),
    )
    audit = audit_undeclared_visible_loss(before, after)
    joined_ids: set[str] = set()
    for unit in visible:
        raw_joined = unit.get("joined_from") or []
        if isinstance(raw_joined, Sequence) and not isinstance(raw_joined, (str, bytes)):
            joined_ids.update(str(member) for member in raw_joined)
    for plan in _join_plans(after):
        joined_ids.update(str(uid) for uid in plan.get("unit_ids") or [])
    join_roots = resolve_root_ids(sorted(joined_ids), by_id, r_entries)
    isolated = set(_isolated_ids(after))
    covered_ids = set(joined_ids) | join_roots | recoverable | isolated
    covered_texts = {_text_of(uid, by_id) for uid in covered_ids}
    for row in r_entries:
        extra_raw = row.get("extra")
        extra = extra_raw if isinstance(extra_raw, Mapping) else {}
        if extra.get("original_text"):
            covered_texts.add(str(extra["original_text"]))
    undeclared_units = [uid for uid in audit["undeclared_units"] if uid not in covered_ids]
    undeclared_texts = [text for text in audit["undeclared_texts"] if text not in covered_texts]
    silent = len(undeclared_texts) + len(undeclared_units)
    quarantine_ok = all(
        str(row.get("unit_id")) not in isolated or row.get("recoverable") is True
        for row in r_entries
    ) and all(
        any(str(row.get("unit_id")) == uid and row.get("recoverable") is True for row in r_entries)
        for uid in isolated
    )

    ops = [str(op) for op in sequence]
    reduce_ok = True
    if "REDUCE_v2" in ops or "REDUCE" in ops:
        after_idents: list[tuple[str, str]] = []
        for unit in visible:
            try:
                ident = identity_of_text(str(unit.get("text", "")))
            except Exception:  # noqa: BLE001
                ident = None
            if ident is not None:
                after_idents.append(ident)
        reduce_ok = all(count <= 1 for count in Counter(after_idents).values())

    clusters = explicit_join_clusters(input_units)
    integrate_ok = True
    overmerge_ok = True
    if "INTEGRATE" in ops:
        alive_clusters = []
        for cluster in clusters:
            alive = [uid for uid in cluster["unit_ids"] if uid not in isolated]
            if len(alive) >= 2:
                alive_clusters.append(alive)
        plans = _join_plans(after)
        plan_root_sets = [
            resolve_root_ids([str(uid) for uid in plan.get("unit_ids") or []], by_id, r_entries)
            for plan in plans
        ]
        for alive in alive_clusters:
            cluster_roots = resolve_root_ids(alive, by_id, r_entries)
            if not any(cluster_roots <= plan_roots for plan_roots in plan_root_sets):
                integrate_ok = False
        composite = [
            unit
            for unit in visible
            if isinstance(unit.get("joined_from"), list) and len(unit.get("joined_from") or []) >= 2
        ]
        if alive_clusters and not composite:
            integrate_ok = False
        for plan in plans:
            if str(plan.get("method")) == "dependency_edge":
                overmerge_ok = False
                continue
            members = [str(uid) for uid in plan.get("unit_ids") or []]
            member_roots = resolve_root_ids(members, by_id, r_entries)
            keysets = [
                set(extract_explicit_join_keys(_text_of(uid, by_id))) for uid in members
            ]
            keysets = [keys for keys in keysets if keys]
            if len(keysets) < 2:
                keysets = [
                    set(extract_explicit_join_keys(_text_of(uid, by_id)))
                    for uid in member_roots
                ]
                keysets = [keys for keys in keysets if keys]
            shared = set.intersection(*keysets) if len(keysets) >= 2 else set()
            if not shared:
                overmerge_ok = False
    elif _join_plans(after):
        overmerge_ok = False
        integrate_ok = False

    checks = {
        "lineage_recall": lineage_recall == 1.0,
        "provenance_completeness": completeness == 1.0,
        "conservation_untraced": untraced == [],
        "silent_loss": silent == 0,
        "quarantine_recoverable": quarantine_ok,
        "reduce_only_logical_duplicates": reduce_ok,
        "integrate_explicit_join_composite": integrate_ok,
        "no_unrelated_overmerge": overmerge_ok,
    }
    return {
        "lineage_recall": lineage_recall,
        "provenance_completeness": completeness,
        "conservation_untraced": untraced,
        "silent_loss": silent,
        "quarantine_recoverable": quarantine_ok,
        "reduce_only_logical_duplicates": reduce_ok,
        "integrate_explicit_join_composite": integrate_ok,
        "no_unrelated_overmerge": overmerge_ok,
        "ok": all(checks.values()),
        "checks": checks,
        "join_roots_used": sorted(join_roots),
        "token_proxy_before": estimate_tokens_char4(str(before.get("document") or "")),
        "token_proxy_after": estimate_tokens_char4(
            "\n".join(str(unit.get("text", "")) for unit in visible)
        ),
    }
