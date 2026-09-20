"""Phase 3O one-shot BITE-XFER-1 transfer evaluation.

Does not retune predicates, sensors, or operators. Does not import phase3m
to build corpus. Does not open p3f. Does not change RulePolicy.
"""

from __future__ import annotations

import json
import subprocess
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bite_bench.phase3o import (
    CLAIM_BOUNDARY,
    FAILURE_CLASSES,
    FREEZE_PATH,
    N3_SHA,
    N_SURFACES,
    O1_VERDICTS,
    PROTOCOL_FROZEN,
    VERDICT_BLOCKED,
    VERDICT_CONFIRMED,
    VERDICT_FAILED,
    corpus_hashes,
    derive_expected_sequence,
    refuse_p3f_evaluation,
    validate_phase3o_freeze,
)
from bite_bench.xfer1_corpus import (
    ANNOTATIONS_PATH,
    CORPUS_DIR,
    FORMATS,
    MANIFEST_PATH,
    forbidden_hits,
)
from bite_eval.phase3m_eval import composition_safety
from bite_ingestion.adapters.bite_xfer1 import (
    assert_no_annotation_leak,
    packet_from_document,
)
from bite_ingestion.operators.preflight import (
    explicit_join_clusters,
    routing_untangle_reasons,
)
from bite_ingestion.policies.conditional_texture_policy_v1 import (
    ConditionalTexturePolicyV1,
    PolicyLeakError,
    assert_policy_gold_isolated,
)
from bite_ingestion.profilers.dependency_dispersion_v1 import measure as measure_dispersion
from bite_ingestion.profilers.structural_redundancy_v1 import measure as measure_redundancy

SCHEMA_ID = "bite-phase3o-xfer1-transfer/v0.1"
CROSS_SCHEMA_ID = "bite-phase3o-cross-format/v0.1"
ACTION_SCHEMA_ID = "bite-phase3o-actionability/v0.1"
SAFETY_SCHEMA_ID = "bite-phase3o-composition-safety/v0.1"
FAIL_SCHEMA_ID = "bite-phase3o-failure-classification/v0.1"
PROTOCOL_COMMIT_SHA = "76998156d3cbf67fc0a53e151688e46bd3c26dc7"
LOCKED_T_HIGH = 4.0
LOCKED_BLOBS_PATH = Path(__file__).resolve().parents[2] / "benchmarks" / "spec" / "phase3n-locked-blobs.json"
PHASE3N_PATH = Path(__file__).resolve().parents[2] / "artifacts" / "phase3n" / "conditional-routing-first-open.json"
_REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = _REPO / "artifacts" / "phase3o"
RESULT_PATH = ARTIFACT_DIR / "xfer1-transfer.json"
RESULT_MD_PATH = ARTIFACT_DIR / "xfer1-transfer.md"
CROSS_PATH = ARTIFACT_DIR / "cross-format.json"
ACTION_PATH = ARTIFACT_DIR / "actionability.json"
SAFETY_PATH = ARTIFACT_DIR / "composition-safety.json"
FAIL_PATH = ARTIFACT_DIR / "failure-classification.json"


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


def _logical_pair(text: str, fmt: str) -> tuple[str, str] | None:
    if fmt == "key_value":
        if "=" not in text:
            return None
        key, _, value = text.partition("=")
        return key, value
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if isinstance(obj, dict) and "k" in obj and "v" in obj:
        return str(obj["k"]), str(obj["v"])
    return None


def _logical_counts(
    units: Sequence[Mapping[str, Any]], fmt: str
) -> tuple[Counter[tuple[str, str]], dict[tuple[str, str], set[str]]]:
    counts: Counter[tuple[str, str]] = Counter()
    texts: dict[tuple[str, str], set[str]] = defaultdict(set)
    for unit in units:
        pair = _logical_pair(str(unit.get("text", "")), fmt)
        if pair is None:
            continue
        counts[pair] += 1
        texts[pair].add(str(unit.get("text", "")))
    return counts, texts


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


