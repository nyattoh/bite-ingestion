"""Phase 2D frozen confirmatory offline evaluation.

Opens the Phase 2A evaluation split under Phase 2C v0.2 rules.
Does not change profiler, thresholds, routing, operators, or the freeze.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from bite_bench.phase2a import PHASE2A_REVISION, design_cells, generate_phase2a_bundle
from bite_bench.phase2c import (
    PHASE2C_REVISION,
    PHASE2D_ARMS,
    PHASE2D_VERDICTS,
    classify_dispersion_pair,
    confirmatory_pairs,
    decide_phase2d_verdict,
    freeze_manifest,
    validate_freeze_doc,
)
from bite_bench.token_match import (
    TOKEN_MATCH_MAX_ABS_DELTA,
    TOKEN_MATCH_MAX_RELATIVE_DELTA,
    relative_token_delta,
    token_length_match,
)
from bite_eval.interface import extract_budget
from bite_eval.phase1_matrix import OFFLINE_WRAPPER, arm_rows_for_packet
from bite_eval.phase1d_confirmatory import _annotate_vs_raw, run_negative_control_self_check
from bite_ingestion.packet_contract import provenance_completeness, visible_evidence_from_units

SCHEMA_ID = "bite-phase2d-confirmatory-offline/v0.1"
BASE_MAIN_SHA = "dce759efbb94ae941a86c3358b1b717da3224c14"
CASE_KIND = "canonical_evaluation"
PromptTokens = Callable[[str, str], int]


def _v02_path() -> Path:
    return Path(__file__).resolve().parents[2] / "benchmarks" / "spec" / (
        "phase2c-dispersion-freeze-v0.2.json"
    )


def verify_phase2c_v02() -> dict[str, Any]:
    path = _v02_path()
    mismatches: list[str] = []
    if not path.is_file():
        return {"ok": False, "mismatches": [f"missing {path}"], "revision": None}
    committed = json.loads(path.read_text(encoding="utf-8"))
    if committed != freeze_manifest():
        mismatches.append("committed v0.2 freeze does not match freeze_manifest()")
    mismatches.extend(validate_freeze_doc(committed))
    if committed.get("revision") != PHASE2C_REVISION:
        mismatches.append(f"freeze revision drifted: {committed.get('revision')}")
    return {
        "ok": not mismatches,
        "mismatches": mismatches,
        "revision": committed.get("revision"),
        "n_planned_pairs": committed.get("n_planned_pairs"),
    }


def surface_packet(bundle: Mapping[str, Any], family: str) -> dict[str, Any]:
    rec = bundle["surfaces"][family]
    canonical = bundle["canonical"]
    units = [dict(u) for u in rec["units"]]
    case_id = str(canonical["case_id"])
    return {
        "instance_id": f"{case_id}:{family}",
        "family": family,
        "texture": family,
        "facts_id": str(bundle["facts_id"]),
        "benchmark_split": "evaluation",
        "domain": "synthetic",
        "source_uri": f"bitebench://{case_id}/{family}",
        "document": rec["text"],
        "query": str(canonical["question"]),
        "gold_answer": str(canonical["answer"]),
        "units": units,
        "gold_evidence_ids": [str(x) for x in canonical["required_evidence_ids"]],
        "visible_evidence": visible_evidence_from_units(units),
        "recoverable_evidence_ids": [],
        "provenance_complete_rate": provenance_completeness(units),
        "synthetic": True,
        "paid_api": False,
    }


def _seq(row: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(str(x) for x in (row.get("operator_sequence") or []))


def _behavior(row: Mapping[str, Any]) -> tuple[tuple[str, ...], bool, str]:
    return (_seq(row), bool(row.get("no_op")), str(row.get("status")))


def _recovery_fired(row: Mapping[str, Any]) -> bool:
    return int(row.get("T_rebite") or 0) > 0 or int(row.get("rebite_count") or 0) > 0


def _arm(rows: Sequence[Mapping[str, Any]], method: str) -> Mapping[str, Any] | None:
    for row in rows:
        if row.get("method") == method:
            return row
    return None


def _frozen_contract_ok(bundle: Mapping[str, Any], pair: Mapping[str, Any]) -> bool:
    left = bundle["surfaces"][pair["left"]["family"]]
    right = bundle["surfaces"][pair["right"]["family"]]
    required = {str(x) for x in bundle["canonical"]["required_evidence_ids"]}
    left_gold = {str(u.get("fact_id")) for u in left["units"] if u.get("is_required_evidence")}
    right_gold = {str(u.get("fact_id")) for u in right["units"] if u.get("is_required_evidence")}
    return (
        bundle["benchmark_split"] == "evaluation"
        and int(pair["replica"]) in {2, 3}
        and left_gold == required
        and right_gold == required
        and str(bundle["identity_sha256"]) != ""
    )


def _breakdown(pairs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    out: dict[str, dict[str, Any]] = {}
    for key in ("scale", "dependency", "structure", "redundancy"):
        buckets: dict[str, dict[str, int]] = defaultdict(
            lambda: {"n_planned": 0, "n_eligible": 0, "n_signal": 0}
        )
        for pair in pairs:
            name = str(pair[key])
            buckets[name]["n_planned"] += 1
            if pair.get("eligible"):
                buckets[name]["n_eligible"] += 1
            if pair.get("dispersion_specific_signal"):
                buckets[name]["n_signal"] += 1
        out[key] = dict(sorted(buckets.items()))
    return out


def _pair_metrics(clustered: Sequence[Mapping[str, Any]], dispersed: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    def side(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        rp = _arm(rows, "rule_pi") or {}
        raw = _arm(rows, "raw_full") or {}
        reb = _arm(rows, "rule_pi_rebite") or {}
        return {
            "rule_pi_sequence": list(_seq(rp)),
            "rule_pi_status": rp.get("status"),
            "rule_pi_no_op": rp.get("no_op"),
            "length_pi_sequence": list(_seq(_arm(rows, "length_pi") or {})),
            "length_pi_status": (_arm(rows, "length_pi") or {}).get("status"),
            "raw_payload_sha256": raw.get("payload_sha256"),
            "rule_pi_payload_sha256": rp.get("payload_sha256"),
            "visible_evidence_recall": rp.get("evidence_recall_visible"),
            "recoverable_evidence_recall": rp.get("evidence_recall_recoverable"),
            "provenance": rp.get("provenance"),
            "T_total": rp.get("T_total"),
            "T_rebite": reb.get("T_rebite"),
            "rebite_count": reb.get("rebite_count"),
            "payload_matches_raw": rp.get("payload_matches_raw"),
        }

    return {"clustered": side(clustered), "dispersed": side(dispersed)}


def classify_measured_pair(
    *,
    pair: Mapping[str, Any],
    left_tokens: int,
    right_tokens: int,
    clustered_rows: Sequence[Mapping[str, Any]],
    dispersed_rows: Sequence[Mapping[str, Any]],
    frozen_contract_ok: bool,
    instrumentation_ok: bool,
) -> dict[str, Any]:
    length_ok = token_length_match(left_tokens, right_tokens)
    lp_c, lp_d = _arm(clustered_rows, "length_pi"), _arm(dispersed_rows, "length_pi")
    rp_c, rp_d = _arm(clustered_rows, "rule_pi"), _arm(dispersed_rows, "rule_pi")
    rb_c, rb_d = _arm(clustered_rows, "rule_pi_rebite"), _arm(dispersed_rows, "rule_pi_rebite")
    raw_c, raw_d = _arm(clustered_rows, "raw_full"), _arm(dispersed_rows, "raw_full")
    length_pi_same = bool(lp_c and lp_d and _behavior(lp_c) == _behavior(lp_d))
    seq_diff = bool(rp_c and rp_d and _seq(rp_c) != _seq(rp_d))
    noop_diff = bool(
        rp_c
        and rp_d
        and (bool(rp_c.get("no_op")) != bool(rp_d.get("no_op")) or rp_c.get("status") != rp_d.get("status"))
    )
    recovery_diff = bool(rb_c and rb_d and _recovery_fired(rb_c) != _recovery_fired(rb_d))
    hash_diff = bool(
        raw_c and raw_d and raw_c.get("payload_sha256") != raw_d.get("payload_sha256")
    )
    recall_diff = bool(
        rp_c
        and rp_d
        and (
            rp_c.get("evidence_recall_visible") != rp_d.get("evidence_recall_visible")
            or rp_c.get("evidence_recall_recoverable") != rp_d.get("evidence_recall_recoverable")
        )
    )
    prov_diff = bool(rp_c and rp_d and rp_c.get("provenance") != rp_d.get("provenance"))
    t_diff = bool(rp_c and rp_d and rp_c.get("T_total") != rp_d.get("T_total"))
    lp_ne_rp = False
    for rows in (clustered_rows, dispersed_rows):
        lp, rp = _arm(rows, "length_pi"), _arm(rows, "rule_pi")
        if lp and rp and (_seq(lp) != _seq(rp) or lp.get("payload_sha256") != rp.get("payload_sha256")):
            lp_ne_rp = True
    classified = classify_dispersion_pair(
        length_criterion_ok=length_ok,
        instrumentation_ok=instrumentation_ok,
        frozen_contract_ok=frozen_contract_ok,
        length_pi_behavior_same=length_pi_same,
        rule_pi_sequence_differs=seq_diff,
        rule_pi_noop_status_differs=noop_diff,
        rule_pi_rebite_recovery_differs=recovery_diff,
        raw_payload_hash_differs=hash_diff,
        recall_differs=recall_diff,
        provenance_differs=prov_diff,
        t_total_differs=t_diff,
        length_pi_neq_rule_pi=lp_ne_rp,
    )
    abs_delta = abs(left_tokens - right_tokens)
    return {
        "pair_id": pair["pair_id"],
        "case_id": pair["case_id"],
        "scale": pair["scale"],
        "dependency": pair["dependency"],
        "replica": pair["replica"],
        "structure": pair["structure"],
        "redundancy": pair["redundancy"],
        "left_family": pair["left"]["family"],
        "right_family": pair["right"]["family"],
        "left_tokens": left_tokens,
        "right_tokens": right_tokens,
        "abs_delta": abs_delta,
        "relative_delta": relative_token_delta(left_tokens, right_tokens),
        "length_matched": length_ok,
        "frozen_contract_ok": frozen_contract_ok,
        "instrumentation_ok": instrumentation_ok,
        "length_pi_behavior_same": length_pi_same,
        "rule_pi_sequence_differs": seq_diff,
        "rule_pi_noop_status_differs": noop_diff,
        "rule_pi_rebite_recovery_differs": recovery_diff,
        "raw_payload_hash_differs": hash_diff,
        "recall_differs": recall_diff,
        "provenance_differs": prov_diff,
        "t_total_differs": t_diff,
        "length_pi_neq_rule_pi": lp_ne_rp,
        **classified,
        "metrics": _pair_metrics(clustered_rows, dispersed_rows)
        if clustered_rows and dispersed_rows
        else None,
    }


def _run_surface(
    bundle: Mapping[str, Any],
    family: str,
    pair: Mapping[str, Any],
    dispersion: str,
) -> list[dict[str, Any]]:
    packet = surface_packet(bundle, family)
    packet["instance_id"] = f"{pair['pair_id']}::{dispersion}"
    budget = extract_budget(packet, None)
    rows = arm_rows_for_packet(packet, case_kind=CASE_KIND, family=family)
    for row in rows:
        row["pair_id"] = pair["pair_id"]
        row["benchmark_split"] = "evaluation"
        row["dispersion"] = dispersion
        row["structure"] = pair["structure"]
        row["redundancy"] = pair["redundancy"]
        row["scale"] = pair["scale"]
        row["dependency"] = pair["dependency"]
        row["replica"] = pair["replica"]
        row["wrapper"] = OFFLINE_WRAPPER
        row["budget"] = {k: budget[k] for k in ("char_len", "n_tokens") if k in budget}
        row["canonical_case_id"] = pair["case_id"]
    _annotate_vs_raw(rows)
    return rows


def build_phase2d_doc(
    *,
    prompt_tokens: PromptTokens | None = None,
    tokenizer_reference: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    blocked: list[str] = []
    freeze_check = verify_phase2c_v02()
    if not freeze_check["ok"]:
        blocked.append("Phase 2C v0.2 freeze contract broken")
        blocked.extend(str(x) for x in freeze_check.get("mismatches") or [])
    neg = run_negative_control_self_check()
    if not neg["ok"]:
        blocked.append("negative control / instrumentation self-check failed")

    pair_rows: list[dict[str, Any]] = []
    arm_rows: list[dict[str, Any]] = []
    evaluation_opened = False
    if not blocked:
        if prompt_tokens is None:
            blocked.append("tokenizer prompt counter missing; cannot open evaluation fairly")
        else:
            evaluation_opened = True
            bundles = {
                cell.case_id: generate_phase2a_bundle(cell)
                for cell in design_cells("evaluation")
            }
            token_cache: dict[tuple[str, str], int] = {}
            for pair in confirmatory_pairs():
                bundle = bundles[str(pair["case_id"])]
                query = str(bundle["canonical"]["question"])
                left_fam = str(pair["left"]["family"])
                right_fam = str(pair["right"]["family"])
                for fam in (left_fam, right_fam):
                    key = (str(pair["case_id"]), fam)
                    if key not in token_cache:
                        token_cache[key] = int(
                            prompt_tokens(str(bundle["surfaces"][fam]["text"]), query)
                        )
                left_n = token_cache[(str(pair["case_id"]), left_fam)]
                right_n = token_cache[(str(pair["case_id"]), right_fam)]
                contract_ok = _frozen_contract_ok(bundle, pair)
                length_ok = token_length_match(left_n, right_n)
                clustered: list[dict[str, Any]] = []
                dispersed: list[dict[str, Any]] = []
                instrumentation_ok = True
                if length_ok and contract_ok:
                    clustered = _run_surface(bundle, left_fam, pair, "clustered")
                    dispersed = _run_surface(bundle, right_fam, pair, "dispersed")
                    ran = clustered + dispersed
                    if any(r.get("failed") or r.get("status") == "failed" for r in ran):
                        instrumentation_ok = False
                    else:
                        arm_rows.extend(ran)
                measured = classify_measured_pair(
                    pair=pair,
                    left_tokens=left_n,
                    right_tokens=right_n,
                    clustered_rows=clustered,
                    dispersed_rows=dispersed,
                    frozen_contract_ok=contract_ok,
                    instrumentation_ok=instrumentation_ok,
                )
                pair_rows.append(measured)

    n_eligible = sum(1 for p in pair_rows if p.get("eligible"))
    n_signal = sum(1 for p in pair_rows if p.get("dispersion_specific_signal"))
    verdict = decide_phase2d_verdict(
        n_eligible=n_eligible,
        n_dispersion_specific_signal=n_signal,
        blocked_reasons=blocked or None,
    )
    return {
        "schema": SCHEMA_ID,
        "offline": True,
        "paid_api": False,
        "synthetic": True,
        "research_conclusion": False,
        "purpose": (
            "Phase 2D frozen confirmatory offline evaluation of dispersion pairs; "
            "not a paid-model result and not an architecture-superiority claim"
        ),
        "base_main_sha": BASE_MAIN_SHA,
        "phase2a_revision": PHASE2A_REVISION,
        "phase2c_revision": PHASE2C_REVISION,
        "arms": list(PHASE2D_ARMS),
        "freeze_verification": freeze_check,
        "negative_control_self_check": {
            "ok": neg["ok"],
            "n_matrix_rows": neg.get("n_matrix_rows"),
            "matrix_validation": neg.get("matrix_validation"),
            "negative_control_report": neg.get("negative_control_report"),
        },
        "tokenizer_reference": dict(tokenizer_reference or {}),
        "length_criterion": {
            "max_abs_delta": TOKEN_MATCH_MAX_ABS_DELTA,
            "max_relative_delta": TOKEN_MATCH_MAX_RELATIVE_DELTA,
            "no_padding": True,
            "widened": False,
        },
        "blocked_reasons": blocked,
        "evaluation_opened": evaluation_opened,
        "verdict": verdict,
        "n_planned_pairs": 48,
        "n_length_matched": sum(1 for p in pair_rows if p.get("length_matched")),
        "n_eligible": n_eligible,
        "n_signal": n_signal,
        "n_excluded_length": sum(
            1 for p in pair_rows if p.get("length_matched") is False
        ),
        "n_consistency_issue": sum(
            1
            for p in pair_rows
            if p.get("classification") == "instrumentation_or_policy_consistency_issue"
        ),
        "n_pairs_length_pi_neq_rule_pi": sum(
            1 for p in pair_rows if p.get("length_pi_neq_rule_pi")
        ),
        "n_rows": len(arm_rows),
        "generalization": {
            "one_pair_is_still_signal": True,
            "no_strong_generalization": True,
            "n_signal_over_n_eligible": (
                f"{n_signal}/{n_eligible}" if n_eligible else "0/0"
            ),
        },
        "breakdowns": _breakdown(pair_rows),
        "pairs": pair_rows,
        "rows": arm_rows,
    }


def render_phase2d_md(doc: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 2D confirmatory offline evaluation",
        "",
        "有料モデル精度は測っていない。BITE の優劣は主張しない。",
        "判定規則は Phase 2C v0.2 のみ。",
        "",
        f"- verdict: **{doc.get('verdict')}**",
        f"- freeze: `{doc.get('phase2c_revision')}`",
        f"- n_signal / n_eligible: {doc.get('n_signal')} / {doc.get('n_eligible')}",
        f"- n_planned: {doc.get('n_planned_pairs')} length_matched: {doc.get('n_length_matched')}",
        f"- n_excluded_length: {doc.get('n_excluded_length')}",
        f"- n_consistency_issue: {doc.get('n_consistency_issue')}",
        f"- n_pairs_length_pi_neq_rule_pi (endpoint, not signal): {doc.get('n_pairs_length_pi_neq_rule_pi')}",
        f"- confirmatory rows: {doc.get('n_rows')} (max 384)",
        f"- paid_api: {doc.get('paid_api')}",
        f"- evaluation_opened: {doc.get('evaluation_opened')}",
        "",
        "## Self-check",
        "",
        f"- freeze v0.2 ok: {(doc.get('freeze_verification') or {}).get('ok')}",
        (
            f"- negative controls ok: "
            f"{(doc.get('negative_control_self_check') or {}).get('ok')}"
        ),
        "",
        "## Breakdowns (n_signal / n_eligible)",
        "",
    ]
    breakdowns = dict(doc.get("breakdowns") or {})
    for axis in ("scale", "dependency", "structure", "redundancy"):
        lines.append(f"**{axis}**")
        lines.append("")
        rows = dict(breakdowns.get(axis) or {})
        for name, row in rows.items():
            lines.append(
                f"- {name}: {row.get('n_signal')}/{row.get('n_eligible')} "
                f"(planned {row.get('n_planned')})"
            )
        lines.append("")
    lines += [
        "## Recorded, not counted as dispersion signal",
        "",
        (
            f"- raw payload hash differs: "
            f"{sum(1 for p in list(doc.get('pairs') or []) if isinstance(p, Mapping) and p.get('raw_payload_hash_differs'))}"
        ),
        (
            f"- recall differs: "
            f"{sum(1 for p in list(doc.get('pairs') or []) if isinstance(p, Mapping) and p.get('recall_differs'))}"
        ),
        (
            f"- provenance differs: "
            f"{sum(1 for p in list(doc.get('pairs') or []) if isinstance(p, Mapping) and p.get('provenance_differs'))}"
        ),
        (
            f"- T_total differs: "
            f"{sum(1 for p in list(doc.get('pairs') or []) if isinstance(p, Mapping) and p.get('t_total_differs'))}"
        ),
        (
            f"- length_pi != rule_pi pairs: "
            f"{doc.get('n_pairs_length_pi_neq_rule_pi')}"
        ),
        "",
    ]
    signal_pairs = [
        p for p in list(doc.get("pairs") or [])
        if isinstance(p, Mapping) and p.get("dispersion_specific_signal")
    ]
    lines += ["## Signal pairs", ""]
    if not signal_pairs:
        lines += ["なし", ""]
    else:
        for pair in signal_pairs:
            lines.append(
                f"- `{pair.get('pair_id')}` "
                f"({pair.get('scale')}/{pair.get('dependency')}/"
                f"{pair.get('structure')}/{pair.get('redundancy')})"
            )
        lines.append("")
    if int(doc.get("n_signal") or 0) == 1:
        lines += [
            "SIGNAL は 1 pair。一般化しない。",
            "",
        ]
    blocked = list(doc.get("blocked_reasons") or [])
    if blocked:
        lines += ["## BLOCKED reasons", ""]
        for reason in blocked:
            lines.append(f"- {reason}")
        lines.append("")
    return "\n".join(lines)


def validate_phase2d_doc(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("paid_api") is not False:
        errs.append("paid_api must be false")
    if doc.get("schema") != SCHEMA_ID:
        errs.append(f"bad schema: {doc.get('schema')!r}")
    if doc.get("phase2c_revision") != PHASE2C_REVISION:
        errs.append("must use Phase 2C v0.2 as the only verdict rule")
    if doc.get("verdict") not in PHASE2D_VERDICTS:
        errs.append(f"bad verdict: {doc.get('verdict')!r}")
    if doc.get("research_conclusion") is not False:
        errs.append("research_conclusion must be false")
    n_eligible = int(doc.get("n_eligible") or 0)
    n_signal = int(doc.get("n_signal") or 0)
    verdict = doc.get("verdict")
    if verdict == "PHASE2D_OFFLINE_SIGNAL" and not (n_eligible >= 1 and n_signal >= 1):
        errs.append("SIGNAL requires n_eligible>=1 and n_signal>=1")
    if verdict == "PHASE2D_OFFLINE_NO_SIGNAL" and not (n_eligible >= 1 and n_signal == 0):
        errs.append("NO_SIGNAL requires n_eligible>=1 and n_signal==0")
    if int(doc.get("n_rows") or 0) > 384:
        errs.append("n_rows exceeds 48*2*4")
    if n_eligible and int(doc.get("n_rows") or 0) != 8 * n_eligible:
        errs.append("eligible pairs must contribute 8 confirmatory rows each")
    for pair in list(doc.get("pairs") or []):
        if not isinstance(pair, Mapping):
            continue
        if pair.get("dispersion_specific_signal"):
            if not (
                pair.get("rule_pi_sequence_differs")
                or pair.get("rule_pi_noop_status_differs")
                or pair.get("rule_pi_rebite_recovery_differs")
            ):
                errs.append(f"{pair.get('pair_id')}: signal without a declared rule_pi diff")
            if pair.get("length_pi_behavior_same") is False:
                errs.append(f"{pair.get('pair_id')}: length_pi inconsistency counted as signal")
        if pair.get("replica") not in {2, 3}:
            errs.append(f"{pair.get('pair_id')}: not an evaluation replica")
    for row in list(doc.get("rows") or []):
        if isinstance(row, Mapping) and row.get("benchmark_split") != "evaluation":
            errs.append("non-evaluation row in confirmatory table")
        if isinstance(row, Mapping) and row.get("replica") not in {2, 3}:
            errs.append("row replica is not evaluation")
    return errs
