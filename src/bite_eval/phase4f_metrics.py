"""Phase 4F visible-evidence metrics. Scorer-only; not sensor accuracy."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from bite_eval.atom_aware_reference import GoldTriple
from bite_ingestion.logical_record import LogicalRecordError, identity_of_text

Identity = tuple[str, str]


def serialize_routing(units: Sequence[Mapping[str, Any]]) -> str:
    return "\n".join(str(unit.get("text", "")) for unit in units)


def complete_prefix_indices(unit_texts: Sequence[str], visible: str) -> list[int]:
    kept: list[int] = []
    acc = ""
    for index, text in enumerate(unit_texts):
        nxt = text if index == 0 else f"{acc}\n{text}"
        if len(nxt) <= len(visible) and visible.startswith(nxt):
            kept.append(index)
            acc = nxt
            continue
        break
    return kept


def identities_of(texts: Sequence[str]) -> list[Identity]:
    out: list[Identity] = []
    for text in texts:
        try:
            ident = identity_of_text(text)
        except LogicalRecordError:
            ident = None
        if ident is not None:
            out.append(ident)
    return out


def unique_assignment_identity_retention(
    source_texts: Sequence[str],
    visible_texts: Sequence[str],
) -> float | str:
    denom = set(identities_of(source_texts))
    if not denom:
        return "NA"
    kept = set(identities_of(visible_texts))
    return len(denom & kept) / len(denom)


def duplicate_diagnostic(
    source_texts: Sequence[str],
    visible_texts: Sequence[str],
) -> dict[str, int]:
    source_ids = identities_of(source_texts)
    visible_ids = identities_of(visible_texts)
    src = Counter(source_ids)
    vis = Counter(visible_ids)
    groups = [key for key, count in src.items() if count > 1]
    return {
        "source_exact_duplicate_groups": len(groups),
        "visible_duplicate_excess": sum(max(0, count - 1) for count in vis.values()),
        "duplicate_groups_collapsed": sum(1 for key in groups if vis.get(key, 0) == 1),
    }


def visible_reference_retention(
    gold: Sequence[GoldTriple],
    visible_lines: set[int],
) -> float | str:
    if not gold:
        return "NA"
    hits = sum(1 for src, _name, dst in gold if src in visible_lines and dst in visible_lines)
    return hits / len(gold)


def bite_complete_lines(
    routing: Sequence[Mapping[str, Any]],
    after_units: Sequence[Mapping[str, Any]],
) -> set[int]:
    original = {str(unit.get("unit_id")): str(unit.get("text", "")) for unit in routing}
    lines = {
        int(unit["line_no"]): str(unit.get("unit_id"))
        for unit in routing
        if unit.get("line_no") is not None
    }
    complete_ids = {
        str(unit.get("unit_id"))
        for unit in after_units
        if original.get(str(unit.get("unit_id"))) == str(unit.get("text", ""))
    }
    return {line for line, uid in lines.items() if uid in complete_ids}


def prefix_complete_lines(
    routing: Sequence[Mapping[str, Any]],
    visible: str,
) -> set[int]:
    texts = [str(unit.get("text", "")) for unit in routing]
    kept = complete_prefix_indices(texts, visible)
    out: set[int] = set()
    for index in kept:
        line = routing[index].get("line_no")
        if line is not None:
            out.add(int(line))
    return out
