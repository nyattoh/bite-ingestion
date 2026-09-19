"""Phase 3N first-open evaluation of conditional_texture_policy_v1 on p3m r2/r3.

Does not change predicates, thresholds, fixtures, operators, sensors, or RulePolicy.
Does not open p3f evaluation. Does not remeasure development.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bite_bench.phase3m import (
    EVALUATION_REPLICAS,
    GENERATION,
    LOCKED_CANDIDATE,
    LOCKED_FEATURE,
    LOCKED_T_HIGH,
    LOCKED_T_LOW,
    POLICY_NAME,
    EvaluationSealError,
    refuse_p3f_evaluation,
)
from bite_bench.phase3n import (
    CLAIM_BOUNDARY,
    LOCKED_GIT_BLOBS,
    M0_COMMIT_SHA,
    M1_COMMIT_SHA,
    N1_VERDICTS,
    N_EVAL_SURFACES,
    PROTOCOL_FROZEN,
    REVISION,
    VERDICT_BLOCKED,
    VERDICT_CONFIRMED,
    VERDICT_FAILED,
    evaluation_case_ids,
    evaluation_surfaces,
    freeze_manifest,
    observed_git_blobs,
)
from bite_eval.phase3m_eval import composition_safety
from bite_ingestion.packet_contract import (
    make_unit,
    validate_units,
    visible_evidence_from_units,
)
from bite_ingestion.policies.conditional_texture_policy_v1 import (
    ConditionalTexturePolicyV1,
    PolicyLeakError,
    assert_policy_gold_isolated,
)
from bite_ingestion.profilers.dependency_dispersion_v1 import measure as measure_dispersion

SCHEMA_ID = "bite-phase3n-conditional-routing-first-open/v0.1"
SAFETY_SCHEMA_ID = "bite-phase3n-composition-safety/v0.1"
ROUTING_SCHEMA_ID = "bite-phase3n-routing-comparison/v0.1"
PROTOCOL_COMMIT_SHA = "297f3270b85436fe1d247e62541c66469fc1205a"
_REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = _REPO / "artifacts" / "phase3n"
RESULT_PATH = ARTIFACT_DIR / "conditional-routing-first-open.json"
RESULT_MD_PATH = ARTIFACT_DIR / "conditional-routing-first-open.md"
ROUTING_PATH = ARTIFACT_DIR / "routing-comparison.json"
SAFETY_PATH = ARTIFACT_DIR / "composition-safety.json"
PHASE3M_PATH = _REPO / "artifacts" / "phase3m" / "conditional-routing.json"


def packet_from_surface(surface: Mapping[str, Any]) -> dict[str, Any]:
    cid = str(surface["case_id"])
    refuse_p3f_evaluation(cid)
    if int(surface["replica"]) not in EVALUATION_REPLICAS:
        raise EvaluationSealError(f"p3m development sealed from 3N remeasure: {cid}")
    texts = [str(text) for text in surface["unit_texts"]]
    ids = [str(uid) for uid in surface["unit_ids"]]
    uri = f"bitebench://{cid}"
    units: list[dict[str, Any]] = []
    start = 0
    for uid, text in zip(ids, texts, strict=True):
        end = start + len(text)
        units.append(
            make_unit(
                unit_id=uid,
                text=text,
                start=start,
                end=end,
                source_uri=uri,
                renderer_id="p3m",
            )
        )
        start = end + 1
    document = "\n".join(texts)
    validate_units(units, document=document)
    return {
        "packet_id": cid,
        "document": document,
        "units": units,
        "visible_evidence": visible_evidence_from_units(units),
        "source_uri": uri,
    }


def _premise_errors() -> list[str]:
    errs: list[str] = []
    freeze = freeze_manifest()
    if freeze.get("verdict") != PROTOCOL_FROZEN:
        errs.append("N0 freeze drifted")
    if freeze.get("revision") != REVISION:
        errs.append("N0 revision drifted")
    if freeze.get("m0_commit_sha") != M0_COMMIT_SHA:
        errs.append("M0 SHA drifted")
    if freeze.get("m1_commit_sha") != M1_COMMIT_SHA:
        errs.append("M1 SHA drifted")
    if freeze.get("locked_git_blobs") != LOCKED_GIT_BLOBS:
        errs.append("locked git blobs drifted")
    try:
        if observed_git_blobs() != LOCKED_GIT_BLOBS:
            errs.append("locked blob hashes drifted")
    except Exception as exc:  # noqa: BLE001
        errs.append(f"locked blob check failed: {exc}")
    if list(freeze.get("evaluation_case_ids") or []) != evaluation_case_ids():
        errs.append("evaluation case ids drifted")
    if not PHASE3M_PATH.is_file():
        errs.append("Phase 3M artifact missing")
    else:
        phase3m = json.loads(PHASE3M_PATH.read_text(encoding="utf-8"))
        if phase3m.get("verdict") != "PHASE3M_CONDITIONAL_ROUTING_READY":
            errs.append("Phase 3M verdict rewritten")
    return errs


def _measure_row(surface: Mapping[str, Any], policy: ConditionalTexturePolicyV1) -> dict[str, Any]:
    refuse_p3f_evaluation(str(surface["case_id"]))
    packet = packet_from_surface(surface)
    assert_policy_gold_isolated(packet)
    payload = str(surface["payload"])
    disp = measure_dispersion({"payload": payload, "text": payload})
    n_edges = float(disp.features["n_edges"])
    mean = float(disp.features[LOCKED_FEATURE])
    gated = (not disp.fail_closed) and n_edges > 0.0 and mean >= float(LOCKED_T_HIGH)
    decision = policy.explain_propose(packet)
    sequence = [op.value for op in decision.sequence]
    after = policy.apply(packet)
    expect = list(surface["expected_sequence"])
    safety = composition_safety(
        packet,
        after,
        gold_ids=list(surface["gold_unit_ids"]),
        sequence=sequence,
    )
    high = str(surface["dispersion"]) == "high"
    gate_ok = gated if high else not gated
    return {
        "case_id": surface["case_id"],
        "generation": GENERATION,
        "texture": surface["texture"],
        "dispersion": surface["dispersion"],
        "replica": surface["replica"],
        "split": "evaluation",
        "n_edges": n_edges,
        "mean_edge_distance": mean,
        "fail_closed": disp.fail_closed,
        "gated": gated,
        "gate_ok": gate_ok,
        "n_edges_eq_0": n_edges == 0.0,
        "n_edges_eq_0_as_low": False,
        "gate_notes": list(decision.notes),
        "sequence": sequence,
        "expected_sequence": expect,
        "sequence_ok": sequence == expect,
        "cut_present": "CUT" in sequence,
        "safety": safety,
        "safety_ok": safety["ok"],
        "ok": sequence == expect and safety["ok"] and "CUT" not in sequence and gate_ok,
    }


def run_evaluation() -> dict[str, Any]:
    blocked = _premise_errors()
    rows: list[dict[str, Any]] = []
    policy = ConditionalTexturePolicyV1()
    try:
        for surface in evaluation_surfaces():
            rows.append(_measure_row(surface, policy))
    except (PolicyLeakError, EvaluationSealError, Exception) as exc:  # noqa: BLE001
        blocked.append(str(exc))
    ids = [str(row.get("case_id")) for row in rows]
    if ids != evaluation_case_ids():
        blocked.append("evaluation set mismatch")
    if len(rows) != N_EVAL_SURFACES:
        blocked.append(f"expected {N_EVAL_SURFACES} rows, got {len(rows)}")
    if any(row.get("split") != "evaluation" for row in rows):
        blocked.append("non-evaluation row")
    if any(row.get("replica") not in EVALUATION_REPLICAS for row in rows):
        blocked.append("development replica remeasured")
    blob = json.dumps(rows, sort_keys=True)
    if "p3f-" in blob:
        blocked.append("p3f identifier leaked")
    sequence_ok = bool(rows) and all(row.get("sequence_ok") for row in rows)
    safety_ok = bool(rows) and all(row.get("safety_ok") for row in rows)
    gate_ok = bool(rows) and all(row.get("gate_ok") for row in rows)
    no_cut = bool(rows) and not any(row.get("cut_present") for row in rows)
    no_zero_as_low = bool(rows) and not any(row.get("n_edges_eq_0_as_low") for row in rows)
    checks = {
        "n_48": len(rows) == N_EVAL_SURFACES,
        "sequence_exact": sequence_ok,
        "composition_safety": safety_ok,
        "gate": gate_ok,
        "no_cut": no_cut,
        "n_edges_zero_not_low": no_zero_as_low,
        "locked_blobs_unchanged": not any("hashes drifted" in item for item in blocked),
        "evaluation_set_exact": ids == evaluation_case_ids(),
    }
    if blocked:
        verdict = VERDICT_BLOCKED
    elif all(checks.values()) and all(row.get("ok") for row in rows):
        verdict = VERDICT_CONFIRMED
    else:
        verdict = VERDICT_FAILED
    if verdict not in N1_VERDICTS:
        verdict = VERDICT_BLOCKED
        blocked.append("verdict not in frozen set")
    routing_rows = [
        {
            "case_id": row["case_id"],
            "texture": row["texture"],
            "dispersion": row["dispersion"],
            "replica": row["replica"],
            "sequence": row["sequence"],
            "expected_sequence": row["expected_sequence"],
            "sequence_ok": row["sequence_ok"],
            "cut_present": row["cut_present"],
            "gated": row["gated"],
            "n_edges": row["n_edges"],
            "mean_edge_distance": row["mean_edge_distance"],
        }
        for row in rows
    ]
    safety_rows = [
        {
            "case_id": row["case_id"],
            "texture": row["texture"],
            "dispersion": row["dispersion"],
            "replica": row["replica"],
            "sequence": row["sequence"],
            **row["safety"],
        }
        for row in rows
    ]
    return {
        "schema": SCHEMA_ID,
        "revision": "phase3n-conditional-routing-first-open-v0.1",
        "protocol_revision": REVISION,
        "protocol_commit_sha": PROTOCOL_COMMIT_SHA,
        "m0_commit_sha": M0_COMMIT_SHA,
        "m1_commit_sha": M1_COMMIT_SHA,
        "verdict": verdict,
        "blocked_reasons": blocked,
        "paid_api": False,
        "offline": True,
        "synthetic": True,
        "research_conclusion": False,
        "p3f_evaluation_holdout_used": False,
        "remeasure_development": False,
        "generation": GENERATION,
        "policy_name": POLICY_NAME,
        "phase3m_verdict_unchanged": "PHASE3M_CONDITIONAL_ROUTING_READY",
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "unseen texture",
            "unseen serialization",
            "external corpus generalization",
            "BITE superiority",
        ],
        "rule_policy_changed": False,
        "rule_policy_executed": False,
        "no_new_a_threshold": True,
        "no_new_k_threshold": True,
        "no_v1_edges_as_integrate_context": True,
        "cut_in_conditional_map": False,
        "predicate_unchanged": True,
        "threshold_unchanged": True,
        "fixture_unchanged": True,
        "v1_unchanged": True,
        "a_unchanged": True,
        "locked_from_phase3g": {
            "selected_candidate": LOCKED_CANDIDATE,
            "feature": LOCKED_FEATURE,
            "T_low": LOCKED_T_LOW,
            "T_high": LOCKED_T_HIGH,
        },
        "token_reduction": "diagnostic_only",
        "no_winner_score": True,
        "on_failed": "do not retune predicates or thresholds in this PR",
        "n_rows": len(rows),
        "n_ok": sum(1 for row in rows if row.get("ok")),
        "n_sequence_ok": sum(1 for row in rows if row.get("sequence_ok")),
        "n_safety_ok": sum(1 for row in rows if row.get("safety_ok")),
        "n_gate_ok": sum(1 for row in rows if row.get("gate_ok")),
        "checks": checks,
        "rows": rows,
        "routing_comparison": {
            "schema": ROUTING_SCHEMA_ID,
            "n_ok": sum(1 for row in routing_rows if row.get("sequence_ok")),
            "rows": routing_rows,
        },
        "composition_safety": {
            "schema": SAFETY_SCHEMA_ID,
            "n_ok": sum(1 for row in safety_rows if row.get("ok")),
            "rows": safety_rows,
        },
        "evaluation_replicas": list(EVALUATION_REPLICAS),
    }


def validate_phase3n_result(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("protocol_commit_sha") != PROTOCOL_COMMIT_SHA:
        errs.append("protocol commit SHA mismatch")
    if doc.get("m0_commit_sha") != M0_COMMIT_SHA:
        errs.append("M0 SHA mismatch")
    if doc.get("verdict") not in N1_VERDICTS:
        errs.append("verdict not in frozen set")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation opened")
    if doc.get("remeasure_development") is not False:
        errs.append("development remeasured")
    if doc.get("rule_policy_changed") is not False:
        errs.append("RulePolicy changed")
    if doc.get("rule_policy_executed") is not False:
        errs.append("RulePolicy executed")
    if doc.get("cut_in_conditional_map") is not False:
        errs.append("CUT entered the map")
    blob = json.dumps(doc, sort_keys=True)
    if "p3f-" in blob:
        errs.append("p3f identifier leaked")
    for row in doc.get("rows") or []:
        cid = str(row.get("case_id", ""))
        if not cid.startswith("p3m-"):
            errs.append(f"non-p3m case {cid}")
        if row.get("split") != "evaluation":
            errs.append("non-evaluation row")
        if row.get("replica") not in EVALUATION_REPLICAS:
            errs.append("development replica opened")
    return errs


def render_md(doc: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 3N conditional routing first-open evaluation",
        "",
        f"verdict: `{doc.get('verdict')}`",
        f"protocol SHA: `{doc.get('protocol_commit_sha')}`",
        f"ok: {doc.get('n_ok')}/{doc.get('n_rows')}",
        f"claim: `{doc.get('claim_boundary')}`",
        "rule_policy_executed: `false`",
        "p3f evaluation: sealed",
        "token_reduction: diagnostic only",
        "",
        "## Checks",
        "",
    ]
    for key, ok in dict(doc.get("checks") or {}).items():
        lines.append(f"- {key}: `{ok}`")
    lines.extend(["", "BITE wins / Go ではない。unseen texture 評価ではない。", ""])
    reasons = list(doc.get("blocked_reasons") or [])
    if reasons:
        lines.append("blocked:")
        lines.extend(f"- {reason}" for reason in reasons)
        lines.append("")
    return "\n".join(lines)


def write_artifacts(doc: Mapping[str, Any] | None = None) -> tuple[Path, Path, Path]:
    if doc is None:
        doc = run_evaluation()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    RESULT_MD_PATH.write_text(render_md(doc), encoding="utf-8")
    ROUTING_PATH.write_text(
        json.dumps(doc["routing_comparison"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    SAFETY_PATH.write_text(
        json.dumps(doc["composition_safety"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return RESULT_PATH, ROUTING_PATH, SAFETY_PATH


if __name__ == "__main__":
    write_artifacts()
