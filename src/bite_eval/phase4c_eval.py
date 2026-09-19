"""Phase 4C first-open evaluation on frozen REALSTRUCT-1 eval documents.

Does not retune frozen BITE code. Does not open p3f. Does not rewrite Phase 4A/4B.
"""

from __future__ import annotations

import json
import subprocess
import time
from collections import Counter
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
from bite_bench.phase4c import (
    ADAPTER_BLOB,
    ADAPTER_PATH,
    BASELINES,
    CLAIM_BOUNDARY,
    EQ_PATH,
    FREEZE_PATH,
    PHASE3Q_VERDICT,
    PHASE3S_VERDICT,
    PHASE3T_VERDICT,
    PHASE4A_VERDICT,
    PHASE4B_EVAL_HARNESS_BLOB,
    PHASE4B_EVAL_PATH,
    PHASE4B_HEAD,
    PHASE4B_LOCK_BLOB,
    PHASE4B_LOCK_PATH,
    PREMISE,
    PROTOCOL_FROZEN,
    VERDICT_BLOCKED,
    VERDICT_FAILED,
    VERDICT_MEASURED,
    freeze_manifest,
    overlay_v2_sha256,
    raw_sha256_map,
    validate_phase4c_freeze,
)
from bite_bench.realstruct1 import ASSIGN_RE, RAW_DIR, sha256_bytes
from bite_eval.accounting.estimate import LOCAL_ESTIMATE_LABEL, estimate_tokens_char4
from bite_eval.chain_span_reachable import chain_span_reachable
from bite_eval.composition_safety_v2 import composition_safety_v2
from bite_ingestion.adapters.realstruct1_adapter_v1 import (
    ADAPTER_ID,
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
from bite_ingestion.profilers.structural_redundancy_v2 import measure as measure_redundancy

SCHEMA_ID = "bite-phase4c-real-holdout/v0.1"
REVISION = "phase4c-real-holdout-v0.1"
C0_COMMIT_SHA = "8ed272fc7cd0487386656f2be7120b554be7921a"
C0_FREEZE_BLOB = "8e7dc9196bb5c98e79198263b0d4eeadc6254ff2"
_REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = _REPO / "artifacts" / "phase4c"
RESULT_PATH = ARTIFACT_DIR / "real-holdout.json"
ROW_PATH = ARTIFACT_DIR / "eval-rows.json"
COV_PATH = ARTIFACT_DIR / "reference-coverage.json"
DUP_PATH = ARTIFACT_DIR / "exact-duplicate.json"
ROUTE_PATH = ARTIFACT_DIR / "route-observation.json"
PROV_PATH = ARTIFACT_DIR / "full-source-provenance.json"
BASE_PATH = ARTIFACT_DIR / "baselines.json"
RUNTIME_PATH = ARTIFACT_DIR / "runtime-diagnostic.json"
FAIL_PATH = ARTIFACT_DIR / "failure-classification.json"
V2_PATH = _REPO / "corpora" / "realstruct-1" / "annotations-v2.json"
EDGE_SAMPLE = 32

_disp_v0._chain_span = chain_span_reachable  # type: ignore[misc]
_disp_v3._chain_span = chain_span_reachable  # type: ignore[misc]


class EvalProtocolError(RuntimeError):
    """Phase 4C measures the frozen evaluation 9 only."""


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


def _gold_dest_index(doc: Mapping[str, Any]) -> dict[tuple[int, str], set[int]]:
    index: dict[tuple[int, str], set[int]] = {}
    for edge in doc.get("explicit_reference_edges") or []:
        key = (int(edge["source_line"]), str(edge["name"]))
        index.setdefault(key, set()).update(int(dest) for dest in edge.get("dest_lines") or [])
    return index


def _gold_lines(doc: Mapping[str, Any]) -> set[int]:
    lines: set[int] = set()
    for edge in doc.get("explicit_reference_edges") or []:
        lines.add(int(edge["source_line"]))
        lines.update(int(dest) for dest in edge.get("dest_lines") or [])
    return lines


def _literal_ref(value: str, atom: str) -> bool:
    return f"${{{atom}}}" in value


def _value_of(text: str) -> str:
    match = ASSIGN_RE.match(text)
    if match:
        return str(match.group(2))
    if "=" in text:
        return text.split("=", 1)[1]
    return text


def _coverage_status(gold_n: int, hits: int) -> str:
    if gold_n == 0:
        return "not_observed"
    if hits == gold_n:
        return "complete"
    return "gap_observed"


def _blob_errors() -> list[str]:
    errs: list[str] = []
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    errs.extend(validate_phase4c_freeze(freeze))
    if freeze != freeze_manifest():
        errs.append("C0 freeze drifted")
    if freeze.get("verdict") != PROTOCOL_FROZEN:
        errs.append("C0 not frozen")
    if _git_blob("benchmarks/spec/phase4c-holdout-first-open-freeze.json") != C0_FREEZE_BLOB:
        errs.append("C0 freeze blob drifted")
    if _git_blob(ADAPTER_PATH) != ADAPTER_BLOB:
        errs.append("adapter blob drifted")
    if _git_blob("corpora/realstruct-1/annotations-v2.json") != OVERLAY_V2_BLOB:
        errs.append("annotations-v2 blob drifted")
    if _git_blob(PHASE4B_LOCK_PATH) != PHASE4B_LOCK_BLOB:
        errs.append("Phase 4B lock blob drifted")
    if _git_blob(PHASE4B_EVAL_PATH) != PHASE4B_EVAL_HARNESS_BLOB:
        errs.append("Phase 4B eval harness blob drifted")
    for path, expected in {**LOCKED_PHASE4A_BLOBS, **LOCKED_BITE_BLOBS}.items():
        if _git_blob(path) != expected:
            errs.append(f"frozen blob drifted: {path}")
    if overlay_v2_sha256() != freeze.get("overlay_v2_sha256"):
        errs.append("overlay v2 sha256 drifted")
    eq = json.loads(EQ_PATH.read_text(encoding="utf-8"))
    if eq.get("exact") is not True:
        errs.append("reachability-equivalence failed")
    return errs


def _classify(row: Mapping[str, Any]) -> str | None:
    if row.get("unsupported_lost"):
        return "unsupported_loss"
    if row.get("silent_loss"):
        return "silent_loss"
    if (
        row.get("provenance_completeness") != 1.0
        or row.get("lineage_recall") != 1.0
        or list(row.get("conservation_untraced") or []) != []
    ):
        return "provenance_failure"
    if not row.get("planner_ok") or row.get("operator_noop_hidden"):
        return "planner_mismatch"
    if row.get("overmerge_ok") is False:
        return "unrelated_overmerge"
    if not row.get("ok"):
        return "execution_failure"
    return None


def _run_bite(source_id: str, gold: Mapping[str, Any], policy: ConditionalTexturePolicyV4) -> dict[str, Any]:
    started = time.perf_counter()
    refuse_p3f_evaluation(source_id)
    if source_id in DEV_SOURCE_IDS:
        raise EvalProtocolError(f"development sealed from 4C remeasure: {source_id}")
    if source_id not in EVAL_SOURCE_IDS:
        raise EvalProtocolError(f"unknown source: {source_id}")
    raw = (RAW_DIR / source_id).read_bytes()
    digest = sha256_bytes(raw)
    if digest != raw_sha256_map()[source_id]:
        raise AdapterError(f"{source_id}: raw sha256 drifted")
    adapted = adapt(raw, source_id=source_id)
    joined = "".join(str(unit["text"]) for unit in adapted["source"]["units"])
    reconstruction_exact = joined.encode(str(adapted["encoding"])) == raw
    routing = adapted["routing_packet"]
    if "document" in routing:
        raise AdapterError(f"{source_id}: routing packet carried raw document")
    assert_policy_gold_isolated(routing)
    payload = "\n".join(str(unit.get("text", "")) for unit in routing["units"])
    v3 = measure_v3({"payload": payload, "text": payload})
    red = measure_redundancy({"payload": payload, "text": payload})
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
    dest_index = _gold_dest_index(gold)
    sensor_pairs: list[tuple[int, int]] = []
    tp = 0
    fp = 0
    extras = 0
    for edge in v3.edges:
        src_u = routing["units"][int(edge["src"])]
        dst_u = routing["units"][int(edge["dst"])]
        pair = (int(src_u["line_no"]), int(dst_u["line_no"]))
        sensor_pairs.append(pair)
        atom = str(edge.get("atom") or "")
        if _literal_ref(_value_of(str(src_u.get("text", ""))), atom):
            if pair[1] in dest_index.get((pair[0], atom), set()):
                tp += 1
            else:
                fp += 1
        elif pair not in gold_set:
            extras += 1
    hits = sum(1 for pair in gold_pairs if pair in set(sensor_pairs))
    gold_n = len(gold_pairs)
    recall: float | str = "NA" if gold_n == 0 else hits / gold_n
    precision: float | str = "NA" if (tp + fp) == 0 else tp / (tp + fp)
    n_exact = int(gold.get("n_exact_duplicate_groups") or 0)
    after_idents = []
    for unit in _units(after):
        try:
            ident = identity_of_text(str(unit.get("text", "")))
        except Exception:  # noqa: BLE001
            ident = None
        if ident is not None:
            after_idents.append(ident)
    post_multiplicity = sum(1 for count in Counter(after_idents).values() if count > 1)
    n_before = len(_units(routing))
    n_after = len(_units(after))
    op_noop = bool(actual) and n_before == n_after and not _r_entries(after)
    steps = list(plan.get("actionability_before_each_step") or [])
    planner_ok = actual == projected and all(
        bool(step.get("included")) == bool(step.get("actionable")) for step in steps
    )
    n_ref = float(v3.features["n_reference_edges"])
    mean = float(v3.features["mean_reference_edge_distance"])
    gated = (not v3.fail_closed) and n_ref > 0.0 and mean >= float(LOCKED_T_HIGH)
    visible_chars = sum(len(str(unit.get("text", ""))) for unit in full_after_units)
    row = {
        "source_id": source_id,
        "source_sha256": digest,
        "reconstruction_exact": reconstruction_exact,
        "n_source_units": adapted["n_source_units"],
        "n_routing_assignments": adapted["n_routing_assignments"],
        "n_unsupported_passthrough": adapted["n_unsupported_passthrough"],
        "unsupported_lost": unsupported_lost,
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
        "overmerge_ok": bool(safety["no_unrelated_overmerge"]),
        "safety_ok": bool(safety["ok"]),
        "visible_chars": visible_chars,
        "token_proxy_source": estimate_tokens_char4(str(adapted["source"]["document"])),
        "token_proxy_routing": estimate_tokens_char4(payload),
        "token_proxy_after": estimate_tokens_char4(
            "\n".join(str(unit.get("text", "")) for unit in full_after_units)
        ),
        "token_proxy_label": LOCAL_ESTIMATE_LABEL,
        "gold_n": gold_n,
        "gold_hits": hits,
        "gold_reference_recall": recall,
        "scoped_precision_tp": tp,
        "scoped_precision_fp": fp,
        "scoped_precision": precision,
        "reference_coverage_status": _coverage_status(gold_n, hits),
        "n_unadjudicated_extra_edges": extras,
        "n_sensor_directed_edges": len(sensor_pairs),
        "n_exact_duplicate_groups": n_exact,
        "redundancy_status": "not_observed" if n_exact == 0 else "observed",
        "redundancy_n_duplicate_records": int(red.diagnostics.get("n_duplicate_records") or 0),
        "reduce_in_sequence": "REDUCE_v2" in actual,
        "post_reduce_multiplicity": post_multiplicity,
        "untangle_in_sequence": "UNTANGLE" in actual,
        "integrate_in_sequence": "INTEGRATE" in actual,
        "n_raw_edge_rows": len(v3.edges),
        "raw_edge_sample": list(v3.edges[:EDGE_SAMPLE]),
        "fail_closed": bool(v3.fail_closed),
        "wall_clock_s": round(time.perf_counter() - started, 6),
        "ok": (
            reconstruction_exact
            and unsupported_lost == 0
            and planner_ok
            and not op_noop
            and safety["provenance_completeness"] == 1.0
            and safety["lineage_recall"] == 1.0
            and safety["silent_loss"] == 0
            and list(safety["conservation_untraced"]) == []
            and bool(safety["no_unrelated_overmerge"])
            and not v3.fail_closed
        ),
    }
    row["failure_class"] = _classify(row)
    return row


def _run_baselines(source_id: str, gold: Mapping[str, Any]) -> dict[str, Any]:
    raw = (RAW_DIR / source_id).read_bytes()
    adapted = adapt(raw, source_id=source_id)
    source_units = list(adapted["source"]["units"])
    joined = "".join(str(unit["text"]) for unit in source_units)
    gold_lines = _gold_lines(gold)
    routing_lines = {int(unit["line_no"]) for unit in adapted["routing_units"]}
    kept = sorted(line for line in gold_lines if line in routing_lines)
    missing = sorted(line for line in gold_lines if line not in routing_lines)
    return {
        "source_id": source_id,
        "raw_full": {
            "n_bytes": len(raw),
            "n_source_units": adapted["n_source_units"],
            "reconstruction_exact": joined.encode(str(adapted["encoding"])) == raw,
            "visible_chars": len(str(adapted["source"]["document"])),
            "token_proxy": estimate_tokens_char4(str(adapted["source"]["document"])),
        },
        "adapter_only": {
            "n_routing_assignments": adapted["n_routing_assignments"],
            "n_unsupported_passthrough": adapted["n_unsupported_passthrough"],
            "visible_chars": sum(len(str(unit["text"])) for unit in adapted["routing_units"]),
            "token_proxy": estimate_tokens_char4(
                "\n".join(str(unit["text"]) for unit in adapted["routing_units"])
            ),
            "n_gold_assignment_lines": len(gold_lines),
            "n_gold_lines_kept": len(kept),
            "n_gold_lines_missing": len(missing),
        },
    }


def run_evaluation() -> dict[str, Any]:
    errs = _blob_errors()
    gold_map = _gold_by_id()
    policy = ConditionalTexturePolicyV4()
    rows: list[dict[str, Any]] = []
    baselines: list[dict[str, Any]] = []
    try:
        for source_id in EVAL_SOURCE_IDS:
            rows.append(_run_bite(source_id, gold_map[source_id], policy))
            baselines.append(_run_baselines(source_id, gold_map[source_id]))
    except EvalProtocolError as exc:
        errs.append(str(exc))
    except EvaluationSealError as exc:
        errs.append(str(exc))
    except AdapterError as exc:
        errs.append(str(exc))
    n_ok = sum(1 for row in rows if row.get("ok"))
    if any(row["source_id"] in DEV_SOURCE_IDS for row in rows):
        errs.append("dev leakage")
    classes = sorted({row["failure_class"] for row in rows if row.get("failure_class")})
    if n_ok == 9 and not errs and not classes:
        verdict = VERDICT_MEASURED
    elif any("drift" in err or "sealed" in err or "leakage" in err for err in errs):
        verdict = VERDICT_BLOCKED
    else:
        verdict = VERDICT_FAILED
    result = {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "protocol_commit_sha": C0_COMMIT_SHA,
        "c0_freeze_blob": C0_FREEZE_BLOB,
        "phase4b_head_sha": PHASE4B_HEAD,
        "adapter_id": ADAPTER_ID,
        "adapter_blob": ADAPTER_BLOB,
        "verdict": verdict,
        "paid_api": False,
        "research_conclusion": False,
        "premise": PREMISE,
        "phase4a_verdict": PHASE4A_VERDICT,
        "phase3t_verdict": PHASE3T_VERDICT,
        "phase3s_verdict": PHASE3S_VERDICT,
        "phase3q_verdict": PHASE3Q_VERDICT,
        "p3f_evaluation_holdout_used": False,
        "eval_opened": True,
        "n_eval": len(rows),
        "n_ok": n_ok,
        "t_high_reference": LOCKED_T_HIGH,
        "baselines": list(BASELINES),
        "no_winner_score": True,
        "no_xfer3": True,
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "representative sample",
            "real-world generalization",
            "downstream answer-quality evidence",
            "BITE superiority",
        ],
        "errors": errs,
        "rows": [{"source_id": row["source_id"], "ok": row["ok"]} for row in rows],
    }
    _dump(ROW_PATH, {"schema": "bite-phase4c-eval-rows/v0.1", "revision": REVISION, "documents": rows})
    _dump(
        COV_PATH,
        {
            "schema": "bite-phase4c-reference-coverage/v0.1",
            "revision": REVISION,
            "documents": [
                {
                    "source_id": row["source_id"],
                    "gold_n": row["gold_n"],
                    "gold_hits": row["gold_hits"],
                    "gold_reference_recall": row["gold_reference_recall"],
                    "scoped_precision": row["scoped_precision"],
                    "scoped_precision_tp": row["scoped_precision_tp"],
                    "scoped_precision_fp": row["scoped_precision_fp"],
                    "reference_coverage_status": row["reference_coverage_status"],
                    "n_unadjudicated_extra_edges": row["n_unadjudicated_extra_edges"],
                }
                for row in rows
            ],
        },
    )
    _dump(
        DUP_PATH,
        {
            "schema": "bite-phase4c-exact-duplicate/v0.1",
            "revision": REVISION,
            "documents": [
                {
                    "source_id": row["source_id"],
                    "n_exact_duplicate_groups": row["n_exact_duplicate_groups"],
                    "redundancy_status": row["redundancy_status"],
                    "redundancy_n_duplicate_records": row["redundancy_n_duplicate_records"],
                    "reduce_in_sequence": row["reduce_in_sequence"],
                    "post_reduce_multiplicity": row["post_reduce_multiplicity"],
                }
                for row in rows
            ],
        },
    )
    _dump(
        ROUTE_PATH,
        {
            "schema": "bite-phase4c-route-observation/v0.1",
            "revision": REVISION,
            "no_route_correctness_score": True,
            "documents": [
                {
                    "source_id": row["source_id"],
                    "gate": row["gate"],
                    "projected_sequence": row["projected_sequence"],
                    "actual_sequence": row["actual_sequence"],
                    "planner_ok": row["planner_ok"],
                    "reduce_in_sequence": row["reduce_in_sequence"],
                    "untangle_in_sequence": row["untangle_in_sequence"],
                    "integrate_in_sequence": row["integrate_in_sequence"],
                    "operator_noop_hidden": row["operator_noop_hidden"],
                }
                for row in rows
            ],
        },
    )
    _dump(
        PROV_PATH,
        {
            "schema": "bite-phase4c-full-source-provenance/v0.1",
            "revision": REVISION,
            "documents": [
                {
                    "source_id": row["source_id"],
                    "provenance_completeness": row["provenance_completeness"],
                    "lineage_recall": row["lineage_recall"],
                    "silent_loss": row["silent_loss"],
                    "conservation_untraced": row["conservation_untraced"],
                    "unsupported_lost": row["unsupported_lost"],
                    "overmerge_ok": row["overmerge_ok"],
                }
                for row in rows
            ],
        },
    )
    _dump(
        BASE_PATH,
        {
            "schema": "bite-phase4c-baselines/v0.1",
            "revision": REVISION,
            "ids": list(BASELINES),
            "no_winner_score": True,
            "token_proxy_label": LOCAL_ESTIMATE_LABEL,
            "documents": baselines,
        },
    )
    _dump(
        RUNTIME_PATH,
        {
            "schema": "bite-phase4c-runtime-diagnostic/v0.1",
            "revision": REVISION,
            "documents": [
                {"source_id": row["source_id"], "wall_clock_s": row["wall_clock_s"]}
                for row in rows
            ],
        },
    )
    _dump(
        FAIL_PATH,
        {
            "schema": "bite-phase4c-failure-classification/v0.1",
            "revision": REVISION,
            "allowed": [
                "unsupported_loss",
                "silent_loss",
                "provenance_failure",
                "planner_mismatch",
                "unrelated_overmerge",
                "execution_failure",
                "lock_drift",
            ],
            "classes": classes,
            "by_document": [
                {"source_id": row["source_id"], "failure_class": row["failure_class"]}
                for row in rows
            ],
        },
    )
    _dump(RESULT_PATH, result)
    return result


def validate_phase4c_result(doc: Mapping[str, Any]) -> list[str]:
    errs = _blob_errors()
    if doc.get("protocol_commit_sha") != C0_COMMIT_SHA:
        errs.append("C0 commit drifted")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f opened")
    if doc.get("eval_opened") is not True:
        errs.append("eval 9 not marked opened")
    if int(doc.get("n_eval") or 0) != 9:
        errs.append("eval count drifted")
    if doc.get("t_high_reference") != LOCKED_T_HIGH:
        errs.append("T_high drifted")
    if doc.get("verdict") == VERDICT_MEASURED:
        if doc.get("errors"):
            errs.append("MEASURED with errors")
        if int(doc.get("n_ok") or 0) != 9:
            errs.append("MEASURED without 9/9 ok")
    return errs


if __name__ == "__main__":
    payload = run_evaluation()
    print(payload["verdict"], "ok", payload["n_ok"], "errors", payload["errors"])
