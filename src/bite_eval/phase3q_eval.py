"""Phase 3Q one-shot BITE-XFER-2 transfer evaluation.

Does not retune predicates, sensors, or operators. Does not import XFER-1 /
p3p / p3m generators. Does not open p3f. Does not rewrite Phase 3O/3P.
"""

from __future__ import annotations

import json
import subprocess
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

from bite_bench.phase3q import (
    CLAIM_BOUNDARY,
    FAILURE_CLASSES,
    FREEZE_PATH,
    LOCKED_BLOBS,
    LOCKED_BLOBS_PATH,
    N_SURFACES,
    O0_SHA,
    P3P_PRIMARY_BLOB,
    P3P_PRIMARY_PATH,
    PHASE3O_PATH,
    PHASE3O_VERDICT,
    PHASE3P_PATH,
    PREMISE,
    PROTOCOL_FROZEN,
    Q1_VERDICTS,
    VERDICT_BLOCKED,
    VERDICT_CONFIRMED,
    VERDICT_FAILED,
    corpus_hashes,
    derive_expected_sequence,
    refuse_p3f_evaluation,
    validate_phase3q_freeze,
)
from bite_bench.xfer2_corpus import (
    ANNOTATIONS_PATH,
    CORPUS_DIR,
    FORMATS,
    MANIFEST_PATH,
    forbidden_hits,
)
from bite_eval.composition_safety_v2 import composition_safety_v2
from bite_ingestion.adapters.bite_xfer2 import (
    assert_no_annotation_leak,
    packet_from_document,
)
from bite_ingestion.logical_record import LogicalRecordError, identity_of_text
from bite_ingestion.operators.integrate import IntegrateOperator
from bite_ingestion.operators.preflight import (
    explicit_join_clusters,
    routing_untangle_reasons,
)
from bite_ingestion.operators.reduce_v2 import LogicalReduceOperatorV2
from bite_ingestion.operators.untangle import UntangleOperator
from bite_ingestion.policies.conditional_texture_policy_v2 import (
    ConditionalTexturePolicyV2,
    PolicyLeakError,
    assert_policy_gold_isolated,
)
from bite_ingestion.profilers.dependency_dispersion_v1 import measure as measure_dispersion
from bite_ingestion.profilers.structural_redundancy_v2 import measure as measure_redundancy

SCHEMA_ID = "bite-phase3q-xfer2-transfer/v0.1"
CROSS_SCHEMA_ID = "bite-phase3q-cross-format/v0.1"
ACTION_SCHEMA_ID = "bite-phase3q-actionability/v0.1"
SAFETY_SCHEMA_ID = "bite-phase3q-composition-safety/v0.1"
INTERFERE_SCHEMA_ID = "bite-phase3q-operator-interference/v0.1"
FAIL_SCHEMA_ID = "bite-phase3q-failure-classification/v0.1"
PROTOCOL_COMMIT_SHA = "67bfd22f782c6663de6e977848a5a381cd62ae51"
LOCKED_T_HIGH = 4.0
_REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = _REPO / "artifacts" / "phase3q"
RESULT_PATH = ARTIFACT_DIR / "xfer2-transfer.json"
RESULT_MD_PATH = ARTIFACT_DIR / "xfer2-transfer.md"
CROSS_PATH = ARTIFACT_DIR / "cross-format.json"
ACTION_PATH = ARTIFACT_DIR / "actionability.json"
SAFETY_PATH = ARTIFACT_DIR / "composition-safety.json"
INTERFERE_PATH = ARTIFACT_DIR / "operator-interference.json"
FAIL_PATH = ARTIFACT_DIR / "failure-classification.json"
ADVERSARIAL_CASES = {"xfer2-q025", "xfer2-q026", "xfer2-q027", "xfer2-q028"}


def _git_blob(path: str) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", f"HEAD:{path}"],
        cwd=_REPO,
        text=True,
    ).strip()


