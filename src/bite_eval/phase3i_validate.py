"""Phase 3I composite provenance validation (I1).

Fresh p3i development fixtures. Does not rewrite Phase 3H. Does not open p3f
evaluation. Does not connect routing.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bite_bench.phase3i import (
    GENERATION,
    KIND_COMPOSITE,
    LOCKED_CANDIDATE,
    LOCKED_T_HIGH,
    LOCKED_T_LOW,
    MAP_VERDICTS,
    PROTOCOL_FROZEN,
    REVISION,
    SPAN_ENVELOPE,
    SPAN_SOURCE_EXACT,
    SPLIT,
    VERDICT_BLOCKED,
    VERDICT_PARTIAL,
    VERDICT_VALIDATED,
    freeze_manifest,
    planned_cases,
)
from bite_ingestion.operators import apply_operator
from bite_ingestion.operators.base import packet_digest
from bite_ingestion.packet_contract import (
    PacketContractError,
    conservation_untraced,
    make_unit,
    provenance_completeness,
    provenance_kind,
    root_ids_of,
    validate_unit,
    validate_units,
    visible_evidence_from_units,
)

SCHEMA_ID = "bite-phase3i-composite-provenance/v0.1"
PROTOCOL_COMMIT_SHA = "e6bc818ec37c2b31f33a800b4e724b10acbfb887"
_REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = _REPO / "artifacts" / "phase3i"
RESULT_PATH = ARTIFACT_DIR / "composite-provenance.json"
RESULT_MD_PATH = ARTIFACT_DIR / "composite-provenance.md"
PHASE3H_PATH = _REPO / "artifacts" / "phase3h" / "operator-map-experiment.json"


def _layout(
    rows: Sequence[tuple[str, str, str]],
    *,
    renderer: str = "p3i",
) -> tuple[list[dict[str, Any]], str | None]:
    uris = {uri for _uid, _text, uri in rows}
    units: list[dict[str, Any]] = []
    if len(uris) == 1:
        uri = next(iter(uris))
        start = 0
        for uid, text, _uri in rows:
            end = start + len(text)
            units.append(
                make_unit(
                    unit_id=uid,
                    text=text,
                    start=start,
                    end=end,
                    source_uri=uri,
                    renderer_id=renderer,
                )
            )
            start = end + 1
        return units, "\n".join(text for _uid, text, _uri in rows)
    for uid, text, uri in rows:
        units.append(
            make_unit(
                unit_id=uid,
                text=text,
                start=0,
                end=len(text),
                source_uri=uri,
                renderer_id=renderer,
            )
        )
    return units, None


def _packet(
    case_id: str,
    units: Sequence[Mapping[str, Any]],
    document: str | None,
) -> dict[str, Any]:
    copied = [dict(u) for u in units]
    validate_units(copied, document=document)
    return {
        "packet_id": case_id,
        "document": document or "",
        "units": copied,
        "visible_evidence": visible_evidence_from_units(copied),
        "source_uri": copied[0]["source_uri"] if copied else f"bitebench://{case_id}",
    }


def well_formed_fixture(case_id: str) -> dict[str, Any]:
    uri = f"bitebench://{case_id}"
    other = f"bitebench://{case_id}/other"
    gold: list[str]
    rows: list[tuple[str, str, str]]
    context: dict[str, Any] | None = None
    if case_id == "p3i-same-uri-2way":
        gold = [f"{case_id}-a", f"{case_id}-c"]
        rows = [
            (gold[0], "id=tok_p3i_2way left", uri),
            (f"{case_id}-b", "padk=padv", uri),
            (gold[1], "id=tok_p3i_2way right", uri),
        ]
    elif case_id == "p3i-three-way":
        gold = [f"{case_id}-a", f"{case_id}-c", f"{case_id}-e"]
        rows = [
            (gold[0], "id=tok_p3i_3way one", uri),
            (f"{case_id}-b", "padk=padv_b", uri),
            (gold[1], "id=tok_p3i_3way two", uri),
            (f"{case_id}-d", "padk=padv_d", uri),
            (gold[2], "id=tok_p3i_3way three", uri),
        ]
    elif case_id == "p3i-mixed-uri":
        gold = [f"{case_id}-a", f"{case_id}-b"]
        rows = [
            (gold[0], "id=tok_p3i_mix left", uri),
            (gold[1], "id=tok_p3i_mix right", other),
        ]
    elif case_id == "p3i-passthrough":
        gold = [f"{case_id}-a", f"{case_id}-b"]
        rows = [
            (gold[0], "alpha=one", uri),
            (gold[1], "bravo=two", uri),
        ]
    elif case_id == "p3i-dep-edge":
        gold = [f"{case_id}-a", f"{case_id}-c"]
        rows = [
            (gold[0], "origin=hop_p3i_dep", uri),
            (f"{case_id}-b", "padk=padv", uri),
            (gold[1], "bin_hop=ans_p3i_dep", uri),
        ]
        context = {"dependency_edges": [(gold[0], gold[1])]}
    elif case_id == "p3i-explicit-key":
        gold = [f"{case_id}-a", f"{case_id}-c"]
        rows = [
            (gold[0], "key=zz_p3i left", uri),
            (f"{case_id}-b", "padk=padv", uri),
            (gold[1], "key=zz_p3i right", uri),
        ]
    else:
        raise ValueError(case_id)
    units, document = _layout(rows)
    return {
        "case_id": case_id,
        "split": SPLIT,
        "generation": GENERATION,
        "gold_unit_ids": gold,
        "context": context,
        "packet": _packet(case_id, units, document),
        "input_ids": [str(u["unit_id"]) for u in units],
    }


def malformed_unit(case_id: str) -> dict[str, Any]:
    source = make_unit(
        unit_id=f"{case_id}-a",
        text="id=tok left",
        start=0,
        end=10,
        source_uri=f"bitebench://{case_id}",
        renderer_id="p3i",
    )
    other = make_unit(
        unit_id=f"{case_id}-b",
        text="id=tok right",
        start=20,
        end=32,
        source_uri=f"bitebench://{case_id}",
        renderer_id="p3i",
    )
    if case_id == "p3i-malformed-joined-from-only":
        return {
            "unit_id": f"{case_id}-join",
            "text": f"{source['text']}\n{other['text']}",
            "span": source["span"],
            "source_uri": source["source_uri"],
            "joined_from": [source["unit_id"], other["unit_id"]],
            "parent_unit_id": source["unit_id"],
        }
    return {
        "unit_id": f"{case_id}-join",
        "text": f"{source['text']}\n{other['text']}",
        "span": dict(source["span"]),
        "source_uri": source["source_uri"],
        "joined_from": [source["unit_id"], other["unit_id"]],
        "provenance": {
            "kind": KIND_COMPOSITE,
            "sources": [
                {
                    "unit_id": source["unit_id"],
                    "source_uri": source["source_uri"],
                    "byte_or_token_span": source["provenance"]["byte_or_token_span"],
                    "renderer_id": "p3i",
                },
                {
                    "unit_id": other["unit_id"],
                    "source_uri": other["source_uri"],
                    "byte_or_token_span": other["provenance"]["byte_or_token_span"],
                    "renderer_id": "p3i",
                },
            ],
        },
    }


def _join_matches(after: Mapping[str, Any]) -> bool:
    plans = list((after.get("integrate") or {}).get("join_plan") or [])
    units = [u for u in after.get("units") or [] if isinstance(u, Mapping)]
    for plan in plans:
        members = {str(x) for x in plan.get("unit_ids") or []}
        found = [u for u in units if set(u.get("joined_from") or []) == members]
        if len(found) != 1:
            return False
        unit = found[0]
        if provenance_kind(unit) != KIND_COMPOSITE:
            return False
        sources = {
            str(row.get("unit_id"))
            for row in (unit.get("provenance") or {}).get("sources") or []
            if isinstance(row, Mapping)
        }
        if sources != members:
            return False
        span = unit.get("span")
        if not isinstance(span, Mapping) or span.get("kind") != SPAN_ENVELOPE:
            return False
        if span.get("contiguous") is not False:
            return False
        if span.get("kind") == SPAN_SOURCE_EXACT:
            return False
    return True


def score_well_formed(spec: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    gold = {str(x) for x in spec["gold_unit_ids"]}
    input_ids = [str(x) for x in spec["input_ids"]]
    visible = [dict(u) for u in after.get("units") or [] if isinstance(u, Mapping)]
    roots = root_ids_of([str(u["unit_id"]) for u in visible], visible)
    untraced = conservation_untraced(
        input_ids,
        visible_units=visible,
        r_entries=list((after.get("R") or {}).get("entries") or []),
        loss_ledger=list(after.get("irreversible_loss_ledger") or []),
    )
    recall = (len(gold & roots) / len(gold)) if gold else 1.0
    completeness = provenance_completeness(visible)
    expect_join = bool(next(c for c in planned_cases() if c["case_id"] == spec["case_id"]).get("expect_join"))
    plans = list((after.get("integrate") or {}).get("join_plan") or [])
    joined_ids: set[str] = set()
    for plan in plans:
        joined_ids.update(str(x) for x in plan.get("unit_ids") or [])
    return {
        "case_id": spec["case_id"],
        "generation": GENERATION,
        "split": SPLIT,
        "expect_join": expect_join,
        "joined": bool(plans),
        "provenance_completeness": completeness,
        "lineage_recall": recall,
        "conservation_untraced": untraced,
        "silent_loss": len(untraced),
        "join_plan_matches_sources": _join_matches(after),
        "op_status": after.get("op_status"),
        "ok": (
            completeness == 1.0
            and recall == 1.0
            and untraced == []
            and gold <= roots
            and (bool(plans) == expect_join)
            and _join_matches(after)
            and after.get("op_status") == "ok"
        ),
    }


def _premise_errors() -> list[str]:
    errs: list[str] = []
    freeze = freeze_manifest()
    if freeze.get("verdict") != PROTOCOL_FROZEN:
        errs.append("I0 freeze drifted")
    if freeze.get("revision") != REVISION:
        errs.append("I0 revision drifted")
    if not PHASE3H_PATH.is_file():
        errs.append("Phase 3H artifact missing")
        return errs
    phase3h = json.loads(PHASE3H_PATH.read_text(encoding="utf-8"))
    if phase3h.get("verdict") != "PHASE3H_CONDITIONAL_MAP_REQUIRED":
        errs.append("Phase 3H verdict rewritten")
    if phase3h.get("rule_policy_implemented") is not False:
        errs.append("Phase 3H started implementing routing")
    return errs


def run_validation() -> dict[str, Any]:
    blocked = _premise_errors()
    rows: list[dict[str, Any]] = []
    malformed_rows: list[dict[str, Any]] = []
    for spec in planned_cases():
        case_id = str(spec["case_id"])
        if spec.get("fail_closed"):
            unit = malformed_unit(case_id)
            raised = False
            try:
                validate_unit(unit)
            except PacketContractError:
                raised = True
            malformed_rows.append(
                {
                    "case_id": case_id,
                    "defect": spec.get("defect"),
                    "fail_closed": raised,
                    "ok": raised,
                }
            )
            continue
        fixture = well_formed_fixture(case_id)
        packet = fixture["packet"]
        after = dict(apply_operator("INTEGRATE", packet, fixture["context"]))
        again = dict(apply_operator("INTEGRATE", packet, fixture["context"]))
        row = score_well_formed(fixture, after)
        row["deterministic"] = packet_digest(after) == packet_digest(again)
        row["ok"] = bool(row["ok"] and row["deterministic"])
        raw_units = after.get("units")
        units_seq = raw_units if isinstance(raw_units, list) else []
        validate_units(
            [dict(u) for u in units_seq if isinstance(u, Mapping)],
            document=None,
        )
        rows.append(row)

    well_ok = bool(rows) and all(r["ok"] for r in rows)
    mal_ok = bool(malformed_rows) and all(r["ok"] for r in malformed_rows)
    if blocked:
        verdict = VERDICT_BLOCKED
    elif well_ok and mal_ok:
        verdict = VERDICT_VALIDATED
    elif any(r["ok"] for r in rows):
        verdict = VERDICT_PARTIAL
    else:
        verdict = VERDICT_BLOCKED
    if verdict not in MAP_VERDICTS:
        verdict = VERDICT_BLOCKED
        blocked.append("verdict not in frozen set")
    return {
        "schema": SCHEMA_ID,
        "revision": "phase3i-composite-provenance-v0.1",
        "protocol_revision": REVISION,
        "protocol_commit_sha": PROTOCOL_COMMIT_SHA,
        "verdict": verdict,
        "blocked_reasons": blocked,
        "paid_api": False,
        "offline": True,
        "synthetic": True,
        "research_conclusion": False,
        "p3f_evaluation_holdout_used": False,
        "phase3h_verdict_unchanged": "PHASE3H_CONDITIONAL_MAP_REQUIRED",
        "locked_candidate": LOCKED_CANDIDATE,
        "locked_thresholds": {"T_low": LOCKED_T_LOW, "T_high": LOCKED_T_HIGH},
        "v1_sensor_changed": False,
        "rule_policy_changed": False,
        "rule_policy_implemented": False,
        "routing_connected": False,
        "n_well_formed": len(rows),
        "n_malformed": len(malformed_rows),
        "rows": rows,
        "malformed": malformed_rows,
    }


def validate_phase3i_result(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("protocol_commit_sha") != PROTOCOL_COMMIT_SHA:
        errs.append("protocol commit SHA mismatch")
    if doc.get("verdict") not in MAP_VERDICTS:
        errs.append("verdict not in frozen set")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation opened")
    if doc.get("phase3h_verdict_unchanged") != "PHASE3H_CONDITIONAL_MAP_REQUIRED":
        errs.append("Phase 3H verdict rewritten")
    if doc.get("rule_policy_implemented") is not False:
        errs.append("routing implemented")
    if doc.get("locked_candidate") != LOCKED_CANDIDATE:
        errs.append("candidate A changed")
    blob = json.dumps(doc, sort_keys=True)
    if "p3f-" in blob:
        errs.append("p3f identifier leaked")
    if '"replica": 2' in blob or '"replica": 3' in blob:
        errs.append("evaluation replica leaked")
    for row in doc.get("rows") or []:
        if not str(row.get("case_id", "")).startswith("p3i-"):
            errs.append(f"non-p3i case {row.get('case_id')}")
    return errs


def render_md(doc: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 3I composite provenance",
        "",
        f"verdict: `{doc.get('verdict')}`",
        f"protocol SHA: `{doc.get('protocol_commit_sha')}`",
        "Phase 3H verdict unchanged: `PHASE3H_CONDITIONAL_MAP_REQUIRED`",
        "routing implemented: `false`",
        "",
        "| case | ok | completeness | lineage recall | join |",
        "|---|---|---|---|---|",
    ]
    for row in doc.get("rows") or []:
        lines.append(
            f"| {row.get('case_id')} | {row.get('ok')} | "
            f"{row.get('provenance_completeness')} | {row.get('lineage_recall')} | "
            f"{row.get('joined')} |"
        )
    lines.extend(["", "malformed fail-closed:", ""])
    for row in doc.get("malformed") or []:
        lines.append(f"- `{row.get('case_id')}` fail_closed={row.get('fail_closed')}")
    lines.extend(["", "BITE wins / Go ではない。", ""])
    return "\n".join(lines)


def write_artifacts(doc: Mapping[str, Any] | None = None) -> tuple[Path, Path]:
    if doc is None:
        doc = run_validation()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    RESULT_MD_PATH.write_text(render_md(doc), encoding="utf-8")
    return RESULT_PATH, RESULT_MD_PATH


if __name__ == "__main__":
    write_artifacts()
