"""Gold-free logical record identity v2 (Phase 3P).

KV: strip only around `=`. JSON: exact {k,v} string fields; whitespace and
field order do not affect identity. Extra fields are not logical records.
Malformed / NUL fail closed. No fuzzy / lowercase / semantic match.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

Identity = tuple[str, str]


class LogicalRecordError(ValueError):
    """Fail-closed parse of a logical record."""


def _from_object(obj: MappingLike) -> Identity | None:
    if not isinstance(obj, dict):
        return None
    if set(obj.keys()) != {"k", "v"}:
        return None
    key, value = obj["k"], obj["v"]
    if isinstance(key, str) and isinstance(value, str):
        return key, value
    return None


def identity_of_text(text: str) -> Identity | None:
    """Return (k, v) for one supported logical unit, else None.

    Raises LogicalRecordError on NUL or malformed JSON that starts as JSON.
    """
    if "\x00" in text:
        raise LogicalRecordError("nul")
    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        try:
            parsed: object = json.loads(stripped)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise LogicalRecordError("malformed") from exc
        if isinstance(parsed, dict):
            return _from_object(parsed)
        return None
    if "=" not in text:
        return None
    key, _, value = text.partition("=")
    return key.rstrip(), value.lstrip()


def identities_from_payload(payload: str) -> tuple[list[Identity], bool, list[str]]:
    """Parse a document into supported logical identities.

    fail_closed True means the payload is unusable (NUL / malformed structured).
    Extra-field objects are skipped, not fail-closed.
    """
    notes: list[str] = []
    if not isinstance(payload, str):
        return [], True, ["non_str_payload"]
    if "\x00" in payload:
        return [], True, ["fail_closed_nul"]
    stripped = payload.strip()
    if stripped.startswith("["):
        try:
            parsed = json.loads(payload)
        except (json.JSONDecodeError, TypeError, ValueError):
            return [], True, ["malformed_structured"]
        if not isinstance(parsed, list):
            return [], True, ["malformed_structured"]
        out: list[Identity] = []
        for item in parsed:
            if not isinstance(item, dict):
                return [], True, ["malformed_structured"]
            ident = _from_object(item)
            if ident is not None:
                out.append(ident)
        return out, False, notes
    if stripped.startswith("{"):
        try:
            parsed_obj = json.loads(payload)
        except (json.JSONDecodeError, TypeError, ValueError):
            return [], True, ["malformed_structured"]
        if not isinstance(parsed_obj, dict):
            return [], True, ["malformed_structured"]
        ident = _from_object(parsed_obj)
        return ([ident] if ident is not None else []), False, notes
    out = []
    for line in payload.splitlines():
        if not line.strip():
            continue
        ident = identity_of_text(line)
        if ident is not None:
            out.append(ident)
    return out, False, notes


def identities_of_units(units: Sequence[MappingLike]) -> list[Identity | None]:
    out: list[Identity | None] = []
    for unit in units:
        if not isinstance(unit, dict):
            out.append(None)
            continue
        try:
            out.append(identity_of_text(str(unit.get("text", ""))))
        except LogicalRecordError:
            out.append(None)
    return out


MappingLike = dict[str, Any]
