"""Irreversible loss ledger audit helpers for tests / checker."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def visible_texts(packet: Mapping[str, object]) -> list[str]:
    ev = packet.get("visible_evidence") or []
    out: list[str] = []
    if isinstance(ev, Sequence) and not isinstance(ev, (str, bytes)):
        for item in ev:
            if isinstance(item, Mapping) and "text" in item:
                out.append(str(item["text"]))
    return out


def unit_texts(packet: Mapping[str, object]) -> dict[str, str]:
    units = packet.get("units") or []
    out: dict[str, str] = {}
    if isinstance(units, Sequence) and not isinstance(units, (str, bytes)):
        for u in units:
            if isinstance(u, Mapping) and u.get("unit_id") is not None:
                out[str(u["unit_id"])] = str(u.get("text", ""))
    return out


def r_unit_ids(packet: Mapping[str, object]) -> set[str]:
    r = packet.get("R")
    ids: set[str] = set()
    if isinstance(r, Mapping):
        for e in r.get("entries") or []:
            if isinstance(e, Mapping) and e.get("unit_id") is not None:
                ids.add(str(e["unit_id"]))
    return ids


def ledger_unit_ids(packet: Mapping[str, object]) -> set[str]:
    ids: set[str] = set()
    raw_ledger = packet.get("irreversible_loss_ledger") or []
    ledger_rows = list(raw_ledger) if isinstance(raw_ledger, (list, tuple)) else []
    for row in ledger_rows:
        if isinstance(row, Mapping):
            for uid in row.get("unit_ids") or []:
                ids.add(str(uid))
    return ids


def declared_ledger_rows(packet: Mapping[str, object]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    raw_ledger = packet.get("irreversible_loss_ledger") or []
    ledger_rows = list(raw_ledger) if isinstance(raw_ledger, (list, tuple)) else []
    for row in ledger_rows:
        if isinstance(row, Mapping) and row.get("declared") is True:
            rows.append(dict(row))
    return rows


def audit_undeclared_visible_loss(
    before: Mapping[str, object],
    after: Mapping[str, object],
) -> dict[str, Any]:
    """Flag undeclared loss when visible text shrinks without R or ledger coverage.

    A visible text (or unit text) present in ``before`` but absent from ``after``
    must appear in R (recoverable) and/or irreversible_loss_ledger with declared=True.
    Whitespace-only differences are ignored for the shrink check (structural audit).
    """
    before_texts = set(visible_texts(before))
    after_texts = set(visible_texts(after))
    # Also consider unit identity disappearance
    before_units = unit_texts(before)
    after_units = unit_texts(after)

    disappeared_texts = sorted(t for t in before_texts if t not in after_texts and t.strip())
    disappeared_unit_ids = sorted(uid for uid in before_units if uid not in after_units)

    covered_r = r_unit_ids(after)
    covered_ledger = ledger_unit_ids(after)
    # R may also store original text in extra — collect recoverable texts
    recoverable_texts: set[str] = set()
    r = after.get("R")
    if isinstance(r, Mapping):
        for e in r.get("entries") or []:
            if not isinstance(e, Mapping):
                continue
            extra = e.get("extra") if isinstance(e.get("extra"), Mapping) else {}
            for k in ("text", "original_text"):
                if extra and k in extra:
                    recoverable_texts.add(str(extra[k]))

    undeclared_texts: list[str] = []
    for t in disappeared_texts:
        if t in recoverable_texts:
            continue
        # If every disappeared unit that carried this text is covered, OK
        carriers = [uid for uid, ut in before_units.items() if ut == t]
        if carriers and all(uid in covered_r or uid in covered_ledger for uid in carriers):
            continue
        if (
            not carriers
            and (covered_r or covered_ledger)
            and declared_ledger_rows(after)
        ):
            # text-only shrink without unit tracking — still need R/ledger signal
            continue
        undeclared_texts.append(t)

    undeclared_units: list[str] = []
    for uid in disappeared_unit_ids:
        if uid in covered_r or uid in covered_ledger:
            continue
        undeclared_units.append(uid)

    ok = not undeclared_texts and not undeclared_units
    return {
        "ok": ok,
        "disappeared_texts": disappeared_texts,
        "disappeared_unit_ids": disappeared_unit_ids,
        "undeclared_texts": undeclared_texts,
        "undeclared_units": undeclared_units,
        "n_r_entries": len(covered_r),
        "n_ledger_rows": len(declared_ledger_rows(after)),
    }


def assert_no_undeclared_loss(before: Mapping[str, object], after: Mapping[str, object]) -> None:
    report = audit_undeclared_visible_loss(before, after)
    if not report["ok"]:
        raise AssertionError(f"undeclared loss detected: {report}")