def _units(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = packet.get("units") or []
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return [dict(unit) for unit in raw if isinstance(unit, Mapping)]
    return []


def _ident(text: str) -> tuple[str, str] | None:
    try:
        return identity_of_text(text)
    except LogicalRecordError:
        return None


def _isolated_ids(packet: Mapping[str, Any]) -> set[str]:
    blob = packet.get("untangle")
    if not isinstance(blob, Mapping):
        return set()
    out: set[str] = set()
    for row in blob.get("isolated") or []:
        if isinstance(row, Mapping) and row.get("unit_id"):
            out.add(str(row["unit_id"]))
    return out


def _recoverable_ids(packet: Mapping[str, Any]) -> set[str]:
    blob = packet.get("R")
    if not isinstance(blob, Mapping):
        return set()
    out: set[str] = set()
    for row in blob.get("entries") or []:
        if isinstance(row, Mapping) and row.get("unit_id") and row.get("recoverable") is True:
            out.add(str(row["unit_id"]))
    return out


def _composites(packet: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        unit
        for unit in _units(packet)
        if isinstance(unit.get("joined_from"), list) and len(unit.get("joined_from") or []) >= 2
    ]


def _has_logical_dups(units: Sequence[Mapping[str, Any]]) -> bool:
    counts: Counter[tuple[str, str]] = Counter()
    for unit in units:
        ident = _ident(str(unit.get("text", "")))
        if ident is not None:
            counts[ident] += 1
    return any(count >= 2 for count in counts.values())


def _alive_join(units: Sequence[Mapping[str, Any]], isolated: set[str]) -> bool:
    for cluster in explicit_join_clusters(units):
        alive = [uid for uid in cluster["unit_ids"] if uid not in isolated]
        if len(alive) >= 2:
            return True
    return False


def _apply_op(packet: Mapping[str, Any], op: str) -> dict[str, Any]:
    if op == "UNTANGLE":
        return dict(UntangleOperator().apply(packet))
    if op == "REDUCE_v2":
        return dict(LogicalReduceOperatorV2().apply(packet))
    if op == "INTEGRATE":
        return dict(IntegrateOperator().apply(packet))
    raise PolicyLeakError(f"forbidden operator {op}")


def _interference(before: Mapping[str, Any], expect: Sequence[str]) -> bool:
    if not expect:
        return False
    current = deepcopy(dict(before))
    isolated: set[str] = set()
    for index, op in enumerate(expect):
        units = _units(current)
        isolated |= _isolated_ids(current)
        actionable = True
        if op == "UNTANGLE":
            actionable = any(
                routing_untangle_reasons(str(unit.get("text", ""))) for unit in units
            )
        elif op == "REDUCE_v2":
            actionable = _has_logical_dups(units)
        elif op == "INTEGRATE":
            actionable = _alive_join(units, isolated)
        if index > 0 and not actionable:
            return True
        current = _apply_op(current, op)
    return False


def _actionability(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    sequence: Sequence[str],
    annotation: Mapping[str, Any],
) -> dict[str, Any]:
    ops = [str(op) for op in sequence]
    before_by_id = {
        str(unit["unit_id"]): unit for unit in _units(before) if unit.get("unit_id")
    }
    after_idents: Counter[tuple[str, str]] = Counter()
    for unit in _units(after):
        ident = _ident(str(unit.get("text", "")))
        if ident is not None:
            after_idents[ident] += 1
    reduce_ok = True
    sensor_mismatch = False
    groups = list(annotation.get("duplicate_groups") or [])
    if "REDUCE_v2" in ops:
        for group in groups:
            idents = [
                _ident(str(before_by_id.get(str(uid), {}).get("text", ""))) for uid in group
            ]
            if any(item is None for item in idents) or len(set(idents)) != 1:
                reduce_ok = False
                continue
            ident = idents[0]
            assert ident is not None
            before_n = sum(
                1
                for uid in group
                if _ident(str(before_by_id.get(str(uid), {}).get("text", ""))) == ident
            )
            if before_n < 2 or after_idents.get(ident, 0) > 1:
                reduce_ok = False
        if groups and not reduce_ok:
            sensor_mismatch = True
    anomaly_ids = [str(uid) for uid in list(annotation.get("anomaly_unit_ids") or [])]
    isolated = _isolated_ids(after)
    recoverable = _recoverable_ids(after)
    untangle_ok = True
    if "UNTANGLE" in ops:
        untangle_ok = bool(anomaly_ids) and all(
            uid in isolated and uid in recoverable for uid in anomaly_ids
        )
    integrate_ok = True
    join_groups = list(annotation.get("explicit_join_groups") or [])
    if "INTEGRATE" in ops:
        integrate_ok = bool(join_groups) and bool(_composites(after))
    ok = reduce_ok and untangle_ok and integrate_ok
    return {
        "reduce_realizes_logical_duplicates": reduce_ok,
        "untangle_quarantines_anomaly": untangle_ok,
        "integrate_makes_explicit_cluster": integrate_ok,
        "sensor_operator_mismatch": sensor_mismatch,
        "n_duplicate_groups": len(groups),
        "n_anomaly_units": len(anomaly_ids),
        "n_join_groups": len(join_groups),
        "ok": ok,
    }


def _row_failure_classes(
    *,
    sequence_ok: bool,
    gate_ok: bool,
    safety_ok: bool,
    action: Mapping[str, Any],
    interference: bool,
    cut: bool,
) -> list[str]:
    classes: list[str] = []
    if action.get("sensor_operator_mismatch"):
        classes.append("sensor_operator_mismatch")
    if interference:
        classes.append("operator_interference")
    if not safety_ok:
        classes.append("composition_safety")
    leftover = (not sequence_ok) or (not gate_ok) or cut or (not action.get("ok"))
    if leftover and not classes:
        classes.append("other")
    return classes


def _premise_errors() -> list[str]:
    errs: list[str] = []
    if not FREEZE_PATH.is_file():
        return ["Q0 freeze missing"]
    committed = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    errs.extend(validate_phase3q_freeze(committed))
    if committed.get("verdict") != PROTOCOL_FROZEN:
        errs.append("protocol not frozen")
    if dict(committed.get("corpus_hashes") or {}) != corpus_hashes():
        errs.append("corpus hashes drifted")
    if not PHASE3O_PATH.is_file():
        errs.append("Phase 3O artifact missing")
    else:
        phase3o = json.loads(PHASE3O_PATH.read_text(encoding="utf-8"))
        if phase3o.get("verdict") != PHASE3O_VERDICT:
            errs.append("Phase 3O verdict rewritten")
    if not PHASE3P_PATH.is_file():
        errs.append("Phase 3P artifact missing")
    else:
        phase3p = json.loads(PHASE3P_PATH.read_text(encoding="utf-8"))
        if phase3p.get("verdict") != PREMISE:
            errs.append("Phase 3P verdict rewritten")
    if not LOCKED_BLOBS_PATH.is_file():
        errs.append("3Q locked blobs missing")
    for path, expected in LOCKED_BLOBS.items():
        try:
            observed = _git_blob(str(path))
        except Exception as exc:  # noqa: BLE001
            errs.append(f"blob check failed {path}: {exc}")
            continue
        if observed != expected:
            errs.append(f"frozen blob drifted: {path}")
    try:
        p3p_blob = _git_blob(P3P_PRIMARY_PATH)
    except Exception as exc:  # noqa: BLE001
        errs.append(f"Phase 3P artifact blob check failed: {exc}")
        p3p_blob = ""
    if p3p_blob and p3p_blob != P3P_PRIMARY_BLOB:
        errs.append("Phase 3P primary artifact drifted")
    return errs


def _iter_surfaces() -> list[dict[str, Any]]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    anns = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))["annotations"]
    surfaces: list[dict[str, Any]] = []
    for row in manifest["surfaces"]:
        cid = str(row["case_id"])
        fmt = str(row["format"])
        refuse_p3f_evaluation(cid)
        rel = str(row["path"])
        document = (CORPUS_DIR / rel).read_text(encoding="utf-8")
        surfaces.append(
            {
                "surface_id": row["surface_id"],
                "case_id": cid,
                "format": fmt,
                "path": rel,
                "document": document,
                "annotation": anns[cid],
            }
        )
    return surfaces


