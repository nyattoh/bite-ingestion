"""Shared helpers for provenance-preserving deterministic operators."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any

from bite_ingestion.interfaces.operator import OperatorId
from bite_ingestion.packet_contract import PacketContractError

OP_MODE = "deterministic"

# Reason codes used across operators / R entries
REASON_BUDGET_TRUNCATED = "budget_truncated"
REASON_NOT_SELECTED = "not_selected"
REASON_OMITTED_BY_REDUCE = "omitted_by_reduce"
REASON_QUARANTINED = "quarantined"
REASON_DEDUPE_COLLAPSE = "dedupe_collapse"
REASON_AGGREGATE_COUNT = "aggregate_count"
REASON_CANONICALISE_WHITESPACE = "canonicalise_whitespace"

LOSS_DEDUPE = "dedupe_collapse"
LOSS_AGGREGATE = "aggregate_count"
LOSS_WHITESPACE = "canonicalise_whitespace"


def deep_copy_packet(packet: Mapping[str, object]) -> dict[str, Any]:
    """Deep-copy a working packet into a mutable dict."""
    return copy.deepcopy(dict(packet))


def canonical_json(obj: object) -> str:
    """Deterministic JSON serialization for hashing / comparison."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stable_id(prefix: str, *parts: object, length: int = 12) -> str:
    """Stable short id: ``u_`` / ``r_`` / ``h_`` / ``loss_`` + sha256 prefix."""
    material = "|".join(canonical_json(p) if not isinstance(p, str) else p for p in parts)
    return f"{prefix}{sha256_hex(material)[:length]}"


def packet_digest(packet: Mapping[str, object]) -> str:
    return sha256_hex(canonical_json(dict(packet)))


def _empty_tau() -> dict[str, Any]:
    return {"sequence": [], "steps": []}


def _empty_r() -> dict[str, Any]:
    return {"entries": []}


