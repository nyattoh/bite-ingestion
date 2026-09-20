"""Gold-free structural redundancy v2 (Phase 3P).

Uses logical_record_identity_v2 only. Does not change structural_redundancy_v1.
No new threshold; actionability is ratio>0 and not fail_closed.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from bite_ingestion.logical_record import identities_from_payload

SENSOR_NAME = "structural_redundancy_v2"
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


def measure(source_unit: Mapping[str, object]) -> SensorReport:
    if not isinstance(source_unit, Mapping):
        return _zeros("fail_closed", ["source_unit_not_mapping"])
    payload = source_unit.get("payload", source_unit.get("text", ""))
    identities, fail_closed, notes = identities_from_payload(str(payload) if payload is not None else "")
    if fail_closed:
        parsed = "fail_closed"
        if any("nul" in note for note in notes):
            parsed = "nul"
        elif any("malformed" in note for note in notes):
            parsed = "malformed"
        return _zeros(parsed, notes)
    stripped = str(payload).strip()
    parsed_format = "json" if stripped.startswith(("{", "[")) else "key_value"
    n_records = len(identities)
    counts = Counter(identities)
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


class StructuralRedundancySensorV2:
    name = SENSOR_NAME

    def measure(self, source_unit: Mapping[str, object]) -> SensorReport:
        return measure(source_unit)

    def profile(self, source_unit: Mapping[str, object]) -> Mapping[str, float]:
        return self.measure(source_unit).features
