"""Unified evidence-unit packet contract (Phase 1 foundation).

One unit graph is shared by three consumers that previously disagreed:

- the payload actually sent to the target model,
- evidence recall / recovery accounting,
- the deterministic operators (CUT / UNTANGLE / REDUCE / INTEGRATE).

A **unit** is a Mapping carrying:

===================  ====================================================
``unit_id``          stable id, unique within a packet
``text``             exact substring of the source document
``span``             ``{"start": int, "end": int, "unit": "char"}``
``source_uri``       provenance root
``parent_unit_id``   optional derivation link (``None`` for source units)
``provenance``       ``{unit_id, source_uri, byte_or_token_span, renderer_id}``
===================  ====================================================

Contract rules enforced here:

1. **An evidence id must have a body.** ``gold_evidence_ids`` that do not
   resolve to a unit are a contract violation, not a warning.
2. **Spans must resolve.** ``document[span.start:span.end] == unit.text``.
3. **No silent empty output.** A packet that declares evidence but yields
   zero units raises :class:`PacketContractError`.
4. **Visibility is derived, never declared.** A unit is visible only when
   its span survives into the payload; partial survival counts as omitted.

Threshold values are deliberately absent from this module — it describes
structure only.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

SPAN_UNIT = "char"
KIND_SOURCE = "source"
KIND_COMPOSITE = "composite"
SPAN_SOURCE_EXACT = "source_exact"
SPAN_ENVELOPE = "envelope"
SOURCE_RECORD_REQUIRED: tuple[str, ...] = ("unit_id", "source_uri", "byte_or_token_span")

#: Keys every source unit must carry.
UNIT_REQUIRED_KEYS: tuple[str, ...] = ("unit_id", "text", "span", "source_uri")


class PacketContractError(ValueError):
    """Raised when a packet violates the evidence-unit contract.

    Always fail-closed: callers must surface this as ``status=failed`` with a
    reason code rather than continuing on an empty/unanchored unit graph.
    """


def _sha12(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def make_span(start: int, end: int) -> dict[str, Any]:
    return {"start": int(start), "end": int(end), "unit": SPAN_UNIT}


def make_unit(
    *,
    unit_id: str,
    text: str,
    start: int,
    end: int,
    source_uri: str,
    renderer_id: str | None = None,
    parent_unit_id: str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    """Build one contract-compliant source unit."""
    span = make_span(start, end)
    return {
        "unit_id": str(unit_id),
        "text": str(text),
        "span": span,
        "source_uri": str(source_uri),
        "parent_unit_id": parent_unit_id,
        "role": role,
        "provenance": {
            "kind": KIND_SOURCE,
            "unit_id": str(unit_id),
            "source_uri": str(source_uri),
            "byte_or_token_span": f"{SPAN_UNIT}:{span['start']}-{span['end']}",
            "renderer_id": renderer_id,
        },
    }


def provenance_kind(unit: Mapping[str, Any]) -> str:
    """Distinguish legacy/source provenance from composite and malformed joins."""
    joined = unit.get("joined_from")
    is_join = (
        isinstance(joined, Sequence)
        and not isinstance(joined, (str, bytes))
        and len([x for x in joined if x]) >= 2
    )
    prov = unit.get("provenance")
    if isinstance(prov, Mapping) and prov.get("kind") == KIND_COMPOSITE:
        return KIND_COMPOSITE
    if is_join:
        return "malformed"
    if isinstance(prov, Mapping) and prov.get("kind") not in (None, KIND_SOURCE):
        return "malformed"
    return KIND_SOURCE


def _joined_from_ids(unit: Mapping[str, Any]) -> list[str]:
    raw = unit.get("joined_from")
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return [str(x) for x in raw if x]
    return []


def source_records_from_unit(unit: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Immediate source records. Composite members flatten; envelope is not a source span."""
    if provenance_kind(unit) == KIND_COMPOSITE:
        prov = unit.get("provenance")
        if not isinstance(prov, Mapping):
            raise PacketContractError("composite unit missing provenance")
        out: list[dict[str, Any]] = []
        for row in prov.get("sources") or []:
            if not isinstance(row, Mapping):
                raise PacketContractError("composite sources must be mappings")
            missing = [k for k in SOURCE_RECORD_REQUIRED if not row.get(k)]
            if missing:
                raise PacketContractError(f"incomplete composite source record: {missing}")
            out.append(
                {
                    "unit_id": str(row["unit_id"]),
                    "source_uri": str(row["source_uri"]),
                    "byte_or_token_span": str(row["byte_or_token_span"]),
                    "renderer_id": row.get("renderer_id"),
                }
            )
        if len(out) < 2:
            raise PacketContractError("composite provenance needs at least two sources")
        return out
    if provenance_kind(unit) == "malformed":
        raise PacketContractError(
            f"joined unit {unit.get('unit_id')!r} has joined_from but not composite provenance"
        )
    prov = unit.get("provenance") if isinstance(unit.get("provenance"), Mapping) else {}
    uid = str((prov or {}).get("unit_id") or unit.get("unit_id") or "")
    uri = (prov or {}).get("source_uri") or unit.get("source_uri")
    span = unit.get("span")
    if isinstance(span, Mapping) and span.get("kind") == SPAN_ENVELOPE:
        raise PacketContractError(
            f"unit {unit.get('unit_id')!r} envelope span is not a source-exact span"
        )
    bspan = (prov or {}).get("byte_or_token_span")
    if not bspan and isinstance(span, Mapping) and span.get("end") is not None:
        bspan = f"{SPAN_UNIT}:{int(span['start'])}-{int(span['end'])}"
    if not uid or not uri or not bspan:
        raise PacketContractError(
            f"unit {unit.get('unit_id')!r} cannot yield a source provenance record"
        )
    return [
        {
            "unit_id": uid,
            "source_uri": str(uri),
            "byte_or_token_span": str(bspan),
            "renderer_id": (prov or {}).get("renderer_id"),
        }
    ]


