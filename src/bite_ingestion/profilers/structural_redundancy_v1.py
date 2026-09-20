"""Gold-free structural redundancy v1 (Phase 3K).

Logical-record duplicate ratio. Does not overwrite deterministic_v0.r.
Does not take gold/texture/operator labels. Not wired to routing.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

SENSOR_NAME = "structural_redundancy_v1"
PRIMARY_FEATURE = "duplicate_unit_ratio"
FEATURE_KEYS = (PRIMARY_FEATURE,)


@dataclass
class SensorReport:
    features: dict[str, float]
    diagnostics: dict[str, Any]
    fail_closed: bool
    notes: list[str] = field(default_factory=list)


def _zeros(parsed_format: str, notes: list[str]) -> SensorReport:
    return SensorReport(
        features={PRIMARY_FEATURE: 0.0},
        diagnostics={
            "n_records": 0,
            "n_unique_records": 0,
            "n_duplicate_records": 0,
            "max_multiplicity": 0,
            "parsed_format": parsed_format,
            "fail_closed": True,
        },
        fail_closed=True,
        notes=notes,
    )


def _summarize(
    records: list[tuple[str, str]], parsed_format: str, notes: list[str]
) -> SensorReport:
    n_records = len(records)
    counts = Counter(records)
    n_unique = len(counts)
    n_duplicate = n_records - n_unique
    max_mult = max(counts.values()) if counts else 0
    ratio = 0.0 if n_records == 0 else 1.0 - (n_unique / n_records)
    return SensorReport(
        features={PRIMARY_FEATURE: float(ratio)},
        diagnostics={
            "n_records": n_records,
            "n_unique_records": n_unique,
            "n_duplicate_records": n_duplicate,
            "max_multiplicity": max_mult,
            "parsed_format": parsed_format,
            "fail_closed": False,
        },
        fail_closed=False,
        notes=notes,
    )


def _payload_of(source_unit: Mapping[str, object]) -> tuple[str, bool, list[str]]:
    notes: list[str] = []
    payload = source_unit.get("payload", source_unit.get("text", ""))
    if payload is None:
        payload = ""
    if not isinstance(payload, str):
        notes.append("non_str_payload")
        return "", True, notes
    if "\x00" in payload:
        notes.append("fail_closed_nul")
        return payload, True, notes
    return payload, False, notes


def _records_from_kv(payload: str) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    for line in payload.splitlines():
        if not line.strip():
            continue
        left, sep, right = line.partition("=")
        key = left.rstrip()
        value = right.lstrip() if sep else ""
        records.append((key, value))
    return records


def _records_from_json_array(payload: str) -> list[tuple[str, str]] | None:
    try:
        parsed: object = json.loads(payload)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(parsed, list):
        return None
    records: list[tuple[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict) or "k" not in item or "v" not in item:
            return None
        key, value = item["k"], item["v"]
        if not isinstance(key, str) or not isinstance(value, str):
            return None
        records.append((key, value))
    return records


def measure(source_unit: Mapping[str, object]) -> SensorReport:
    if not isinstance(source_unit, Mapping):
        return _zeros("fail_closed", ["source_unit_not_mapping"])
    payload, fail_closed, notes = _payload_of(source_unit)
    if fail_closed:
        return _zeros("fail_closed", notes)
    stripped = payload.strip()
    if stripped.startswith("["):
        records = _records_from_json_array(payload)
        if records is None:
            notes.append("malformed_structured")
            return _zeros("fail_closed", notes)
        return _summarize(records, "json", notes)
    if stripped.startswith("{"):
        notes.append("malformed_structured")
        return _zeros("fail_closed", notes)
    return _summarize(_records_from_kv(payload), "key_value", notes)


class StructuralRedundancySensorV1:
    """Logical-record duplicate thermometer. Do not route on these values in Phase 3K."""

    name = SENSOR_NAME

    def measure(self, source_unit: Mapping[str, object]) -> SensorReport:
        return measure(source_unit)

    def profile(self, source_unit: Mapping[str, object]) -> Mapping[str, float]:
        return self.measure(source_unit).features
