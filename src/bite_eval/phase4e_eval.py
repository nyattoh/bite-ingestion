"""Phase 4E evaluation of full-key reference identity v2.

Does not change v1/v3/policy v4, planner, or operators.
Does not rewrite Phase 4C/4D. Does not open p3f. Does not add baselines.
"""

from __future__ import annotations

import json
import subprocess
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4b import DEV_SOURCE_IDS, EVAL_SOURCE_IDS
from bite_bench.phase4d import AUDIT_SOURCE_IDS
from bite_bench.phase4e import (
    CLAIM_BOUNDARY,
    FORMATS,
    FREEZE_PATH,
    LOCKED_BLOBS,
    LOCKED_T_HIGH,
    N_SURFACES,
    PHASE3Q_VERDICT,
    PHASE3S_VERDICT,
    PHASE3T_VERDICT,
    PHASE4C_VERDICT,
    PREMISE,
    PROTOCOL_FROZEN,
    VERDICT_BLOCKED,
    VERDICT_PARTIAL,
    VERDICT_VALIDATED,
    dest_index_for,
    forbidden_hits,
    freeze_manifest,
    gate_expected,
    intended_mean,
    intended_reference_edges,
    render_records,
    validate_phase4e_freeze,
)
from bite_bench.realstruct1 import RAW_DIR, sha256_bytes
from bite_eval.atom_aware_reference import (
    atom_aware_predictions,
    gold_triples,
    score_triples,
)
from bite_eval.composition_safety_v2 import composition_safety_v2
from bite_ingestion.adapters.bite_xfer2 import (
    UnitizerError,
    assert_no_annotation_leak,
    packet_from_document,
)
from bite_ingestion.adapters.realstruct1_adapter_v1 import adapt, merge_full_source_after
from bite_ingestion.packet_contract import visible_evidence_from_units
from bite_ingestion.policies.conditional_texture_policy_v5 import (
    ConditionalTexturePolicyV5,
    PolicyLeakError,
    assert_policy_gold_isolated,
)
from bite_ingestion.profilers.dependency_dispersion_v3 import measure as measure_v3
from bite_ingestion.profilers.dependency_dispersion_v4 import measure as measure_v4

SCHEMA_ID = "bite-phase4e-full-key-reference/v0.1"
REVISION = "phase4e-full-key-reference-v0.1"
E0_COMMIT_SHA = "9349087ab4fd5bb095a4904646243665c4464b52"
E0_FREEZE_BLOB = "911a22ff9d210de05ae799fce5c90f09c65c1029"
_REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = _REPO / "artifacts" / "phase4e"
RESULT_PATH = ARTIFACT_DIR / "full-key-reference.json"
EDGE_PATH = ARTIFACT_DIR / "exact-edge.json"
BRIDGE_PATH = ARTIFACT_DIR / "threshold-bridge.json"
FMT_PATH = ARTIFACT_DIR / "format-invariance.json"
RUNTIME_PATH = ARTIFACT_DIR / "runtime-diagnostic.json"
SECONDARY_PATH = ARTIFACT_DIR / "realstruct1-retrospective.json"
V2_PATH = _REPO / "corpora" / "realstruct-1" / "annotations-v2.json"
MANIFEST_PATH = _REPO / "corpora" / "realstruct-1" / "manifest.json"


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


def _tau_sequence(packet: Mapping[str, Any]) -> list[str]:
    tau = packet.get("tau")
    if isinstance(tau, Mapping):
        return [str(item) for item in list(tau.get("sequence") or [])]
    return []


def _undirected_pairs(rows: Sequence[Mapping[str, Any]]) -> list[list[int]]:
    seen: set[tuple[int, int]] = set()
    out: list[list[int]] = []
    for row in rows:
        src = int(row["src"])
        dst = int(row["dst"])
        if src == dst:
            continue
        pair = (src, dst) if src < dst else (dst, src)
        if pair not in seen:
            seen.add(pair)
            out.append([pair[0], pair[1]])
    return out