def ensure_extended_fields(packet: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    """Ensure extended working-packet fields exist (in-place)."""
    if "packet_id" not in packet or not packet["packet_id"]:
        packet["packet_id"] = stable_id("pkt_", canonical_json(packet.get("visible_evidence", [])))
    if "visible_evidence" not in packet or packet["visible_evidence"] is None:
        packet["visible_evidence"] = []
    if "provenance" not in packet or not isinstance(packet["provenance"], Mapping):
        packet["provenance"] = {
            "unit_id": "unknown",
            "source_uri": None,
            "byte_or_token_span": None,
            "renderer_id": None,
        }
    if "op_last_touch" not in packet:
        packet["op_last_touch"] = "NONE"
    if "R" not in packet or not isinstance(packet["R"], Mapping):
        packet["R"] = _empty_r()
    elif "entries" not in packet["R"]:
        packet["R"] = {**dict(packet["R"]), "entries": []}
    if "tau" not in packet or not isinstance(packet["tau"], Mapping):
        packet["tau"] = _empty_tau()
    else:
        tau = dict(packet["tau"])
        tau.setdefault("sequence", [])
        tau.setdefault("steps", [])
        packet["tau"] = tau
    if "recovery_handles" not in packet or packet["recovery_handles"] is None:
        packet["recovery_handles"] = []
    if "irreversible_loss_ledger" not in packet or packet["irreversible_loss_ledger"] is None:
        packet["irreversible_loss_ledger"] = []
    if "op_status" not in packet:
        packet["op_status"] = "ok"
    if "units" not in packet or packet["units"] is None:
        packet["units"] = []
    return packet


def synthesize_units_from_evidence(packet: MutableMapping[str, Any]) -> list[dict[str, Any]]:
    """Build units from visible_evidence texts with contiguous char spans over a virtual concat.

    Virtual concat joins evidence texts with a single newline between items so spans
    remain contiguous and reconstructible. Documented for CUT span round-trips.

    Fail-closed: non-Mapping evidence entries (e.g. bare string ids) are a
    packet-contract violation, not something to skip silently. Skipping them
    used to turn a populated packet into an empty unit list, which the
    operators then reported as a clean no-loss run.
    """
    evidence = packet.get("visible_evidence") or []
    bad = [
        (i, type(item).__name__) for i, item in enumerate(evidence) if not isinstance(item, Mapping)
    ]
    if bad:
        raise PacketContractError(
            "visible_evidence entries must be Mappings carrying 'text'; "
            f"non-Mapping entries at {bad}. A list of bare evidence ids cannot "
            "be turned into units — anchor them to document spans first "
            "(see bite_ingestion.packet_contract)."
        )
    units: list[dict[str, Any]] = []
    cursor = 0
    prov = packet.get("provenance") if isinstance(packet.get("provenance"), Mapping) else {}
    source_uri = prov.get("source_uri") if isinstance(prov, Mapping) else None
    for i, item in enumerate(evidence):
        text = item.get("text")
        if text is None:
            text = ""
        if not isinstance(text, str):
            text = str(text)
        if i > 0:
            cursor += 1  # newline separator in virtual concat
        start = cursor
        end = start + len(text)
        uid = stable_id("u_", packet.get("packet_id", ""), i, text, start, end)
        units.append(
            {
                "unit_id": uid,
                "text": text,
                "span": {"start": start, "end": end, "unit": "char"},
                "source_uri": source_uri,
                "version": None,
                "media_type": None,
            }
        )
        cursor = end
    return units


def ensure_units(packet: MutableMapping[str, Any]) -> list[dict[str, Any]]:
    """Return units list; synthesize from evidence when missing/empty.

    Fail-closed: if the packet declares evidence but synthesis yields zero
    units, raise instead of returning ``[]``. An empty unit list makes every
    downstream operator report "nothing to omit", which silently converts
    total evidence loss into a clean run.
    """
    ensure_extended_fields(packet)
    units = packet.get("units")
    if isinstance(units, list) and len(units) > 0:
        return [dict(u) if isinstance(u, Mapping) else u for u in units]
    evidence = packet.get("visible_evidence") or []
    synth = synthesize_units_from_evidence(packet)
    if evidence and not synth:
        raise PacketContractError(
            f"packet {packet.get('packet_id', '<no id>')!r} declares "
            f"{len(evidence)} visible_evidence entries but produced 0 units; "
            "refusing to continue with an empty unit graph"
        )
    packet["units"] = synth
    return synth


def append_tau_step(
    packet: MutableMapping[str, Any],
    *,
    op: str | OperatorId,
    inputs_ref: Sequence[str],
    outputs_ref: Sequence[str],
    omitted_ref: Sequence[str] | None = None,
    errors: Sequence[object] | None = None,
    extra: Mapping[str, object] | None = None,
) -> None:
    ensure_extended_fields(packet)
    op_s = op.value if isinstance(op, OperatorId) else str(op)
    step = {
        "op": op_s,
        "mode": OP_MODE,
        "inputs_ref": list(inputs_ref),
        "outputs_ref": list(outputs_ref),
        "omitted_ref": list(omitted_ref or []),
        "errors": list(errors or []),
        "extra": dict(extra or {}),
    }
    tau = packet["tau"]
    assert isinstance(tau, dict)
    seq = list(tau.get("sequence") or [])
    seq.append(op_s)
    tau["sequence"] = seq
    steps = list(tau.get("steps") or [])
    steps.append(step)
    tau["steps"] = steps
    packet["tau"] = tau
    packet["op_last_touch"] = op_s


def add_r_entry(
    packet: MutableMapping[str, Any],
    *,
    unit_id: str,
    reason: str,
    recoverable: bool = True,
    locator: Mapping[str, object] | None = None,
    aggregate_parent: str | None = None,
    extra: Mapping[str, object] | None = None,
) -> str:
    ensure_extended_fields(packet)
    r_id = stable_id("r_", unit_id, reason, aggregate_parent or "", canonical_json(locator or {}))
    entry: dict[str, Any] = {
        "r_id": r_id,
        "unit_id": unit_id,
        "reason": reason,
        "recoverable": recoverable,
        "locator": dict(locator or {}),
        "aggregate_parent": aggregate_parent,
    }
    if extra:
        entry["extra"] = dict(extra)
    entries = list(packet["R"].get("entries") or [])  # type: ignore[union-attr]
    # Deterministic: replace same r_id or append sorted later
    entries = [e for e in entries if not (isinstance(e, Mapping) and e.get("r_id") == r_id)]
    entries.append(entry)
    entries.sort(key=lambda e: str(e.get("r_id", "")) if isinstance(e, Mapping) else "")
    packet["R"] = {"entries": entries}
    return r_id


def add_recovery_handle(
    packet: MutableMapping[str, Any],
    *,
    r_ids: Sequence[str],
    op: str | OperatorId,
) -> str:
    ensure_extended_fields(packet)
    op_s = op.value if isinstance(op, OperatorId) else str(op)
    sorted_r = sorted(r_ids)
    handle_id = stable_id("h_", op_s, *sorted_r)
    handle = {"handle_id": handle_id, "r_ids": sorted_r, "op": op_s}
    handles = [
        h
        for h in (packet.get("recovery_handles") or [])
        if isinstance(h, Mapping) and h.get("handle_id") != handle_id
    ]
    handles.append(handle)
    handles.sort(key=lambda h: str(h.get("handle_id", "")))
    packet["recovery_handles"] = handles
    return handle_id


def add_loss_ledger_entry(
    packet: MutableMapping[str, Any],
    *,
    op: str | OperatorId,
    kind: str,
    unit_ids: Sequence[str],
    note: str = "",
    declared: bool = True,
) -> str:
    ensure_extended_fields(packet)
    op_s = op.value if isinstance(op, OperatorId) else str(op)
    sorted_uids = sorted(unit_ids)
    loss_id = stable_id("loss_", op_s, kind, *sorted_uids, note)
    row = {
        "loss_id": loss_id,
        "op": op_s,
        "declared": declared,
        "kind": kind,
        "unit_ids": sorted_uids,
        "note": note,
    }
    ledger = [
        x
        for x in (packet.get("irreversible_loss_ledger") or [])
        if isinstance(x, Mapping) and x.get("loss_id") != loss_id
    ]
    ledger.append(row)
    ledger.sort(key=lambda x: str(x.get("loss_id", "")))
    packet["irreversible_loss_ledger"] = ledger
    return loss_id


def unit_locator(unit: Mapping[str, Any]) -> dict[str, Any]:
    span = unit.get("span") if isinstance(unit.get("span"), Mapping) else {}
    return {
        "source_uri": unit.get("source_uri"),
        "version": unit.get("version"),
        "span": dict(span) if span else {},
    }


def rebuild_visible_from_units(
    units: Sequence[Mapping[str, Any]],
    *,
    role: str | None = None,
    unit_ids_key: bool = True,
) -> list[dict[str, Any]]:
    """Rebuild visible_evidence items from units (deterministic order by span then unit_id)."""
    ordered = sorted(
        units,
        key=lambda u: (
            int((u.get("span") or {}).get("start", 0)) if isinstance(u.get("span"), Mapping) else 0,
            str(u.get("unit_id", "")),
        ),
    )
    out: list[dict[str, Any]] = []
    for u in ordered:
        item: dict[str, Any] = {"text": str(u.get("text", "")), "role": role}
        if unit_ids_key:
            item["unit_ids"] = [str(u.get("unit_id", ""))]
        out.append(item)
    return out


def split_paragraphs(text: str) -> list[tuple[int, int, str]]:
    """Split on blank-line paragraph boundaries; return (start, end, segment)."""
    if not text:
        return [(0, 0, "")]
    parts: list[tuple[int, int, str]] = []
    # Split keeping positions via finditer on blank-line separators
    pattern = re.compile(r"\n\s*\n+")
    last = 0
    for m in pattern.finditer(text):
        seg = text[last : m.start()]
        if seg.strip() or seg:  # keep non-empty; empty between only if whole empty handled
            parts.append((last, m.start(), seg))
        last = m.end()
    parts.append((last, len(text), text[last:]))
    # Drop trailing empty segment if text ended with blank lines and we already have content
    if len(parts) > 1 and parts[-1][2] == "":
        parts.pop()
    return parts if parts else [(0, len(text), text)]


def split_lines(text: str) -> list[tuple[int, int, str]]:
    """Split on newlines; each line excludes its terminating newline from the segment text
    but span end includes up to (not including) next line start — char offsets into original.
    """
    if not text:
        return [(0, 0, "")]
    parts: list[tuple[int, int, str]] = []
    start = 0
    for i, ch in enumerate(text):
        if ch == "\n":
            parts.append((start, i, text[start:i]))
            start = i + 1
    parts.append((start, len(text), text[start:]))
    return parts


def split_records(text: str) -> list[tuple[int, int, str]]:
    """Split CSV/JSON-ish records when structure is clear; else fall back to lines.

    - JSON array of objects: one record per top-level element (best-effort brace scan)
    - CSV: header + one record per newline line
    - Otherwise: line split
    """
    stripped = text.lstrip()
    if stripped.startswith("["):
        records = _split_json_array_records(text)
        if records:
            return records
    if stripped.startswith("{") and "\n" in text:
        # NDJSON-ish or multi-object: try line-wise JSON objects
        line_parts = split_lines(text)
        ok = True
        for _, _, seg in line_parts:
            s = seg.strip()
            if not s:
                continue
            try:
                json.loads(s)
            except (json.JSONDecodeError, TypeError):
                ok = False
                break
        if ok:
            return [(a, b, s) for a, b, s in line_parts if s.strip()]
    # CSV heuristic: commas in first non-empty line
    lines = split_lines(text)
    nonempty = [p for p in lines if p[2].strip()]
    if nonempty and "," in nonempty[0][2]:
        return nonempty
    return split_lines(text)


def _split_json_array_records(text: str) -> list[tuple[int, int, str]]:
    """Best-effort split of a JSON array into element spans (deterministic brace scan)."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    # Re-serialize each element and locate in original via sequential search — fragile;
    # instead emit canonical segments with synthetic contiguous spans over joined form.
    # Prefer locating raw slices when possible by scanning brackets.
    records: list[tuple[int, int, str]] = []
    i = text.find("[")
    if i < 0:
        return []
    i += 1
    n = len(text)
    depth = 0
    in_str = False
    escape = False
    start: int | None = None
    while i < n:
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            if start is None:
                start = i
            i += 1
            continue
        if ch in " \t\r\n":
            i += 1
            continue
        if ch == "]":
            break
        if start is None:
            start = i
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                end = i + 1
                records.append((start, end, text[start:end]))
                start = None
                # skip comma
                j = end
                while j < n and text[j] in " \t\r\n":
                    j += 1
                if j < n and text[j] == ",":
                    i = j + 1
                    continue
                i = end
                continue
        elif ch == "," and depth == 0 and start is not None:
            # primitive element
            end = i
            seg = text[start:end].rstrip()
            # trim trailing whitespace already; find real end
            end2 = start + len(seg)
            records.append((start, end2, seg))
            start = None
        elif depth == 0 and ch not in ",]" and start is not None and ch in '0123456789n"t-[':
            pass
        i += 1
    if not records and data:
        # fallback: canonical one-per-element with virtual concat spans
        cursor = 0
        out: list[tuple[int, int, str]] = []
        for el in data:
            seg = json.dumps(el, sort_keys=True, ensure_ascii=False)
            out.append((cursor, cursor + len(seg), seg))
            cursor += len(seg) + 1
        return out
    return records


def absolute_span(
    parent_span: Mapping[str, Any] | None, local_start: int, local_end: int
) -> dict[str, Any]:
    base = int(parent_span.get("start", 0)) if isinstance(parent_span, Mapping) else 0
    return {"start": base + local_start, "end": base + local_end, "unit": "char"}


def sort_units(units: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [dict(u) for u in units],
        key=lambda u: (
            int((u.get("span") or {}).get("start", 0)) if isinstance(u.get("span"), Mapping) else 0,
            str(u.get("unit_id", "")),
        ),
    )