def make_envelope_span(units: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Bounding span for ordering only. Not a source-exact contiguous span."""
    starts: list[int] = []
    ends: list[int] = []
    for unit in units:
        span = unit.get("span")
        if not isinstance(span, Mapping) or span.get("end") is None:
            raise PacketContractError("envelope span requires member start/end")
        starts.append(int(span["start"]))
        ends.append(int(span["end"]))
    if not starts:
        raise PacketContractError("envelope span requires at least one member")
    return {
        "kind": SPAN_ENVELOPE,
        "start": min(starts),
        "end": max(ends),
        "unit": SPAN_UNIT,
        "contiguous": False,
    }


def make_composite_provenance(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    for row in records:
        if not isinstance(row, Mapping):
            raise PacketContractError("composite source record must be a mapping")
        missing = [k for k in SOURCE_RECORD_REQUIRED if not row.get(k)]
        if missing:
            raise PacketContractError(f"incomplete composite source record: {missing}")
        sources.append(
            {
                "unit_id": str(row["unit_id"]),
                "source_uri": str(row["source_uri"]),
                "byte_or_token_span": str(row["byte_or_token_span"]),
                "renderer_id": row.get("renderer_id"),
            }
        )
    if len(sources) < 2:
        raise PacketContractError("composite provenance needs at least two sources")
    return {"kind": KIND_COMPOSITE, "sources": sources}


def synth_unit_id(prefix: str, *parts: object) -> str:
    material = "|".join(str(p) for p in parts)
    return f"{prefix}{_sha12(material)}"


def _validate_composite_unit(unit: Mapping[str, Any]) -> None:
    uid = unit.get("unit_id")
    if not uid or unit.get("text") is None:
        raise PacketContractError(
            f"composite unit {uid!r} missing unit_id or text"
        )
    prov = unit.get("provenance")
    if not isinstance(prov, Mapping) or prov.get("kind") != KIND_COMPOSITE:
        raise PacketContractError(
            f"joined unit {uid!r} must carry provenance.kind={KIND_COMPOSITE!r}"
        )
    records = source_records_from_unit(unit)
    joined = _joined_from_ids(unit)
    if len(joined) < 2:
        raise PacketContractError(f"composite unit {uid!r} missing joined_from")
    span = unit.get("span")
    if not isinstance(span, Mapping) or span.get("kind") != SPAN_ENVELOPE:
        raise PacketContractError(
            f"composite unit {uid!r} must use envelope span, not a source-exact span"
        )
    if span.get("contiguous") is not False:
        raise PacketContractError(f"composite unit {uid!r} envelope must set contiguous=false")
    try:
        start = int(span["start"])
        end = int(span["end"])
    except (TypeError, ValueError, KeyError) as exc:
        raise PacketContractError(f"composite unit {uid!r} envelope bounds are invalid") from exc
    if start < 0 or end < start:
        raise PacketContractError(f"composite unit {uid!r} has invalid envelope range")
    top_uri = unit.get("source_uri")
    uris = {row["source_uri"] for row in records}
    if top_uri and (len(uris) != 1 or str(top_uri) not in uris):
        raise PacketContractError(
            f"composite unit {uid!r} top-level source_uri fakes a mixed-URI join"
        )


def validate_unit(unit: Mapping[str, Any], *, document: str | None = None) -> None:
    """Raise :class:`PacketContractError` if *unit* breaks the contract."""
    if not isinstance(unit, Mapping):
        raise PacketContractError(f"unit must be a Mapping, got {type(unit).__name__}")
    if provenance_kind(unit) == "malformed":
        raise PacketContractError(
            f"unit {unit.get('unit_id', '<no id>')!r} is a multi-source join without "
            "composite provenance"
        )
    if provenance_kind(unit) == KIND_COMPOSITE:
        _validate_composite_unit(unit)
        return
    missing = [k for k in UNIT_REQUIRED_KEYS if k not in unit or unit[k] is None]
    if missing:
        raise PacketContractError(
            f"unit {unit.get('unit_id', '<no id>')!r} missing required keys: {missing}"
        )
    span = unit.get("span")
    if not isinstance(span, Mapping) or "start" not in span or "end" not in span:
        raise PacketContractError(f"unit {unit.get('unit_id')!r} has unresolvable span: {span!r}")
    if span.get("kind") == SPAN_ENVELOPE:
        raise PacketContractError(
            f"unit {unit.get('unit_id')!r} source unit cannot carry an envelope span"
        )
    try:
        start = int(span["start"])
        end = int(span["end"])
    except (TypeError, ValueError) as exc:
        raise PacketContractError(
            f"unit {unit.get('unit_id')!r} span bounds are not integers: {span!r}"
        ) from exc
    if start < 0 or end < start:
        raise PacketContractError(
            f"unit {unit.get('unit_id')!r} has invalid span range: {start}..{end}"
        )
    if document is not None:
        if end > len(document):
            raise PacketContractError(
                f"unit {unit.get('unit_id')!r} span {start}..{end} exceeds "
                f"document length {len(document)}"
            )
        if document[start:end] != str(unit.get("text", "")):
            raise PacketContractError(
                f"unit {unit.get('unit_id')!r} text does not match document"
                f"[{start}:{end}] — evidence id has no real body"
            )


def validate_units(
    units: Sequence[Mapping[str, Any]],
    *,
    document: str | None = None,
) -> None:
    """Validate every unit and reject duplicate ids."""
    seen: set[str] = set()
    for unit in units:
        validate_unit(unit, document=document)
        uid = str(unit["unit_id"])
        if uid in seen:
            raise PacketContractError(f"duplicate unit_id in packet: {uid!r}")
        seen.add(uid)


def assert_evidence_ids_resolve(
    evidence_ids: Sequence[str],
    units: Sequence[Mapping[str, Any]],
    *,
    where: str = "gold_evidence_ids",
) -> None:
    """Every declared evidence id must name a real unit (rule 1)."""
    known = {str(u.get("unit_id")) for u in units}
    dangling = sorted({str(e) for e in evidence_ids} - known)
    if dangling:
        raise PacketContractError(
            f"{where} without a unit body (evidence id with no substance): {dangling}; "
            f"known unit_ids={sorted(known)}"
        )


def split_units_by_char_limit(
    units: Sequence[Mapping[str, Any]],
    *,
    limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split units into (visible, omitted) for a payload kept to ``[0, limit)``.

    A unit is visible only when its span lies **entirely** inside the kept
    range. Partially-surviving evidence counts as omitted: we never assume
    that a truncated prefix still carries the evidence.
    """
    visible: list[dict[str, Any]] = []
    omitted: list[dict[str, Any]] = []
    for unit in units:
        span = unit.get("span") or {}
        end = int(span.get("end", 0)) if isinstance(span, Mapping) else 0
        if end <= limit:
            visible.append(dict(unit))
        else:
            omitted.append(dict(unit))
    return visible, omitted


def assert_units_in_payload(
    units: Sequence[Mapping[str, Any]],
    payload_text: str,
    *,
    where: str = "visible units",
) -> None:
    """Every visible unit's body must really occur in the payload (rule 4)."""
    missing = [
        str(u.get("unit_id"))
        for u in units
        if str(u.get("text", "")) and str(u.get("text", "")) not in payload_text
    ]
    if missing:
        raise PacketContractError(f"{where} present by id but absent from payload text: {missing}")


def is_complete_provenance(unit: Mapping[str, Any]) -> bool:
    """True when the unit carries complete source or composite provenance.

    ``joined_from`` alone is not complete provenance.
    """
    kind = provenance_kind(unit)
    if kind == "malformed":
        return False
    if kind == KIND_COMPOSITE:
        prov = unit.get("provenance")
        span = unit.get("span")
        if not isinstance(prov, Mapping) or prov.get("kind") != KIND_COMPOSITE:
            return False
        sources = prov.get("sources")
        if not isinstance(sources, Sequence) or isinstance(sources, (str, bytes)):
            return False
        if len(list(sources)) < 2:
            return False
        for row in sources:
            if not isinstance(row, Mapping):
                return False
            if not all(row.get(k) for k in SOURCE_RECORD_REQUIRED):
                return False
        if not isinstance(span, Mapping) or span.get("kind") != SPAN_ENVELOPE:
            return False
        if span.get("contiguous") is not False or span.get("end") is None:
            return False
        return len(_joined_from_ids(unit)) >= 2
    prov = unit.get("provenance")
    span = unit.get("span")
    return bool(
        isinstance(prov, Mapping)
        and prov.get("unit_id")
        and prov.get("source_uri")
        and prov.get("byte_or_token_span")
        and isinstance(span, Mapping)
        and span.get("end") is not None
        and span.get("kind") != SPAN_ENVELOPE
    )


def provenance_completeness(units: Sequence[Mapping[str, Any]]) -> float:
    """Measured share of units carrying complete provenance.

    Replaces self-declared ``provenance_complete_rate``. Source units still
    need ``unit_id`` / ``source_uri`` / resolved source-exact span. Composite
    units need ``kind=composite`` plus per-parent source records. ``joined_from``
    is not a substitute.
    """
    units = list(units)
    if not units:
        return 1.0
    complete = sum(1 for unit in units if is_complete_provenance(unit))
    return complete / len(units)


def lineage_parent_ids(unit: Mapping[str, Any]) -> list[str]:
    """Immediate ancestors of a derived unit (CUT / REDUCE / INTEGRATE)."""
    parents: list[str] = []
    for key in ("parent_unit_id", "derived_from"):
        v = unit.get(key)
        if v:
            parents.append(str(v))
    for key in ("joined_from", "aggregate_members"):
        v = unit.get(key)
        if isinstance(v, Sequence) and not isinstance(v, (str, bytes)):
            parents.extend(str(x) for x in v if x)
    prov = unit.get("provenance")
    if isinstance(prov, Mapping) and prov.get("kind") == KIND_COMPOSITE:
        for row in prov.get("sources") or []:
            if isinstance(row, Mapping) and row.get("unit_id"):
                parents.append(str(row["unit_id"]))
    seen: set[str] = set()
    out: list[str] = []
    for p in parents:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _walk_roots(uid: str, by_id: Mapping[str, Mapping[str, Any]]) -> set[str]:
    """Walk parent/join links until a unit with no parent (or a missing id)."""
    seen: set[str] = set()
    stack = [uid]
    roots: set[str] = set()
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        unit = by_id.get(cur)
        if unit is None:
            roots.add(cur)
            continue
        parents = lineage_parent_ids(unit)
        if not parents:
            roots.add(cur)
            continue
        stack.extend(parents)
    return roots


def root_ids_of(
    unit_ids: Sequence[str],
    units: Sequence[Mapping[str, Any]],
) -> set[str]:
    """Resolve visible/derived ids to source (gold-comparable) unit ids."""
    by_id = {str(u.get("unit_id")): u for u in units if isinstance(u, Mapping) and u.get("unit_id")}
    roots: set[str] = set()
    for uid in unit_ids:
        if uid:
            roots |= _walk_roots(str(uid), by_id)
    return roots


def conservation_untraced(
    input_ids: Sequence[str],
    *,
    visible_units: Sequence[Mapping[str, Any]],
    r_entries: Sequence[Mapping[str, Any]],
    loss_ledger: Sequence[Mapping[str, Any]],
) -> list[str]:
    """Input ids not covered by visible lineage, R, or declared irreversible loss.

    Count equality can fail when CUT splits 1→N or INTEGRATE joins N→1.
    Lineage coverage is the conservation proof in those cases.
    """
    lineage: list[Mapping[str, Any]] = [u for u in visible_units if isinstance(u, Mapping)]
    for e in r_entries:
        if not isinstance(e, Mapping):
            continue
        raw_extra = e.get("extra")
        extra: Mapping[str, Any] = raw_extra if isinstance(raw_extra, Mapping) else {}
        uid = e.get("unit_id")
        if uid:
            lineage.append(
                {
                    "unit_id": str(uid),
                    "parent_unit_id": extra.get("parent_unit_id") or e.get("parent_unit_id"),
                    "derived_from": extra.get("derived_from"),
                    "joined_from": extra.get("joined_from"),
                    "aggregate_members": extra.get("aggregate_members"),
                }
            )
    by_id = {
        str(u.get("unit_id")): u for u in lineage if isinstance(u, Mapping) and u.get("unit_id")
    }
    accounted: set[str] = set()
    for u in lineage:
        uid = str(u.get("unit_id", ""))
        if uid:
            accounted.add(uid)
            accounted |= _walk_roots(uid, by_id)
    for row in loss_ledger:
        if not isinstance(row, Mapping):
            continue
        for uid in row.get("unit_ids") or []:
            accounted.add(str(uid))
            accounted |= _walk_roots(str(uid), by_id)
    return [str(i) for i in input_ids if str(i) not in accounted]


def visible_evidence_from_units(
    units: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Render units into the operator-facing ``visible_evidence`` shape."""
    return [
        {
            "text": str(u.get("text", "")),
            "role": u.get("role"),
            "unit_ids": [str(u.get("unit_id", ""))],
        }
        for u in units
    ]


def units_from_document(
    document: str,
    *,
    source_uri: str,
    unit_id: str | None = None,
    renderer_id: str | None = None,
) -> list[dict[str, Any]]:
    """Fallback: treat the whole document as one resolvable unit.

    Used for legacy eval packets that carry a ``document`` but declare no
    evidence ids. Packets that *do* declare evidence ids must anchor them
    explicitly — see :func:`resolve_packet_units`.
    """
    if not document:
        return []
    uid = unit_id or synth_unit_id("u_", source_uri, document)
    return [
        make_unit(
            unit_id=uid,
            text=document,
            start=0,
            end=len(document),
            source_uri=source_uri,
            renderer_id=renderer_id,
        )
    ]


def resolve_packet_units(
    packet: Mapping[str, Any],
    *,
    document: str | None = None,
    source_uri: str | None = None,
) -> list[dict[str, Any]]:
    """Return the packet's validated unit graph, failing closed.

    Resolution order:

    1. ``packet["units"]`` when present — validated against the document.
    2. Otherwise, if the packet declares ``gold_evidence_ids``, raise:
       evidence ids without unit bodies are a contract violation.
    3. Otherwise synthesise a single whole-document unit.
    """
    doc = document if document is not None else str(packet.get("document") or "")
    uri = source_uri or str(
        packet.get("source_uri") or f"synthetic://{packet.get('instance_id', 'unknown')}"
    )

    raw_units = packet.get("units")
    if isinstance(raw_units, Sequence) and not isinstance(raw_units, (str, bytes)) and raw_units:
        units = [dict(u) for u in raw_units if isinstance(u, Mapping)]
        if len(units) != len(list(raw_units)):
            raise PacketContractError(
                "packet['units'] contains non-Mapping entries; "
                "string evidence lists are no longer accepted"
            )
        validate_units(units, document=doc or None)
        gold = packet.get("gold_evidence_ids") or []
        if isinstance(gold, Sequence) and not isinstance(gold, (str, bytes)):
            assert_evidence_ids_resolve([str(g) for g in gold], units)
        return units

    gold = packet.get("gold_evidence_ids") or []
    if isinstance(gold, Sequence) and not isinstance(gold, (str, bytes)) and list(gold):
        raise PacketContractError(
            f"packet declares gold_evidence_ids={list(gold)!r} but carries no "
            "units; evidence ids must be anchored to document spans"
        )

    if not doc:
        return []
    return units_from_document(doc, source_uri=uri)


__all__ = [
    "KIND_COMPOSITE",
    "KIND_SOURCE",
    "SOURCE_RECORD_REQUIRED",
    "SPAN_ENVELOPE",
    "SPAN_SOURCE_EXACT",
    "SPAN_UNIT",
    "UNIT_REQUIRED_KEYS",
    "PacketContractError",
    "assert_evidence_ids_resolve",
    "assert_units_in_payload",
    "conservation_untraced",
    "is_complete_provenance",
    "lineage_parent_ids",
    "make_composite_provenance",
    "make_envelope_span",
    "make_span",
    "make_unit",
    "provenance_completeness",
    "provenance_kind",
    "resolve_packet_units",
    "root_ids_of",
    "source_records_from_unit",
    "split_units_by_char_limit",
    "synth_unit_id",
    "units_from_document",
    "validate_unit",
    "validate_units",
    "visible_evidence_from_units",
]
