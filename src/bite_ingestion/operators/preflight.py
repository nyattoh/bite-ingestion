"""Gold-free actionability helpers shared by UNTANGLE/INTEGRATE and routing.

No gold / texture / operator labels. No a/k thresholds.
"""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from typing import Any

INJECT_MARKERS = (
    "<<<INJECT",
    ">>>INJECT",
    "{{INJECTION",
    "<script>",
    "IGNORE PREVIOUS INSTRUCTIONS",
)
ANOMALY_MARKERS = re.compile(r"\b(ERROR|FATAL|EXCEPTION|TRACEBACK|PANIC)\b", re.IGNORECASE)
ID_FIELD = re.compile(r"\b(?:id|key)\s*=\s*([A-Za-z0-9_\-.]+)", re.IGNORECASE)
ROUTING_UNTANGLE_REASONS = ("malformed", "injection_suspect", "anomaly_candidate")


def looks_malformed_json(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if stripped[0] not in "{[":
        return ("{" in stripped or "[" in stripped) and (
            stripped.count("{") != stripped.count("}") or stripped.count("[") != stripped.count("]")
        )
    try:
        json.loads(stripped)
        return False
    except (json.JSONDecodeError, TypeError):
        return True


def injection_suspect(text: str) -> bool:
    upper = text.upper()
    return any(marker.upper() in upper for marker in INJECT_MARKERS)


def anomaly_candidate(text: str) -> bool:
    return bool(ANOMALY_MARKERS.search(text))


def routing_untangle_reasons(text: str) -> list[str]:
    reasons: list[str] = []
    if looks_malformed_json(text):
        reasons.append("malformed")
    if injection_suspect(text):
        reasons.append("injection_suspect")
    if anomaly_candidate(text):
        reasons.append("anomaly_candidate")
    return reasons


def extract_explicit_join_keys(text: str) -> list[str]:
    return [match.group(1) for match in ID_FIELD.finditer(text)]


def explicit_join_clusters(units: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: OrderedDict[str, list[str]] = OrderedDict()
    for unit in units:
        uid = str(unit.get("unit_id", ""))
        keys = extract_explicit_join_keys(str(unit.get("text", "")))
        if not uid or not keys:
            continue
        groups.setdefault(keys[0], []).append(uid)
    return [
        {"join_key": key, "unit_ids": members}
        for key, members in groups.items()
        if len(members) >= 2
    ]