def _measure_row(
    surface: Mapping[str, Any], policy: ConditionalTexturePolicyV2
) -> dict[str, Any]:
    cid = str(surface["case_id"])
    fmt = str(surface["format"])
    refuse_p3f_evaluation(cid)
    if forbidden_hits(str(surface["document"])):
        raise PolicyLeakError(f"gold leak in corpus body {cid}")
    packet = packet_from_document(str(surface["document"]), case_id=cid, fmt=fmt)
    assert_no_annotation_leak(packet)
    assert_policy_gold_isolated(packet)
    payload = str(packet["document"])
    disp = measure_dispersion({"payload": payload, "text": payload})
    red = measure_redundancy({"payload": payload, "text": payload})
    n_edges = float(disp.features["n_edges"])
    mean = float(disp.features["mean_edge_distance"])
    ratio = float(red.features["duplicate_unit_ratio"])
    gated = (not disp.fail_closed) and n_edges > 0.0 and mean >= LOCKED_T_HIGH
    decision = policy.explain_propose(packet)
    sequence = [op.value for op in decision.sequence]
    after = policy.apply(packet)
    annotation = dict(surface["annotation"])
    expect = derive_expected_sequence(annotation)
    intended = str(annotation["intended_dispersion"])
    high = intended == "high"
    gate_ok = gated if high else not gated
    safety = composition_safety_v2(
        packet,
        after,
        gold_ids=list(annotation["required_evidence_ids"]),
        sequence=sequence,
    )
    action = _actionability(packet, after, sequence=sequence, annotation=annotation)
    interference = _interference(packet, expect)
    preds = {fire.rule_id: fire.effect == "include" for fire in decision.rules_fired}
    sequence_ok = sequence == expect
    cut = "CUT" in sequence
    safety_ok = bool(safety["ok"])
    classes = _row_failure_classes(
        sequence_ok=sequence_ok,
        gate_ok=gate_ok,
        safety_ok=safety_ok,
        action=action,
        interference=interference,
        cut=cut,
    )
    ok = (
        sequence_ok
        and gate_ok
        and safety_ok
        and bool(action["ok"])
        and not cut
        and not interference
    )
    return {
        "surface_id": surface["surface_id"],
        "case_id": cid,
        "format": fmt,
        "intended_dispersion": intended,
        "adversarial": cid in ADVERSARIAL_CASES,
        "n_edges": n_edges,
        "mean_edge_distance": mean,
        "fail_closed": disp.fail_closed,
        "gated": gated,
        "gate_ok": gate_ok,
        "n_edges_eq_0": n_edges == 0.0,
        "duplicate_unit_ratio": ratio,
        "redundancy_fail_closed": red.fail_closed,
        "predicates": {
            "UNTANGLE": bool(preds.get("pred.UNTANGLE")),
            "REDUCE_v2": bool(preds.get("pred.REDUCE_v2")),
            "INTEGRATE": bool(preds.get("pred.INTEGRATE")),
        },
        "sequence": sequence,
        "expected_sequence": expect,
        "sequence_ok": sequence_ok,
        "cut_present": cut,
        "operator_interference": interference,
        "safety": safety,
        "safety_ok": safety_ok,
        "actionability": action,
        "actionability_ok": action["ok"],
        "failure_classes": classes,
        "ok": ok,
    }