def _actionability(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    fmt: str,
    sequence: Sequence[str],
    annotation: Mapping[str, Any],
) -> dict[str, Any]:
    ops = [str(op) for op in sequence]
    before_units = _units(before)
    after_units = _units(after)
    before_counts, before_texts = _logical_counts(before_units, fmt)
    after_counts, _after_texts = _logical_counts(after_units, fmt)
    dup_pairs = {pair: n for pair, n in before_counts.items() if n >= 2}
    sensor_mismatch = False
    reduce_ok = True
    if "REDUCE" in ops:
        reduce_ok = all(after_counts.get(pair, 0) <= 1 for pair in dup_pairs)
        if annotation.get("has_exact_duplicate") and not dup_pairs:
            reduce_ok = False
        if not reduce_ok and any(len(before_texts[pair]) > 1 for pair in dup_pairs):
            sensor_mismatch = True
    anomaly_ids = [
        str(unit["unit_id"])
        for unit in before_units
        if routing_untangle_reasons(str(unit.get("text", "")))
    ]
    isolated = _isolated_ids(after)
    recoverable = _recoverable_ids(after)
    untangle_ok = True
    if "UNTANGLE" in ops:
        untangle_ok = bool(anomaly_ids) and all(
            uid in isolated and uid in recoverable for uid in anomaly_ids
        )
        if annotation.get("has_quarantinable_anomaly") and not anomaly_ids:
            untangle_ok = False
    integrate_ok = True
    if "INTEGRATE" in ops:
        clusters = explicit_join_clusters(before_units)
        integrate_ok = bool(clusters) and bool(_composites(after))
        if annotation.get("has_explicit_join_cluster") and not clusters:
            integrate_ok = False
    ok = reduce_ok and untangle_ok and integrate_ok
    return {
        "reduce_realizes_logical_duplicates": reduce_ok,
        "untangle_quarantines_anomaly": untangle_ok,
        "integrate_makes_explicit_cluster": integrate_ok,
        "sensor_operator_mismatch": sensor_mismatch,
        "n_logical_duplicate_pairs": len(dup_pairs),
        "n_anomaly_units": len(anomaly_ids),
        "ok": ok,
    }


def _row_failure_classes(
    *,
    sequence_ok: bool,
    gate_ok: bool,
    safety_ok: bool,
    action: Mapping[str, Any],
    cut: bool,
) -> list[str]:
    classes: list[str] = []
    if action.get("sensor_operator_mismatch"):
        classes.append("sensor_operator_mismatch")
    if not safety_ok:
        classes.append("composition_safety")
    leftover = (not sequence_ok) or (not gate_ok) or cut or (not action.get("ok"))
    if leftover and not classes:
        classes.append("other")
    return classes


