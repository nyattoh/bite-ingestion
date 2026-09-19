"""Source-exact unitizer for BITE-XFER-1 renderings.

Does not rewrite policy, operators, or sensors. Fail closed if spans cannot
be recovered from the source document.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bite_ingestion.packet_contract import (
    make_unit,
    validate_units,
    visible_evidence_from_units,
)


class UnitizerError(ValueError):
    """Raised when a rendering cannot be split into source-exact units."""


def _json_object_spans(document: str) -> list[tuple[int, int]]:
    index = 0
    n = len(document)
    while index < n and document[index].isspace():
        index += 1
    if index >= n or document[index] != "[":
        raise UnitizerError("expected top-level JSON array")
    index += 1
    spans: list[tuple[int, int]] = []
    while index < n:
        while index < n and document[index].isspace():
            index += 1
        if index < n and document[index] == "]":
            return spans
        if index < n and document[index] == ",":
            index += 1
            continue
        if index >= n or document[index] != "{":
            raise UnitizerError("expected JSON object")
        start = index
        depth = 0
        in_str = False
        esc = False
        while index < n:
            ch = document[index]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    index += 1
                    spans.append((start, index))
                    break
            index += 1
        else:
            raise UnitizerError("unclosed JSON object")
    raise UnitizerError("unclosed JSON array")


def _kv_spans(document: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    offset = 0
    for line in document.splitlines(keepends=True):
        raw = line.rstrip("\r\n")
        if raw.strip():
            spans.append((offset, offset + len(raw)))
        offset += len(line)
    return spans


def unitize(
    document: str,
    *,
    case_id: str,
    fmt: str,
    source_uri: str | None = None,
) -> list[dict[str, Any]]:
    if fmt == "key_value":
        spans = _kv_spans(document)
    elif fmt in {"compact_json", "pretty_json", "mixed_order_json"}:
        spans = _json_object_spans(document)
    else:
        raise UnitizerError(f"unsupported format {fmt}")
    if not spans:
        raise UnitizerError("no units")
    uri = source_uri or f"bitebench://{case_id}"
    units: list[dict[str, Any]] = []
    for index, (start, end) in enumerate(spans):
        text = document[start:end]
        if not text:
            raise UnitizerError("empty unit span")
        units.append(
            make_unit(
                unit_id=f"{case_id}-u{index:02d}",
                text=text,
                start=start,
                end=end,
                source_uri=uri,
                renderer_id="bite-xfer-1",
            )
        )
    validate_units(units, document=document)
    return units


def packet_from_document(
    document: str,
    *,
    case_id: str,
    fmt: str,
) -> dict[str, Any]:
    units = unitize(document, case_id=case_id, fmt=fmt)
    return {
        "packet_id": f"{case_id}-{fmt}",
        "document": document,
        "units": units,
        "visible_evidence": visible_evidence_from_units(units),
        "source_uri": f"bitebench://{case_id}",
    }


def assert_no_annotation_leak(packet: Mapping[str, Any]) -> None:
    forbidden = {
        "texture",
        "expected_sequence",
        "required_evidence_ids",
        "intended_dispersion",
        "has_exact_duplicate",
        "has_quarantinable_anomaly",
        "has_explicit_join_cluster",
        "gold_unit_ids",
        "operator",
        "route",
        "answer",
    }
    found = sorted(key for key in packet if str(key) in forbidden)
    if found:
        raise UnitizerError(f"annotation leak into packet: {found}")
