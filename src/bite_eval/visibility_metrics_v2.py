"""Provenance-aware visible source records v2 (Phase 4G Track B).

Does not change BITE output. Lineage alone is not visibility.
Exact text without source mapping is not visibility.
Substring occurrence is not visibility.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from bite_eval.atom_aware_reference import GoldTriple
from bite_ingestion.logical_record import LogicalRecordError, identity_of_text
from bite_ingestion.packet_contract import lineage_parent_ids

Identity = tuple[str, str]


def _is_composite(unit: Mapping[str, Any]) -> bool:
    joined = unit.get("joined_from")
    if isinstance(joined, Sequence) and not isinstance(joined, (str, bytes)) and len(joined) >= 2:
        return True
    prov = unit.get("provenance")
    return isinstance(prov, Mapping) and prov.get("kind") == "composite"


def _components(text: str) -> list[str]:
    if not text:
        return []
    return text.split("\n")


def visible_source_record_ids_v2(
    source_assignments: Sequence[Mapping[str, Any]],
    visible_units: Sequence[Mapping[str, Any]] | None,
    *,
    complete_visible_texts: Sequence[str] | None = None,
) -> set[str]:
    original = {
        str(unit.get("unit_id")): str(unit.get("text", "")).rstrip("\r\n")
        for unit in source_assignments
    }
    if visible_units is not None:
        visible: set[str] = set()
        for unit in visible_units:
            uid = str(unit.get("unit_id") or "")
            text = str(unit.get("text", ""))
            if uid in original and original[uid] == text and not _is_composite(unit):
                visible.add(uid)
                continue
            if not _is_composite(unit):
                continue
            lineage = set(lineage_parent_ids(unit))
            components = _components(text)
            for src_id, src_text in original.items():
                if src_id in lineage and src_text in components:
                    visible.add(src_id)
        return visible
    texts = list(complete_visible_texts or [])
    used = [False] * len(texts)
    visible_ids: set[str] = set()
    for unit in source_assignments:
        uid = str(unit.get("unit_id") or "")
        body = original[uid]
        idx = next((i for i, rec in enumerate(texts) if not used[i] and rec == body), None)
        if idx is None:
            continue
        used[idx] = True
        visible_ids.add(uid)
    return visible_ids


def _identities(units: Sequence[Mapping[str, Any]]) -> list[Identity]:
    out: list[Identity] = []
    for unit in units:
        try:
            ident = identity_of_text(str(unit.get("text", "")).rstrip("\r\n"))
        except LogicalRecordError:
            ident = None
        if ident is not None:
            out.append(ident)
    return out


def unique_assignment_identity_retention_v2(
    source_assignments: Sequence[Mapping[str, Any]],
    visible_ids: set[str],
) -> float | str:
    denom = set(_identities(source_assignments))
    if not denom:
        return "NA"
    kept = [unit for unit in source_assignments if str(unit.get("unit_id")) in visible_ids]
    return len(denom & set(_identities(kept))) / len(denom)


def duplicate_diagnostic_v2(
    source_assignments: Sequence[Mapping[str, Any]],
    visible_ids: set[str],
) -> dict[str, int]:
    src = Counter(_identities(source_assignments))
    vis = Counter(
        _identities([unit for unit in source_assignments if str(unit.get("unit_id")) in visible_ids])
    )
    groups = [key for key, count in src.items() if count > 1]
    return {
        "source_exact_duplicate_groups": len(groups),
        "visible_duplicate_excess": sum(max(0, count - 1) for count in vis.values()),
        "duplicate_groups_collapsed": sum(1 for key in groups if vis.get(key, 0) == 1),
    }


def visible_reference_retention_v2(
    gold: Sequence[GoldTriple],
    visible_ids: set[str],
    source_assignments: Sequence[Mapping[str, Any]],
) -> float | str:
    if not gold:
        return "NA"
    lines = {
        int(unit["line_no"]): str(unit.get("unit_id"))
        for unit in source_assignments
        if unit.get("line_no") is not None
    }
    visible_lines = {line for line, uid in lines.items() if uid in visible_ids}
    hits = sum(1 for src, _name, dst in gold if src in visible_lines and dst in visible_lines)
    return hits / len(gold)
