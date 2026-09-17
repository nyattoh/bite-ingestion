"""Offline Phase-1 comparative matrix. No paid API. Not a research conclusion."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bite_eval.accounting.dc_validators import validate_ledger_totals
from bite_eval.accounting.estimate import LOCAL_ESTIMATE_LABEL, estimate_tokens_char4
from bite_eval.accounting.ledger import TokenLedger
from bite_eval.arm_runtime import (
    FEATURE_KEYS,
    PHASE1_ARMS,
    attach_morphology,
    payload_hash,
    payload_text_from_packet,
)
from bite_eval.interface import extract_text
from bite_ingestion.packet_contract import provenance_completeness, root_ids_of

SCHEMA_ID = "bite-phase1-offline-matrix/v0.1"

OFFLINE_WRAPPER = (
    "Document:\n{payload}\n\nQuestion:\n{query}\n\n"
    "Answer with only the final value/string, no explanation."
)
OUTPUT_CONSTRAINT = "Answer with only the final value/string, no explanation."

ROW_KEYS: tuple[str, ...] = (
    "case_id",
    "case_kind",
    "facts_id",
    "texture",
    "method",
    "payload_sha256",
    "operator_sequence",
    "morphology",
    "visible_evidence_ids",
    "recoverable_evidence_ids",
    "loss_ledger",
    "status",
    "no_op",
    "failed",
    "T_profiler",
    "T_router",
    "T_operator",
    "T_target_in",
    "T_target_out",
    "T_rebite",
    "T_total",
)

FAIRNESS = {
    "query": "packet.query — identical for all four arms of a case",
    "target_wrapper": OFFLINE_WRAPPER,
    "output_constraint": OUTPUT_CONSTRAINT,
    "tokenizer": LOCAL_ESTIMATE_LABEL,
    "timeout_s": None,
    "retry_policy": "n/a_offline_no_network",
    "evaluation_row_set": "inner join on case_id; a case is kept only if all 4 arms are present",
    "length_pi_vs_rule_pi": "same packet, wrapper, estimator; only policy input and routing differ",
    "rule_pi_rebite_extra": (
        "bounded recovery only (J=3, B_r=512 TBD). Extra visible text is billed as "
        "T_rebite plus a larger T_target_in on the post-recovery payload. "
        "Offline has no second model call."
    ),
}


#: What each negative control must produce, stated from the design before the
#: numbers were measured. ``rebite`` is compared as ">0" or "==0".
#:
#: These are assertions about the *instrument*, not about BITE: they say that a
#: lost unit shows up as a lost unit, that R and an actual recovery are
#: distinguishable, and that missing provenance is visible.
NEGATIVE_EXPECTATIONS: dict[tuple[str, str], dict[str, Any]] = {
    # Half the gold evidence is on an ERROR line -> UNTANGLE quarantines it.
    ("neg_gold_quarantined", "raw_full"): {"recall_vis": 1.0, "recall_rec": 1.0, "rebite": "==0"},
    ("neg_gold_quarantined", "length_pi"): {"recall_vis": 1.0, "recall_rec": 1.0, "rebite": "==0"},
    ("neg_gold_quarantined", "rule_pi"): {"recall_vis": 0.5, "recall_rec": 1.0, "rebite": "==0"},
    ("neg_gold_quarantined", "rule_pi_rebite"): {
        "recall_vis": 1.0,
        "recall_rec": 1.0,
        "rebite": ">0",
    },
    # Same quarantine, but recovery cannot form a request -> stays lost.
    ("neg_unrecoverable_gold", "raw_full"): {"recall_vis": 1.0, "recall_rec": 1.0, "rebite": "==0"},
    ("neg_unrecoverable_gold", "length_pi"): {
        "recall_vis": 1.0,
        "recall_rec": 1.0,
        "rebite": "==0",
    },
    ("neg_unrecoverable_gold", "rule_pi"): {"recall_vis": 0.5, "recall_rec": 1.0, "rebite": "==0"},
    ("neg_unrecoverable_gold", "rule_pi_rebite"): {
        "recall_vis": 0.5,
        "recall_rec": 1.0,
        "rebite": "==0",
    },
    # One unit has no recorded origin -> provenance below 1.0 for every arm.
    ("neg_missing_provenance", "raw_full"): {"provenance": 0.5},
    ("neg_missing_provenance", "length_pi"): {"provenance": 0.5},
    ("neg_missing_provenance", "rule_pi"): {"provenance": 0.5},
    ("neg_missing_provenance", "rule_pi_rebite"): {"provenance": 0.5},
}


def negative_control_report(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Compare negative-control rows against their declared expectations.

    A violation means the measurement instrument failed to report a failure it
    was supposed to report — that is a blocker, not a metric movement.
    """
    observed: dict[str, dict[str, Any]] = {}
    violations: list[str] = []
    checked = 0
    for row in rows:
        if str(row.get("case_kind")) != "negative_control":
            continue
        family = str(row.get("case_id", "")).rsplit("-", 1)[0]
        method = str(row.get("method"))
        key = (family, method)
        observed.setdefault(family, {})[method] = {
            "recall_vis": row.get("evidence_recall_visible"),
            "recall_rec": row.get("evidence_recall_recoverable"),
            "provenance": row.get("provenance"),
            "T_rebite": row.get("T_rebite"),
            "status": row.get("status"),
        }
        expect = NEGATIVE_EXPECTATIONS.get(key)
        if expect is None:
            continue
        checked += 1
        for field in ("recall_vis", "recall_rec", "provenance"):
            if field not in expect:
                continue
            actual = row.get(
                {
                    "recall_vis": "evidence_recall_visible",
                    "recall_rec": "evidence_recall_recoverable",
                    "provenance": "provenance",
                }[field]
            )
            if not isinstance(actual, (int, float)) or abs(float(actual) - expect[field]) > 1e-9:
                violations.append(f"{family}/{method}: {field} expected {expect[field]}, got {actual}")
        if "rebite" in expect:
            tok = int(row.get("T_rebite") or 0)
            if expect["rebite"] == ">0" and tok <= 0:
                violations.append(f"{family}/{method}: expected T_rebite > 0, got {tok}")
            if expect["rebite"] == "==0" and tok != 0:
                violations.append(f"{family}/{method}: expected T_rebite == 0, got {tok}")
    return {
        "n_checked": checked,
        "violations": violations,
        "observed": observed,
        "note": (
            "negative controls prove the instrument reports failure; they are not "
            "workload results and must never be averaged into workload numbers"
        ),
    }