def _pairs_key(pairs: Sequence[Sequence[int]]) -> list[list[int]]:
    return sorted(
        ([int(a), int(b)] if a <= b else [int(b), int(a)] for a, b in pairs),
        key=lambda item: (item[0], item[1]),
    )


def _blob_errors() -> list[str]:
    errs: list[str] = []
    if not FREEZE_PATH.is_file():
        return ["E0 freeze missing"]
    committed = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    errs.extend(validate_phase4e_freeze(committed))
    if freeze_manifest() != committed:
        errs.append("E0 freeze drifted from generator")
    if committed.get("verdict") != PROTOCOL_FROZEN:
        errs.append("E0 not frozen")
    if _git_blob("benchmarks/spec/phase4e-full-key-reference-freeze.json") != E0_FREEZE_BLOB:
        errs.append("E0 freeze blob drifted")
    for path, expected in LOCKED_BLOBS.items():
        if _git_blob(path) != expected:
            errs.append(f"frozen blob drifted: {path}")
    return errs


def _gold_ids(case_id: str, packet: Mapping[str, Any]) -> list[str]:
    dest = dest_index_for(case_id)
    units = _units(packet)
    if dest is None or dest >= len(units):
        return []
    return [str(units[0]["unit_id"]), str(units[dest]["unit_id"])]


def _surface_row(spec: Mapping[str, Any], fmt: str, policy: ConditionalTexturePolicyV5) -> dict[str, Any]:
    case_id = str(spec["case_id"])
    refuse_p3f_evaluation(case_id)
    started = time.perf_counter()
    records = [(str(key), str(value)) for key, value in spec["records"]]
    document = render_records(records, fmt)
    hits = forbidden_hits(document)
    if hits:
        raise PolicyLeakError(f"gold leak in {case_id}: {hits}")
    intended = _pairs_key(intended_reference_edges(case_id))
    expect_gate = gate_expected(case_id)
    v4 = measure_v4({"payload": document, "text": document})
    observed = _pairs_key(_undirected_pairs(v4.edges))
    n_ref = float(v4.features["n_reference_edges"])
    mean = float(v4.features["mean_reference_edge_distance"])
    extra = [pair for pair in observed if pair not in intended]
    missing = [pair for pair in intended if pair not in observed]
    edge_ok = observed == intended and n_ref == float(len(intended))
    gated = (not v4.fail_closed) and n_ref > 0.0 and mean >= LOCKED_T_HIGH
    packet = packet_from_document(document, case_id=case_id, fmt=fmt)
    assert_no_annotation_leak(packet)
    assert_policy_gold_isolated(packet)
    after = policy.apply(packet)
    actual = _tau_sequence(after)
    expect_seq = list(spec.get("policy_sequence_expected") or [])
    safety = composition_safety_v2(
        packet, after, gold_ids=_gold_ids(case_id, packet), sequence=actual
    )
    bridge = None
    if spec.get("bridge"):
        v3 = measure_v3({"payload": document, "text": document})
        v3_obs = _pairs_key(_undirected_pairs(v3.edges))
        v3_n = float(v3.features["n_reference_edges"])
        v3_mean = float(v3.features["mean_reference_edge_distance"])
        bridge = {
            "surface_id": f"{case_id}-{fmt}",
            "v3_edges": v3_obs,
            "v4_edges": observed,
            "v3_n": v3_n,
            "v4_n": n_ref,
            "v3_mean": v3_mean,
            "v4_mean": mean,
            "exact": v3_obs == observed and v3_n == n_ref and v3_mean == mean,
        }
    ok = (
        edge_ok
        and gated is expect_gate
        and actual == expect_seq
        and bool(safety["ok"])
        and (not v4.fail_closed)
    )
    return {
        "surface_id": f"{case_id}-{fmt}",
        "case_id": case_id,
        "family": spec["family"],
        "format": fmt,
        "distance": spec["distance"],
        "bridge": bool(spec.get("bridge")),
        "intended_reference_edges": intended,
        "intended_mean": intended_mean(intended),
        "observed_edges": observed,
        "n_reference_edges": n_ref,
        "mean_reference_edge_distance": mean,
        "extra_edges": extra,
        "missing_edges": missing,
        "false_reference_edges": len(extra),
        "edge_set_exact": edge_ok,
        "gate_expected": expect_gate,
        "gate_observed": gated,
        "gate_ok": gated is expect_gate,
        "policy_sequence_expected": expect_seq,
        "policy_sequence": actual,
        "policy_seq_ok": actual == expect_seq,
        "safety_ok": bool(safety["ok"]),
        "bridge_row": bridge,
        "wall_clock_s": round(time.perf_counter() - started, 6),
        "ok": ok,
    }


