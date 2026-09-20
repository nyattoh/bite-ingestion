"""Phase 4B development adapter run on frozen REALSTRUCT-1 dev documents.

Does not open eval 9. Does not open p3f. Does not change frozen BITE code.
Does not execute baselines.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4b import (
    B0_COMMIT_SHA,
    B0_FREEZE_BLOB,
    CLAIM_BOUNDARY,
    DEV_SOURCE_IDS,
    EVAL_SOURCE_IDS,
    LOCKED_BITE_BLOBS,
    LOCKED_PHASE4A_BLOBS,
    LOCKED_T_HIGH,
    OVERLAY_V2_BLOB,
    PHASE3Q_VERDICT,
    PHASE3S_VERDICT,
    PHASE3T_VERDICT,
    PREMISE,
    PROTOCOL_FROZEN,
    VERDICT_BLOCKED,
    VERDICT_PARTIAL,
    VERDICT_READY,
    freeze_manifest,
    overlay_v2_sha256,
    raw_sha256_map,
    validate_phase4b_freeze,
)
from bite_bench.realstruct1 import RAW_DIR, sha256_bytes
from bite_eval.accounting.estimate import LOCAL_ESTIMATE_LABEL, estimate_tokens_char4
from bite_eval.composition_safety_v2 import composition_safety_v2
from bite_ingestion.adapters.realstruct1_adapter_v1 import (
    ADAPTER_ID,
    AdapterError,
    adapt,
    merge_full_source_after,
)
from bite_ingestion.packet_contract import visible_evidence_from_units
from bite_ingestion.policies.conditional_texture_policy_v4 import (
    ConditionalTexturePolicyV4,
    assert_policy_gold_isolated,
)
from bite_ingestion.profilers import dependency_dispersion as _disp_v0
from bite_ingestion.profilers import dependency_dispersion_v3 as _disp_v3
from bite_ingestion.profilers.dependency_dispersion_v3 import measure as measure_v3
from bite_ingestion.profilers.structural_redundancy_v2 import measure as measure_redundancy

SCHEMA_ID = "bite-phase4b-real-adapter/v0.1"
ROW_SCHEMA_ID = "bite-phase4b-dev-rows/v0.1"
COV_SCHEMA_ID = "bite-phase4b-reference-coverage/v0.1"
ROUTE_SCHEMA_ID = "bite-phase4b-route-observation/v0.1"
PROV_SCHEMA_ID = "bite-phase4b-full-source-provenance/v0.1"
LOCK_SCHEMA_ID = "bite-phase4b-evaluation-lock/v0.1"
REVISION = "phase4b-real-adapter-v0.1"
ADAPTER_PATH = "src/bite_ingestion/adapters/realstruct1_adapter_v1.py"
_REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = _REPO / "artifacts" / "phase4b"
RESULT_PATH = ARTIFACT_DIR / "real-adapter.json"
ROW_PATH = ARTIFACT_DIR / "dev-rows.json"
COV_PATH = ARTIFACT_DIR / "reference-coverage.json"
ROUTE_PATH = ARTIFACT_DIR / "route-observation.json"
PROV_PATH = ARTIFACT_DIR / "full-source-provenance.json"
LOCK_PATH = ARTIFACT_DIR / "evaluation-lock.json"
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase4b-scorer-addendum-freeze.json"
V2_PATH = _REPO / "corpora" / "realstruct-1" / "annotations-v2.json"
EDGE_SAMPLE = 32


def _chain_span_reachable(n: int, directed: Sequence[tuple[int, int]]) -> int:
    # ponytail: frozen v3 DFS enumerates simple paths and does not finish on dense
    # identifier graphs; max reachable index equals that max (node-start).
    adj: dict[int, set[int]] = {i: set() for i in range(n)}
    for src, dst in directed:
        if src != dst:
            adj[int(src)].add(int(dst))
    best = 0
    for start in range(n):
        seen = {start}
        stack = [start]
        max_idx = start
        while stack:
            node = stack.pop()
            for nxt in adj[node]:
                if nxt in seen:
                    continue
                seen.add(nxt)
                max_idx = max(max_idx, nxt)
                stack.append(nxt)
        best = max(best, max_idx - start)
    return best


_disp_v0._chain_span = _chain_span_reachable  # type: ignore[misc]
_disp_v3._chain_span = _chain_span_reachable  # type: ignore[misc]


class EvalSealError(RuntimeError):
    """REALSTRUCT-1 evaluation documents stay sealed in Phase 4B."""


def refuse_eval_source(source_id: str) -> None:
    if source_id in EVAL_SOURCE_IDS:
        raise EvalSealError(f"REALSTRUCT-1 evaluation sealed: refused {source_id}")


def _git_blob(path: str) -> str:
    return subprocess.check_output(["git", "hash-object", path], cwd=_REPO, text=True).strip()


def _dump(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(doc), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _units(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = packet.get("units") or []
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return [dict(unit) for unit in raw if isinstance(unit, Mapping)]
    return []


def _r_entries(packet: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    blob = packet.get("R")
    if not isinstance(blob, Mapping):
        return []
    raw = blob.get("entries") or []
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return [row for row in raw if isinstance(row, Mapping)]
    return []


def _gold_by_id() -> dict[str, Mapping[str, Any]]:
    overlay = json.loads(V2_PATH.read_text(encoding="utf-8"))
    return {str(row["source_id"]): row for row in overlay["documents"]}


def _gold_pairs(doc: Mapping[str, Any]) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for edge in doc.get("explicit_reference_edges") or []:
        src = int(edge["source_line"])
        for dest in edge.get("dest_lines") or []:
            pairs.append((src, int(dest)))
    return pairs


def _coverage_status(gold_n: int, hits: int) -> str:
    if gold_n == 0:
        return "not_observed"
    if hits == gold_n:
        return "complete"
    return "gap_observed"


def _blob_errors() -> list[str]:
    errs: list[str] = []
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    errs.extend(validate_phase4b_freeze(freeze))
    if freeze != freeze_manifest():
        errs.append("B0 freeze drifted")
    if freeze.get("verdict") != PROTOCOL_FROZEN:
        errs.append("B0 not frozen")
    for path, expected in {**LOCKED_PHASE4A_BLOBS, **LOCKED_BITE_BLOBS}.items():
        try:
            observed = _git_blob(path)
        except Exception as exc:  # noqa: BLE001
            errs.append(f"blob check failed {path}: {exc}")
            continue
        if observed != expected:
            errs.append(f"frozen blob drifted: {path}")
    if _git_blob("benchmarks/spec/phase4b-scorer-addendum-freeze.json") != B0_FREEZE_BLOB:
        errs.append("B0 freeze blob drifted")
    if _git_blob("corpora/realstruct-1/annotations-v2.json") != OVERLAY_V2_BLOB:
        errs.append("annotations-v2 blob drifted")
    return errs


def _run_one(source_id: str, gold: Mapping[str, Any], policy: ConditionalTexturePolicyV4) -> dict[str, Any]:
    refuse_p3f_evaluation(source_id)
    refuse_eval_source(source_id)
    raw = (RAW_DIR / source_id).read_bytes()
    digest = sha256_bytes(raw)
    expected = raw_sha256_map()[source_id]
    if digest != expected:
        raise AdapterError(f"{source_id}: raw sha256 drifted")
    adapted = adapt(raw, source_id=source_id)
    routing = adapted["routing_packet"]
    if "document" in routing:
        raise AdapterError(f"{source_id}: routing packet carried raw document")
    assert_policy_gold_isolated(routing)
    payload = "\n".join(str(unit.get("text", "")) for unit in routing["units"])
    v3 = measure_v3({"payload": payload, "text": payload})
    red = measure_redundancy({"payload": payload, "text": payload})
    before = routing
    after = policy.apply(routing)
    actual = [str(op) for op in list((after.get("tau") or {}).get("sequence") or [])]
    plan = (after.get("tau") or {}).get("projected_plan") or {}
    projected = [str(op) for op in list(plan.get("projected_sequence") or [])]
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
    safety = composition_safety_v2(
        adapted["source_packet"], full_after, gold_ids=gold_ids, sequence=actual
    )
    unsupported_after = [
        unit
        for unit in full_after_units
        if unit.get("line_kind") and unit.get("line_kind") != "assignment"
    ]
    unsupported_lost = adapted["n_unsupported_passthrough"] - len(unsupported_after)
    gold_pairs = _gold_pairs(gold)
    gold_set = set(gold_pairs)
    sensor_pairs: list[tuple[int, int]] = []
    for edge in v3.edges:
        src_u = routing["units"][int(edge["src"])]
        dst_u = routing["units"][int(edge["dst"])]
        sensor_pairs.append((int(src_u["line_no"]), int(dst_u["line_no"])))
    hits = sum(1 for pair in gold_pairs if pair in set(sensor_pairs))
    extras = [pair for pair in sensor_pairs if pair not in gold_set]
    gold_n = len(gold_pairs)
    recall: float | str = "NA" if gold_n == 0 else hits / gold_n
    n_exact = int(gold.get("n_exact_duplicate_groups") or 0)
    redundancy_status = "not_observed" if n_exact == 0 else "observed"
    n_before = len(_units(before))
    n_after = len(_units(after))
    op_noop = bool(actual) and n_before == n_after and not _r_entries(after)
    steps = list(plan.get("actionability_before_each_step") or [])
    planner_ok = actual == projected and all(
        bool(step.get("included")) == bool(step.get("actionable")) for step in steps
    )
    n_ref = float(v3.features["n_reference_edges"])
    mean = float(v3.features["mean_reference_edge_distance"])
    gated = (not v3.fail_closed) and n_ref > 0.0 and mean >= float(LOCKED_T_HIGH)
    row = {
        "source_id": source_id,
        "source_sha256": digest,
        "n_source_units": adapted["n_source_units"],
        "n_routing_assignments": adapted["n_routing_assignments"],
        "n_unsupported_passthrough": adapted["n_unsupported_passthrough"],
        "unsupported_lost": unsupported_lost,
        "reconstruction_exact": True,
        "n_reference_edges": n_ref,
        "mean_reference_edge_distance": mean,
        "gate": gated,
        "projected_sequence": projected,
        "actual_sequence": actual,
        "planner_ok": planner_ok,
        "operator_noop_hidden": op_noop,
        "n_units_before": n_before,
        "n_units_after": n_after,
        "n_r_entries": len(_r_entries(after)),
        "provenance_completeness": safety["provenance_completeness"],
        "lineage_recall": safety["lineage_recall"],
        "silent_loss": safety["silent_loss"],
        "conservation_untraced": list(safety["conservation_untraced"]),
        "safety_ok": bool(safety["ok"]),
        "token_proxy_source": estimate_tokens_char4(str(adapted["source"]["document"])),
        "token_proxy_routing": estimate_tokens_char4(payload),
        "token_proxy_label": LOCAL_ESTIMATE_LABEL,
        "gold_n": gold_n,
        "gold_hits": hits,
        "gold_reference_recall": recall,
        "reference_coverage_status": _coverage_status(gold_n, hits),
        "n_unadjudicated_extra_edges": len(extras),
        "n_sensor_directed_edges": len(sensor_pairs),
        "n_exact_duplicate_groups": n_exact,
        "redundancy_status": redundancy_status,
        "redundancy_duplicate_unit_ratio": float(red.features.get("duplicate_unit_ratio") or 0.0),
        "redundancy_n_duplicate_records": int(red.diagnostics.get("n_duplicate_records") or 0),
        "reduce_in_sequence": "REDUCE_v2" in actual,
        "untangle_in_sequence": "UNTANGLE" in actual,
        "integrate_in_sequence": "INTEGRATE" in actual,
        "n_raw_edge_rows": len(v3.edges),
        "raw_edge_sample": list(v3.edges[:EDGE_SAMPLE]),
        "fail_closed": bool(v3.fail_closed),
        "ok": (
            unsupported_lost == 0
            and planner_ok
            and not op_noop
            and safety["provenance_completeness"] == 1.0
            and safety["lineage_recall"] == 1.0
            and safety["silent_loss"] == 0
            and list(safety["conservation_untraced"]) == []
            and not v3.fail_closed
        ),
    }
    return row


def _lock_doc(adapter_blob: str) -> dict[str, Any]:
    return {
        "schema": LOCK_SCHEMA_ID,
        "revision": REVISION,
        "b0_commit_sha": B0_COMMIT_SHA,
        "b0_freeze_blob": B0_FREEZE_BLOB,
        "adapter_id": ADAPTER_ID,
        "adapter_blob": adapter_blob,
        "overlay_v2_blob": OVERLAY_V2_BLOB,
        "overlay_v2_sha256": overlay_v2_sha256(),
        "t_high_reference": LOCKED_T_HIGH,
        "raw_sha256": raw_sha256_map(),
        "dev_source_ids": list(DEV_SOURCE_IDS),
        "eval_source_ids": list(EVAL_SOURCE_IDS),
        "eval_unopened": True,
        "p3f_unopened": True,
        "no_baseline_execution": True,
        "locked_phase4a_blobs": dict(LOCKED_PHASE4A_BLOBS),
        "locked_bite_blobs": dict(LOCKED_BITE_BLOBS),
        "measurement_definitions": {
            "gold_reference_recall": "hits / gold directed ${NAME} pairs; NA if gold_n=0",
            "unadjudicated_extra_edges": "sensor edges not in gold; not called false positives",
            "exact_duplicate_gold": "exact (assignment_key, assignment_value)",
            "full_source_conservation": (
                "provenance_completeness=1; lineage_recall=1; silent_loss=0; "
                "conservation_untraced=[]"
            ),
        },
        "provenance_invariants": [
            "every source unit is passthrough, visible descendant, or recoverable R",
            "unsupported source lines must remain",
        ],
    }


def run_evaluation() -> dict[str, Any]:
    errs = _blob_errors()
    gold_map = _gold_by_id()
    policy = ConditionalTexturePolicyV4()
    rows: list[dict[str, Any]] = []
    try:
        for source_id in DEV_SOURCE_IDS:
            rows.append(_run_one(source_id, gold_map[source_id], policy))
    except EvalSealError as exc:
        errs.append(str(exc))
    except EvaluationSealError as exc:
        errs.append(str(exc))
    except AdapterError as exc:
        errs.append(str(exc))
    n_ok = sum(1 for row in rows if row.get("ok"))
    if any(row["source_id"] in EVAL_SOURCE_IDS for row in rows):
        errs.append("eval leakage")
    if n_ok == 3 and not errs:
        verdict = VERDICT_READY
    elif rows and not any("eval leakage" in err or "sealed" in err for err in errs):
        verdict = VERDICT_PARTIAL
    else:
        verdict = VERDICT_BLOCKED if errs else VERDICT_PARTIAL
        if n_ok != 3:
            verdict = VERDICT_PARTIAL if rows else VERDICT_BLOCKED
    adapter_blob = _git_blob(ADAPTER_PATH)
    result = {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "protocol_commit_sha": B0_COMMIT_SHA,
        "b0_freeze_blob": B0_FREEZE_BLOB,
        "adapter_id": ADAPTER_ID,
        "adapter_blob": adapter_blob,
        "verdict": verdict,
        "paid_api": False,
        "research_conclusion": False,
        "premise": PREMISE,
        "phase3t_verdict": PHASE3T_VERDICT,
        "phase3s_verdict": PHASE3S_VERDICT,
        "phase3q_verdict": PHASE3Q_VERDICT,
        "p3f_evaluation_holdout_used": False,
        "eval_unopened": True,
        "no_xfer3": True,
        "no_baseline_execution": True,
        "t_high_reference": LOCKED_T_HIGH,
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "real-world generalization",
            "evaluation result",
            "BITE superiority",
        ],
        "n_dev": len(rows),
        "n_ok": n_ok,
        "errors": errs,
        "rows": [{"source_id": row["source_id"], "ok": row["ok"]} for row in rows],
    }
    _dump(ROW_PATH, {"schema": ROW_SCHEMA_ID, "revision": REVISION, "documents": rows})
    _dump(
        COV_PATH,
        {
            "schema": COV_SCHEMA_ID,
            "revision": REVISION,
            "documents": [
                {
                    "source_id": row["source_id"],
                    "gold_n": row["gold_n"],
                    "gold_hits": row["gold_hits"],
                    "gold_reference_recall": row["gold_reference_recall"],
                    "reference_coverage_status": row["reference_coverage_status"],
                    "n_unadjudicated_extra_edges": row["n_unadjudicated_extra_edges"],
                }
                for row in rows
            ],
        },
    )
    _dump(
        ROUTE_PATH,
        {
            "schema": ROUTE_SCHEMA_ID,
            "revision": REVISION,
            "no_route_correctness_score": True,
            "documents": [
                {
                    "source_id": row["source_id"],
                    "gate": row["gate"],
                    "projected_sequence": row["projected_sequence"],
                    "actual_sequence": row["actual_sequence"],
                    "planner_ok": row["planner_ok"],
                    "untangle_in_sequence": row["untangle_in_sequence"],
                    "integrate_in_sequence": row["integrate_in_sequence"],
                    "reduce_in_sequence": row["reduce_in_sequence"],
                    "n_units_before": row["n_units_before"],
                    "n_units_after": row["n_units_after"],
                    "operator_noop_hidden": row["operator_noop_hidden"],
                }
                for row in rows
            ],
        },
    )
    _dump(
        PROV_PATH,
        {
            "schema": PROV_SCHEMA_ID,
            "revision": REVISION,
            "documents": [
                {
                    "source_id": row["source_id"],
                    "provenance_completeness": row["provenance_completeness"],
                    "lineage_recall": row["lineage_recall"],
                    "silent_loss": row["silent_loss"],
                    "conservation_untraced": row["conservation_untraced"],
                    "unsupported_lost": row["unsupported_lost"],
                }
                for row in rows
            ],
        },
    )
    _dump(LOCK_PATH, _lock_doc(adapter_blob))
    _dump(RESULT_PATH, result)
    return result


def validate_phase4b_result(doc: Mapping[str, Any]) -> list[str]:
    errs = _blob_errors()
    if doc.get("protocol_commit_sha") != B0_COMMIT_SHA:
        errs.append("B0 commit drifted")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f opened")
    if doc.get("eval_unopened") is not True:
        errs.append("eval 9 opened")
    if doc.get("no_baseline_execution") is not True:
        errs.append("baseline executed")
    if doc.get("t_high_reference") != LOCKED_T_HIGH:
        errs.append("T_high drifted")
    if int(doc.get("n_dev") or 0) != 3:
        errs.append("dev count drifted")
    if doc.get("verdict") == VERDICT_READY:
        if doc.get("errors"):
            errs.append("READY with errors")
        if int(doc.get("n_ok") or 0) != 3:
            errs.append("READY without 3/3 ok")
    return errs


if __name__ == "__main__":
    payload = run_evaluation()
    print(payload["verdict"], "ok", payload["n_ok"], "errors", payload["errors"])