def metrics_from_transformed(
    *,
    gold_ids: Sequence[str],
    visible_ids: Sequence[str],
    units: Sequence[Mapping[str, Any]],
    r_entries: Sequence[Mapping[str, Any]],
) -> dict[str, float]:
    """Recall / provenance from the transformed graph. Never packet self-scores."""
    gold = {str(g) for g in gold_ids if g}
    vis = [str(v) for v in visible_ids if v]
    rec = [
        str(e.get("unit_id"))
        for e in r_entries
        if isinstance(e, Mapping) and e.get("unit_id") and e.get("recoverable", True)
    ]
    lineage: list[Mapping[str, Any]] = [u for u in units if isinstance(u, Mapping)]
    for e in r_entries:
        if not isinstance(e, Mapping):
            continue
        raw_extra = e.get("extra")
        extra: Mapping[str, Any] = raw_extra if isinstance(raw_extra, Mapping) else {}
        lineage.append(
            {
                "unit_id": e.get("unit_id"),
                "parent_unit_id": extra.get("parent_unit_id") or e.get("parent_unit_id"),
            }
        )
    vis_roots = set(vis) | root_ids_of(vis, lineage)
    rec_roots = set(rec) | root_ids_of(rec, lineage)
    if gold:
        recall_vis = len(gold & vis_roots) / len(gold)
        recall_rec = len(gold & (vis_roots | rec_roots)) / len(gold)
    else:
        recall_vis = 1.0
        recall_rec = 1.0
    vis_set = set(vis)
    vis_units = [u for u in units if isinstance(u, Mapping) and str(u.get("unit_id")) in vis_set]
    if vis_units:
        prov = provenance_completeness(vis_units)
    elif vis:
        prov = 0.0
    else:
        prov = 1.0
    return {
        "evidence_recall_visible": recall_vis,
        "evidence_recall_recoverable": recall_rec,
        "provenance": prov,
    }


