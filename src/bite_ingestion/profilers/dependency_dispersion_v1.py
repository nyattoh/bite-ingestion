"""Gold-free dependency-dispersion sensor v1 (Phase 3E).

Implements phase3d-sensor-v1-design-freeze. Coexists with v0.
Does not take gold labels. Not wired to routing.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from bite_ingestion.profilers.dependency_dispersion import (
    STOPWORDS,
    _chain_span,
    _component_span,
    _payload_of,
    _undirected,
)

SENSOR_NAME = "dependency_dispersion_v1"
PRIMARY_FEATURE = "mean_edge_distance"
PRIMARY_EDGE_RULE = "value_to_key_or_record_id"
RECORD_ID_FIELDS = frozenset({"id", "k"})
FEATURE_KEYS = (
    "n_edges",
    "mean_edge_distance",
    "mean_edge_distance_norm",
    "component_span",
    "chain_span",
)

_ATOM = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


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


def _is_identifier(atom: str) -> bool:
    if atom.casefold() in STOPWORDS:
        return False
    if atom.isdigit():
        return False
    return len(atom) >= 4 or ("_" in atom)


def _maximal_atoms(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for match in _ATOM.finditer(text):
        atom = match.group(0)
        if _is_identifier(atom) and atom not in seen:
            seen.add(atom)
            out.append(atom)
    return out


def _key_side_atoms(text: str) -> list[str]:
    """Maximal key tokens plus `_`-suffix identifiers (`bin_id_x` exposes `id_x`)."""
    seen: set[str] = set()
    out: list[str] = []
    for match in _ATOM.finditer(text):
        tok = match.group(0)
        parts = tok.split("_")
        candidates = [tok, *("_".join(parts[i:]) for i in range(1, len(parts)))]
        for atom in candidates:
            if _is_identifier(atom) and atom not in seen:
                seen.add(atom)
                out.append(atom)
    return out


def _zeros() -> tuple[dict[str, float], dict[str, float]]:
    features = {key: 0.0 for key in FEATURE_KEYS}
    diagnostics = {
        "n_logical_units": 0.0,
        "n_identifier_occurrences": 0.0,
        "n_value_identifiers": 0.0,
        "n_index_lookups": 0.0,
        "n_candidate_targets": 0.0,
    }
    return features, diagnostics


def _unit_from_kv(index: int, key_text: str, value_text: str) -> _Unit:
    key_atoms = tuple(_key_side_atoms(key_text))
    record_id_atoms = key_atoms
    value_atoms = tuple(_maximal_atoms(value_text))
    targets = tuple(dict.fromkeys([*key_atoms, *record_id_atoms]))
    return _Unit(
        index=index,
        key_atoms=key_atoms,
        record_id_atoms=record_id_atoms,
        value_atoms=value_atoms,
        canonical=f"{key_text}={value_text}",
        targets=targets,
    )


def _unit_from_object(index: int, obj: Mapping[str, Any]) -> _Unit:
    if "k" in obj and "v" in obj:
        return _unit_from_kv(index, str(obj["k"]), str(obj["v"]))
    key_atoms = tuple(_key_side_atoms(" ".join(str(k) for k in obj)))
    record_ids: list[str] = []
    values: list[str] = []
    for key_name, raw in obj.items():
        if not isinstance(raw, str):
            continue
        if str(key_name) in RECORD_ID_FIELDS:
            record_ids.extend(_key_side_atoms(raw))
        else:
            values.extend(_maximal_atoms(raw))
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


def _units_from_json(payload: str) -> list[_Unit] | None:
    stripped = payload.strip()
    if not stripped.startswith(("{", "[")):
        return None
    try:
        parsed: object = json.loads(payload)
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    if isinstance(parsed, dict):
        records: list[object] = [parsed]
    elif isinstance(parsed, list):
        records = list(parsed)
    else:
        return []
    units: list[_Unit] = []
    for item in records:
        if isinstance(item, dict):
            units.append(_unit_from_object(len(units), item))
    return units


def _units_from_kv(payload: str) -> list[_Unit]:
    units: list[_Unit] = []
    for line in payload.splitlines():
        stripped = line.strip()
        if not stripped or "=" not in stripped:
            continue
        if stripped.startswith(("{", "[")):
            continue
        left, _, right = stripped.partition("=")
        units.append(_unit_from_kv(len(units), left, right.strip().strip('"')))
    return units


def _parse_units(payload: str) -> tuple[list[_Unit], list[str]]:
    notes: list[str] = []
    json_units = _units_from_json(payload)
    if json_units is None:
        return _units_from_kv(payload), notes
    if not json_units and payload.strip().startswith(("{", "[")):
        notes.append("unparseable_json")
    return json_units, notes


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
    n_units = len(units)
    n_occ = 0.0
    n_value = 0.0
    for unit in units:
        n_occ += float(len(unit.key_atoms) + len(unit.record_id_atoms) + len(unit.value_atoms))
        n_value += float(len(unit.value_atoms))

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
        "n_edges": float(len(undirected)),
        "mean_edge_distance": mean_d,
        "mean_edge_distance_norm": mean_d / denom if n_units else 0.0,
        "component_span": float(_component_span(n_units, undirected)),
        "chain_span": float(_chain_span(n_units, directed)),
    }
    diagnostics = {
        "n_logical_units": float(n_units),
        "n_identifier_occurrences": n_occ,
        "n_value_identifiers": n_value,
        "n_index_lookups": n_lookups,
        "n_candidate_targets": n_candidates,
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
        },
        edges=edge_rows,
        fail_closed=False,
        notes=notes,
    )


class DependencyDispersionSensorV1:
    """Logical-unit thermometer. Do not route on these values in Phase 3E."""

    name = SENSOR_NAME

    def measure(self, source_unit: Mapping[str, object]) -> SensorReport:
        return measure(source_unit)

    def profile(self, source_unit: Mapping[str, object]) -> Mapping[str, float]:
        return self.measure(source_unit).features
