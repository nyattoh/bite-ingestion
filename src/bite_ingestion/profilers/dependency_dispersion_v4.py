"""Gold-free exact full-key dependency-dispersion sensor v4 (Phase 4E).

Does not change dependency_dispersion_v3. Uses reference_identity_v2.
Chain span uses the validated reachability replacement.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from bite_eval.chain_span_reachable import chain_span_reachable
from bite_ingestion.profilers.dependency_dispersion import (
    _component_span,
    _payload_of,
    _undirected,
)
from bite_ingestion.profilers.reference_identity_v2 import (
    join_span_count,
    source_tokens,
    target_tokens,
)

SENSOR_NAME = "dependency_dispersion_v4"
PRIMARY_FEATURE = "mean_reference_edge_distance"
PRIMARY_EDGE_RULE = "value_atom_exact_full_key_identity"
RECORD_ID_FIELDS = frozenset({"id", "k"})
FEATURE_KEYS = (
    "n_reference_edges",
    "mean_reference_edge_distance",
    "mean_reference_edge_distance_norm",
    "reference_component_span",
    "reference_chain_span",
)


@dataclass
class SensorReport:
    features: dict[str, float]
    diagnostics: dict[str, float]
    evidence: dict[str, str]
    edges: list[dict[str, Any]]
    fail_closed: bool
    notes: list[str] = field(default_factory=list)


@dataclass
class _Unit:
    index: int
    key_atoms: tuple[str, ...]
    record_id_atoms: tuple[str, ...]
    value_atoms: tuple[str, ...]
    canonical: str
    targets: tuple[str, ...]


def _zeros() -> tuple[dict[str, float], dict[str, float]]:
    features = {key: 0.0 for key in FEATURE_KEYS}
    diagnostics = {
        "n_logical_units": 0.0,
        "n_identifier_occurrences": 0.0,
        "n_value_identifiers": 0.0,
        "n_index_lookups": 0.0,
        "n_candidate_targets": 0.0,
        "n_join_spans_masked": 0.0,
    }
    return features, diagnostics


def _unit_from_kv(index: int, key_text: str, value_text: str) -> _Unit:
    key_atoms = target_tokens(key_text)
    value_atoms = source_tokens(value_text)
    return _Unit(
        index=index,
        key_atoms=key_atoms,
        record_id_atoms=key_atoms,
        value_atoms=value_atoms,
        canonical=f"{key_text}={value_text}",
        targets=key_atoms,
    )


def _unit_from_object(index: int, obj: Mapping[str, Any]) -> _Unit:
    if "k" in obj and "v" in obj:
        return _unit_from_kv(index, str(obj["k"]), str(obj["v"]))
    key_atoms = target_tokens(" ".join(str(k) for k in obj))
    record_ids: list[str] = []
    values: list[str] = []
    for key_name, raw in obj.items():
        if not isinstance(raw, str):
            continue
        if str(key_name) in RECORD_ID_FIELDS:
            record_ids.extend(target_tokens(raw))
        elif str(key_name) == "v":
            values.extend(source_tokens(raw))
        else:
            values.extend(source_tokens(raw))
    record_id_atoms = tuple(dict.fromkeys(record_ids))
    value_atoms = tuple(dict.fromkeys(values))
    targets = tuple(dict.fromkeys([*key_atoms, *record_id_atoms]))
    return _Unit(
        index=index,
        key_atoms=key_atoms,
        record_id_atoms=record_id_atoms,
        value_atoms=value_atoms,
        canonical=json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str),
        targets=targets,
    )


def _parse_units(payload: str) -> tuple[list[_Unit] | None, list[str]]:
    notes: list[str] = []
    stripped = payload.strip()
    if stripped.startswith(("{", "[")):
        try:
            parsed: object = json.loads(payload)
        except (json.JSONDecodeError, TypeError, ValueError):
            notes.append("malformed_structured")
            return None, notes
        if isinstance(parsed, dict):
            records: list[object] = [parsed]
        elif isinstance(parsed, list):
            records = list(parsed)
        else:
            notes.append("malformed_structured")
            return None, notes
        units: list[_Unit] = []
        for item in records:
            if isinstance(item, dict):
                units.append(_unit_from_object(len(units), item))
            else:
                notes.append("malformed_structured")
                return None, notes
        return units, notes
    units = []
    for line in payload.splitlines():
        line_stripped = line.strip()
        if not line_stripped or "=" not in line_stripped:
            continue
        if line_stripped.startswith(("{", "[")):
            continue
        left, _, right = line_stripped.partition("=")
        units.append(_unit_from_kv(len(units), left, right.strip().strip('"')))
    return units, notes


def _build_target_index(units: Sequence[_Unit]) -> dict[str, list[int]]:
    index: dict[str, list[int]] = {}
    seen: set[tuple[str, int]] = set()
    for unit in units:
        for atom in unit.targets:
            pair = (atom, unit.index)
            if pair in seen:
                continue
            seen.add(pair)
            index.setdefault(atom, []).append(unit.index)
    return index


def measure(source_unit: Mapping[str, object]) -> SensorReport:
    payload, fail_closed, notes = _payload_of(source_unit)
    if fail_closed:
        features, diagnostics = _zeros()
        return SensorReport(features, diagnostics, {"error": "nul_byte"}, [], True, notes)

    units, parse_notes = _parse_units(payload)
    notes.extend(parse_notes)
    if units is None:
        features, diagnostics = _zeros()
        return SensorReport(features, diagnostics, {"error": "malformed"}, [], True, notes)

    n_units = len(units)
    n_occ = 0.0
    n_value = 0.0
    for unit in units:
        n_occ += float(len(unit.key_atoms) + len(unit.record_id_atoms) + len(unit.value_atoms))
        n_value += float(len(unit.value_atoms))
    n_masked = float(join_span_count(payload))

    target_index = _build_target_index(units)
    directed: list[tuple[int, int]] = []
    edge_rows: list[dict[str, Any]] = []
    n_lookups = 0.0
    n_candidates = 0.0
    for unit in units:
        for atom in unit.value_atoms:
            n_lookups += 1.0
            targets = target_index.get(atom)
            if not targets:
                continue
            n_candidates += float(len(targets))
            for dst in targets:
                if dst == unit.index:
                    continue
                if unit.canonical == units[dst].canonical:
                    continue
                directed.append((unit.index, dst))
                edge_rows.append(
                    {
                        "src": unit.index,
                        "dst": dst,
                        "atom": atom,
                        "distance": abs(dst - unit.index),
                    }
                )

    undirected = _undirected(directed)
    distances = [abs(b - a) for a, b in undirected]
    denom = max(n_units - 1, 1)
    mean_d = float(sum(distances) / len(distances)) if distances else 0.0
    features = {
        "n_reference_edges": float(len(undirected)),
        "mean_reference_edge_distance": mean_d,
        "mean_reference_edge_distance_norm": mean_d / denom if n_units else 0.0,
        "reference_component_span": float(_component_span(n_units, undirected)),
        "reference_chain_span": float(chain_span_reachable(n_units, directed)),
    }
    diagnostics = {
        "n_logical_units": float(n_units),
        "n_identifier_occurrences": n_occ,
        "n_value_identifiers": n_value,
        "n_index_lookups": n_lookups,
        "n_candidate_targets": n_candidates,
        "n_join_spans_masked": n_masked,
    }
    if not distances:
        notes.append("no_reference_edges")
    return SensorReport(
        features=features,
        diagnostics=diagnostics,
        evidence={
            "n_logical_units": str(n_units),
            "n_directed": str(len(directed)),
            "primary": PRIMARY_FEATURE,
            "edge_rule": PRIMARY_EDGE_RULE,
            "distance_unit": "logical_unit_index",
            "chain_span": "reachability_replacement",
        },
        edges=edge_rows,
        fail_closed=False,
        notes=notes,
    )


class DependencyDispersionSensorV4:
    """Exact full-key reference thermometer. No component split."""

    name = SENSOR_NAME

    def measure(self, source_unit: Mapping[str, object]) -> SensorReport:
        return measure(source_unit)

    def profile(self, source_unit: Mapping[str, object]) -> Mapping[str, float]:
        return self.measure(source_unit).features
