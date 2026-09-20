"""Phase 3M development evaluation of conditional_texture_policy_v1.

Does not rewrite RulePolicy. Does not open p3m/p3f evaluation.
Does not retune predicates or thresholds.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bite_bench.phase3m import (
    CALIBRATION_REPLICAS,
    EVALUATION_REPLICAS,
    GENERATION,
    LOCKED_CANDIDATE,
    LOCKED_FEATURE,
    LOCKED_T_HIGH,
    LOCKED_T_LOW,
    M1_VERDICTS,
    POLICY_NAME,
    PROTOCOL_FROZEN,
    REVISION,
    SAFETY_KEYS,
    VERDICT_BLOCKED,
    VERDICT_PARTIAL,
    VERDICT_READY,
    development_surfaces,
    expected_sequence,
    freeze_manifest,
    planned_case_ids,
    refuse_evaluation,
    split_manifest,
    validate_phase3m_freeze,
    validate_phase3m_split,
)
from bite_eval.accounting.estimate import estimate_tokens_char4
from bite_ingestion.operators.loss_ledger import audit_undeclared_visible_loss
from bite_ingestion.operators.preflight import (
    explicit_join_clusters,
    extract_explicit_join_keys,
)
from bite_ingestion.packet_contract import (
    conservation_untraced,
    make_unit,
    provenance_completeness,
    root_ids_of,
    validate_units,
    visible_evidence_from_units,
)
from bite_ingestion.policies.conditional_texture_policy_v1 import (
    ConditionalTexturePolicyV1,
    PolicyLeakError,
    assert_policy_gold_isolated,
)
from bite_ingestion.profilers.dependency_dispersion_v1 import measure as measure_dispersion

SCHEMA_ID = "bite-phase3m-conditional-routing/v0.1"
SAFETY_SCHEMA_ID = "bite-phase3m-composition-safety/v0.1"
PROTOCOL_COMMIT_SHA = "ad95ed8bb0a60ec6c3a10c4a9ccc96f395bcf702"
SINGLE_TEXTURES = frozenset({"redundant", "explicit_join", "anomaly", "neutral"})
COMPOSITE_TEXTURES = frozenset(
    {"redundant_join", "anomaly_redundant", "anomaly_join", "all_three"}
)
_REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = _REPO / "artifacts" / "phase3m"
RESULT_PATH = ARTIFACT_DIR / "conditional-routing.json"
RESULT_MD_PATH = ARTIFACT_DIR / "conditional-routing.md"
SAFETY_PATH = ARTIFACT_DIR / "composition-safety.json"
PHASE3L_PATH = _REPO / "artifacts" / "phase3l" / "redundancy-first-open.json"
POLICY_PY = _REPO / "src" / "bite_ingestion" / "policies" / "rule_policy.py"
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase3m-conditional-routing-freeze.json"
SPLIT_PATH = _REPO / "benchmarks" / "spec" / "phase3m-split-manifest.json"


def packet_from_surface(surface: Mapping[str, Any]) -> dict[str, Any]:
    refuse_evaluation(str(surface["case_id"]))
    texts = [str(text) for text in surface["unit_texts"]]
    ids = [str(uid) for uid in surface["unit_ids"]]
    uri = f"bitebench://{surface['case_id']}"
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
        "packet_id": str(surface["case_id"]),
        "document": document,
        "units": units,
        "visible_evidence": visible_evidence_from_units(units),
        "source_uri": uri,
    }


def _r_entries(packet: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    blob = packet.get("R")
    if not isinstance(blob, Mapping):
        return []
    raw = blob.get("entries") or []
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return [row for row in raw if isinstance(row, Mapping)]
    return []


def _ledger(packet: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = packet.get("irreversible_loss_ledger") or []
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return [row for row in raw if isinstance(row, Mapping)]
    return []


def _isolated_ids(packet: Mapping[str, Any]) -> list[str]:
    blob = packet.get("untangle")
    if not isinstance(blob, Mapping):
        return []
    out: list[str] = []
    for row in blob.get("isolated") or []:
        if isinstance(row, Mapping) and row.get("unit_id"):
            out.append(str(row["unit_id"]))
    return out


def _join_plans(packet: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    blob = packet.get("integrate")
    if not isinstance(blob, Mapping):
        return []
    raw = blob.get("join_plan") or []
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return [row for row in raw if isinstance(row, Mapping)]
    return []


def composition_safety(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    gold_ids: Sequence[str],
    sequence: Sequence[str],
) -> dict[str, Any]:
    visible = [dict(unit) for unit in after.get("units") or [] if isinstance(unit, Mapping)]
    input_units = [dict(unit) for unit in before.get("units") or [] if isinstance(unit, Mapping)]
    input_ids = [str(unit["unit_id"]) for unit in input_units]
    gold = {str(uid) for uid in gold_ids}
    roots = root_ids_of([str(unit["unit_id"]) for unit in visible], visible)
    recoverable = {
        str(row["unit_id"])
        for row in _r_entries(after)
        if row.get("unit_id") and row.get("recoverable") is True
    }
    lineage_recall = (
        1.0 if not gold else len(gold & (roots | recoverable)) / len(gold)
    )
    completeness = provenance_completeness(visible)
    untraced = conservation_untraced(
        input_ids,
        visible_units=visible,
        r_entries=_r_entries(after),
        loss_ledger=_ledger(after),
    )
    before_by_id = {str(unit["unit_id"]): str(unit.get("text", "")) for unit in input_units}
    audit = audit_undeclared_visible_loss(before, after)
    joined_ids: set[str] = set()
    for unit in visible:
        raw_joined = unit.get("joined_from") or []
        if isinstance(raw_joined, Sequence) and not isinstance(raw_joined, (str, bytes)):
            joined_ids.update(str(member) for member in raw_joined)
    for plan in _join_plans(after):
        joined_ids.update(str(uid) for uid in plan.get("unit_ids") or [])
    joined_texts = {before_by_id[uid] for uid in joined_ids if uid in before_by_id}
    undeclared_units = [
        uid for uid in audit["undeclared_units"] if uid not in joined_ids
    ]
    undeclared_texts = [
        text for text in audit["undeclared_texts"] if text not in joined_texts
    ]
    silent = len(undeclared_texts) + len(undeclared_units)
    isolated = set(_isolated_ids(after))
    quarantine_ok = all(
        str(row.get("unit_id")) not in isolated or row.get("recoverable") is True
        for row in _r_entries(after)
    ) and all(
        any(
            str(row.get("unit_id")) == uid and row.get("recoverable") is True
            for row in _r_entries(after)
        )
        for uid in isolated
    )

    ops = [str(op) for op in sequence]
    after_texts = Counter(str(unit.get("text", "")) for unit in visible)
    if "REDUCE" in ops:
        reduce_ok = all(count == 1 for count in after_texts.values())
    else:
        reduce_ok = True
        for text, n in Counter(before_by_id.values()).items():
            if n < 2:
                continue
            members = [uid for uid, body in before_by_id.items() if body == text]
            remaining = sum(1 for unit in visible if str(unit.get("text", "")) == text)
            consumed = sum(
                1
                for unit in visible
                for member in unit.get("joined_from") or []
                if str(member) in members
            )
            if remaining + consumed + len([uid for uid in members if uid in isolated]) < n:
                reduce_ok = False

    clusters = explicit_join_clusters(input_units)
    integrate_ok = True
    overmerge_ok = True
    if "INTEGRATE" in ops:
        alive_clusters = []
        for cluster in clusters:
            alive = [uid for uid in cluster["unit_ids"] if uid not in isolated]
            if len(alive) >= 2:
                alive_clusters.append(alive)
        joined = [row.get("unit_ids") or [] for row in _join_plans(after)]
        for alive in alive_clusters:
            if not any(set(alive) <= {str(uid) for uid in members} for members in joined):
                integrate_ok = False
        composite = [
            unit
            for unit in visible
            if isinstance(unit.get("joined_from"), list) and len(unit.get("joined_from") or []) >= 2
        ]
        if alive_clusters and not composite:
            integrate_ok = False
        for plan in _join_plans(after):
            members = [str(uid) for uid in plan.get("unit_ids") or []]
            keysets = [
                set(extract_explicit_join_keys(before_by_id.get(uid, "")))
                for uid in members
                if uid in before_by_id
            ]
            shared = set.intersection(*keysets) if keysets else set()
            if not shared or str(plan.get("method")) == "dependency_edge":
                overmerge_ok = False
    elif _join_plans(after):
        overmerge_ok = False
        integrate_ok = False

    checks = {
        "lineage_recall": lineage_recall == 1.0,
        "provenance_completeness": completeness == 1.0,
        "conservation_untraced": untraced == [],
        "silent_loss": silent == 0,
        "quarantine_recoverable": quarantine_ok,
        "reduce_only_exact_duplicates": reduce_ok,
        "integrate_explicit_join_composite": integrate_ok,
        "no_unrelated_overmerge": overmerge_ok,
    }
    return {
        "lineage_recall": lineage_recall,
        "provenance_completeness": completeness,
        "conservation_untraced": untraced,
        "silent_loss": silent,
        "quarantine_recoverable": quarantine_ok,
        "reduce_only_exact_duplicates": reduce_ok,
        "integrate_explicit_join_composite": integrate_ok,
        "no_unrelated_overmerge": overmerge_ok,
        "ok": all(checks.values()),
        "checks": checks,
        "token_proxy_before": estimate_tokens_char4(str(before.get("document") or "")),
        "token_proxy_after": estimate_tokens_char4(
            "\n".join(str(unit.get("text", "")) for unit in visible)
        ),
    }


def _premise_errors() -> list[str]:
    errs = validate_phase3m_freeze(freeze_manifest())
    errs.extend(validate_phase3m_split(split_manifest()))
    committed = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    if committed != freeze_manifest():
        errs.append("committed freeze drifted")
    split = json.loads(SPLIT_PATH.read_text(encoding="utf-8"))
    if split != split_manifest():
        errs.append("committed split drifted")
    if freeze_manifest().get("verdict") != PROTOCOL_FROZEN:
        errs.append("M0 freeze drifted")
    if freeze_manifest().get("revision") != REVISION:
        errs.append("M0 revision drifted")
    if not PHASE3L_PATH.is_file():
        errs.append("Phase 3L artifact missing")
    else:
        phase3l = json.loads(PHASE3L_PATH.read_text(encoding="utf-8"))
        if phase3l.get("verdict") != "PHASE3L_REDUNDANCY_HOLDOUT_CONFIRMED":
            errs.append("Phase 3L verdict rewritten")
    if "class RulePolicy" not in POLICY_PY.read_text(encoding="utf-8"):
        errs.append("RulePolicy missing")
    return errs


def _measure_row(surface: Mapping[str, Any], policy: ConditionalTexturePolicyV1) -> dict[str, Any]:
    refuse_evaluation(str(surface["case_id"]))
    packet = packet_from_surface(surface)
    assert_policy_gold_isolated(packet)
    payload = str(surface["payload"])
    disp = measure_dispersion({"payload": payload, "text": payload})
    decision = policy.explain_propose(packet)
    sequence = [op.value for op in decision.sequence]
    after = policy.apply(packet)
    safety = composition_safety(
        packet,
        after,
        gold_ids=list(surface["gold_unit_ids"]),
        sequence=sequence,
    )
    expect = list(expected_sequence(surface["texture"], surface["dispersion"]))
    return {
        "case_id": surface["case_id"],
        "generation": GENERATION,
        "texture": surface["texture"],
        "dispersion": surface["dispersion"],
        "replica": surface["replica"],
        "split": "development",
        "n_edges": disp.features["n_edges"],
        "mean_edge_distance": disp.features[LOCKED_FEATURE],
        "fail_closed": disp.fail_closed,
        "gate_notes": list(decision.notes),
        "predicates": [
            {
                "rule_id": fire.rule_id,
                "feature": fire.feature,
                "effect": fire.effect,
                "observed": fire.observed,
            }
            for fire in decision.rules_fired
        ],
        "sequence": sequence,
        "expected_sequence": expect,
        "sequence_ok": sequence == expect,
        "cut_present": "CUT" in sequence,
        "safety": safety,
        "safety_ok": safety["ok"],
        "ok": sequence == expect and safety["ok"] and "CUT" not in sequence,
    }


def _subset_ok(rows: list[dict[str, Any]], textures: frozenset[str]) -> bool:
    chosen = [
        row
        for row in rows
        if row["texture"] in textures and row["dispersion"] == "high"
    ]
    return bool(chosen) and all(row["ok"] for row in chosen)


def decide_verdict(
    *,
    blocked: list[str],
    rows: list[dict[str, Any]],
) -> str:
    if blocked:
        return VERDICT_BLOCKED
    if any(row.get("split") != "development" for row in rows):
        return VERDICT_BLOCKED
    if any(row.get("replica") not in CALIBRATION_REPLICAS for row in rows):
        return VERDICT_BLOCKED
    if any(row.get("cut_present") for row in rows):
        return VERDICT_BLOCKED
    if all(row.get("ok") for row in rows) and len(rows) == 48:
        return VERDICT_READY
    singles = _subset_ok(rows, SINGLE_TEXTURES)
    composites = _subset_ok(rows, COMPOSITE_TEXTURES)
    mid_low_ok = all(
        row["ok"] for row in rows if row["dispersion"] != "high"
    )
    if singles and mid_low_ok and not composites:
        return VERDICT_PARTIAL
    return VERDICT_BLOCKED


def run_experiment() -> dict[str, Any]:
    blocked = _premise_errors()
    rows: list[dict[str, Any]] = []
    policy = ConditionalTexturePolicyV1()
    try:
        for surface in development_surfaces():
            rows.append(_measure_row(surface, policy))
    except (PolicyLeakError, Exception) as exc:  # noqa: BLE001
        blocked.append(str(exc))
    ids = [str(row.get("case_id")) for row in rows]
    if ids != [
        cid
        for cid in planned_case_ids()
        if cid.endswith(("-r0", "-r1"))
    ]:
        blocked.append("development set mismatch")
    if len(rows) != 48:
        blocked.append(f"expected 48 rows, got {len(rows)}")
    blob = json.dumps(rows, sort_keys=True)
    if "p3f-" in blob:
        blocked.append("p3f identifier leaked")
    if any(
        "-r2" in str(row.get("case_id")) or "-r3" in str(row.get("case_id")) for row in rows
    ):
        blocked.append("p3m evaluation opened")
    verdict = decide_verdict(blocked=blocked, rows=rows)
    if verdict not in M1_VERDICTS:
        verdict = VERDICT_BLOCKED
        blocked.append("verdict not in frozen set")
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
        "revision": "phase3m-conditional-routing-v0.1",
        "protocol_revision": REVISION,
        "protocol_commit_sha": PROTOCOL_COMMIT_SHA,
        "verdict": verdict,
        "blocked_reasons": blocked,
        "paid_api": False,
        "offline": True,
        "synthetic": True,
        "research_conclusion": False,
        "p3f_evaluation_holdout_used": False,
        "p3m_evaluation_opened": False,
        "generation": GENERATION,
        "policy_name": POLICY_NAME,
        "rule_policy_changed": False,
        "rule_policy_executed": False,
        "routing_connected": True,
        "cut_in_conditional_map": False,
        "no_new_a_threshold": True,
        "no_new_k_threshold": True,
        "no_v1_edges_as_integrate_context": True,
        "v1_unchanged": True,
        "a_unchanged": True,
        "locked_from_phase3g": {
            "selected_candidate": LOCKED_CANDIDATE,
            "feature": LOCKED_FEATURE,
            "T_low": LOCKED_T_LOW,
            "T_high": LOCKED_T_HIGH,
        },
        "token_reduction": "diagnostic_only",
        "on_partial_or_blocked": "do not retune predicates or thresholds in this PR",
        "n_rows": len(rows),
        "n_ok": sum(1 for row in rows if row.get("ok")),
        "n_sequence_ok": sum(1 for row in rows if row.get("sequence_ok")),
        "n_safety_ok": sum(1 for row in rows if row.get("safety_ok")),
        "singles_ok": _subset_ok(rows, SINGLE_TEXTURES) if rows else False,
        "composites_ok": _subset_ok(rows, COMPOSITE_TEXTURES) if rows else False,
        "rows": rows,
        "composition_safety": {
            "schema": SAFETY_SCHEMA_ID,
            "keys": list(SAFETY_KEYS),
            "n_ok": sum(1 for row in safety_rows if row.get("ok")),
            "rows": safety_rows,
        },
        "evaluation_replicas_sealed": list(EVALUATION_REPLICAS),
    }


def validate_phase3m_result(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("protocol_commit_sha") != PROTOCOL_COMMIT_SHA:
        errs.append("protocol commit SHA mismatch")
    if doc.get("verdict") not in M1_VERDICTS:
        errs.append("verdict not in frozen set")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation opened")
    if doc.get("p3m_evaluation_opened") is not False:
        errs.append("p3m evaluation opened")
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
        if row.get("split") != "development":
            errs.append("non-development row")
        if row.get("replica") not in CALIBRATION_REPLICAS:
            errs.append("evaluation replica opened")
    return errs


def render_md(doc: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 3M gold-free conditional routing",
        "",
        f"verdict: `{doc.get('verdict')}`",
        f"protocol SHA: `{doc.get('protocol_commit_sha')}`",
        f"ok: {doc.get('n_ok')}/{doc.get('n_rows')}",
        f"policy: `{doc.get('policy_name')}`",
        "rule_policy_changed: `false`",
        "p3m evaluation: sealed",
        "p3f evaluation: sealed",
        "token_reduction: diagnostic only",
        "",
    ]
    reasons = list(doc.get("blocked_reasons") or [])
    if reasons:
        lines.append("blocked:")
        lines.extend(f"- {reason}" for reason in reasons)
        lines.append("")
    return "\n".join(lines)


def write_artifacts(doc: Mapping[str, Any] | None = None) -> tuple[Path, Path, Path]:
    if doc is None:
        doc = run_experiment()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    RESULT_MD_PATH.write_text(render_md(doc), encoding="utf-8")
    SAFETY_PATH.write_text(
        json.dumps(doc["composition_safety"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return RESULT_PATH, RESULT_MD_PATH, SAFETY_PATH


if __name__ == "__main__":
    write_artifacts()
