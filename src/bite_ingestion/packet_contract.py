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
            "unit_id": str(unit_id),
            "source_uri": str(source_uri),
            "byte_or_token_span": f"{SPAN_UNIT}:{span['start']}-{span['end']}",
            "renderer_id": renderer_id,
        },
    }


def synth_unit_id(prefix: str, *parts: object) -> str:
    material = "|".join(str(p) for p in parts)
    return f"{prefix}{_sha12(material)}"


def validate_unit(unit: Mapping[str, Any], *, document: str | None = None) -> None:
    """Raise :class:`PacketContractError` if *unit* breaks the contract."""
    if not isinstance(unit, Mapping):
        raise PacketContractError(f"unit must be a Mapping, got {type(unit).__name__}")
    missing = [k for k in UNIT_REQUIRED_KEYS if k not in unit or unit[k] is None]
    if missing:
        raise PacketContractError(
            f"unit {unit.get('unit_id', '<no id>')!r} missing required keys: {missing}"
        )
    span = unit.get("span")
    if not isinstance(span, Mapping) or "start" not in span or "end" not in span:
        raise PacketContractError(f"unit {unit.get('unit_id')!r} has unresolvable span: {span!r}")
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


def provenance_completeness(units: Sequence[Mapping[str, Any]]) -> float:
    """Measured share of units carrying complete provenance.

    Replaces self-declared ``provenance_complete_rate``: a unit counts only
    when it actually has ``unit_id``, ``source_uri`` and a resolved span.
    """
    units = list(units)
    if not units:
        return 1.0
    complete = 0
    for unit in units:
        prov = unit.get("provenance")
        span = unit.get("span")
        if (
            isinstance(prov, Mapping)
            and prov.get("unit_id")
            and prov.get("source_uri")
            and prov.get("byte_or_token_span")
            and isinstance(span, Mapping)
            and span.get("end") is not None
        ):
            complete += 1
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
    "SPAN_UNIT",
    "UNIT_REQUIRED_KEYS",
    "PacketContractError",
    "assert_evidence_ids_resolve",
    "assert_units_in_payload",
    "conservation_untraced",
    "lineage_parent_ids",
    "make_span",
    "make_unit",
    "provenance_completeness",
    "resolve_packet_units",
    "root_ids_of",
    "split_units_by_char_limit",
    "synth_unit_id",
    "units_from_document",
    "validate_unit",
    "validate_units",
    "visible_evidence_from_units",
]