def _conservation_ok(safety: Mapping[str, Any], unsupported_lost: int) -> bool:
    return (
        safety["provenance_completeness"] == 1.0
        and safety["lineage_recall"] == 1.0
        and safety["silent_loss"] == 0
        and list(safety["conservation_untraced"] or []) == []
        and unsupported_lost == 0
        and bool(safety["no_unrelated_overmerge"])
    )


def _secondary(policy: ConditionalTexturePolicyV5) -> dict[str, Any]:
    overlay = json.loads(V2_PATH.read_text(encoding="utf-8"))
    gold_map = {str(row["source_id"]): row for row in overlay["documents"]}
    sha_map = {
        str(row["source_id"]): str(row["sha256"])
        for row in json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["sources"]
    }
    rows: list[dict[str, Any]] = []
    for source_id in AUDIT_SOURCE_IDS:
        refuse_p3f_evaluation(source_id)
        started = time.perf_counter()
        raw = (RAW_DIR / source_id).read_bytes()
        if sha256_bytes(raw) != sha_map[source_id]:
            raise PolicyLeakError(f"{source_id}: raw sha256 drifted")
        adapted = adapt(raw, source_id=source_id)
        routing = adapted["routing_packet"]
        assert_policy_gold_isolated(routing)
        payload = "\n".join(str(unit.get("text", "")) for unit in routing["units"])
        v4 = measure_v4({"payload": payload, "text": payload})
        after = policy.apply(routing)
        actual = _tau_sequence(after)
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
        pred, unadj = atom_aware_predictions(v4.edges, routing["units"])
        scores = score_triples(gold_triples(gold_map[source_id]), pred)
        n_ref = float(v4.features["n_reference_edges"])
        mean = float(v4.features["mean_reference_edge_distance"])
        gated = (not v4.fail_closed) and n_ref > 0.0 and mean >= LOCKED_T_HIGH
        split_role = "development" if source_id in DEV_SOURCE_IDS else "evaluation"
        rows.append(
            {
                "source_id": source_id,
                "split_role": split_role,
                "atom_aware_recall": scores["atom_aware_recall"],
                "atom_aware_precision": scores["atom_aware_precision"],
                "n_unadjudicated_extra_edges": unadj,
                "n_reference_edges": n_ref,
                "mean_reference_edge_distance": mean,
                "gate": gated,
                "route_sequence": actual,
                "full_source_conservation_safety": _conservation_ok(safety, unsupported_lost),
                "wall_clock_s": round(time.perf_counter() - started, 6),
                "primary": False,
            }
        )
    return {
        "schema": "bite-phase4e-realstruct1-retrospective/v0.1",
        "revision": REVISION,
        "role": "development / retrospective diagnostic",
        "not_holdout": True,
        "not_confirmatory": True,
        "not_generalization": True,
        "not_primary_pass_criterion": True,
        "eval_source_ids": list(EVAL_SOURCE_IDS),
        "documents": rows,
    }


