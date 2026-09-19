"""Gold-free dependency-dispersion sensor (Phase 3B).

Independent of deterministic_v0. Reads payload/text only.
Does not take gold labels as inputs. Not wired to routing.
"""

from __future__ import annotations

import json
import re
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

SENSOR_NAME = "dependency_dispersion_v0"
QUERY_SENSOR_NAME = "query_identifier_span_v0"
PRIMARY_FEATURE = "mean_edge_distance"

# Exact-token blocklist. Not Phase-2 key prefixes.
STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "what",
        "which",
        "who",
        "this",
        "that",
        "these",
        "those",
        "for",
        "from",
        "with",
        "and",
        "or",
        "not",
        "no",
        "yes",
        "true",
        "false",
        "null",
        "none",
        "value",
        "key",
        "record",
        "error",
        "status",
        "type",
        "name",
        "data",
        "item",
        "line",
        "text",
        "json",
        "unit",
        "id",
        "ref",
        "import",
        "class",
        "def",
        "function",
        "const",
        "let",
        "var",
        "answer",
        "query",
        "document",
        "question",
        "payload",
        "object",
        "field",
        "entry",
        "where",
        "used",
        "result",
        "stored",
    }
)

_ATOM = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass
class SensorReport:
    features: dict[str, float]
    evidence: dict[str, str]
    edges: list[dict[str, Any]]
    fail_closed: bool
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_identifier(atom: str) -> bool:
    if atom.casefold() in STOPWORDS:
        return False
    if atom.isdigit():
        return False
    return len(atom) >= 4 or ("_" in atom)


def _atoms(text: str) -> list[str]:
    return [m.group(0) for m in _ATOM.finditer(text)]


def _json_strings(obj: object) -> list[str]:
    out: list[str] = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for val in obj.values():
            out.extend(_json_strings(val))
    elif isinstance(obj, list):
        for val in obj:
            out.extend(_json_strings(val))
    return out


def _value_atoms(line: str) -> list[str]:
    raw: list[str] = []
    stripped = line.strip()
    if stripped.startswith(("{", "[")):
        try:
            raw.extend(_json_strings(json.loads(stripped)))
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    elif "=" in stripped:
        raw.append(stripped.split("=", 1)[1].strip().strip('"'))
    seen: set[str] = set()
    out: list[str] = []
    for chunk in raw:
        for atom in _atoms(chunk):
            if _is_identifier(atom) and atom not in seen:
                seen.add(atom)
                out.append(atom)
    return out


def _contains_atom(text: str, atom: str) -> bool:
    return (
        re.search(rf"(?<![A-Za-z0-9]){re.escape(atom)}(?![A-Za-z0-9])", text) is not None
    )


def _payload_of(source_unit: Mapping[str, object]) -> tuple[str, bool, list[str]]:
    notes: list[str] = []
    payload = source_unit.get("payload", source_unit.get("text", ""))
    if payload is None:
        payload = ""
    if not isinstance(payload, str):
        try:
            payload = json.dumps(payload, ensure_ascii=False)
            notes.append("non_str_payload_json_serialized")
        except (TypeError, ValueError, OverflowError):
            payload = str(payload)
            notes.append("non_str_payload_str_fallback")
    fail_closed = "\x00" in payload
    if fail_closed:
        notes.append("fail_closed_nul")
    return payload, fail_closed, notes


