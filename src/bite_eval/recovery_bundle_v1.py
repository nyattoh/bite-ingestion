"""Canonical recovery bundle v1 (Phase 4G Track A).

Same serialization for every arm. Reconstructs original raw bytes from
model-visible payload plus counted omitted records. Does not store an
uncounted original-source copy.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

DUMP_KW: dict[str, Any] = {"sort_keys": True, "separators": (",", ":"), "ensure_ascii": False}

CountFn = Callable[[str], int]


class RecoveryError(ValueError):
    """Raised when the bundle cannot reconstruct raw source bytes."""


def dump_canonical(obj: object) -> str:
    return json.dumps(obj, **DUMP_KW)


def is_empty_bundle(bundle: Mapping[str, Any] | None) -> bool:
    return not bundle


def complete_visible_records(
    visible: str,
    *,
    n_complete: int,
) -> list[str]:
    if n_complete <= 0 or not visible:
        return []
    parts = visible.split("\n")
    return parts[:n_complete]


def flatten_visible_units(units: Sequence[Mapping[str, Any]]) -> list[str]:
    out: list[str] = []
    for unit in units:
        text = str(unit.get("text", ""))
        if _is_composite(unit):
            if text:
                out.extend(text.split("\n"))
            continue
        out.append(text)
    return out


def _is_composite(unit: Mapping[str, Any]) -> bool:
    joined = unit.get("joined_from")
    if isinstance(joined, Sequence) and not isinstance(joined, (str, bytes)) and len(joined) >= 2:
        return True
    prov = unit.get("provenance")
    return isinstance(prov, Mapping) and prov.get("kind") == "composite"


def reconstruct(visible: str, bundle: Mapping[str, Any] | None) -> bytes:
    if is_empty_bundle(bundle):
        return visible.encode("utf-8")
    assert bundle is not None
    encoding = str(bundle.get("encoding") or "utf-8")
    slots = bundle.get("slots") or []
    omitted = [str(item) for item in list(bundle.get("omitted") or [])]
    if not slots and not omitted:
        return visible.encode(encoding)
    n_complete = int(bundle.get("n_complete_visible_records") or 0)
    records = complete_visible_records(visible, n_complete=n_complete)
    omit_i = 0
    parts: list[str] = []
    for slot in slots:
        if not isinstance(slot, Mapping):
            raise RecoveryError("slot must be a mapping")
        via = str(slot.get("via") or "")
        if via == "visible":
            idx = int(slot["record_index"])
            if idx < 0 or idx >= len(records):
                raise RecoveryError(f"visible record_index out of range: {idx}")
            parts.append(records[idx] + str(slot.get("terminator") or ""))
            continue
        if via == "omitted":
            if omit_i >= len(omitted):
                raise RecoveryError("omitted content exhausted")
            parts.append(omitted[omit_i])
            omit_i += 1
            continue
        raise RecoveryError(f"unknown via {via}")
    if omit_i != len(omitted):
        raise RecoveryError("omitted content unused")
    return "".join(parts).encode(encoding)


def account_bundle(bundle: Mapping[str, Any] | None, payload_tokens: CountFn) -> dict[str, int]:
    if is_empty_bundle(bundle):
        return {
            "recovery_bundle_bytes": 0,
            "recovery_bundle_tokens": 0,
            "recovery_metadata_bytes": 0,
            "recovery_content_bytes": 0,
        }
    assert bundle is not None
    full = dump_canonical(dict(bundle))
    meta = {key: value for key, value in bundle.items() if key != "omitted"}
    content = dump_canonical(list(bundle.get("omitted") or []))
    return {
        "recovery_bundle_bytes": len(full.encode("utf-8")),
        "recovery_bundle_tokens": int(payload_tokens(full)),
        "recovery_metadata_bytes": len(dump_canonical(meta).encode("utf-8")),
        "recovery_content_bytes": len(content.encode("utf-8")),
    }


def build_recovery_bundle(
    *,
    raw: bytes,
    encoding: str,
    source_units: Sequence[Mapping[str, Any]],
    visible: str,
    complete_records: Sequence[str],
) -> dict[str, Any]:
    if encoding == "utf-8" and visible.encode("utf-8") == raw:
        return {}
    if visible.encode(encoding) == raw:
        return {
            "encoding": encoding,
            "n_complete_visible_records": 0,
            "omitted": [],
            "slots": [],
        }
    complete = list(complete_records)
    used = [False] * len(complete)
    slots: list[dict[str, Any]] = []
    omitted: list[str] = []
    for unit in source_units:
        uid = str(unit.get("unit_id") or "")
        full = str(unit.get("text", ""))
        if unit.get("line_kind") != "assignment":
            slots.append({"unit_id": uid, "via": "omitted"})
            omitted.append(full)
            continue
        body = full.rstrip("\r\n")
        idx = next((i for i, rec in enumerate(complete) if not used[i] and rec == body), None)
        if idx is None:
            slots.append({"unit_id": uid, "via": "omitted"})
            omitted.append(full)
            continue
        used[idx] = True
        slots.append(
            {
                "unit_id": uid,
                "via": "visible",
                "record_index": idx,
                "terminator": full[len(body) :],
            }
        )
    bundle = {
        "encoding": encoding,
        "n_complete_visible_records": len(complete),
        "omitted": omitted,
        "slots": slots,
    }
    got = reconstruct(visible, bundle)
    if got != raw:
        raise RecoveryError("bundle does not reconstruct raw source")
    return bundle
