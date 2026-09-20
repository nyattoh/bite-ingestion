"""Atom-aware overlay-v2 reference identity for Phase 4D.

Does not change overlay v2, sensors, or Phase 4C artifacts.
Legacy line-pair recall is computed separately and never rewritten.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from bite_bench.realstruct1 import ASSIGN_RE

GoldTriple = tuple[int, str, int]
PredTriple = tuple[int, str, int]


def gold_triples(doc: Mapping[str, Any]) -> list[GoldTriple]:
    rows: list[GoldTriple] = []
    for edge in doc.get("explicit_reference_edges") or []:
        name = str(edge["name"])
        src = int(edge["source_line"])
        for dest in edge.get("dest_lines") or []:
            rows.append((src, name, int(dest)))
    return rows


def gold_pairs_legacy(doc: Mapping[str, Any]) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for edge in doc.get("explicit_reference_edges") or []:
        src = int(edge["source_line"])
        for dest in edge.get("dest_lines") or []:
            pairs.append((src, int(dest)))
    return pairs


def assign_key(text: str) -> str | None:
    match = ASSIGN_RE.match(text.rstrip("\r\n"))
    if match:
        return str(match.group(1)).strip()
    return None


def assign_value(text: str) -> str:
    match = ASSIGN_RE.match(text.rstrip("\r\n"))
    if match:
        return str(match.group(2))
    if "=" in text:
        return text.split("=", 1)[1]
    return text


def literal_ref(value: str, atom: str) -> bool:
    return f"${{{atom}}}" in value


def atom_aware_predictions(
    edges: Sequence[Mapping[str, Any]],
    routing_units: Sequence[Mapping[str, Any]],
) -> tuple[list[PredTriple], int]:
    pred: list[PredTriple] = []
    unadjudicated = 0
    for edge in edges:
        src_u = routing_units[int(edge["src"])]
        dst_u = routing_units[int(edge["dst"])]
        atom = str(edge.get("atom") or "")
        triple = (
            int(src_u["line_no"]),
            atom,
            int(dst_u["line_no"]),
        )
        value = assign_value(str(src_u.get("text", "")))
        dest_key = assign_key(str(dst_u.get("text", ""))) or ""
        if literal_ref(value, atom) and dest_key == atom:
            pred.append(triple)
        else:
            unadjudicated += 1
    return pred, unadjudicated


def score_triples(
    gold: Sequence[GoldTriple],
    pred: Sequence[PredTriple],
) -> dict[str, Any]:
    gold_set = set(gold)
    pred_set = set(pred)
    tp_set = gold_set & pred_set
    fp_set = pred_set - gold_set
    fn_set = gold_set - pred_set
    n_gold = len(gold_set)
    n_pred = len(pred_set)
    recall: float | str = "NA" if n_gold == 0 else len(tp_set) / n_gold
    precision: float | str = "NA" if n_pred == 0 else len(tp_set) / (len(tp_set) + len(fp_set))
    return {
        "n_gold_triples": n_gold,
        "n_adjudicated_predictions": n_pred,
        "tp": len(tp_set),
        "fp": len(fp_set),
        "fn": len(fn_set),
        "atom_aware_recall": recall,
        "atom_aware_precision": precision,
    }


def score_pairs_legacy(
    gold_pairs: Sequence[tuple[int, int]],
    sensor_pairs: Sequence[tuple[int, int]],
) -> dict[str, Any]:
    gold_n = len(gold_pairs)
    sensor_set = set(sensor_pairs)
    hits = sum(1 for pair in gold_pairs if pair in sensor_set)
    recall: float | str = "NA" if gold_n == 0 else hits / gold_n
    return {
        "gold_n_pairs": gold_n,
        "gold_hits_pairs": hits,
        "line_pair_recall_legacy": recall,
    }
