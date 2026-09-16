"""hyve_like — machine-data structured view stub (JSON/CSV field projection).

Applicable ONLY when domain=machine_data; else status=not_applicable.
NO full HYVE reimplementation; fairness contrast stub only.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Mapping

from bite_eval.interface import (
    empty_accounting,
    extract_domain,
    extract_query,
    extract_text,
    make_output,
)

APPLICABLE_DOMAINS = frozenset({"machine_data", "machine-data", "tabular", "observability"})


def _project_json(text: str, query_tokens: set[str]) -> str:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try line-delimited JSON
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                return _fallback_fields(text, query_tokens)
        data = rows
    return json.dumps(_filter_obj(data, query_tokens), ensure_ascii=False, indent=2)


def _filter_obj(obj: object, query_tokens: set[str]) -> object:
    if isinstance(obj, Mapping):
        if not query_tokens:
            # project first-level keys only (structured view)
            return {k: _summarize_val(v) for k, v in list(obj.items())[:20]}
        out = {}
        for k, v in obj.items():
            ks = str(k).lower()
            hit = any(t in ks for t in query_tokens) or _value_hit(v, query_tokens)
            if hit:
                out[k] = _filter_obj(v, query_tokens) if isinstance(v, (Mapping, list)) else v
        return out or {k: _summarize_val(v) for k, v in list(obj.items())[:5]}
    if isinstance(obj, list):
        filtered = [_filter_obj(x, query_tokens) for x in obj[:50]]
        return [x for x in filtered if x not in (None, {}, [])][:20] or obj[:3]
    return obj


def _summarize_val(v: object) -> object:
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, list):
        return f"<list n={len(v)}>"
    if isinstance(v, Mapping):
        return f"<object keys={list(v.keys())[:8]}>"
    return str(type(v).__name__)


def _value_hit(v: object, query_tokens: set[str]) -> bool:
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    low = s.lower()
    return any(t in low for t in query_tokens)


def _project_csv(text: str, query_tokens: set[str]) -> str:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return _fallback_fields(text, query_tokens)
    fields = list(reader.fieldnames)
    if query_tokens:
        keep = [f for f in fields if any(t in f.lower() for t in query_tokens)]
        if not keep:
            keep = fields[: min(4, len(fields))]
    else:
        keep = fields[: min(6, len(fields))]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=keep, extrasaction="ignore")
    writer.writeheader()
    for i, row in enumerate(reader):
        if i >= 50:
            break
        if query_tokens:
            blob = " ".join(str(row.get(f, "")) for f in fields).lower()
            if not any(t in blob for t in query_tokens):
                continue
        writer.writerow({k: row.get(k, "") for k in keep})
    return buf.getvalue()


def _fallback_fields(text: str, query_tokens: set[str]) -> str:
    lines = text.splitlines()
    if not query_tokens:
        return "\n".join(lines[:30])
    kept = [ln for ln in lines if any(t in ln.lower() for t in query_tokens)]
    return "\n".join(kept[:40] or lines[:10])


def _tokenize(q: str) -> set[str]:
    return {t for t in re.findall(r"[A-Za-z0-9_]+", q.lower()) if len(t) > 1}


class HyveLikeBaseline:
    """HYVE-*like* stub for machine_data only — NO full HYVE reimplementation."""

    baseline_id: str = "hyve_like"

    fairness_note: str = (
        "stub-offline JSON/CSV field projection; domain=machine_data only; "
        "NOT a HYVE reimplementation; trademark-safe -like label; fairness contrast"
    )

    def run(
        self,
        packet: Mapping[str, object],
        context: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        domain = extract_domain(packet, context)
        if domain not in APPLICABLE_DOMAINS:
            return make_output(
                baseline_id=self.baseline_id,
                status="not_applicable",
                visible_evidence="",
                accounting=empty_accounting(),
                baseline_trace={
                    "domain": domain or None,
                    "required_domain": "machine_data",
                    "fairness_note": self.fairness_note,
                },
                reason=(
                    f"hyve_like not applicable for domain={domain!r}; "
                    "requires domain=machine_data"
                ),
            )
        try:
            text = extract_text(packet)
            query = extract_query(packet, context)
            qtok = _tokenize(query)
            stripped = text.lstrip()
            if stripped.startswith(("{", "[")):
                visible = _project_json(text, qtok)
                kind = "json_projection"
            elif "," in text.split("\n", 1)[0] and "\n" in text:
                visible = _project_csv(text, qtok)
                kind = "csv_projection"
            else:
                visible = _fallback_fields(text, qtok)
                kind = "line_filter_fallback"
            return make_output(
                baseline_id=self.baseline_id,
                status="ok",
                visible_evidence=visible,
                accounting=empty_accounting(),
                tau=[{"op": "HYVE_LIKE", "kind": kind, "domain": domain}],
                baseline_trace={
                    "label": "hyve_like",
                    "domain": domain,
                    "kind": kind,
                    "fairness_note": self.fairness_note,
                    "NOT_reimplemented": "HYVE",
                },
            )
        except Exception as exc:  # noqa: BLE001
            return make_output(
                baseline_id=self.baseline_id,
                status="failed",
                visible_evidence="",
                accounting=empty_accounting(),
                reason=f"hyve_like failed: {exc}",
            )


__all__ = ["APPLICABLE_DOMAINS", "HyveLikeBaseline"]
