"""Source-exact dual-plane adapter for REALSTRUCT-1.

Does not change sensors, policy v4, planner, or operators.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from bite_bench.realstruct1 import ASSIGN_RE, COMMENT_RE, SECTION_RE, decode_source
from bite_ingestion.packet_contract import (
    make_unit,
    validate_units,
    visible_evidence_from_units,
)

ADAPTER_ID = "realstruct1_adapter_v1"
RENDERER_ID = "realstruct1-adapter-v1"


class AdapterError(ValueError):
    """Raised when source-exact projection cannot be built."""


def classify_line(body: str) -> tuple[str, str | None]:
    if not body.strip():
        return "unsupported", "blank"
    if COMMENT_RE.match(body):
        return "unsupported", "comment"
    if SECTION_RE.match(body):
        return "unsupported", "section"
    if ASSIGN_RE.match(body):
        return "assignment", None
    return "unsupported", "other"


def _source_uri(source_id: str) -> str:
    return f"realstruct-1://{source_id}"


def source_units_from_bytes(raw: bytes, *, source_id: str) -> dict[str, Any]:
    text, encoding = decode_source(raw)
    if text.encode(encoding) != raw:
        raise AdapterError(f"{source_id}: decoded text does not round-trip to raw bytes")
    uri = _source_uri(source_id)
    units: list[dict[str, Any]] = []
    offset = 0
    for line_no, line in enumerate(text.splitlines(keepends=True), 1):
        start = offset
        end = offset + len(line)
        body = line.rstrip("\r\n")
        kind, reason = classify_line(body)
        unit = make_unit(
            unit_id=f"{source_id}-s{line_no:04d}",
            text=line,
            start=start,
            end=end,
            source_uri=uri,
            renderer_id=RENDERER_ID,
        )
        unit["line_no"] = line_no
        unit["plane"] = "source"
        unit["line_kind"] = kind
        if reason:
            unit["unsupported_reason"] = reason
        units.append(unit)
        offset = end
    if offset != len(text):
        raise AdapterError(f"{source_id}: source spans leave a gap")
    joined = "".join(str(unit["text"]) for unit in units)
    if joined != text:
        raise AdapterError(f"{source_id}: source concat drifted from decoded text")
    if joined.encode(encoding) != raw:
        raise AdapterError(f"{source_id}: source concat drifted from raw SHA256 bytes")
    validate_units(units, document=text)
    return {
        "encoding": encoding,
        "document": text,
        "units": units,
        "n_source_units": len(units),
        "n_assignments": sum(1 for unit in units if unit["line_kind"] == "assignment"),
        "n_unsupported": sum(1 for unit in units if unit["line_kind"] != "assignment"),
    }


def routing_units_from_source(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    document = str(source["document"])
    out: list[dict[str, Any]] = []
    for unit in source["units"]:
        if unit.get("line_kind") != "assignment":
            continue
        start = int(unit["span"]["start"])
        body = str(unit["text"]).rstrip("\r\n")
        end = start + len(body)
        routed = make_unit(
            unit_id=str(unit["unit_id"]),
            text=body,
            start=start,
            end=end,
            source_uri=str(unit["source_uri"]),
            renderer_id=RENDERER_ID,
        )
        routed["line_no"] = unit["line_no"]
        routed["plane"] = "routing"
        routed["source_unit_id"] = unit["unit_id"]
        routed["line_kind"] = "assignment"
        out.append(routed)
    validate_units(out, document=document)
    return out


def source_packet(source: Mapping[str, Any], *, source_id: str) -> dict[str, Any]:
    units = list(source["units"])
    return {
        "packet_id": f"{source_id}-source",
        "document": source["document"],
        "units": units,
        "visible_evidence": visible_evidence_from_units(units),
        "source_uri": _source_uri(source_id),
        "plane": "source",
    }


def routing_packet(routing: Sequence[Mapping[str, Any]], *, source_id: str) -> dict[str, Any]:
    units = [dict(unit) for unit in routing]
    return {
        "packet_id": f"{source_id}-routing",
        "units": units,
        "visible_evidence": visible_evidence_from_units(units),
        "source_uri": _source_uri(source_id),
        "plane": "routing",
    }


def merge_full_source_after(
    source_units: Sequence[Mapping[str, Any]],
    after_routing: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_by_id = {str(unit["unit_id"]): dict(unit) for unit in source_units}
    visible_after = [
        dict(unit)
        for unit in list(after_routing.get("units") or [])
        if isinstance(unit, Mapping)
    ]
    after_ids = {str(unit.get("unit_id")) for unit in visible_after}
    full: list[dict[str, Any]] = []
    for unit in source_units:
        uid = str(unit.get("unit_id"))
        if unit.get("line_kind") != "assignment":
            if uid in after_ids:
                raise AdapterError("unsupported line leaked into routing visible set")
            full.append(dict(unit))
            continue
        if uid not in after_ids:
            continue
        routed = next(item for item in visible_after if str(item.get("unit_id")) == uid)
        routed_text = str(routed.get("text", ""))
        source_text = str(unit.get("text", ""))
        if routed_text == source_text.rstrip("\r\n"):
            full.append(dict(unit))
        else:
            full.append(routed)
    source_ids = set(source_by_id)
    for unit in visible_after:
        if str(unit.get("unit_id")) not in source_ids:
            full.append(unit)

    r_blob = after_routing.get("R")
    r_out: dict[str, Any] = dict(r_blob) if isinstance(r_blob, Mapping) else {}
    entries = []
    for row in list(r_out.get("entries") or []):
        if not isinstance(row, Mapping):
            continue
        entry = dict(row)
        uid = str(entry.get("unit_id") or "")
        extra = dict(entry.get("extra") or {}) if isinstance(entry.get("extra"), Mapping) else {}
        if uid in source_by_id:
            extra["original_text"] = str(source_by_id[uid].get("text", ""))
            extra["parent_unit_id"] = extra.get("parent_unit_id") or uid
            entry["extra"] = extra
        entries.append(entry)
    if entries:
        r_out["entries"] = entries
    return full, r_out


def adapt(raw: bytes, *, source_id: str) -> dict[str, Any]:
    source = source_units_from_bytes(raw, source_id=source_id)
    routing = routing_units_from_source(source)
    return {
        "adapter_id": ADAPTER_ID,
        "source_id": source_id,
        "encoding": source["encoding"],
        "source": source,
        "source_packet": source_packet(source, source_id=source_id),
        "routing_units": routing,
        "routing_packet": routing_packet(routing, source_id=source_id),
        "n_source_units": source["n_source_units"],
        "n_routing_assignments": len(routing),
        "n_unsupported_passthrough": source["n_unsupported"],
    }