def _r_entries(r_obj: object) -> list[dict[str, Any]]:
    if not isinstance(r_obj, Mapping):
        return []
    raw = r_obj.get("entries") or []
    if not isinstance(raw, list):
        return []
    return [dict(e) for e in raw if isinstance(e, Mapping)]


def _arm_ledger(
    *,
    method: str,
    case_id: str,
    profiler_cpu_ms: float,
    accounting: Mapping[str, object] | None,
    payload: str,
) -> TokenLedger:
    ledger = TokenLedger()
    ledger.record(
        {
            "category": "profiler",
            "kind": "deterministic",
            "call_id": f"{method}:{case_id}:profiler",
            "tokens_in": 0,
            "tokens_out": 0,
            "cpu_ms": profiler_cpu_ms,
            "note": "DC-2 deterministic profiler",
        }
    )
    ledger.record(
        {
            "category": "router",
            "kind": "deterministic",
            "call_id": f"{method}:{case_id}:router",
            "tokens_in": 0,
            "tokens_out": 0,
            "note": "DC-2 deterministic policy",
        }
    )
    if accounting:
        ledger.merge_baseline_accounting(accounting)
    ledger.record(
        {
            "category": "target",
            "kind": "local_estimate",
            "call_id": f"{method}:{case_id}:target",
            "tokens_in": estimate_tokens_char4(payload),
            "tokens_out": 0,
            "estimate_source": LOCAL_ESTIMATE_LABEL,
            "note": "offline T_target_in from final payload (post-rebite if any)",
        }
    )
    return ledger


def _row_status(arm: str, baseline_status: str, is_no_op: bool) -> str:
    if baseline_status == "failed":
        return "failed"
    if arm == "raw_full":
        return "pass_through"
    if is_no_op:
        return "no_op"
    return "transformed"


