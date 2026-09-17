"""Eval-path wiring: profiler attach, operator execution, bounded re-bite.

Deterministic. No paid API. Gold / oracle / family labels never enter the
profiler source unit or policy routing maps.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from typing import Any, cast

from bite_eval.interface import extract_query, extract_text
from bite_ingestion.packet_contract import (
    resolve_packet_units,
    visible_evidence_from_units,
)
from bite_ingestion.profilers import DeterministicMorphologyProfiler
from bite_ingestion.profilers.deterministic import FEATURE_KEYS, ProfileReport

PHASE1_ARMS: tuple[str, ...] = ("raw_full", "length_pi", "rule_pi", "rule_pi_rebite")
_QUERY_TOKEN = re.compile(r"[A-Za-z0-9_]+")


def profiler_source_unit(
    packet: Mapping[str, object],
    context: Mapping[str, object] | None = None,
) -> dict[str, str]:
    """Payload + query only. No gold / oracle / family / evidence ids."""
    text = extract_text(packet)
    query = extract_query(packet, context)
    return {"payload": text, "text": text, "query": query}


def attach_morphology(
    packet: Mapping[str, object],
    context: Mapping[str, object] | None = None,
) -> tuple[dict[str, Any], ProfileReport]:
    """Copy *packet*, measure morphology, attach 8 features. Fail-closed later."""
    report = DeterministicMorphologyProfiler().profile_report(profiler_source_unit(packet, context))
    working = dict(packet)
    working["morphology"] = {k: float(report.features[k]) for k in FEATURE_KEYS}
    working["_profiler_cpu_ms"] = float(report.cpu_ms)
    return working, report


def _omitted_spans(packet: Mapping[str, object]) -> list[tuple[int, int]]:
    """Char ranges removed by an operator, taken from R locators."""
    spans: list[tuple[int, int]] = []
    for entry in _r_entries(packet):
        loc = entry.get("locator")
        span = loc.get("span") if isinstance(loc, Mapping) else None
        if isinstance(span, Mapping) and span.get("start") is not None:
            try:
                spans.append((int(span["start"]), int(span["end"])))
            except (TypeError, ValueError, KeyError):
                continue
    return spans


def _reconstruct_from_document(packet: Mapping[str, object]) -> str | None:
    """Rebuild the payload from the source document, keeping its separators.

    Returns ``None`` when the units are not verbatim document slices (REDUCE
    rewrites text, INTEGRATE joins it), in which case the caller falls back to
    joining unit texts.

    Without this, a text-preserving sequence such as CUT re-emitted the
    document with ``\\n`` between every unit. A genuine no-op then looked like
    a transformation, and the candidate arms sent whitespace the baseline did
    not — a raw-vs-candidate prompt difference with no compression behind it.
    """
    doc = extract_text(packet)
    if not doc:
        return None
    raw_units = packet.get("units")
    if not isinstance(raw_units, list) or not raw_units:
        return None

    kept: list[tuple[int, int]] = []
    for u in raw_units:
        if not isinstance(u, Mapping):
            return None
        span = u.get("span")
        if not isinstance(span, Mapping) or span.get("start") is None:
            return None
        try:
            start, end = int(span["start"]), int(span["end"])
        except (TypeError, ValueError, KeyError):
            return None
        if end > len(doc) or doc[start:end] != str(u.get("text", "")):
            # Derived / rewritten unit — span no longer addresses its body.
            return None
        kept.append((start, end))

    kept.sort()
    omitted = _omitted_spans(packet)

    def _gap(lo: int, hi: int) -> str:
        """Inter-unit text, kept only when nothing was removed inside it."""
        if lo >= hi:
            return ""
        if any(o_s < hi and o_e > lo for o_s, o_e in omitted):
            return ""
        return doc[lo:hi]

    parts: list[str] = []
    cursor = 0
    for start, end in kept:
        parts.append(_gap(cursor, start))
        parts.append(doc[start:end])
        cursor = end
    parts.append(_gap(cursor, len(doc)))
    return "".join(parts)


def payload_text_from_packet(packet: Mapping[str, object]) -> str:
    """Canonical payload: document slices when verbatim, else joined unit texts."""
    rebuilt = _reconstruct_from_document(packet)
    if rebuilt is not None:
        return rebuilt
    ve = packet.get("visible_evidence")
    if isinstance(ve, str) and ve:
        return ve
    if isinstance(ve, list) and ve:
        parts: list[str] = []
        for item in ve:
            if isinstance(item, Mapping) and item.get("text") is not None:
                parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        if parts:
            return "\n".join(parts)
    units = packet.get("units")
    if isinstance(units, list) and units:
        ordered = sorted(
            [u for u in units if isinstance(u, Mapping)],
            key=lambda u: (
                int((u.get("span") or {}).get("start", 0))
                if isinstance(u.get("span"), Mapping)
                else 0,
                str(u.get("unit_id", "")),
            ),
        )
        if ordered:
            return "\n".join(str(u.get("text", "")) for u in ordered)
    # A packet that carries a unit graph has an EMPTY payload when that graph
    # is empty. Falling back to the raw document here re-emitted text that
    # UNTANGLE had just quarantined into R: visible_unit_ids=[] and R=1 while
    # the quarantined body was still in the prompt.
    if "units" in packet or isinstance(packet.get("visible_evidence"), list):
        return ""
    return extract_text(packet)


def payload_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


#: Evaluation-only keys that must not travel into the operator layer.
OPERATOR_FORBIDDEN_KEYS: frozenset[str] = frozenset({"family", "texture", "facts_id"})
OPERATOR_FORBIDDEN_PREFIXES: tuple[str, ...] = ("gold_", "oracle_", "eval_")


def scrub_eval_only_keys(packet: Mapping[str, object]) -> dict[str, Any]:
    """Drop gold / oracle / family labels before handing a packet downstream."""
    out: dict[str, Any] = {}
    for k, v in packet.items():
        key = str(k)
        if key in OPERATOR_FORBIDDEN_KEYS or key.startswith(OPERATOR_FORBIDDEN_PREFIXES):
            continue
        out[k] = v
    return out


def ensure_operator_packet(packet: Mapping[str, object]) -> dict[str, Any]:
    """Make a working packet operators can consume (span-backed units).

    Units are resolved (and gold ids validated) *before* scrubbing, so the
    evidence-id contract is still enforced while the operators never receive
    gold / oracle / family labels.
    """
    working = dict(packet)
    doc = extract_text(working)
    if not working.get("packet_id"):
        working["packet_id"] = str(working.get("instance_id") or "pkt")
    units = working.get("units")
    if not (isinstance(units, list) and units):
        units = resolve_packet_units(working, document=doc)
        working["units"] = units
    raw_units = working.get("units")
    unit_list = (
        [u for u in raw_units if isinstance(u, Mapping)] if isinstance(raw_units, list) else []
    )
    working["visible_evidence"] = visible_evidence_from_units(unit_list)
    return scrub_eval_only_keys(working)


def execute_sequence(
    packet: Mapping[str, object],
    sequence: Sequence[object],
    *,
    policy_name: str,
    context: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    from bite_ingestion.interfaces.operator import OperatorId
    from bite_ingestion.policies import apply_sequence

    # Neither the packet nor the context may carry gold / oracle / family.
    working = ensure_operator_packet(packet)
    op_context = scrub_eval_only_keys(context or {})
    seq = cast(Sequence[OperatorId | str], sequence)
    return apply_sequence(seq, working, policy_name=policy_name, context=op_context)


def is_no_op(original_text: str, transformed: Mapping[str, object]) -> bool:
    payload = payload_text_from_packet(transformed)
    r = transformed.get("R")
    entries = []
    if isinstance(r, Mapping):
        raw = r.get("entries") or []
        if isinstance(raw, list):
            entries = raw
    return payload == original_text and not entries


def visible_unit_ids(transformed: Mapping[str, object]) -> list[str]:
    units = transformed.get("units")
    if isinstance(units, list):
        return [str(u.get("unit_id")) for u in units if isinstance(u, Mapping) and u.get("unit_id")]
    ve = transformed.get("visible_evidence")
    ids: list[str] = []
    if isinstance(ve, list):
        for item in ve:
            if isinstance(item, Mapping):
                for uid in item.get("unit_ids") or []:
                    ids.append(str(uid))
    return ids


def _query_tokens(query: str) -> list[str]:
    return [t.lower() for t in _QUERY_TOKEN.findall(query) if len(t) > 1]


def _r_entries(packet: Mapping[str, object]) -> list[dict[str, Any]]:
    r = packet.get("R")
    if not isinstance(r, Mapping):
        return []
    raw = r.get("entries") or []
    if not isinstance(raw, list):
        return []
    return [dict(e) for e in raw if isinstance(e, Mapping)]


def _omitted_text(entry: Mapping[str, object]) -> str:
    extra = entry.get("extra") if isinstance(entry.get("extra"), Mapping) else {}
    if isinstance(extra, Mapping):
        for k in ("text", "original_text"):
            v = extra.get(k)
            if isinstance(v, str) and v:
                return v
    return ""


def insufficient_r_targets(
    payload: str,
    query: str,
    r_entries: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """R entries to fetch when visible evidence cannot cover the query.

    Uses query tokens vs omitted text. Never consults gold / oracle ids.
    """
    vis = payload.lower()
    qtoks = _query_tokens(query)
    hits: list[dict[str, Any]] = []
    vis_empty = not payload.strip()
    for e in r_entries:
        if e.get("recoverable", True) is False:
            continue
        text = _omitted_text(e)
        if not text:
            continue
        low = text.lower()
        if vis_empty:
            hits.append(dict(e))
            continue
        if not qtoks:
            continue
        in_omitted = [t for t in qtoks if t in low]
        if in_omitted and not any(t in vis for t in in_omitted):
            hits.append(dict(e))
    hits.sort(key=lambda e: str(e.get("r_id") or e.get("unit_id") or ""))
    return hits


def source_store_from(
    original_units: Sequence[Mapping[str, Any]],
    transformed: Mapping[str, object],
) -> Any:
    from bite_ingestion.recovery import SourceRecord, SourceStore

    store = SourceStore()
    for u in original_units:
        if not isinstance(u, Mapping) or not u.get("unit_id"):
            continue
        span = u.get("span") if isinstance(u.get("span"), Mapping) else None
        store.put(
            SourceRecord(
                unit_id=str(u["unit_id"]),
                text=str(u.get("text", "")),
                uri=str(u["source_uri"]) if u.get("source_uri") else None,
                span=dict(span) if span else None,
            )
        )
    for e in _r_entries(transformed):
        uid = str(e.get("unit_id") or "")
        if not uid or uid in store:
            continue
        loc = e.get("locator") if isinstance(e.get("locator"), Mapping) else {}
        span = (
            loc.get("span")
            if isinstance(loc, Mapping) and isinstance(loc.get("span"), Mapping)
            else None
        )
        store.put(
            SourceRecord(
                unit_id=uid,
                text=_omitted_text(e),
                uri=str(loc.get("source_uri"))
                if isinstance(loc, Mapping) and loc.get("source_uri")
                else None,
                span=dict(span) if span else None,
            )
        )
    return store


def bounded_rebite(
    transformed: Mapping[str, object],
    *,
    query: str,
    original_units: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], int, list[dict[str, Any]]]:
    """Fetch omitted query-relevant units from R, up to J / B_r. No gold."""
    from bite_ingestion.recovery import (
        DEFAULT_BR_TOKENS,
        DEFAULT_J,
        RebiteRequest,
        RecoverBudget,
        RecoverEngine,
        RecoverState,
    )

    pkt = dict(transformed)
    payload_before = payload_text_from_packet(pkt)
    targets = insufficient_r_targets(payload_before, query, _r_entries(pkt))
    if not targets:
        return pkt, 0, []

    store = source_store_from(original_units, pkt)
    engine = RecoverEngine(RecoverBudget(max_calls=DEFAULT_J, token_ceiling=DEFAULT_BR_TOKENS))
    state = RecoverState()
    steps: list[dict[str, Any]] = []
    tokens = 0
    fetched: set[str] = set()
    from bite_ingestion.recovery.budget import estimate_tokens as _est

    for entry in targets:
        uid = str(entry.get("unit_id") or "")
        if not uid or uid in fetched:
            continue
        result = engine.recover(
            pkt,
            RebiteRequest(request_type="fetch_unit", unit_id=uid),
            store,
            state,
        )
        pkt = dict(result.packet)
        step_tok = int(result.estimated_tokens or 0)
        if result.returned_evidence_ids and step_tok <= 0:
            step_tok = _est(
                _omitted_text(entry) or payload_text_from_packet(pkt)[len(payload_before) :]
            )
        tokens += step_tok
        fetched.add(uid)
        loc = entry.get("locator") if isinstance(entry.get("locator"), Mapping) else {}
        steps.append(
            {
                "unit_id": uid,
                "r_id": entry.get("r_id"),
                "locator": dict(loc) if isinstance(loc, Mapping) else {},
                "outcome": result.outcome,
                "estimated_tokens": step_tok,
                "returned_evidence_ids": list(result.returned_evidence_ids or []),
            }
        )
        if state.calls >= DEFAULT_J:
            break
    payload_after = payload_text_from_packet(pkt)
    if payload_after != payload_before and tokens <= 0:
        tokens = _est(payload_after[len(payload_before) :] or payload_after)
    return pkt, tokens, steps


def output_fields_from_transformed(
    transformed: Mapping[str, object],
    *,
    original_text: str,
) -> dict[str, Any]:
    payload = payload_text_from_packet(transformed)
    raw_r = transformed.get("R")
    raw_units = transformed.get("units")
    raw_loss = transformed.get("irreversible_loss_ledger")
    raw_tau = transformed.get("tau")
    no_op = is_no_op(original_text, transformed)
    return {
        "payload_text": payload,
        "payload_hash": payload_hash(payload),
        "visible_unit_ids": visible_unit_ids(transformed),
        "R": dict(raw_r) if isinstance(raw_r, Mapping) else {"entries": []},
        "units": list(raw_units) if isinstance(raw_units, list) else [],
        "irreversible_loss_ledger": list(raw_loss) if isinstance(raw_loss, list) else [],
        "operator_tau": dict(raw_tau) if isinstance(raw_tau, Mapping) else {},
        "transformation_status": "no_op" if no_op else "transformed",
        "is_no_op": no_op,
    }


def run_phase1_matrix(*args: Any, **kwargs: Any) -> dict[str, Any]:
    from bite_eval.phase1_matrix import run_phase1_matrix as _run

    return _run(*args, **kwargs)


__all__ = [
    "FEATURE_KEYS",
    "OPERATOR_FORBIDDEN_KEYS",
    "OPERATOR_FORBIDDEN_PREFIXES",
    "PHASE1_ARMS",
    "attach_morphology",
    "bounded_rebite",
    "ensure_operator_packet",
    "execute_sequence",
    "insufficient_r_targets",
    "is_no_op",
    "output_fields_from_transformed",
    "payload_hash",
    "payload_text_from_packet",
    "profiler_source_unit",
    "run_phase1_matrix",
    "scrub_eval_only_keys",
    "visible_unit_ids",
]
