from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable

from .models import CanonicalCase, Fact

TEXTURE_FAMILIES: tuple[str, ...] = (
    "prose_narrative",
    "table_csv",
    "nested_json",
    "event_logs",
    "code_config",
    "mixed_payload",
)


def _fact_map(case: CanonicalCase) -> dict[str, Fact]:
    return {f.fact_id: f for f in case.facts}


def render_prose_narrative(case: CanonicalCase, *, dense: bool = True) -> str:
    lines = [f"Question: {case.question}", ""]
    for f in case.facts:
        if dense:
            lines.append(f"Record {f.fact_id}: {f.key} is {f.value}.")
        else:
            lines.append(f"According to unit {f.fact_id}, the field named {f.key} holds the value {f.value}.")
            lines.append("(neutral filler line; not part of gold evidence)")
    lines.append("")
    lines.append(f"Canonical answer label: {case.answer}")
    return "\n".join(lines)


def render_table_csv(case: CanonicalCase) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["fact_id", "key", "value"])
    for f in case.facts:
        w.writerow([f.fact_id, f.key, f.value])
    return f"# question: {case.question}\n# answer: {case.answer}\n" + buf.getvalue()


def render_nested_json(case: CanonicalCase) -> str:
    payload = {
        "query": case.question,
        "answer": case.answer,
        "graph": {
            "nodes": [
                {"id": f.fact_id, "attrs": {"key": f.key, "value": f.value}} for f in case.facts
            ]
        },
        "required_evidence_ids": list(case.required_evidence_ids),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_event_logs(case: CanonicalCase, *, repetitive: bool = True) -> str:
    lines = [f"INFO query={case.question}"]
    for f in case.facts:
        lines.append(f"INFO unit={f.fact_id} key={f.key} value={f.value}")
        if repetitive:
            lines.append(f"DEBUG heartbeat unit={f.fact_id} ok=1")
            lines.append(f"DEBUG heartbeat unit={f.fact_id} ok=1")
    lines.append(f"INFO gold_answer={case.answer}")
    return "\n".join(lines)


def render_code_config(case: CanonicalCase) -> str:
    body = ["# synthetic config; not a real service", f"query = {case.question!r}", "records = {"]
    for f in case.facts:
        body.append(f"    {f.fact_id!r}: {{{f.key!r}: {f.value!r}}},")
    body.append("}")
    body.append(f"answer = {case.answer!r}")
    return "\n".join(body)


def render_mixed_payload(case: CanonicalCase) -> str:
    prose = render_prose_narrative(case, dense=True)
    table = render_table_csv(case)
    logs = render_event_logs(case, repetitive=False)
    return "\n--- PROSE ---\n" + prose + "\n--- TABLE ---\n" + table + "\n--- LOGS ---\n" + logs


RENDERERS: dict[str, Callable[[CanonicalCase], str]] = {
    "prose_narrative": lambda c: render_prose_narrative(c, dense=True),
    "table_csv": render_table_csv,
    "nested_json": render_nested_json,
    "event_logs": lambda c: render_event_logs(c, repetitive=True),
    "code_config": render_code_config,
    "mixed_payload": render_mixed_payload,
}