def _premise_errors() -> list[str]:
    errs: list[str] = []
    if not FREEZE_PATH.is_file():
        return ["O0 freeze missing"]
    committed = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    errs.extend(validate_phase3o_freeze(committed))
    if committed.get("verdict") != PROTOCOL_FROZEN:
        errs.append("protocol not frozen")
    if dict(committed.get("corpus_hashes") or {}) != corpus_hashes():
        errs.append("corpus hashes drifted")
    if not PHASE3N_PATH.is_file():
        errs.append("Phase 3N artifact missing")
    else:
        phase3n = json.loads(PHASE3N_PATH.read_text(encoding="utf-8"))
        if phase3n.get("verdict") != "PHASE3N_CONDITIONAL_ROUTING_HOLDOUT_CONFIRMED":
            errs.append("Phase 3N verdict rewritten")
    if not LOCKED_BLOBS_PATH.is_file():
        errs.append("3N locked blobs missing")
    else:
        locked = json.loads(LOCKED_BLOBS_PATH.read_text(encoding="utf-8")).get("git_blob_sha") or {}
        for path, expected in locked.items():
            try:
                observed = _git_blob(str(path))
            except Exception as exc:  # noqa: BLE001
                errs.append(f"blob check failed {path}: {exc}")
                continue
            if observed != expected:
                errs.append(f"frozen blob drifted: {path}")
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
    surface: Mapping[str, Any], policy: ConditionalTexturePolicyV1
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
    safety = composition_safety(
        packet,
        after,
        gold_ids=list(annotation["required_evidence_ids"]),
        sequence=sequence,
    )
    action = _actionability(
        packet, after, fmt=fmt, sequence=sequence, annotation=annotation
    )
    preds = {
        fire.rule_id: fire.effect == "include" for fire in decision.rules_fired
    }
    sequence_ok = sequence == expect
    cut = "CUT" in sequence
    safety_ok = bool(safety["ok"])
    classes = _row_failure_classes(
        sequence_ok=sequence_ok,
        gate_ok=gate_ok,
        safety_ok=safety_ok,
        action=action,
        cut=cut,
    )
    ok = sequence_ok and gate_ok and safety_ok and bool(action["ok"]) and not cut
    return {
        "surface_id": surface["surface_id"],
        "case_id": cid,
        "format": fmt,
        "intended_dispersion": intended,
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
            "REDUCE": bool(preds.get("pred.REDUCE")),
            "INTEGRATE": bool(preds.get("pred.INTEGRATE")),
        },
        "sequence": sequence,
        "expected_sequence": expect,
        "sequence_ok": sequence_ok,
        "cut_present": cut,
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
    policy = ConditionalTexturePolicyV1()
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
    if any(forbidden_hits(str(row.get("case_id", ""))) for row in rows):
        blocked.append("forbidden identifier in case id")
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
    cross_rows = list(cross.get("rows") or [])
    cross_ok = bool(cross_rows) and all(row.get("ok") for row in cross_rows)
    cross_fail = [str(item) for item in list(cross.get("failure_classes") or [])]
    checks = {
        "n_104": len(rows) == N_SURFACES,
        "sequence_exact": routing_ok,
        "composition_safety": safety_ok,
        "actionability": action_ok,
        "cross_format_sequence": cross_ok,
        "no_cut": no_cut,
        "frozen_blobs": not any("blob drifted" in item for item in blocked),
        "corpus_unchanged": not any("hashes drifted" in item for item in blocked),
        "p3f_sealed": not any("p3f" in item.lower() for item in blocked),
    }
    row_classes = [cls for row in rows for cls in row.get("failure_classes") or []]
    fail_classes = sorted(set(row_classes) | set(cross_fail))
    if blocked:
        verdict = VERDICT_BLOCKED
    elif all(checks.values()) and all(row.get("ok") for row in rows) and not fail_classes:
        verdict = VERDICT_CONFIRMED
    else:
        verdict = VERDICT_FAILED
    if verdict not in O1_VERDICTS:
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
    return {
        "schema": SCHEMA_ID,
        "revision": "phase3o-xfer1-transfer-v0.1",
        "protocol_revision": "phase3o-xfer1-freeze-v0.1",
        "protocol_commit_sha": PROTOCOL_COMMIT_SHA,
        "n3_commit_sha": N3_SHA,
        "verdict": verdict,
        "blocked_reasons": blocked,
        "paid_api": False,
        "offline": True,
        "synthetic": True,
        "research_conclusion": False,
        "p3f_evaluation_holdout_used": False,
        "calibration": False,
        "policy_name": "conditional_texture_policy_v1",
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
        "no_phase3m_corpus_import": True,
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
        "failure_classification": {
            "schema": FAIL_SCHEMA_ID,
            "classes": fail_classes if verdict == VERDICT_FAILED else [],
            "allowed": list(FAILURE_CLASSES),
        },
        "formats": list(FORMATS),
    }


def validate_phase3o_result(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("protocol_commit_sha") != PROTOCOL_COMMIT_SHA:
        errs.append("protocol commit SHA mismatch")
    if doc.get("verdict") not in O1_VERDICTS:
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
        if not cid.startswith("xfer1-c"):
            errs.append(f"non-xfer1 case {cid}")
        if "expected_sequence" in (row.get("annotation") or {}):
            errs.append("annotation leak into row")
    return errs


def render_md(doc: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 3O BITE-XFER-1 transfer",
        "",
        f"verdict: `{doc.get('verdict')}`",
        f"O0 SHA: `{doc.get('protocol_commit_sha')}`",
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
    FAIL_PATH.write_text(
        json.dumps(doc["failure_classification"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return RESULT_PATH, CROSS_PATH, ACTION_PATH, SAFETY_PATH, FAIL_PATH


if __name__ == "__main__":
    write_artifacts()
