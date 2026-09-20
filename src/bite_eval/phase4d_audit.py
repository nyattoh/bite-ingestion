"""Phase 4D retrospective measurement-semantics audit.

Does not rewrite Phase 4C artifacts. Does not retune frozen BITE.
Does not open p3f. Not a second holdout evaluation.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4b import (
    DEV_SOURCE_IDS,
    EVAL_SOURCE_IDS,
    LOCKED_BITE_BLOBS,
    LOCKED_PHASE4A_BLOBS,
    LOCKED_T_HIGH,
    OVERLAY_V2_BLOB,
)
from bite_bench.phase4c import ADAPTER_BLOB, ADAPTER_PATH, overlay_v2_sha256, raw_sha256_map
from bite_bench.phase4d import (
    AUDIT_SOURCE_IDS,
    C0_COMMIT_SHA,
    C0_FREEZE_BLOB,
    CLAIM_BOUNDARY,
    FORBIDDEN_PHASE4C_SAFETY_PHRASE,
    FREEZE_PATH,
    PHASE3Q_VERDICT,
    PHASE3S_VERDICT,
    PHASE3T_VERDICT,
    PHASE4A_VERDICT,
    PHASE4C_HEAD,
    PHASE4C_PROVENANCE_BLOB,
    PHASE4C_PROVENANCE_PATH,
    PHASE4C_REFERENCE_BLOB,
    PHASE4C_REFERENCE_PATH,
    PHASE4C_RESULT_BLOB,
    PHASE4C_RESULT_PATH,
    PHASE4C_SAFETY_PHRASE,
    PREMISE,
    PROTOCOL_FROZEN,
    VERDICT_AUDITED,
    VERDICT_BLOCKED,
    VERDICT_PARTIAL,
    freeze_manifest,
    validate_phase4d_freeze,
)
from bite_bench.realstruct1 import RAW_DIR, sha256_bytes
from bite_eval.atom_aware_reference import (
    atom_aware_predictions,
    gold_pairs_legacy,
    gold_triples,
    score_pairs_legacy,
    score_triples,
)
from bite_eval.chain_span_reachable import chain_span_reachable
from bite_eval.composition_safety_v2 import composition_safety_v2
from bite_ingestion.adapters.realstruct1_adapter_v1 import (
    AdapterError,
    adapt,
    merge_full_source_after,
)
from bite_ingestion.logical_record import identity_of_text
from bite_ingestion.packet_contract import visible_evidence_from_units
from bite_ingestion.policies.conditional_texture_policy_v4 import (
    ConditionalTexturePolicyV4,
    assert_policy_gold_isolated,
)
from bite_ingestion.profilers import dependency_dispersion as _disp_v0
from bite_ingestion.profilers import dependency_dispersion_v3 as _disp_v3
from bite_ingestion.profilers.dependency_dispersion_v3 import measure as measure_v3

SCHEMA_ID = "bite-phase4d-measurement-semantics/v0.1"
REVISION = "phase4d-measurement-semantics-v0.1"
D0_COMMIT_SHA = "45748770815016439aeb11d2ac052b3b19946136"
D0_FREEZE_BLOB = "5e4c252963b3898ff7665e880a77777f66547320"
OPERATOR_CHECKS = (
    "quarantine_recoverable",
    "reduce_only_logical_duplicates",
    "integrate_explicit_join_composite",
)
COMPOSITION_CHECKS = (
    "lineage_recall",
    "provenance_completeness",
    "conservation_untraced",
    "silent_loss",
    "quarantine_recoverable",
    "reduce_only_logical_duplicates",
    "integrate_explicit_join_composite",
    "no_unrelated_overmerge",
)
_REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = _REPO / "artifacts" / "phase4d"
RESULT_PATH = ARTIFACT_DIR / "measurement-semantics.json"
ATOM_PATH = ARTIFACT_DIR / "atom-aware-reference.json"
CMP_PATH = ARTIFACT_DIR / "legacy-vs-atom-aware.json"
SAFE_PATH = ARTIFACT_DIR / "safety-check-decomposition.json"
ROUTE_PATH = ARTIFACT_DIR / "routing-vs-full-source-safety.json"
V2_PATH = _REPO / "corpora" / "realstruct-1" / "annotations-v2.json"
COV4C_PATH = _REPO / PHASE4C_REFERENCE_PATH

_disp_v0._chain_span = chain_span_reachable  # type: ignore[misc]
_disp_v3._chain_span = chain_span_reachable  # type: ignore[misc]


def _git_blob(path: str) -> str:
    return subprocess.check_output(["git", "hash-object", path], cwd=_REPO, text=True).strip()


def _dump(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(dict(doc), indent=2, sort_keys=True) + "\n").encode("utf-8"))


def _units(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = packet.get("units") or []
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return [dict(unit) for unit in raw if isinstance(unit, Mapping)]
    return []


def _gold_by_id() -> dict[str, Mapping[str, Any]]:
    overlay = json.loads(V2_PATH.read_text(encoding="utf-8"))
    return {str(row["source_id"]): row for row in overlay["documents"]}


def _split_role(source_id: str) -> str:
    if source_id in DEV_SOURCE_IDS:
        return "development"
    if source_id in EVAL_SOURCE_IDS:
        return "evaluation"
    return "unknown"


def _blob_errors() -> list[str]:
    errs: list[str] = []
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    errs.extend(validate_phase4d_freeze(freeze))
    if freeze != freeze_manifest():
        errs.append("D0 freeze drifted")
    if freeze.get("verdict") != PROTOCOL_FROZEN:
        errs.append("D0 not frozen")
    if _git_blob("benchmarks/spec/phase4d-measurement-semantics-freeze.json") != D0_FREEZE_BLOB:
        errs.append("D0 freeze blob drifted")
    if _git_blob(PHASE4C_RESULT_PATH) != PHASE4C_RESULT_BLOB:
        errs.append("Phase 4C result blob drifted")
    if _git_blob(PHASE4C_REFERENCE_PATH) != PHASE4C_REFERENCE_BLOB:
        errs.append("Phase 4C reference blob drifted")
    if _git_blob(PHASE4C_PROVENANCE_PATH) != PHASE4C_PROVENANCE_BLOB:
        errs.append("Phase 4C provenance blob drifted")
    if _git_blob("benchmarks/spec/phase4c-holdout-first-open-freeze.json") != C0_FREEZE_BLOB:
        errs.append("C0 freeze blob drifted")
    if _git_blob(ADAPTER_PATH) != ADAPTER_BLOB:
        errs.append("adapter blob drifted")
    if _git_blob("corpora/realstruct-1/annotations-v2.json") != OVERLAY_V2_BLOB:
        errs.append("annotations-v2 blob drifted")
    for path, expected in {**LOCKED_PHASE4A_BLOBS, **LOCKED_BITE_BLOBS}.items():
        if _git_blob(path) != expected:
            errs.append(f"frozen blob drifted: {path}")
    if overlay_v2_sha256() != freeze.get("overlay_v2_sha256"):
        errs.append("overlay v2 sha256 drifted")
    return errs


def _conservation_ok(safety: Mapping[str, Any], unsupported_lost: int) -> bool:
    return (
        safety["provenance_completeness"] == 1.0
        and safety["lineage_recall"] == 1.0
        and safety["silent_loss"] == 0
        and list(safety["conservation_untraced"] or []) == []
        and unsupported_lost == 0
        and bool(safety["no_unrelated_overmerge"])
    )


def _passthrough_duplicate_idents(units: Sequence[Mapping[str, Any]]) -> bool:
    grouped: dict[tuple[str, str], list[str]] = {}
    for unit in units:
        try:
            ident = identity_of_text(str(unit.get("text", "")))
        except Exception:  # noqa: BLE001
            ident = None
        if ident is None:
            continue
        grouped.setdefault(ident, []).append(str(unit.get("line_kind") or ""))
    for kinds in grouped.values():
        if len(kinds) > 1 and any(kind != "assignment" for kind in kinds):
            return True
    return False


def _classify(
    *,
    full_checks: Mapping[str, bool],
    routing_checks: Mapping[str, bool],
    full_units: Sequence[Mapping[str, Any]],
) -> str | None:
    failed = [key for key in COMPOSITION_CHECKS if not full_checks.get(key)]
    if not failed:
        return None
    failed_ops = [key for key in failed if key in OPERATOR_CHECKS]
    if any(not routing_checks.get(key, True) for key in failed_ops):
        return "operator_semantic_failure"
    if failed_ops:
        if _passthrough_duplicate_idents(full_units):
            return "full_source_merge_interaction"
        return "scorer_scope_mismatch"
    return "other"


def _audit_one(
    source_id: str,
    gold: Mapping[str, Any],
    policy: ConditionalTexturePolicyV4,
    cov4c: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    refuse_p3f_evaluation(source_id)
    if source_id not in AUDIT_SOURCE_IDS:
        raise AdapterError(f"unknown source: {source_id}")
    raw = (RAW_DIR / source_id).read_bytes()
    digest = sha256_bytes(raw)
    if digest != raw_sha256_map()[source_id]:
        raise AdapterError(f"{source_id}: raw sha256 drifted")
    adapted = adapt(raw, source_id=source_id)
    routing = adapted["routing_packet"]
    if "document" in routing:
        raise AdapterError(f"{source_id}: routing packet carried raw document")
    assert_policy_gold_isolated(routing)
    payload = "\n".join(str(unit.get("text", "")) for unit in routing["units"])
    v3 = measure_v3({"payload": payload, "text": payload})
    after = policy.apply(routing)
    actual = [str(op) for op in list((after.get("tau") or {}).get("sequence") or [])]
    source_units = list(adapted["source"]["units"])
    full_after_units, full_r = merge_full_source_after(source_units, after)
    full_after = {
        "units": full_after_units,
        "visible_evidence": visible_evidence_from_units(full_after_units),
        "R": full_r,
        "irreversible_loss_ledger": after.get("irreversible_loss_ledger") or [],
        "untangle": after.get("untangle"),
        "integrate": after.get("integrate"),
        "document": adapted["source"]["document"],
    }
    gold_ids = [str(unit["unit_id"]) for unit in source_units]
    routing_ids = [str(unit["unit_id"]) for unit in routing["units"]]
    full_safety = composition_safety_v2(
        adapted["source_packet"], full_after, gold_ids=gold_ids, sequence=actual
    )
    routing_pre = composition_safety_v2(routing, routing, gold_ids=routing_ids, sequence=actual)
    routing_post = composition_safety_v2(routing, after, gold_ids=routing_ids, sequence=actual)
    unsupported_after = [
        unit
        for unit in full_after_units
        if unit.get("line_kind") and unit.get("line_kind") != "assignment"
    ]
    unsupported_lost = adapted["n_unsupported_passthrough"] - len(unsupported_after)
    triples = gold_triples(gold)
    pairs = gold_pairs_legacy(gold)
    pred, unadj = atom_aware_predictions(v3.edges, routing["units"])
    sensor_pairs = []
    for edge in v3.edges:
        src_u = routing["units"][int(edge["src"])]
        dst_u = routing["units"][int(edge["dst"])]
        sensor_pairs.append((int(src_u["line_no"]), int(dst_u["line_no"])))
    atom_scores = score_triples(triples, pred)
    pair_scores = score_pairs_legacy(pairs, sensor_pairs)
    if source_id in EVAL_SOURCE_IDS:
        old = cov4c[source_id]
        if pair_scores["line_pair_recall_legacy"] != old["gold_reference_recall"]:
            raise AdapterError(f"{source_id}: line_pair_recall_legacy mismatch vs Phase 4C")
        if pair_scores["gold_n_pairs"] != old["gold_n"]:
            raise AdapterError(f"{source_id}: legacy gold_n mismatch vs Phase 4C")
    failed_full = [key for key in COMPOSITION_CHECKS if not full_safety["checks"][key]]
    failure_class = _classify(
        full_checks=full_safety["checks"],
        routing_checks=routing_post["checks"],
        full_units=full_after_units,
    )
    return {
        "source_id": source_id,
        "split_role": _split_role(source_id),
        "gold_reconstructable": True,
        "n_gold_triples": atom_scores["n_gold_triples"],
        "n_adjudicated_predictions": atom_scores["n_adjudicated_predictions"],
        "tp": atom_scores["tp"],
        "fp": atom_scores["fp"],
        "fn": atom_scores["fn"],
        "atom_aware_recall": atom_scores["atom_aware_recall"],
        "atom_aware_precision": atom_scores["atom_aware_precision"],
        "n_unadjudicated_extra_edges": unadj,
        "n_sensor_directed_edges": len(v3.edges),
        **pair_scores,
        "actual_sequence": actual,
        "unsupported_lost": unsupported_lost,
        "full_source_conservation_safety": _conservation_ok(full_safety, unsupported_lost),
        "composition_safety_v2_ok": bool(full_safety["ok"]),
        "composition_operator_checks": {key: bool(full_safety["checks"][key]) for key in COMPOSITION_CHECKS},
        "failed_composition_checks": failed_full,
        "routing_pre_checks": {key: bool(routing_pre["checks"][key]) for key in COMPOSITION_CHECKS},
        "routing_post_checks": {key: bool(routing_post["checks"][key]) for key in COMPOSITION_CHECKS},
        "routing_post_ok": bool(routing_post["ok"]),
        "passthrough_in_duplicate_idents": _passthrough_duplicate_idents(full_after_units),
        "failure_class": failure_class,
        "ok": True,
    }


def run_audit() -> dict[str, Any]:
    errs = _blob_errors()
    gold_map = _gold_by_id()
    missing = [sid for sid in AUDIT_SOURCE_IDS if sid not in gold_map]
    if missing:
        errs.append(f"gold identity not reconstructable: {missing}")
    cov4c_rows = {
        str(row["source_id"]): row
        for row in json.loads(COV4C_PATH.read_text(encoding="utf-8"))["documents"]
    }
    policy = ConditionalTexturePolicyV4()
    rows: list[dict[str, Any]] = []
    try:
        for source_id in AUDIT_SOURCE_IDS:
            rows.append(_audit_one(source_id, gold_map[source_id], policy, cov4c_rows))
    except EvaluationSealError as exc:
        errs.append(str(exc))
    except AdapterError as exc:
        errs.append(str(exc))
    except KeyError as exc:
        errs.append(f"identity reconstruction failed: {exc}")
    n_ok = sum(1 for row in rows if row.get("ok") and row.get("gold_reconstructable"))
    poly_gogs = [row for row in rows if row["source_id"] in {"rs1-ini-polybar", "rs1-ini-gogs"}]
    classified = all(row.get("failure_class") for row in poly_gogs) if len(poly_gogs) == 2 else False
    forbidden = any(
        phrase in json.dumps(row, ensure_ascii=False).lower()
        for row in rows
        for phrase in ("second holdout evaluation", "confirmatory")
    )
    if forbidden:
        errs.append("audit leaked second-holdout or confirmatory wording")
    if n_ok == 12 and not errs and classified:
        verdict = VERDICT_AUDITED
    elif any("drift" in err or "sealed" in err or "reconstructable" in err for err in errs):
        verdict = VERDICT_BLOCKED
    else:
        verdict = VERDICT_PARTIAL
    conservation_eval = [
        row["full_source_conservation_safety"]
        for row in rows
        if row["source_id"] in EVAL_SOURCE_IDS
    ]
    result = {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "protocol_commit_sha": D0_COMMIT_SHA,
        "d0_freeze_blob": D0_FREEZE_BLOB,
        "phase4c_head_sha": PHASE4C_HEAD,
        "c0_commit_sha": C0_COMMIT_SHA,
        "c0_freeze_blob": C0_FREEZE_BLOB,
        "verdict": verdict,
        "paid_api": False,
        "research_conclusion": False,
        "premise": PREMISE,
        "phase4a_verdict": PHASE4A_VERDICT,
        "phase3t_verdict": PHASE3T_VERDICT,
        "phase3s_verdict": PHASE3S_VERDICT,
        "phase3q_verdict": PHASE3Q_VERDICT,
        "p3f_evaluation_holdout_used": False,
        "not_second_holdout_evaluation": True,
        "not_confirmatory": True,
        "no_phase4c_rewrite": True,
        "no_bite_retune": True,
        "no_winner_score": True,
        "n_audit": len(rows),
        "n_ok": n_ok,
        "t_high_reference": LOCKED_T_HIGH,
        "phase4c_safety_phrasing": PHASE4C_SAFETY_PHRASE,
        "forbidden_phase4c_safety_phrasing": FORBIDDEN_PHASE4C_SAFETY_PHRASE,
        "eval_conservation_safety_9_of_9": bool(conservation_eval) and all(conservation_eval),
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "new holdout result",
            "real-world generalization",
            "BITE superiority",
            "second holdout evaluation",
            "confirmatory",
        ],
        "errors": errs,
        "rows": [
            {
                "source_id": row["source_id"],
                "split_role": row["split_role"],
                "ok": row["ok"],
                "atom_aware_recall": row["atom_aware_recall"],
                "line_pair_recall_legacy": row["line_pair_recall_legacy"],
                "failure_class": row["failure_class"],
            }
            for row in rows
        ],
    }
    _dump(
        ATOM_PATH,
        {
            "schema": "bite-phase4d-atom-aware-reference/v0.1",
            "revision": REVISION,
            "gold_identity": "(source_line, NAME, dest_line)",
            "prediction_identity": "(source_line, atom, dest_line)",
            "documents": [
                {
                    "source_id": row["source_id"],
                    "split_role": row["split_role"],
                    "gold_reconstructable": row["gold_reconstructable"],
                    "n_gold_triples": row["n_gold_triples"],
                    "n_adjudicated_predictions": row["n_adjudicated_predictions"],
                    "tp": row["tp"],
                    "fp": row["fp"],
                    "fn": row["fn"],
                    "atom_aware_recall": row["atom_aware_recall"],
                    "atom_aware_precision": row["atom_aware_precision"],
                    "n_unadjudicated_extra_edges": row["n_unadjudicated_extra_edges"],
                    "n_sensor_directed_edges": row["n_sensor_directed_edges"],
                }
                for row in rows
            ],
        },
    )
    _dump(
        CMP_PATH,
        {
            "schema": "bite-phase4d-legacy-vs-atom-aware/v0.1",
            "revision": REVISION,
            "legacy_metric_id": "line_pair_recall_legacy",
            "legacy_metric_preserved": True,
            "documents": [
                {
                    "source_id": row["source_id"],
                    "split_role": row["split_role"],
                    "gold_n_pairs": row["gold_n_pairs"],
                    "gold_hits_pairs": row["gold_hits_pairs"],
                    "line_pair_recall_legacy": row["line_pair_recall_legacy"],
                    "n_gold_triples": row["n_gold_triples"],
                    "atom_aware_recall": row["atom_aware_recall"],
                    "atom_aware_precision": row["atom_aware_precision"],
                    "recalls_differ": row["line_pair_recall_legacy"] != row["atom_aware_recall"],
                }
                for row in rows
            ],
        },
    )
    _dump(
        SAFE_PATH,
        {
            "schema": "bite-phase4d-safety-check-decomposition/v0.1",
            "revision": REVISION,
            "phase4c_safety_phrasing": PHASE4C_SAFETY_PHRASE,
            "documents": [
                {
                    "source_id": row["source_id"],
                    "split_role": row["split_role"],
                    "full_source_conservation_safety": row["full_source_conservation_safety"],
                    "composition_safety_v2_ok": row["composition_safety_v2_ok"],
                    "composition_operator_checks": row["composition_operator_checks"],
                    "failed_composition_checks": row["failed_composition_checks"],
                    "failure_class": row["failure_class"],
                    "unsupported_lost": row["unsupported_lost"],
                    "actual_sequence": row["actual_sequence"],
                }
                for row in rows
            ],
        },
    )
    _dump(
        ROUTE_PATH,
        {
            "schema": "bite-phase4d-routing-vs-full-source-safety/v0.1",
            "revision": REVISION,
            "documents": [
                {
                    "source_id": row["source_id"],
                    "split_role": row["split_role"],
                    "actual_sequence": row["actual_sequence"],
                    "routing_pre_checks": row["routing_pre_checks"],
                    "routing_post_checks": row["routing_post_checks"],
                    "routing_post_ok": row["routing_post_ok"],
                    "full_source_conservation_safety": row["full_source_conservation_safety"],
                    "composition_safety_v2_ok": row["composition_safety_v2_ok"],
                    "failed_composition_checks": row["failed_composition_checks"],
                    "passthrough_in_duplicate_idents": row["passthrough_in_duplicate_idents"],
                    "failure_class": row["failure_class"],
                }
                for row in rows
            ],
        },
    )
    _dump(RESULT_PATH, result)
    return result


def validate_phase4d_result(doc: Mapping[str, Any]) -> list[str]:
    errs = _blob_errors()
    if doc.get("protocol_commit_sha") != D0_COMMIT_SHA:
        errs.append("D0 commit drifted")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f opened")
    if doc.get("not_second_holdout_evaluation") is not True:
        errs.append("marked as second holdout")
    if doc.get("not_confirmatory") is not True:
        errs.append("marked confirmatory")
    if int(doc.get("n_audit") or 0) != 12:
        errs.append("audit count drifted")
    if doc.get("t_high_reference") != LOCKED_T_HIGH:
        errs.append("T_high drifted")
    if doc.get("phase4c_safety_phrasing") != PHASE4C_SAFETY_PHRASE:
        errs.append("Phase 4C safety phrasing drifted")
    if doc.get("forbidden_phase4c_safety_phrasing") != FORBIDDEN_PHASE4C_SAFETY_PHRASE:
        errs.append("forbidden Phase 4C aggregate phrasing drifted")
    if doc.get("phase4c_safety_phrasing") == FORBIDDEN_PHASE4C_SAFETY_PHRASE:
        errs.append("used forbidden Phase 4C aggregate phrasing")
    if doc.get("verdict") == VERDICT_AUDITED:
        if doc.get("errors"):
            errs.append("AUDITED with errors")
        if int(doc.get("n_ok") or 0) != 12:
            errs.append("AUDITED without 12/12 ok")
    return errs


if __name__ == "__main__":
    payload = run_audit()
    print(payload["verdict"], "ok", payload["n_ok"], "errors", payload["errors"])