def summarize_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Counts cover every row; means and arm differentiation cover workload only.

    Negative controls are deliberately kept out of the workload means: they are
    built to fail, so averaging them in would corrupt the workload numbers.
    They are not hidden — every control row is reported with its actual values
    by :func:`negative_control_report`.
    """
    all_rows = list(rows)
    workload = [r for r in all_rows if str(r.get("case_kind", "workload")) != "negative_control"]
    controls = [r for r in all_rows if str(r.get("case_kind", "workload")) == "negative_control"]
    n_total = len(all_rows)
    n_failed = sum(1 for r in rows if r.get("failed") or r.get("status") == "failed")
    n_no_op = sum(1 for r in rows if r.get("no_op") or r.get("status") == "no_op")
    n_excluded = sum(
        1
        for r in rows
        if r.get("status") in {"timeout", "error", "missing_pair", "rate_limit", "unknown"}
    )
    n_measured = n_total - n_excluded
    by_case: dict[str, dict[str, Mapping[str, Any]]] = {}
    for row in all_rows:
        by_case.setdefault(str(row.get("case_id")), {})[str(row.get("method"))] = row
    complete_cases = [cid for cid, arms in by_case.items() if set(PHASE1_ARMS) <= set(arms)]
    paired_rows = [r for r in all_rows if str(r.get("case_id")) in set(complete_cases)]

    # Arm differentiation and means describe the workload, never the controls.
    workload_cases = [
        cid
        for cid in complete_cases
        if str(next(iter(by_case[cid].values())).get("case_kind", "workload")) != "negative_control"
    ]

    def _mean(vals: list[float]) -> float | None:
        return sum(vals) / len(vals) if vals else None

    measured = [
        r
        for r in paired_rows
        if r.get("status") not in {"timeout", "error", "missing_pair"}
        and str(r.get("case_kind", "workload")) != "negative_control"
    ]

    # Failed rows stay in the denominator of rates; means skip only missing numbers.
    def _nums(key: str) -> list[float]:
        out: list[float] = []
        n_missing = 0
        for r in measured:
            v = r.get(key)
            if isinstance(v, (int, float)):
                out.append(float(v))
            else:
                n_missing += 1
        return out

    n_missing_payload = sum(
        1 for r in measured if not isinstance(r.get("payload_chars"), (int, float))
    )
    rule_seqs: set[tuple[str, ...]] = set()
    length_vs_rule: set[str] = set()
    raw_vs_cand_diff = 0
    raw_vs_cand_same = 0
    for cid in workload_cases:
        arms = by_case[cid]
        raw = arms.get("raw_full")
        for m in ("length_pi", "rule_pi", "rule_pi_rebite"):
            other = arms.get(m)
            if raw is None or other is None:
                continue
            if raw.get("payload_sha256") == other.get("payload_sha256"):
                raw_vs_cand_same += 1
            else:
                raw_vs_cand_diff += 1
        lp, rp = arms.get("length_pi"), arms.get("rule_pi")
        if lp and rp and lp.get("payload_sha256") != rp.get("payload_sha256"):
            length_vs_rule.add(str(lp.get("case_id")))
        if rp:
            seq = rp.get("operator_sequence") or []
            rule_seqs.add(tuple(str(x) for x in seq))

    recall_vis = _nums("evidence_recall_visible")
    recall_rec = _nums("evidence_recall_recoverable")
    prov = _nums("provenance")
    payload_chars = _nums("payload_chars")
    t_total = _nums("T_total")
    return {
        "n_total": n_total,
        "n_measured": n_measured,
        "n_excluded": n_excluded,
        "n_failed": n_failed,
        "n_no_op": n_no_op,
        "n_pass_through": sum(1 for r in rows if r.get("status") == "pass_through"),
        "n_transformed": sum(1 for r in rows if r.get("status") == "transformed"),
        "n_complete_cases": len(complete_cases),
        "n_paired_rows": len(paired_rows),
        "n_workload_rows": len(workload),
        "n_negative_control_rows": len(controls),
        "n_workload_cases": len(workload_cases),
        "no_op_rate": n_no_op / n_total if n_total else 0.0,
        "failure_rate": n_failed / n_total if n_total else 0.0,
        "n_missing_payload_metric": n_missing_payload,
        "mean_payload_chars": _mean(payload_chars),
        "mean_T_total": _mean(t_total),
        "mean_evidence_recall_visible": _mean(recall_vis),
        "mean_evidence_recall_recoverable": _mean(recall_rec),
        "mean_provenance": _mean(prov),
        "raw_vs_candidate_diff_payload": raw_vs_cand_diff,
        "raw_vs_candidate_same_payload": raw_vs_cand_same,
        "length_vs_rule_diff_families": sorted(length_vs_rule),
        "rule_pi_distinct_sequences": len(rule_seqs),
        "rule_pi_sequences": [list(s) for s in sorted(rule_seqs)],
        "average_rule": (
            "counts and rates use n_total (failed rows stay in the denominator). "
            "means and arm differentiation use WORKLOAD rows only — negative "
            "controls are built to fail and would corrupt them; their actual "
            "values are reported in negative_control_report. "
            "means skip only missing numeric fields; n_missing_* is reported."
        ),
    }


def run_phase1_matrix(
    *,
    n_per_family: int = 1,
    artifact_path: str | Path | None = None,
    summary_path: str | Path | None = None,
) -> dict[str, Any]:
    from bite_eval.baselines import get_baseline
    from bite_eval.pilot.families import (
        NEGATIVE_FAMILIES,
        SYNTHETIC_FAMILIES,
        generate_family_instances,
        generate_negative_instances,
    )

    # Workload families first, then negative controls. Controls run through the
    # identical four arms and the identical wrapper — they are ordinary rows
    # tagged case_kind=negative_control, not a separate code path.
    plan: list[tuple[str, str, list[dict[str, object]]]] = [
        ("workload", f, generate_family_instances(f, n_per_family)) for f in SYNTHETIC_FAMILIES
    ]
    plan += [
        ("negative_control", f, generate_negative_instances(f, n_per_family))
        for f in NEGATIVE_FAMILIES
    ]

    rows: list[dict[str, Any]] = []
    for case_kind, family, packets in plan:
        for packet in packets:
            prepared, report = attach_morphology(packet)
            case_id = str(prepared.get("instance_id") or "")
            facts_id = str(prepared.get("facts_id") or case_id)
            texture = str(prepared.get("texture") or prepared.get("domain") or "unspecified")
            gold_ids = [str(g) for g in (prepared.get("gold_evidence_ids") or [])]
            original = extract_text(prepared)
            morph = {k: float((prepared.get("morphology") or {}).get(k, 0.0)) for k in FEATURE_KEYS}
            query = str(prepared.get("query") or "")
            for arm in PHASE1_ARMS:
                adapter = get_baseline(arm)
                ctx = {
                    "domain": prepared.get("domain"),
                    "query": query,
                    "wrapper": OFFLINE_WRAPPER,
                    "output_constraint": OUTPUT_CONSTRAINT,
                    "timeout_s": None,
                    "retry_policy": "n/a_offline_no_network",
                }
                out = dict(adapter.run(prepared, ctx))  # type: ignore[attr-defined]
                payload = str(out.get("payload_text") or out.get("visible_evidence") or "")
                if not isinstance(out.get("payload_text") or out.get("visible_evidence"), str):
                    payload = payload_text_from_packet(
                        {"visible_evidence": out.get("visible_evidence")}
                    )
                acc = out.get("accounting") if isinstance(out.get("accounting"), Mapping) else {}
                ledger = _arm_ledger(
                    method=arm,
                    case_id=case_id,
                    profiler_cpu_ms=float(report.cpu_ms),
                    accounting=acc if isinstance(acc, Mapping) else None,
                    payload=payload,
                )
                totals = dict(ledger.totals())
                dc = validate_ledger_totals(ledger.rows(), totals)
                vis_ids = [str(x) for x in (out.get("visible_unit_ids") or [])]
                r_entries = _r_entries(out.get("R"))
                rec_ids = [
                    str(e.get("unit_id"))
                    for e in r_entries
                    if e.get("unit_id") and e.get("recoverable", True)
                ]
                units = (
                    [u for u in (out.get("units") or []) if isinstance(u, Mapping)]
                    if isinstance(out.get("units"), list)
                    else []
                )
                metrics = metrics_from_transformed(
                    gold_ids=gold_ids,
                    visible_ids=vis_ids,
                    units=units,
                    r_entries=r_entries,
                )
                tstat = str(out.get("transformation_status") or "")
                is_no_op = (
                    bool(out.get("is_no_op"))
                    or tstat == "no_op"
                    or (arm != "raw_full" and payload == original and out.get("status") == "ok")
                )
                baseline_status = str(out.get("status") or "ok")
                status = _row_status(arm, baseline_status, is_no_op)
                seq = out.get("proposed_sequence")
                if not isinstance(seq, list):
                    trace = (
                        out.get("baseline_trace")
                        if isinstance(out.get("baseline_trace"), Mapping)
                        else {}
                    )
                    seq = list(trace.get("sequence") or []) if isinstance(trace, Mapping) else []
                call_ids = [str(r.get("call_id")) for r in ledger.rows() if r.get("call_id")]
                rows.append(
                    {
                        "case_id": case_id,
                        "case_kind": case_kind,
                        "family": family,
                        "facts_id": facts_id,
                        "texture": texture,
                        "method": arm,
                        "payload_sha256": str(out.get("payload_hash") or payload_hash(payload)),
                        "operator_sequence": seq,
                        "morphology": dict(morph),
                        "policy_used_morphology": arm in {"rule_pi", "rule_pi_rebite"},
                        "visible_evidence_ids": vis_ids,
                        "recoverable_evidence_ids": rec_ids,
                        "loss_ledger": list(out.get("irreversible_loss_ledger") or []),
                        "status": status,
                        "no_op": status == "no_op",
                        "failed": status == "failed",
                        "baseline_status": baseline_status,
                        "reason": out.get("reason"),
                        "payload_chars": len(payload),
                        "token_estimate": estimate_tokens_char4(payload),
                        "evidence_recall_visible": metrics["evidence_recall_visible"],
                        "evidence_recall_recoverable": metrics["evidence_recall_recoverable"],
                        "provenance": metrics["provenance"],
                        "T_profiler": totals.get("T_profiler"),
                        "T_router": totals.get("T_router"),
                        "T_operator": totals.get("T_operator"),
                        "T_target_in": totals.get("T_target_in"),
                        "T_target_out": totals.get("T_target_out"),
                        "T_rebite": totals.get("T_rebite"),
                        "T_total": totals.get("T_total"),
                        "query": query,
                        "ledger_call_ids": call_ids,
                        "dc_violations": dc,
                        "rebite_steps": (out.get("baseline_trace") or {}).get("rebite_steps")
                        if isinstance(out.get("baseline_trace"), Mapping)
                        else None,
                    }
                )

    summary = summarize_rows(rows)
    controls = negative_control_report(rows)
    doc: dict[str, Any] = {
        "schema": SCHEMA_ID,
        "offline": True,
        "paid_api": False,
        "synthetic": True,
        "research_conclusion": False,
        "purpose": "pipeline wiring check — not a scientific result",
        "arms": list(PHASE1_ARMS),
        "fairness": FAIRNESS,
        "n_rows": len(rows),
        "summary": summary,
        "negative_control_report": controls,
        "rows": rows,
    }
    if artifact_path is not None:
        path = Path(artifact_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
        )
        doc["artifact_path"] = str(path)
        md_path = Path(summary_path) if summary_path else path.with_name("arm_summary.md")
        md_path.write_text(render_summary_md(doc), encoding="utf-8")
        doc["summary_path"] = str(md_path)
    return doc


def render_summary_md(doc: Mapping[str, Any]) -> str:
    rows = list(doc.get("rows") or [])
    summary = dict(doc.get("summary") or {})
    raw_ctrl = doc.get("negative_control_report")
    ctrl: Mapping[str, Any] = raw_ctrl if isinstance(raw_ctrl, Mapping) else {}
    by_case: dict[str, dict[str, Mapping[str, Any]]] = {}
    for row in rows:
        if isinstance(row, Mapping):
            by_case.setdefault(str(row.get("case_id")), {})[str(row.get("method"))] = row
    lines = [
        "# Phase 1 offline arm matrix (wiring check)",
        "",
        "Not a research conclusion. Paid API: false.",
        "",
        (
            f"- n_total={summary.get('n_total')} n_measured={summary.get('n_measured')} "
            f"n_excluded={summary.get('n_excluded')} n_failed={summary.get('n_failed')} "
            f"n_no_op={summary.get('n_no_op')}"
        ),
        f"- no_op_rate={summary.get('no_op_rate')} failure_rate={summary.get('failure_rate')}",
        f"- rule_pi sequences: {summary.get('rule_pi_sequences')}",
        f"- length_pi ≠ rule_pi: {summary.get('length_vs_rule_diff_families')}",
        (
            f"- workload rows={summary.get('n_workload_rows')} "
            f"negative-control rows={summary.get('n_negative_control_rows')} "
            f"(means and arm differentiation above use WORKLOAD rows only)"
        ),
        "",
        "## Negative controls (instrument check, must report failure)",
        "",
        f"- checked={ctrl.get('n_checked')} violations={ctrl.get('violations') or 'none'}",
        "",
        "| family | method | recall_vis | recall_rec | provenance | T_rebite |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for fam in sorted(ctrl.get("observed") or {}):
        for method in PHASE1_ARMS:
            obs = (ctrl["observed"][fam] or {}).get(method)
            if not isinstance(obs, Mapping):
                continue
            lines.append(
                f"| {fam} | {method} | {obs.get('recall_vis')} | {obs.get('recall_rec')} | "
                f"{obs.get('provenance')} | {obs.get('T_rebite')} |"
            )
    lines += [
        "",
        "| case_id | method | status | sequence | payload_sha256 | T_rebite | T_total |",
        "|---|---|---|---|---|---:|---:|",
    ]
    for cid in sorted(by_case):
        for method in PHASE1_ARMS:
            row = by_case[cid].get(method)
            if not isinstance(row, Mapping):
                continue
            seq = ",".join(str(x) for x in (row.get("operator_sequence") or [])) or "—"
            sha = str(row.get("payload_sha256") or "")[:16]
            lines.append(
                f"| {cid} | {method} | {row.get('status')} | `{seq}` | `{sha}` | "
                f"{row.get('T_rebite')} | {row.get('T_total')} |"
            )
    lines.append("")
    return "\n".join(lines)


def validate_matrix_doc(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("paid_api") is not False:
        errs.append("paid_api must be false")
    if doc.get("schema") != SCHEMA_ID:
        errs.append(f"bad schema id: {doc.get('schema')!r}")
    rows = doc.get("rows")
    if not isinstance(rows, list):
        return errs + ["rows must be a list"]
    for i, row in enumerate(rows):
        if not isinstance(row, Mapping):
            errs.append(f"row {i} not an object")
            continue
        for k in ROW_KEYS:
            if k not in row:
                errs.append(f"row {i} missing {k}")
        buckets = [
            int(row.get(k) or 0)
            for k in (
                "T_profiler",
                "T_router",
                "T_operator",
                "T_target_in",
                "T_target_out",
                "T_rebite",
            )
        ]
        if "T_total" in row and int(row.get("T_total") or 0) != sum(buckets):
            errs.append(f"row {i} T_total != bucket sum")
        ids = list(row.get("ledger_call_ids") or [])
        if len(ids) != len(set(ids)):
            errs.append(f"row {i} duplicate call_id")
        rec = row.get("recoverable_evidence_ids") or []
        goldish = [x for x in rec if str(x).startswith("gold_")]
        if goldish:
            errs.append(f"row {i} recoverable ids look like gold labels: {goldish}")
    raw_ctrl = doc.get("negative_control_report")
    if isinstance(raw_ctrl, Mapping):
        if int(raw_ctrl.get("n_checked") or 0) <= 0:
            errs.append("negative_control_report checked 0 rows")
        for v in raw_ctrl.get("violations") or []:
            errs.append(f"negative control did not report the failure it must: {v}")
    else:
        errs.append("missing negative_control_report")

    raw_summary = doc.get("summary")
    summary: Mapping[str, Any] = raw_summary if isinstance(raw_summary, Mapping) else {}
    if int(summary.get("n_total") or -1) != len(rows):
        errs.append("summary.n_total != len(rows)")
    return errs


__all__ = [
    "FAIRNESS",
    "NEGATIVE_EXPECTATIONS",
    "OFFLINE_WRAPPER",
    "OUTPUT_CONSTRAINT",
    "ROW_KEYS",
    "SCHEMA_ID",
    "metrics_from_transformed",
    "negative_control_report",
    "render_summary_md",
    "run_phase1_matrix",
    "summarize_rows",
    "validate_matrix_doc",
]