def _undirected(edges: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    seen: set[tuple[int, int]] = set()
    out: list[tuple[int, int]] = []
    for src, dst in edges:
        pair = (src, dst) if src < dst else (dst, src)
        if pair[0] != pair[1] and pair not in seen:
            seen.add(pair)
            out.append(pair)
    return out


def _component_span(n: int, undirected: Sequence[tuple[int, int]]) -> int:
    if n <= 0 or not undirected:
        return 0
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in undirected:
        pa, pb = find(a), find(b)
        if pa != pb:
            parent[pb] = pa
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    best = 0
    for members in groups.values():
        if len(members) < 2:
            continue
        best = max(best, max(members) - min(members))
    return best


def _chain_span(n: int, directed: Sequence[tuple[int, int]]) -> int:
    adj: dict[int, list[int]] = {i: [] for i in range(n)}
    for src, dst in directed:
        adj[src].append(dst)
    best = 0
    seen_stack: set[int] = set()

    def dfs(node: int, start: int) -> None:
        nonlocal best
        best = max(best, node - start)
        for nxt in adj[node]:
            if nxt in seen_stack:
                continue
            seen_stack.add(nxt)
            dfs(nxt, start)
            seen_stack.remove(nxt)

    for i in range(n):
        seen_stack = {i}
        dfs(i, i)
    return best


def measure(source_unit: Mapping[str, object]) -> SensorReport:
    payload, fail_closed, notes = _payload_of(source_unit)
    if fail_closed:
        zeros = {
            "n_edges": 0.0,
            "mean_edge_distance": 0.0,
            "median_edge_distance": 0.0,
            "max_edge_distance": 0.0,
            "mean_edge_distance_norm": 0.0,
            "component_span": 0.0,
            "chain_span": 0.0,
        }
        return SensorReport(zeros, {"error": "nul_byte"}, [], True, notes)

    lines = payload.splitlines() or [payload]
    stripped = [ln.strip() for ln in lines]
    directed: list[tuple[int, int]] = []
    edge_rows: list[dict[str, Any]] = []
    for i, line in enumerate(lines):
        for atom in _value_atoms(line):
            for j, other in enumerate(lines):
                if i == j:
                    continue
                if stripped[i] and stripped[i] == stripped[j]:
                    continue
                if _contains_atom(other, atom):
                    directed.append((i, j))
                    edge_rows.append(
                        {"src": i, "dst": j, "atom": atom, "distance": abs(j - i)}
                    )
    undirected = _undirected(directed)
    distances = [abs(b - a) for a, b in undirected]
    n_lines = max(len(lines), 1)
    denom = max(n_lines - 1, 1)
    mean_d = float(sum(distances) / len(distances)) if distances else 0.0
    median_d = float(statistics.median(distances)) if distances else 0.0
    max_d = float(max(distances)) if distances else 0.0
    features = {
        "n_edges": float(len(undirected)),
        "mean_edge_distance": mean_d,
        "median_edge_distance": median_d,
        "max_edge_distance": max_d,
        "mean_edge_distance_norm": mean_d / denom,
        "component_span": float(_component_span(len(lines), undirected)),
        "chain_span": float(_chain_span(len(lines), directed)),
    }
    if not distances:
        notes.append("no_reference_edges")
    return SensorReport(
        features=features,
        evidence={
            "n_lines": str(n_lines),
            "n_directed": str(len(directed)),
            "primary": PRIMARY_FEATURE,
        },
        edges=edge_rows,
        fail_closed=False,
        notes=notes,
    )


def query_identifier_span(source_unit: Mapping[str, object]) -> dict[str, float]:
    """Separate candidate. Not mixed into deterministic_v0.l."""
    payload, fail_closed, _notes = _payload_of(source_unit)
    query = source_unit.get("query") or source_unit.get("q") or ""
    if fail_closed or not isinstance(query, str):
        return {"q_span": 0.0, "q_span_norm": 0.0, "q_hits": 0.0}
    atoms = [a for a in _atoms(query) if _is_identifier(a)]
    lines = payload.splitlines() or [payload]
    hits = [
        i for i, line in enumerate(lines) if any(_contains_atom(line, atom) for atom in atoms)
    ]
    if len(hits) < 2:
        return {"q_span": 0.0, "q_span_norm": 0.0, "q_hits": float(len(hits))}
    span = float(hits[-1] - hits[0])
    return {
        "q_span": span,
        "q_span_norm": span / max(len(lines) - 1, 1),
        "q_hits": float(len(hits)),
    }


class DependencyDispersionSensor:
    """Thermometer only. Do not route on these values in Phase 3B."""

    name = SENSOR_NAME

    def measure(self, source_unit: Mapping[str, object]) -> SensorReport:
        return measure(source_unit)

    def profile(self, source_unit: Mapping[str, object]) -> Mapping[str, float]:
        return self.measure(source_unit).features
