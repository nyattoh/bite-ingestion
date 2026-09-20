"""REALSTRUCT-1 scorer overlay v2. Independent of BITE implementation.

Same first-= assignment grammar as Phase 4A. Two-pass key index.
Exact (key, value) duplicate gold. Does not import policies or profilers.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bite_bench.phase4b import DIFF_PATH, V2_PATH, write_freeze
from bite_bench.realstruct1 import (
    ANNOTATION_PATH,
    ASSIGN_RE,
    COMMENT_RE,
    REF_RE,
    SECTION_RE,
    SOURCES,
    decode_source,
    load_raw,
)

SCHEMA_ID = "bite-phase4a-realstruct1-annotations-v2/v0.1"
REVISION = "phase4b-annotations-v2-v0.1"
DIFF_SCHEMA_ID = "bite-phase4b-annotation-diff/v0.1"


def annotate_bytes_v2(data: bytes) -> dict[str, Any]:
    text, encoding = decode_source(data)
    records: list[dict[str, Any]] = []
    assignments: list[tuple[int, str, str, int]] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            records.append({"kind": "unsupported", "line": line_no, "reason": "blank"})
            continue
        if COMMENT_RE.match(line):
            records.append({"kind": "unsupported", "line": line_no, "reason": "comment"})
            continue
        if SECTION_RE.match(line):
            records.append({"kind": "unsupported", "line": line_no, "reason": "section"})
            continue
        match = ASSIGN_RE.match(line)
        if not match:
            records.append({"kind": "unsupported", "line": line_no, "reason": "other"})
            continue
        key = match.group(1).strip()
        value = match.group(2)
        records.append(
            {
                "kind": "assignment",
                "line": line_no,
                "assignment_key": key,
                "assignment_value": value,
            }
        )
        assignments.append((line_no, key, value, match.start(2)))

    key_lines: dict[str, list[int]] = defaultdict(list)
    ident_lines: dict[tuple[str, str], list[int]] = defaultdict(list)
    for line_no, key, value, _off in assignments:
        key_lines[key].append(line_no)
        ident_lines[(key, value)].append(line_no)

    edges: list[dict[str, Any]] = []
    for line_no, _key, value, value_off in assignments:
        for ref in REF_RE.finditer(value):
            name = ref.group(1)
            dest = key_lines.get(name) or []
            if not dest:
                continue
            edges.append(
                {
                    "name": name,
                    "source_line": line_no,
                    "source_span": [value_off + ref.start(), value_off + ref.end()],
                    "dest_lines": list(dest),
                }
            )

    exact_duplicate_groups = [
        {"assignment_key": key, "assignment_value": value, "lines": lines}
        for (key, value), lines in sorted(ident_lines.items())
        if len(lines) > 1
    ]
    repeated_key_groups = [
        {"assignment_key": key, "lines": lines}
        for key, lines in sorted(key_lines.items())
        if len(lines) > 1
    ]
    n_assign = sum(1 for rec in records if rec["kind"] == "assignment")
    n_unsup = sum(1 for rec in records if rec["kind"] == "unsupported")
    return {
        "encoding": encoding,
        "records": records,
        "explicit_reference_edges": edges,
        "exact_duplicate_groups": exact_duplicate_groups,
        "repeated_key_groups": repeated_key_groups,
        "n_assignments": n_assign,
        "n_unsupported": n_unsup,
        "n_explicit_reference_edges": len(edges),
        "n_exact_duplicate_groups": len(exact_duplicate_groups),
        "n_lines": len(text.splitlines()),
        "two_pass_key_index": True,
    }


def annotation_v2_manifest() -> dict[str, Any]:
    documents = []
    for spec in SOURCES:
        documents.append({"source_id": spec.source_id, **annotate_bytes_v2(load_raw(spec))})
    return {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "independent_of_bite_implementation": True,
        "raw_syntax_only": True,
        "explicit_reference_gold": "${NAME} only",
        "key_index": "two-pass document-wide",
        "exact_duplicate_identity": "exact (assignment_key, assignment_value)",
        "missing_annotation_is_not_non_reference": True,
        "phase4a_annotations_are_legacy": True,
        "forbidden_scorer_fields": [
            "expected BITE route",
            "expected operator sequence",
        ],
        "documents": documents,
    }


def _edge_key(edge: Mapping[str, Any]) -> tuple[object, ...]:
    return (
        int(edge["source_line"]),
        str(edge["name"]),
        tuple(int(x) for x in edge.get("dest_lines") or []),
        tuple(int(x) for x in edge.get("source_span") or []),
    )


def annotation_diff() -> dict[str, Any]:
    legacy = json.loads(ANNOTATION_PATH.read_text(encoding="utf-8"))
    overlay = annotation_v2_manifest()
    by_v1 = {row["source_id"]: row for row in legacy["documents"]}
    rows = []
    for row in overlay["documents"]:
        sid = str(row["source_id"])
        old = by_v1[sid]
        v1_keys = {_edge_key(edge) for edge in old.get("explicit_reference_edges") or []}
        v2_keys = {_edge_key(edge) for edge in row.get("explicit_reference_edges") or []}
        forward = 0
        for edge in row.get("explicit_reference_edges") or []:
            src = int(edge["source_line"])
            if any(int(dest) > src for dest in edge.get("dest_lines") or []):
                forward += 1
        rows.append(
            {
                "source_id": sid,
                "n_edges_v1": int(old.get("n_explicit_reference_edges") or 0),
                "n_edges_v2": int(row.get("n_explicit_reference_edges") or 0),
                "n_edges_added": len(v2_keys - v1_keys),
                "n_forward_capable_edges": forward,
                "n_repeated_key_groups_v1": len(old.get("duplicate_groups") or []),
                "n_repeated_key_groups_v2": len(row.get("repeated_key_groups") or []),
                "n_exact_duplicate_groups_v2": int(row.get("n_exact_duplicate_groups") or 0),
            }
        )
    return {
        "schema": DIFF_SCHEMA_ID,
        "revision": REVISION,
        "phase4a_legacy_path": "corpora/realstruct-1/annotations.json",
        "overlay_v2_path": "corpora/realstruct-1/annotations-v2.json",
        "documents": rows,
    }


def _dump(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(doc), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_overlay() -> dict[str, Any]:
    overlay = annotation_v2_manifest()
    _dump(V2_PATH, overlay)
    _dump(DIFF_PATH, annotation_diff())
    write_freeze()
    return overlay


if __name__ == "__main__":
    payload = write_overlay()
    print("documents", len(payload["documents"]), "edges", sum(
        int(row["n_explicit_reference_edges"]) for row in payload["documents"]
    ))
