"""Synthetic workload families for BITE-14 offline pilot (bite-04 §3.3).

Generates N_pilot instances per family procedurally. No network, no paid API,
no Gemini ingest. Content is authored synthetic only.
"""

from __future__ import annotations

from collections.abc import Iterator

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


def _base(
    family: str,
    idx: int,
    *,
    document: str,
    query: str,
    gold_answer: str,
    gold_evidence_ids: list[str],
    visible_evidence: list[str],
    recoverable_evidence_ids: list[str] | None = None,
    domain: str = "synthetic",
    provenance_complete_rate: float = 1.0,
    extra: dict | None = None,
) -> dict[str, object]:
    packet: dict[str, object] = {
        "instance_id": f"{family}-{idx:03d}",
        "family": family,
        "domain": domain,
        "document": document,
        "query": query,
        "gold_answer": gold_answer,
        "gold_evidence_ids": gold_evidence_ids,
        "visible_evidence": visible_evidence,
        "recoverable_evidence_ids": recoverable_evidence_ids
        if recoverable_evidence_ids is not None
        else list(gold_evidence_ids),
        "provenance_complete_rate": provenance_complete_rate,
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
            doc = (
                f"Section A. The codeword {code} equals {val}. "
                f"Section B filler about weather and unrelated notes."
            )
            yield _base(
                family,
                i,
                document=doc,
                query=f"What is {code}?",
                gold_answer=str(val),
                gold_evidence_ids=[eid],
                visible_evidence=[eid],
                domain="prose",
            )

        elif family == "repeated_records":
            rows = "\n".join(
                f"rec={j},key=item,value=widget{j % 3}" for j in range(8)
            )
            rows += f"\nrec=rare,key=codeword,value={code}:{val}"
            yield _base(
                family,
                i,
                document=f"schema=kv\n{rows}\n",
                query="What is the rare codeword value?",
                gold_answer=f"{code}:{val}",
                gold_evidence_ids=[eid],
                visible_evidence=[eid],
                domain="tabular_nested_machine_data",
            )

        elif family == "sparse_anomaly":
            noise = "\n".join(f"OK heartbeat={j}" for j in range(12))
            doc = f"{noise}\nALERT anomaly_id={code} severity={val}\n{noise}"
            yield _base(
                family,
                i,
                document=doc,
                query="What is the anomaly_id?",
                gold_answer=code,
                gold_evidence_ids=[eid],
                visible_evidence=[eid],
                domain="observability_logs",
            )

        elif family == "dependency_chain":
            doc = (
                f"unit_u0 depends_on=u1\n"
                f"unit_u1 depends_on=u2\n"
                f"unit_u2 fact={code}={val}\n"
            )
            yield _base(
                family,
                i,
                document=doc,
                query="Resolve fact along dependency chain.",
                gold_answer=str(val),
                gold_evidence_ids=[eid, eid2],
                visible_evidence=[eid, eid2],
                domain="mixed_agent_tool_outputs",
            )

        elif family == "malformed_mixed":
            doc = (
                "{broken_json: true, trailing\n"
                f"NOTE: salvage codeword {code} is {val}.\n"
                "more}}garbage"
            )
            yield _base(
                family,
                i,
                document=doc,
                query=f"Salvage value of {code}.",
                gold_answer=str(val),
                gold_evidence_ids=[eid],
                visible_evidence=[eid],
                domain="mixed_agent_tool_outputs",
            )

        elif family == "dense_cross_reference":
            doc = (
                f"[1] see [2]. [2] defines {code}. [3] {code}={val}. "
                f"[4] cites [3]."
            )
            yield _base(
                family,
                i,
                document=doc,
                query=f"Value of {code}?",
                gold_answer=str(val),
                gold_evidence_ids=[eid, eid2],
                visible_evidence=[eid, eid2],
                domain="prose",
            )

        elif family == "adversarial_omission":
            # Half of gold Ev* kept visible (meets rho_visible=0.50); half omitted
            # but recoverable via R (tests H4 / Recover within J).
            filler = " ".join(f"noise{j}" for j in range(20))
            doc = (
                f"VISIBLE: hint_token={code}\n"
                f"{filler}\nHIDDEN: {code}={val}\n{filler}"
            )
            yield _base(
                family,
                i,
                document=doc,
                query=f"Recover {code}.",
                gold_answer=str(val),
                gold_evidence_ids=[eid, eid2],
                visible_evidence=[eid],  # 1/2 visible → recall_vis=0.50
                recoverable_evidence_ids=[eid, eid2],
                domain="prose",
                extra={"omission": True},
            )

        elif family == "texture_swap":
            # Same facts; alternate surface every other index.
            if i % 2 == 0:
                doc = f"JSON-ish: {{\"{code}\": {val}}}"
            else:
                doc = f"Prose texture: the symbol {code} maps to {val}."
            yield _base(
                family,
                i,
                document=doc,
                query=f"Map {code}.",
                gold_answer=str(val),
                gold_evidence_ids=[eid],
                visible_evidence=[eid],
                domain="prose",
                extra={"texture": "json" if i % 2 == 0 else "prose", "facts_id": f"facts-{i // 2}"},
            )

        else:  # pragma: no cover — guarded by SYNTHETIC_FAMILIES
            return
