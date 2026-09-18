"""Synthetic workload families for BITE-14 offline pilot (bite-04 §3.3).

Generates N_pilot instances per family procedurally. No network, no paid API,
no Gemini ingest. Content is authored synthetic only.

Packet contract (Phase 1 foundation)
------------------------------------
Every packet carries a **unit graph** anchored to ``document`` character
spans. ``gold_evidence_ids`` name real units, so evidence recall can be
derived from the payload instead of being declared up front.

- ``units``: contract-compliant source units (see
  :mod:`bite_ingestion.packet_contract`)
- ``gold_evidence_ids``: unit ids required to answer
- ``visible_evidence``: operator-facing rendering of the same units
- ``recoverable_evidence_ids``: **empty by construction** — recoverability is
  earned by an operator putting a unit into ``R``, never pre-declared

The document strings are byte-identical to the previous revision; only the
evidence representation changed.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from bite_ingestion.packet_contract import (
    make_unit,
    provenance_completeness,
    visible_evidence_from_units,
)

# Locked family ids from bite-04 / d2_lock configs (8 synthetic families).
SYNTHETIC_FAMILIES: tuple[str, ...] = (
    "clean_local",
    "repeated_records",
    "sparse_anomaly",
    "dependency_chain",
    "malformed_mixed",
    "dense_cross_reference",
    "adversarial_omission",
    "texture_swap",
)

FAMILIES_RENDERER_ID = "pilot_families@v0.2"


@dataclass(frozen=True)
class _Seg:
    """One document segment that becomes a unit."""

    text: str
    unit_id: str | None = None
    gold: bool = False
    role: str | None = None
    #: Override the packet source_uri for this unit. ``""`` models a segment
    #: whose origin was never recorded, so provenance cannot be complete.
    source_uri: str | None = None


def _build_document(
    pieces: Sequence[_Seg | str],
    *,
    source_uri: str,
    filler_prefix: str,
) -> tuple[str, list[dict[str, Any]], list[str]]:
    """Concatenate pieces, tracking exact char spans for every unit.

    Plain ``str`` pieces are separators/joiners and belong to no unit.
    """
    parts: list[str] = []
    units: list[dict[str, Any]] = []
    gold_ids: list[str] = []
    pos = 0
    filler_n = 0
    for piece in pieces:
        if isinstance(piece, str):
            parts.append(piece)
            pos += len(piece)
            continue
        start = pos
        end = start + len(piece.text)
        parts.append(piece.text)
        pos = end
        uid = piece.unit_id
        if uid is None:
            uid = f"{filler_prefix}-f{filler_n}"
            filler_n += 1
        units.append(
            make_unit(
                unit_id=uid,
                text=piece.text,
                start=start,
                end=end,
                source_uri=source_uri if piece.source_uri is None else piece.source_uri,
                renderer_id=FAMILIES_RENDERER_ID,
                role=piece.role,
            )
        )
        if piece.gold:
            gold_ids.append(uid)
    return "".join(parts), units, gold_ids


def _base(
    family: str,
    idx: int,
    *,
    pieces: Sequence[_Seg | str],
    query: str,
    gold_answer: str,
    domain: str = "synthetic",
    extra: dict | None = None,
) -> dict[str, object]:
    instance_id = f"{family}-{idx:03d}"
    source_uri = f"synthetic://{instance_id}"
    document, units, gold_ids = _build_document(
        pieces, source_uri=source_uri, filler_prefix=instance_id
    )
    packet: dict[str, object] = {
        "instance_id": instance_id,
        "family": family,
        "domain": domain,
        "source_uri": source_uri,
        "document": document,
        "query": query,
        "gold_answer": gold_answer,
        "units": units,
        "gold_evidence_ids": gold_ids,
        # Operator-facing rendering of the same unit graph.
        "visible_evidence": visible_evidence_from_units(units),
        # Recoverability is earned via R, never declared on the packet.
        "recoverable_evidence_ids": [],
        # Measured from the unit graph, not self-reported.
        "provenance_complete_rate": provenance_completeness(units),
        "synthetic": True,
        "paid_api": False,
    }
    if extra:
        packet.update(extra)
    return packet


def generate_family_instances(
    family: str,
    n: int = 24,
) -> list[dict[str, object]]:
    """Generate up to ``n`` synthetic instances for ``family``.

    All eight lock families are generable offline; returns exactly ``n``
    packets when ``family`` is known, else empty list.
    """
    if family not in SYNTHETIC_FAMILIES:
        return []
    return list(_iter_family(family, n))


def _iter_family(family: str, n: int) -> Iterator[dict[str, object]]:
    for i in range(n):
        code = f"K{i:02d}"
        val = 100 + i
        eid = f"{family}-e{i}"
        eid2 = f"{family}-e{i}b"

        if family == "clean_local":
            yield _base(
                family,
                i,
                pieces=[
                    _Seg(f"Section A. The codeword {code} equals {val}.", eid, gold=True),
                    " ",
                    _Seg("Section B filler about weather and unrelated notes."),
                ],
                query=f"What is {code}?",
                gold_answer=str(val),
                domain="prose",
            )

        elif family == "repeated_records":
            pieces: list[_Seg | str] = [_Seg("schema=kv"), "\n"]
            for j in range(8):
                pieces.append(_Seg(f"rec={j},key=item,value=widget{j % 3}"))
                pieces.append("\n")
            pieces.append(_Seg(f"rec=rare,key=codeword,value={code}:{val}", eid, gold=True))
            pieces.append("\n")
            yield _base(
                family,
                i,
                pieces=pieces,
                query="What is the rare codeword value?",
                gold_answer=f"{code}:{val}",
                domain="tabular_nested_machine_data",
            )

        elif family == "sparse_anomaly":
            pieces = []
            for j in range(12):
                pieces.append(_Seg(f"OK heartbeat={j}"))
                pieces.append("\n")
            pieces.append(_Seg(f"ALERT anomaly_id={code} severity={val}", eid, gold=True))
            pieces.append("\n")
            for j in range(12):
                pieces.append(_Seg(f"OK heartbeat={j}"))
                if j < 11:
                    pieces.append("\n")
            yield _base(
                family,
                i,
                pieces=pieces,
                query="What is the anomaly_id?",
                gold_answer=code,
                domain="observability_logs",
            )

        elif family == "dependency_chain":
            yield _base(
                family,
                i,
                pieces=[
                    _Seg("unit_u0 depends_on=u1"),
                    "\n",
                    _Seg("unit_u1 depends_on=u2", eid, gold=True),
                    "\n",
                    _Seg(f"unit_u2 fact={code}={val}", eid2, gold=True),
                    "\n",
                ],
                # Gold is the bare value. Ask for digits only so the model does
                # not echo "Kxx=val". Do NOT embed gold in the query (leak).
                query=(
                    f"Follow the dependency chain to unit_u2. "
                    f"What is the numeric value of {code}? "
                    f"Reply with only that number (example format: 42), "
                    f"not the key=value form."
                ),
                gold_answer=str(val),
                domain="mixed_agent_tool_outputs",
            )

        elif family == "malformed_mixed":
            yield _base(
                family,
                i,
                pieces=[
                    _Seg("{broken_json: true, trailing"),
                    "\n",
                    _Seg(f"NOTE: salvage codeword {code} is {val}.", eid, gold=True),
                    "\n",
                    _Seg("more}}garbage"),
                ],
                query=f"Salvage value of {code}.",
                gold_answer=str(val),
                domain="mixed_agent_tool_outputs",
            )

        elif family == "dense_cross_reference":
            yield _base(
                family,
                i,
                pieces=[
                    _Seg("[1] see [2]."),
                    " ",
                    _Seg(f"[2] defines {code}.", eid, gold=True),
                    " ",
                    _Seg(f"[3] {code}={val}.", eid2, gold=True),
                    " ",
                    _Seg("[4] cites [3]."),
                ],
                query=f"Value of {code}?",
                gold_answer=str(val),
                domain="prose",
            )

        elif family == "adversarial_omission":
            # Both halves are gold. Under raw_full both are genuinely in the
            # payload, so recall_vis=1.0 is the honest value; an arm that drops
            # the HIDDEN span must move that unit id into R to keep recall_rec.
            filler = " ".join(f"noise{j}" for j in range(20))
            yield _base(
                family,
                i,
                pieces=[
                    _Seg(f"VISIBLE: hint_token={code}", eid, gold=True),
                    "\n",
                    _Seg(filler),
                    "\n",
                    _Seg(f"HIDDEN: {code}={val}", eid2, gold=True),
                    "\n",
                    _Seg(filler),
                ],
                query=f"Recover {code}.",
                gold_answer=str(val),
                domain="prose",
                extra={"omission": True},
            )

        elif family == "texture_swap":
            # Counterfactual pair: index 2p and 2p+1 share one canonical fact,
            # one question, one answer and one required-evidence identity.
            # Only the surface texture differs.
            pair = i // 2
            p_code = f"K{pair:02d}"
            p_val = 100 + pair
            pair_eid = f"{family}-p{pair}-e0"
            if i % 2 == 0:
                surface = f'JSON-ish: {{"{p_code}": {p_val}}}'
                texture = "json"
            else:
                surface = f"Prose texture: the symbol {p_code} maps to {p_val}."
                texture = "prose"
            yield _base(
                family,
                i,
                pieces=[_Seg(surface, pair_eid, gold=True)],
                query=f"Map {p_code}.",
                gold_answer=str(p_val),
                domain="prose",
                extra={
                    "texture": texture,
                    "facts_id": f"facts-{pair}",
                    "canonical_facts": {"code": p_code, "value": p_val},
                    # Char lengths differ between textures; this pair is NOT
                    # token-length matched and must not enter a matched-pair
                    # analysis as if it were.
                    "length_matched": False,
                    "length_match_basis": "not_matched",
                },
            )

        else:  # pragma: no cover — guarded by SYNTHETIC_FAMILIES
            return


# ===========================================================================
# Negative controls
# ===========================================================================
#
# These are NOT workload families. They exist to prove that the measurement
# instrument reports failure when evidence is genuinely lost. They are kept
# out of ``SYNTHETIC_FAMILIES`` so the workload set, the offline pilot and the
# billed runner are unchanged.
#
# Every case fails for a reason a human can state in one sentence, and it
# fails against the *unmodified* policy, profiler and operators: no threshold,
# feature or routing rule was touched to produce these numbers.

NEGATIVE_FAMILIES: tuple[str, ...] = (
    "neg_gold_quarantined",
    "neg_unrecoverable_gold",
    "neg_missing_provenance",
)

#: Why each control must fail, and what the instrument has to report.
NEGATIVE_FAMILY_INTENT: dict[str, str] = {
    "neg_gold_quarantined": (
        "Half of the required evidence sits on an ERROR line inside a malformed "
        "JSON document. UNTANGLE quarantines anomaly lines, so a morphology-aware "
        "arm necessarily removes that half from view. recall_vis must drop to 0.5; "
        "recall_rec must stay 1.0 because the unit is in R; the re-bite arm must "
        "fetch it back to 1.0 and pay T_rebite > 0."
    ),
    "neg_unrecoverable_gold": (
        "Same quarantine, but the surviving text mentions the same fields as the "
        "query, so bounded token-targeted recovery has no signal that anything is "
        "missing. recall_vis must stay below 1.0 for BOTH rule_pi and "
        "rule_pi_rebite, and T_rebite must be 0. Being in R is not the same as "
        "having been recovered."
    ),
    "neg_missing_provenance": (
        "One unit was pasted in with no recorded origin (empty source_uri). "
        "Provenance cannot be complete, so the provenance score must fall below "
        "1.0 for every arm, including raw_full."
    ),
}


def generate_negative_instances(family: str, n: int = 1) -> list[dict[str, object]]:
    """Generate negative-control packets. Returns [] for unknown ids."""
    if family not in NEGATIVE_FAMILIES:
        return []
    return list(_iter_negative(family, n))


def _iter_negative(family: str, n: int) -> Iterator[dict[str, object]]:
    for i in range(n):
        code = f"K{i:02d}"
        val = 100 + i
        eid = f"{family}-e{i}"
        eid2 = f"{family}-e{i}b"

        if family == "neg_gold_quarantined":
            # '{"audit": [' makes the whole document malformed JSON -> profiler
            # a=0.80 -> rule-Pi includes UNTANGLE. The ERROR line is classified
            # anomaly_candidate and is quarantined into R.
            # The query tokens (code / value / Kxx) appear ONLY in the omitted
            # line, so bounded re-bite can form a request for it.
            yield _base(
                family,
                i,
                pieces=[
                    _Seg('{"audit": ['),
                    "\n",
                    _Seg(f"INFO service=alpha region=lab-only slot={i}", eid, gold=True),
                    "\n",
                    _Seg(f"ERROR service=alpha code={code} value={val}", eid2, gold=True),
                    "\n",
                    _Seg("INFO trailing heartbeat ok=1"),
                ],
                query=f"What is the value for code {code}?",
                gold_answer=str(val),
                domain="observability_logs",
                extra={"negative_control": True},
            )

        elif family == "neg_unrecoverable_gold":
            # Same quarantine mechanism, but the surviving INFO line repeats
            # every distinctive query token (status / code / Kxx), so
            # insufficient_r_targets finds nothing to fetch.
            yield _base(
                family,
                i,
                pieces=[
                    _Seg('{"audit": ['),
                    "\n",
                    _Seg(f"INFO code={code} status lookup requested", eid, gold=True),
                    "\n",
                    _Seg(f"ERROR code={code} status={val}", eid2, gold=True),
                    "\n",
                    _Seg("INFO trailing heartbeat ok=1"),
                ],
                query=f"What is the status for code {code}?",
                gold_answer=str(val),
                domain="observability_logs",
                extra={"negative_control": True},
            )

        elif family == "neg_missing_provenance":
            # Plain prose: no anomaly marker, not JSON-ish, so no operator
            # removes anything. The only defect is that one unit has no
            # recorded origin.
            yield _base(
                family,
                i,
                pieces=[
                    _Seg(f"Section A. The codeword {code} equals {val}.", eid, gold=True),
                    " ",
                    _Seg(
                        "Section B was pasted from an unrecorded source.",
                        source_uri="",
                    ),
                ],
                query=f"What is {code}?",
                gold_answer=str(val),
                domain="prose",
                extra={"negative_control": True},
            )

        else:  # pragma: no cover — guarded by NEGATIVE_FAMILIES
            return
