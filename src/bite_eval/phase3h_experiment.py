"""Phase 3H isolated operator-map development experiment (H1).

Runs the H0 freeze only. Does not open p3f evaluation. Does not change
candidate A, thresholds, v1, or routing policy.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bite_bench.phase3h import (
    ARMS,
    LOCKED_CANDIDATE,
    LOCKED_FEATURE,
    LOCKED_T_HIGH,
    LOCKED_T_LOW,
    MAP_VERDICTS,
    N_ROWS,
    N_SURFACES,
    PROTOCOL_FROZEN,
    REVISION,
    Arm,
    EvaluationSealError,
    Fmt,
    bin_univariate,
    consensus_signals,
    decide_verdict,
    design_surfaces,
    freeze_manifest,
    refuse_p3f_evaluation,
)
from bite_eval.accounting.estimate import estimate_tokens_char4
from bite_ingestion.operators import apply_operator
from bite_ingestion.packet_contract import (
    assert_evidence_ids_resolve,
    make_unit,
    provenance_completeness,
    root_ids_of,
    validate_units,
    visible_evidence_from_units,
)
from bite_ingestion.profilers.dependency_dispersion_v1 import measure

SCHEMA_ID = "bite-phase3h-operator-map-experiment/v0.1"
PROTOCOL_COMMIT_SHA = "fb425a0a75a1077b32bc49a0036f2888ea17e802"
_REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = _REPO / "artifacts" / "phase3h"
RESULT_PATH = ARTIFACT_DIR / "operator-map-experiment.json"
RESULT_MD_PATH = ARTIFACT_DIR / "operator-map-experiment.md"
LOCK3G_PATH = _REPO / "artifacts" / "phase3g" / "calibration-lock.json"
V1_PY = _REPO / "src" / "bite_ingestion" / "profilers" / "dependency_dispersion_v1.py"
POLICY_PY = _REPO / "src" / "bite_ingestion" / "policies" / "rule_policy.py"


def _pairs_from_text(text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("{"):
            obj = json.loads(stripped)
            pairs.append((str(obj["k"]), str(obj["v"])))
            continue
        if "=" in stripped:
            key, _, value = stripped.partition("=")
            pairs.append((key, value))
    return pairs


def payload_from_units(fmt: str, units: Sequence[Mapping[str, Any]]) -> str:
    pairs: list[tuple[str, str]] = []
    for unit in units:
        pairs.extend(_pairs_from_text(str(unit.get("text", ""))))
    if fmt == "json":
        return json.dumps([{"k": key, "v": value} for key, value in pairs], separators=(",", ":"))
    return "\n".join(f"{key}={value}" for key, value in pairs)


def packet_from_surface(surface: Mapping[str, Any]) -> dict[str, Any]:
    refuse_p3f_evaluation(str(surface["case_id"]))
    texts = [str(text) for text in surface["unit_texts"]]
    ids = [str(uid) for uid in surface["unit_ids"]]
    uri = f"bitebench://{surface['surface_id']}"
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
                renderer_id="p3h",
            )
        )
        start = end + 1
    document = "\n".join(texts)
    validate_units(units, document=document)
    assert_evidence_ids_resolve(list(surface["gold_unit_ids"]), units)
    return {
        "packet_id": surface["surface_id"],
        "document": document,
        "query": surface["question"],
        "gold_evidence_ids": list(surface["gold_unit_ids"]),
        "units": units,
        "visible_evidence": visible_evidence_from_units(units),
        "source_uri": uri,
    }


def _cut_context(fmt: str) -> dict[str, str]:
    return {"boundary": "record" if fmt == "json" else "line"}


def confirm_high(surface: Mapping[str, Any]) -> dict[str, Any]:
    payload = str(surface["payload"])
    report = measure({"payload": payload, "text": payload})
    value = float(report.features[LOCKED_FEATURE])
    label = bin_univariate(value)
    return {
        "surface_id": surface["surface_id"],
        "mean_edge_distance": value,
        "bin": label,
        "fail_closed": report.fail_closed,
        "high": label == "high" and not report.fail_closed,
    }


def _gold_joined(after: Mapping[str, Any], gold: set[str]) -> int:
    blob = after.get("integrate")
    if not isinstance(blob, Mapping):
        return 0
    n_joined = 0
    for plan in blob.get("join_plan") or []:
        if not isinstance(plan, Mapping):
            continue
        members = {str(uid) for uid in plan.get("unit_ids") or []}
        if len(members & gold) >= 2:
            n_joined += 1
    return n_joined


def score_arm(
    surface: Mapping[str, Any],
    arm: Arm,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    span_before: float,
) -> dict[str, Any]:
    gold = {str(uid) for uid in surface["gold_unit_ids"]}
    source = {str(unit["unit_id"]) for unit in before["units"]}
    visible = [dict(unit) for unit in after.get("units") or [] if isinstance(unit, Mapping)]
    roots = root_ids_of([str(unit["unit_id"]) for unit in visible], visible)
    n_gold_removed = len(gold - roots)
    n_nongold_removed = len((source - gold) - roots)
    recall = (len(gold) - n_gold_removed) / len(gold)
    isolated_ids = []
    untangle = after.get("untangle")
    if isinstance(untangle, Mapping):
        isolated_ids = [
            str(row["unit_id"])
            for row in untangle.get("isolated") or []
            if isinstance(row, Mapping) and row.get("unit_id")
        ]
    payload_after = payload_from_units(str(surface["format"]), visible)
    report = measure({"payload": payload_after, "text": payload_after})
    span_after = float(report.features[LOCKED_FEATURE])
    before_texts = Counter(str(unit.get("text", "")) for unit in before["units"])
    after_texts = Counter(str(unit.get("text", "")) for unit in visible)
    return {
        "surface_id": surface["surface_id"],
        "case_id": surface["case_id"],
        "split": surface["split"],
        "generation": surface["generation"],
        "texture": surface["texture"],
        "replica": surface["replica"],
        "format": surface["format"],
        "arm": arm,
        "recall_visible": recall,
        "provenance_completeness": provenance_completeness(visible),
        "no_op": before_texts == after_texts,
        "effective_dependency_span": span_after,
        "span_before": span_before,
        "span_delta": span_after - span_before,
        "n_gold_removed": n_gold_removed,
        "n_nongold_removed": n_nongold_removed,
        "n_gold_joined": _gold_joined(after, gold),
        "n_quarantined": len(isolated_ids),
        "n_gold_quarantined": len(gold & set(isolated_ids)),
        "n_visible_units": len(visible),
        "token_proxy_before": estimate_tokens_char4(str(surface["payload"])),
        "token_proxy_after": estimate_tokens_char4(payload_after),
        "op_status": after.get("op_status"),
        "v1_fail_closed": report.fail_closed,
    }


def _premise_errors() -> list[str]:
    errs: list[str] = []
    freeze = freeze_manifest()
    if freeze.get("verdict") != PROTOCOL_FROZEN:
        errs.append("H0 freeze is not frozen")
    if freeze.get("revision") != REVISION:
        errs.append("H0 revision drifted")
    if not LOCK3G_PATH.is_file():
        errs.append("phase3g lock missing")
        return errs
    lock = json.loads(LOCK3G_PATH.read_text(encoding="utf-8"))
    if lock.get("selected_candidate") != LOCKED_CANDIDATE:
        errs.append("candidate A drifted")
    thresholds = dict(lock.get("selected_thresholds") or {})
    if thresholds.get("T_low") != LOCKED_T_LOW or thresholds.get("T_high") != LOCKED_T_HIGH:
        errs.append("thresholds drifted")
    if lock.get("rule_policy_changed") is not False:
        errs.append("3G lock already changed routing")
    if not V1_PY.is_file() or not POLICY_PY.is_file():
        errs.append("v1 or routing module missing")
    return errs


def run_experiment() -> dict[str, Any]:
    blocked_reasons = _premise_errors()
    surfaces = design_surfaces()
    if len(surfaces) != N_SURFACES:
        blocked_reasons.append(f"expected {N_SURFACES} surfaces")
    high_rows = []
    rows = []
    try:
        for surface in surfaces:
            refuse_p3f_evaluation(str(surface["case_id"]))
            high = confirm_high(surface)
            high_rows.append(high)
            packet = packet_from_surface(surface)
            fmt: Fmt = surface["format"]
            for arm in ARMS:
                context = _cut_context(fmt) if arm == "CUT" else None
                after = dict(apply_operator(arm, packet, context))
                rows.append(
                    score_arm(surface, arm, packet, after, float(high["mean_edge_distance"]))
                )
    except EvaluationSealError as exc:
        blocked_reasons.append(str(exc))

    if len(rows) != N_ROWS:
        blocked_reasons.append(f"expected {N_ROWS} rows, got {len(rows)}")
    high_confirmed = bool(high_rows) and all(row["high"] for row in high_rows)
    if not high_confirmed:
        blocked_reasons.append("high bin not confirmed on every p3h surface")
    blob = json.dumps(rows, sort_keys=True)
    if "p3f-" in blob:
        blocked_reasons.append("p3f identifier leaked into rows")
    consensus = consensus_signals(rows) if rows else {}
    verdict = decide_verdict(
        blocked=bool(blocked_reasons),
        high_confirmed=high_confirmed,
        consensus=consensus,
    )
    if verdict not in MAP_VERDICTS:
        blocked_reasons.append("verdict not in frozen set")
        verdict = "PHASE3H_MAP_UNRESOLVED"
    return {
        "schema": SCHEMA_ID,
        "revision": "phase3h-operator-map-experiment-v0.1",
        "protocol_revision": REVISION,
        "protocol_commit_sha": PROTOCOL_COMMIT_SHA,
        "verdict": verdict,
        "blocked_reasons": blocked_reasons,
        "paid_api": False,
        "offline": True,
        "synthetic": True,
        "research_conclusion": False,
        "p3f_evaluation_holdout_used": False,
        "evaluation_outcomes_open": False,
        "locked_candidate": LOCKED_CANDIDATE,
        "locked_thresholds": {"T_low": LOCKED_T_LOW, "T_high": LOCKED_T_HIGH},
        "v1_sensor_changed": False,
        "rule_policy_changed": False,
        "rule_policy_implemented": False,
        "routing_connected": False,
        "operator_map_selected": False,
        "selected_operator_map": None,
        "high_bin_mapped_to_operator": False,
        "token_reduction_used_for_verdict": False,
        "must_pick_m1_or_m2": False,
        "high_confirmed": high_confirmed,
        "n_surfaces": len(surfaces),
        "n_rows": len(rows),
        "consensus": consensus,
        "high_confirmation": high_rows,
        "rows": rows,
    }


def validate_phase3h_experiment(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("protocol_commit_sha") != PROTOCOL_COMMIT_SHA:
        errs.append("protocol commit SHA mismatch")
    if doc.get("verdict") not in MAP_VERDICTS:
        errs.append("verdict not in frozen set")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("token_reduction_used_for_verdict") is not False:
        errs.append("token reduction used as winner")
    if doc.get("rule_policy_changed") is not False:
        errs.append("routing policy changed")
    if doc.get("rule_policy_implemented") is not False:
        errs.append("routing policy implemented")
    if doc.get("locked_candidate") != LOCKED_CANDIDATE:
        errs.append("candidate A changed")
    thresholds = dict(doc.get("locked_thresholds") or {})
    if thresholds.get("T_low") != LOCKED_T_LOW or thresholds.get("T_high") != LOCKED_T_HIGH:
        errs.append("thresholds changed")
    rows = list(doc.get("rows") or [])
    if len(rows) != N_ROWS:
        errs.append("row count")
    for row in rows:
        sid = str(row.get("surface_id") or "")
        if not sid.startswith("p3h-"):
            errs.append(f"non-p3h surface {sid}")
        if "-r2-" in sid or "-r3-" in sid:
            errs.append(f"evaluation replica {sid}")
        if row.get("split") != "development":
            errs.append(f"non-development {sid}")
    if doc.get("verdict") == "PHASE3H_CONDITIONAL_MAP_REQUIRED" and doc.get(
        "rule_policy_implemented"
    ):
        errs.append("conditional map must stop without implementation")
    blob = json.dumps(doc, sort_keys=True)
    if '"replica": 2' in blob or '"replica": 3' in blob:
        errs.append("replica 2/3 leaked")
    return errs


def render_md(doc: Mapping[str, Any]) -> str:
    consensus = dict(doc.get("consensus") or {})
    lines = [
        "# Phase 3H operator-map experiment",
        "",
        f"verdict: `{doc.get('verdict')}`",
        f"protocol SHA: `{doc.get('protocol_commit_sha')}`",
        f"high confirmed: `{doc.get('high_confirmed')}`",
        "token reduction used for verdict: `false`",
        "routing policy implemented: `false`",
        "",
        "## Consensus signals",
        "",
        "| texture | CUT | REDUCE | INTEGRATE | UNTANGLE |",
        "|---|---|---|---|---|",
    ]
    for texture in ("redundant", "unique", "anomalous"):
        flags = dict(consensus.get(texture) or {})
        lines.append(
            "| "
            + " | ".join(
                [
                    texture,
                    str(flags.get("CUT")),
                    str(flags.get("REDUCE")),
                    str(flags.get("INTEGRATE")),
                    str(flags.get("UNTANGLE")),
                ]
            )
            + " |"
        )
    lines.extend(["", "BITE wins / Go ではない。", ""])
    reasons = list(doc.get("blocked_reasons") or [])
    if reasons:
        lines.append("blocked:")
        lines.extend(f"- {reason}" for reason in reasons)
        lines.append("")
    return "\n".join(lines)


def write_artifacts(doc: Mapping[str, Any] | None = None) -> tuple[Path, Path]:
    if doc is None:
        doc = run_experiment()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    RESULT_MD_PATH.write_text(render_md(doc), encoding="utf-8")
    return RESULT_PATH, RESULT_MD_PATH


if __name__ == "__main__":
    write_artifacts()