def _cross_format(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_case[str(row["case_id"])].append(row)
    out_rows: list[dict[str, Any]] = []
    classes: list[str] = []
    for cid, group in sorted(by_case.items()):
        seqs = {str(row["format"]): list(row["sequence"]) for row in group}
        gates = {str(row["format"]): bool(row["gated"]) for row in group}
        preds = {str(row["format"]): dict(row["predicates"]) for row in group}
        seq_ok = len({tuple(seq) for seq in seqs.values()}) == 1
        gate_ok = len(set(gates.values())) == 1
        pred_ok = len({tuple(sorted(p.items())) for p in preds.values()}) == 1
        row_classes: list[str] = []
        if not gate_ok:
            row_classes.append("gate_format_dependence")
        if gate_ok and not pred_ok:
            row_classes.append("predicate_format_dependence")
        if not seq_ok and not row_classes:
            row_classes.append("predicate_format_dependence")
        classes.extend(row_classes)
        out_rows.append(
            {
                "case_id": cid,
                "sequences": seqs,
                "gated": gates,
                "predicates": preds,
                "sequence_identity": seq_ok,
                "gate_identity": gate_ok,
                "predicate_identity": pred_ok,
                "ok": seq_ok and gate_ok and pred_ok,
                "failure_classes": row_classes,
            }
        )
    return {
        "schema": CROSS_SCHEMA_ID,
        "n_ok": sum(1 for row in out_rows if row["ok"]),
        "n_cases": len(out_rows),
        "failure_classes": sorted(set(classes)),
        "rows": out_rows,
    }


def run_evaluation() -> dict[str, Any]:
    blocked = _premise_errors()
    rows: list[dict[str, Any]] = []
    policy = ConditionalTexturePolicyV2()
    try:
        surfaces = _iter_surfaces()
        if len(surfaces) != N_SURFACES:
            blocked.append(f"expected {N_SURFACES} surfaces, got {len(surfaces)}")
        for surface in surfaces:
            rows.append(_measure_row(surface, policy))
    except (PolicyLeakError, Exception) as exc:  # noqa: BLE001
        blocked.append(str(exc))
    blob = json.dumps(rows, sort_keys=True)
    if "p3f-" in blob:
        blocked.append("p3f identifier leaked")
    cross: dict[str, Any]
    if rows:
        cross = _cross_format(rows)
    else:
        cross = {
            "schema": CROSS_SCHEMA_ID,
            "n_ok": 0,
            "n_cases": 0,
            "failure_classes": [],
            "rows": [],
        }
    routing_ok = bool(rows) and all(row.get("sequence_ok") and row.get("gate_ok") for row in rows)
    safety_ok = bool(rows) and all(row.get("safety_ok") for row in rows)
    action_ok = bool(rows) and all(row.get("actionability_ok") for row in rows)
    no_cut = bool(rows) and not any(row.get("cut_present") for row in rows)
    no_interference = bool(rows) and not any(row.get("operator_interference") for row in rows)
    cross_rows = list(cross.get("rows") or [])
    cross_ok = bool(cross_rows) and all(row.get("ok") for row in cross_rows)
    cross_fail = [str(item) for item in list(cross.get("failure_classes") or [])]
    adversarial_ok = bool(rows) and all(
        row.get("ok") for row in rows if row.get("case_id") in ADVERSARIAL_CASES
    )
    checks = {
        "n_112": len(rows) == N_SURFACES,
        "sequence_exact": routing_ok,
        "composition_safety": safety_ok,
        "actionability": action_ok,
        "cross_format_identity": cross_ok,
        "no_cut": no_cut,
        "no_operator_interference": no_interference,
        "adversarial_composition": adversarial_ok,
        "frozen_blobs": not any("blob drifted" in item for item in blocked),
        "corpus_unchanged": not any("hashes drifted" in item for item in blocked),
        "p3f_sealed": not any("p3f" in item.lower() for item in blocked),
        "phase3o_failed_unchanged": not any("Phase 3O" in item for item in blocked),
    }
    row_classes = [cls for row in rows for cls in row.get("failure_classes") or []]
    fail_classes = sorted(set(row_classes) | set(cross_fail))
    if blocked:
        verdict = VERDICT_BLOCKED
    elif all(checks.values()) and all(row.get("ok") for row in rows) and not fail_classes:
        verdict = VERDICT_CONFIRMED
    else:
        verdict = VERDICT_FAILED
    if verdict not in Q1_VERDICTS:
        verdict = VERDICT_BLOCKED
        blocked.append("verdict not in frozen set")
    safety_rows = [
        {
            "surface_id": row["surface_id"],
            "case_id": row["case_id"],
            "format": row["format"],
            "sequence": row["sequence"],
            **row["safety"],
        }
        for row in rows
    ]
    action_rows = [
        {
            "surface_id": row["surface_id"],
            "case_id": row["case_id"],
            "format": row["format"],
            "sequence": row["sequence"],
            **row["actionability"],
        }
        for row in rows
    ]
    interfere_rows = [
        {
            "surface_id": row["surface_id"],
            "case_id": row["case_id"],
            "format": row["format"],
            "sequence": row["sequence"],
            "expected_sequence": row["expected_sequence"],
            "operator_interference": row["operator_interference"],
            "ok": not row["operator_interference"],
        }
        for row in rows
    ]
    return {
        "schema": SCHEMA_ID,
        "revision": "phase3q-xfer2-transfer-v0.1",
        "protocol_revision": "phase3q-xfer2-freeze-v0.1",
        "protocol_commit_sha": PROTOCOL_COMMIT_SHA,
        "phase3p_head_sha": "833bb56eec52260bc9a424e6d0ad8af397eb2604",
        "phase3o_o0_sha": O0_SHA,
        "verdict": verdict,
        "blocked_reasons": blocked,
        "paid_api": False,
        "offline": True,
        "synthetic": True,
        "research_conclusion": False,
        "p3f_evaluation_holdout_used": False,
        "calibration": False,
        "development_split": False,
        "policy_name": "conditional_texture_policy_v2",
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": ["real-world corpus generalization", "BITE superiority"],
        "rule_policy_changed": False,
        "rule_policy_executed": False,
        "cut_in_conditional_map": False,
        "predicate_unchanged": True,
        "threshold_unchanged": True,
        "sensor_unchanged": True,
        "operator_unchanged": True,
        "corpus_unchanged": True,
        "no_xfer1_generator_import": True,
        "no_p3p_generator_import": True,
        "no_p3m_import": True,
        "phase3o_verdict_unchanged": True,
        "token_reduction": "diagnostic_only",
        "no_winner_score": True,
        "on_failed": "do not retune predicates, sensors, or operators in this PR",
        "failure_classes": fail_classes if verdict == VERDICT_FAILED else [],
        "n_rows": len(rows),
        "n_ok": sum(1 for row in rows if row.get("ok")),
        "n_sequence_ok": sum(1 for row in rows if row.get("sequence_ok")),
        "n_safety_ok": sum(1 for row in rows if row.get("safety_ok")),
        "n_actionability_ok": sum(1 for row in rows if row.get("actionability_ok")),
        "n_gate_ok": sum(1 for row in rows if row.get("gate_ok")),
        "n_interference": sum(1 for row in rows if row.get("operator_interference")),
        "checks": checks,
        "rows": rows,
        "cross_format": cross,
        "actionability": {
            "schema": ACTION_SCHEMA_ID,
            "n_ok": sum(1 for row in action_rows if row.get("ok")),
            "rows": action_rows,
        },
        "composition_safety": {
            "schema": SAFETY_SCHEMA_ID,
            "n_ok": sum(1 for row in safety_rows if row.get("ok")),
            "rows": safety_rows,
        },
        "operator_interference": {
            "schema": INTERFERE_SCHEMA_ID,
            "n_ok": sum(1 for row in interfere_rows if row.get("ok")),
            "rows": interfere_rows,
        },
        "failure_classification": {
            "schema": FAIL_SCHEMA_ID,
            "classes": fail_classes if verdict == VERDICT_FAILED else [],
            "allowed": list(FAILURE_CLASSES),
        },
        "formats": list(FORMATS),
    }


def validate_phase3q_result(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("protocol_commit_sha") != PROTOCOL_COMMIT_SHA:
        errs.append("protocol commit SHA mismatch")
    if doc.get("verdict") not in Q1_VERDICTS:
        errs.append("verdict not in frozen set")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation opened")
    if doc.get("rule_policy_changed") is not False:
        errs.append("RulePolicy changed")
    if doc.get("rule_policy_executed") is not False:
        errs.append("RulePolicy executed")
    if doc.get("cut_in_conditional_map") is not False:
        errs.append("CUT entered the map")
    if doc.get("calibration") is not False:
        errs.append("calibration ran")
    blob = json.dumps(doc, sort_keys=True)
    if "p3f-" in blob:
        errs.append("p3f identifier leaked")
    if doc.get("verdict") == VERDICT_FAILED:
        classes = list(doc.get("failure_classes") or [])
        if not classes:
            errs.append("FAILED missing failure_classes")
        if any(item not in FAILURE_CLASSES for item in classes):
            errs.append("unknown failure_class")
    for row in doc.get("rows") or []:
        cid = str(row.get("case_id", ""))
        if not cid.startswith("xfer2-q"):
            errs.append(f"non-xfer2 case {cid}")
        if "expected_sequence" in (row.get("annotation") or {}):
            errs.append("annotation leak into row")
    return errs


def render_md(doc: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 3Q BITE-XFER-2 transfer",
        "",
        f"verdict: `{doc.get('verdict')}`",
        f"Q0 SHA: `{doc.get('protocol_commit_sha')}`",
        f"ok: {doc.get('n_ok')}/{doc.get('n_rows')}",
        f"claim: `{doc.get('claim_boundary')}`",
        "rule_policy_executed: `false`",
        "p3f evaluation: sealed",
        "token_reduction: diagnostic only",
        "Phase3O remains FAILED; known failures are repaired in development.",
        "",
        "## Checks",
        "",
    ]
    for key, ok in dict(doc.get("checks") or {}).items():
        lines.append(f"- {key}: `{ok}`")
    classes = list(doc.get("failure_classes") or [])
    if classes:
        lines.extend(["", "## failure_class", ""])
        lines.extend(f"- `{item}`" for item in classes)
    lines.extend(["", "real-world generalization / BITE superiority ではない。", ""])
    reasons = list(doc.get("blocked_reasons") or [])
    if reasons:
        lines.append("blocked:")
        lines.extend(f"- {reason}" for reason in reasons)
        lines.append("")
    return "\n".join(lines)


def write_artifacts(doc: Mapping[str, Any] | None = None) -> tuple[Path, ...]:
    if doc is None:
        doc = run_evaluation()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    RESULT_MD_PATH.write_text(render_md(doc), encoding="utf-8")
    CROSS_PATH.write_text(
        json.dumps(doc["cross_format"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    ACTION_PATH.write_text(
        json.dumps(doc["actionability"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    SAFETY_PATH.write_text(
        json.dumps(doc["composition_safety"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    INTERFERE_PATH.write_text(
        json.dumps(doc["operator_interference"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    FAIL_PATH.write_text(
        json.dumps(doc["failure_classification"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return RESULT_PATH, CROSS_PATH, ACTION_PATH, SAFETY_PATH, INTERFERE_PATH, FAIL_PATH


if __name__ == "__main__":
    write_artifacts()
