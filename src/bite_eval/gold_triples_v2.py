"""Canonical gold triples v2 (Phase 4J).

Reads the two historical annotation shapes without repairing them.
Does not change gold_triples (Phase 4D dest_lines-only reader).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bite_eval.atom_aware_reference import GoldTriple


class GoldSchemaError(ValueError):
    """Raised when an annotation edge cannot be canonicalized fail-closed."""


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def gold_triples_v2(doc: Mapping[str, Any]) -> list[GoldTriple]:
    rows: list[GoldTriple] = []
    source_id = str(doc.get("source_id") or "")
    for index, edge in enumerate(doc.get("explicit_reference_edges") or []):
        if not isinstance(edge, Mapping):
            raise GoldSchemaError(f"{source_id}[{index}]: edge must be an object")
        has_line = "dest_line" in edge
        has_lines = "dest_lines" in edge
        where = f"{source_id}[{index}]"
        if has_line and has_lines:
            raise GoldSchemaError(f"{where}: both dest_line and dest_lines present")
        if not has_line and not has_lines:
            raise GoldSchemaError(f"{where}: neither dest_line nor dest_lines present")
        if "name" not in edge or "source_line" not in edge:
            raise GoldSchemaError(f"{where}: name/source_line missing")
        if not _is_int(edge["source_line"]):
            raise GoldSchemaError(f"{where}: source_line must be integer")
        name = str(edge["name"])
        src = int(edge["source_line"])
        dests: list[int]
        if has_lines:
            raw = edge["dest_lines"]
            if not isinstance(raw, list) or not raw:
                raise GoldSchemaError(f"{where}: dest_lines must be non-empty integer list")
            if not all(_is_int(item) for item in raw):
                raise GoldSchemaError(f"{where}: dest_lines must be integer list")
            dests = [int(item) for item in raw]
        else:
            dest = edge["dest_line"]
            if not _is_int(dest):
                raise GoldSchemaError(f"{where}: dest_line must be integer")
            dests = [int(dest)]
        for dest in dests:
            triple: GoldTriple = (src, name, dest)
            if "gold_identity" in edge:
                ident = edge["gold_identity"]
                expected = [src, name, dest]
                if ident != expected:
                    raise GoldSchemaError(
                        f"{where}: gold_identity {ident!r} != canonical {expected!r}"
                    )
            rows.append(triple)
    return rows