def run_evaluation() -> dict[str, Any]:
    blocked = _blob_errors()
    rows: list[dict[str, Any]] = []
    secondary: dict[str, Any] = {
        "schema": "bite-phase4e-realstruct1-retrospective/v0.1",
        "not_holdout": True,
        "not_confirmatory": True,
        "documents": [],
    }
    try:
        committed = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
        policy = ConditionalTexturePolicyV5()
        for spec in committed["planned_cases"]:
            for fmt in spec["formats"]:
                rows.append(_surface_row(spec, str(fmt), policy))
        if len(rows) != N_SURFACES:
            blocked.append(f"surfaces {len(rows)} != {N_SURFACES}")
        blob = json.dumps(rows, sort_keys=True)
        if "p3f-" in blob:
            blocked.append("p3f identifier leaked")
        if "confirmatory" in blob:
            blocked.append("confirmatory wording leaked into primary")
        primary_ok = bool(rows) and all(row["ok"] for row in rows)
        if primary_ok and not blocked:
            secondary = _secondary(policy)
            sec_blob = json.dumps(secondary, sort_keys=True)
            if "holdout" in sec_blob and secondary.get("not_holdout") is not True:
                blocked.append("secondary unmarked holdout")
    except (PolicyLeakError, UnitizerError, EvaluationSealError, Exception) as exc:  # noqa: BLE001
        blocked.append(f"{type(exc).__name__}: {exc}")

    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_case[str(row["case_id"])].append(row)
    cross_ok = bool(by_case) and all(
        len(group) == len(FORMATS)
        and all(item["observed_edges"] == group[0]["observed_edges"] for item in group)
        and all(item["gate_observed"] == group[0]["gate_observed"] for item in group)
        and all(item["n_reference_edges"] == group[0]["n_reference_edges"] for item in group)
        and all(
            item["mean_reference_edge_distance"] == group[0]["mean_reference_edge_distance"]
            for item in group
        )
        for group in by_case.values()
    )
    edge_ok = bool(rows) and all(row["edge_set_exact"] for row in rows)
    false_zero = bool(rows) and all(row["false_reference_edges"] == 0 for row in rows)
    gate_ok = bool(rows) and all(row["gate_ok"] for row in rows)
    seq_ok = bool(rows) and all(row["policy_seq_ok"] for row in rows)
    safety_ok = bool(rows) and all(row["safety_ok"] for row in rows)
    bridge_rows = [row["bridge_row"] for row in rows if row.get("bridge_row")]
    bridge_ok = bool(bridge_rows) and all(item["exact"] for item in bridge_rows)
    n_ok = sum(1 for row in rows if row["ok"])
    runtime_ok = bool(rows) and all(row["wall_clock_s"] < 5.0 for row in rows)
    secondary_ok = bool(secondary.get("documents")) and secondary.get("not_holdout") is True
    if blocked:
        verdict = VERDICT_BLOCKED
    elif (
        n_ok == N_SURFACES
        and edge_ok
        and false_zero
        and gate_ok
        and seq_ok
        and safety_ok
        and cross_ok
        and bridge_ok
        and runtime_ok
        and secondary_ok
    ):
        verdict = VERDICT_VALIDATED
    else:
        verdict = VERDICT_PARTIAL
    result = {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "protocol_commit_sha": E0_COMMIT_SHA,
        "e0_freeze_blob": E0_FREEZE_BLOB,
        "verdict": verdict,
        "paid_api": False,
        "offline": True,
        "synthetic": True,
        "research_conclusion": False,
        "p3f_evaluation_holdout_used": False,
        "no_baseline_added": True,
        "no_realstruct2": True,
        "no_threshold_grid": True,
        "t_high_carry_forward": bridge_ok,
        "t_high_reference": LOCKED_T_HIGH if bridge_ok else None,
        "policy_name": "conditional_texture_policy_v5",
        "sensor_name": "dependency_dispersion_v4",
        "phase4c_verdict": PHASE4C_VERDICT,
        "phase4d_verdict": PREMISE,
        "phase3t_verdict": PHASE3T_VERDICT,
        "phase3s_verdict": PHASE3S_VERDICT,
        "phase3q_verdict": PHASE3Q_VERDICT,
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "new holdout evidence",
            "real-world generalization",
            "BITE superiority",
            "confirmatory",
        ],
        "n_surfaces": len(rows),
        "n_ok": n_ok,
        "errors": blocked,
        "checks": {
            "edge_set_exact": edge_ok,
            "false_reference_edges_zero": false_zero,
            "gate_expectation_exact": gate_ok,
            "cross_format_exact": cross_ok,
            "policy_consequence": seq_ok,
            "composition_safety": safety_ok,
            "v3_v4_bridge_exact": bridge_ok,
            "t_high_carry_forward": bridge_ok,
            "runtime_no_dfs_explosion": runtime_ok,
            "secondary_marked_retrospective": secondary_ok,
        },
    }
    _dump(
        EDGE_PATH,
        {
            "schema": "bite-phase4e-exact-edge/v0.1",
            "revision": REVISION,
            "n_ok": n_ok,
            "documents": [
                {
                    "surface_id": row["surface_id"],
                    "family": row["family"],
                    "format": row["format"],
                    "intended_reference_edges": row["intended_reference_edges"],
                    "observed_edges": row["observed_edges"],
                    "false_reference_edges": row["false_reference_edges"],
                    "edge_set_exact": row["edge_set_exact"],
                    "ok": row["ok"],
                }
                for row in rows
            ],
        },
    )
    _dump(
        BRIDGE_PATH,
        {
            "schema": "bite-phase4e-threshold-bridge/v0.1",
            "revision": REVISION,
            "ok": bridge_ok,
            "t_high_carry_forward": bridge_ok,
            "rows": bridge_rows,
        },
    )
    _dump(
        FMT_PATH,
        {
            "schema": "bite-phase4e-format-invariance/v0.1",
            "revision": REVISION,
            "ok": cross_ok,
            "cases": [
                {
                    "case_id": case_id,
                    "n_formats": len(group),
                    "edges": group[0]["observed_edges"] if group else [],
                    "gate": group[0]["gate_observed"] if group else False,
                    "ok": len(group) == len(FORMATS)
                    and all(item["observed_edges"] == group[0]["observed_edges"] for item in group),
                }
                for case_id, group in by_case.items()
            ],
        },
    )
    _dump(
        RUNTIME_PATH,
        {
            "schema": "bite-phase4e-runtime-diagnostic/v0.1",
            "revision": REVISION,
            "chain_span": "reachability_replacement",
            "no_evaluator_monkeypatch": True,
            "n_surfaces": len(rows),
            "max_wall_clock_s": max((row["wall_clock_s"] for row in rows), default=0.0),
            "ok": runtime_ok,
            "documents": [
                {"surface_id": row["surface_id"], "wall_clock_s": row["wall_clock_s"]}
                for row in rows
            ],
        },
    )
    _dump(SECONDARY_PATH, secondary)
    _dump(RESULT_PATH, result)
    return result


def validate_phase4e_result(doc: Mapping[str, Any]) -> list[str]:
    errs = _blob_errors()
    if doc.get("protocol_commit_sha") != E0_COMMIT_SHA:
        errs.append("E0 commit drifted")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f opened")
    if int(doc.get("n_surfaces") or 0) != 80:
        errs.append("surface count drifted")
    if doc.get("t_high_reference") not in {LOCKED_T_HIGH, None}:
        errs.append("T_high drifted")
    if doc.get("verdict") == VERDICT_VALIDATED:
        if doc.get("errors"):
            errs.append("VALIDATED with errors")
        if int(doc.get("n_ok") or 0) != 80:
            errs.append("VALIDATED without 80/80 ok")
        if doc.get("t_high_carry_forward") is not True:
            errs.append("VALIDATED without T=4 carry-forward")
    return errs


if __name__ == "__main__":
    payload = run_evaluation()
    print(payload["verdict"], "ok", payload["n_ok"], "errors", payload["errors"])
