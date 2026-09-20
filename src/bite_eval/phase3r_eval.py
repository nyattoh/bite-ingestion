"""Phase 3R evaluation of reference-channel v2 and projected planner v1.

Does not change Phase 3Q/3O, v1 sensor, policy v2, operators, or safety v2.
Does not open p3f. Does not retune thresholds.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

from bite_bench.phase3r import (
    CARRY_FORWARD_T,
    CLAIM_BOUNDARY,
    DISTANCES,
    FORMATS,
    FREEZE_PATH,
    FROZEN_UNCHANGED,
    O0_SHA,
    PHASE3O_PATH,
    PHASE3O_VERDICT,
    PHASE3Q_PATH,
    PHASE3Q_REMAINS,
    PREMISE,
    PROTOCOL_FROZEN,
    Q0_SHA,
    R1_VERDICTS,
    REPRODUCTION_SURFACES,
    TRACK_B_EXPECT,
    VERDICT_BLOCKED,
    VERDICT_PARTIAL,
    VERDICT_VALIDATED,
    dest_index_for,
    development_surfaces,
    forbidden_hits,
    refuse_p3f_evaluation,
    validate_phase3r_freeze,
)
from bite_eval.composition_safety_v2 import composition_safety_v2
from bite_ingestion.adapters.bite_xfer2 import (
    UnitizerError,
    assert_no_annotation_leak,
    packet_from_document,
)
from bite_ingestion.policies.conditional_texture_policy_v3 import (
    ConditionalTexturePolicyV3,
    PolicyLeakError,
    assert_policy_gold_isolated,
)
from bite_ingestion.policies.projected_actionability_plan_v1 import (
    PlannerLeakError,
    actionable,
    apply_operator,
)
from bite_ingestion.policies.projected_actionability_plan_v1 import (
    plan as project_plan,
)
from bite_ingestion.profilers.dependency_dispersion_v1 import measure as measure_v1
from bite_ingestion.profilers.dependency_dispersion_v2 import measure as measure_v2

SCHEMA_ID = "bite-phase3r-channel-planner/v0.1"
CHANNEL_SCHEMA_ID = "bite-phase3r-channel-separation/v0.1"
PLANNER_SCHEMA_ID = "bite-phase3r-planner-integrity/v0.1"
SAFETY_SCHEMA_ID = "bite-phase3r-composition-safety/v0.1"
REPRO_SCHEMA_ID = "bite-phase3r-xfer2-regression/v0.1"
PROTOCOL_COMMIT_SHA = "d1f39ed6dd43180c132510a1723f7c884b6e693c"
LOCKED_BLOBS = {
    "src/bite_ingestion/profilers/dependency_dispersion_v1.py": (
        "890d777bb8179df27c8aeba35f1efebc133dd8eb"
    ),
    "src/bite_ingestion/policies/conditional_texture_policy_v2.py": (
        "848e1e65bf370fb7203be038630b95c61fc763cb"
    ),
    "src/bite_eval/composition_safety_v2.py": "85560279375b30f737eb3825cce72373be70488e",
    "src/bite_ingestion/operators/reduce_v2.py": "d4bafba7dfdd048a0ccad404a8f706202e2157b5",
    "src/bite_ingestion/operators/untangle.py": "2951b7542f96674930e750e438891ca772b46896",
    "src/bite_ingestion/operators/integrate.py": "68e34becd80e7e803f511ec57ea7a23c2aaa1240",
    "src/bite_ingestion/operators/preflight.py": "b3cc6946f515b3ca6f025500a4ffdad45c111eea",
    "src/bite_ingestion/profilers/structural_redundancy_v2.py": (
        "8960396c9a91872a1bfb0ccdaeae834d872cf12e"
    ),
    "src/bite_ingestion/logical_record.py": "c6f8cdd455cbc6814141fdb95458a72cc47b7af0",
}
_REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = _REPO / "artifacts" / "phase3r"
RESULT_PATH = ARTIFACT_DIR / "channel-planner.json"
RESULT_MD_PATH = ARTIFACT_DIR / "channel-planner.md"
CHANNEL_PATH = ARTIFACT_DIR / "channel-separation.json"
PLANNER_PATH = ARTIFACT_DIR / "planner-integrity.json"
SAFETY_PATH = ARTIFACT_DIR / "composition-safety.json"
REPRO_PATH = ARTIFACT_DIR / "xfer2-regression.json"
XFER2_DIR = _REPO / "corpora" / "bite-xfer-2" / "rendered"
_UNGATED = {"p3r-b-mid", "p3r-b-zero"}


def _git_blob(path: str) -> str:
    return subprocess.check_output(
        ["git", "hash-object", path],
        cwd=_REPO,
        text=True,
    ).strip()


def _units(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = packet.get("units") or []
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return [dict(unit) for unit in raw if isinstance(unit, Mapping)]
    return []


def _unit_ids(packet: Mapping[str, Any]) -> list[str]:
    return [str(unit.get("unit_id", "")) for unit in _units(packet) if unit.get("unit_id")]


def _tau_sequence(packet: Mapping[str, Any]) -> list[str]:
    tau = packet.get("tau")
    if isinstance(tau, Mapping):
        return [str(item) for item in list(tau.get("sequence") or [])]
    return []


def _empty_secondary() -> dict[str, Any]:
    return {
        "schema": REPRO_SCHEMA_ID,
        "primary": False,
        "phase3q_remains": PHASE3Q_REMAINS,
        "phase3q_verdict": PREMISE,
        "n_ok": 0,
        "rows": [],
    }


def _premise_errors() -> list[str]:
    errs: list[str] = []
    if not FREEZE_PATH.is_file():
        return ["R0 freeze missing"]
    committed = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    errs.extend(validate_phase3r_freeze(committed))
    if committed.get("verdict") != PROTOCOL_FROZEN:
        errs.append("protocol not frozen")
    if not PHASE3Q_PATH.is_file():
        errs.append("Phase 3Q artifact missing")
    else:
        phase3q = json.loads(PHASE3Q_PATH.read_text(encoding="utf-8"))
        if phase3q.get("verdict") != PREMISE:
            errs.append("Phase 3Q verdict rewritten")
    if not PHASE3O_PATH.is_file():
        errs.append("Phase 3O artifact missing")
    else:
        phase3o = json.loads(PHASE3O_PATH.read_text(encoding="utf-8"))
        if phase3o.get("verdict") != PHASE3O_VERDICT:
            errs.append("Phase 3O verdict rewritten")
    for path, expected in LOCKED_BLOBS.items():
        try:
            observed = _git_blob(path)
        except Exception as exc:  # noqa: BLE001
            errs.append(f"blob check failed {path}: {exc}")
            continue
        if observed != expected:
            errs.append(f"frozen blob drifted: {path}")
    return errs


def _gold_ids(case_id: str, packet: Mapping[str, Any]) -> list[str]:
    dest = dest_index_for(case_id)
    units = _units(packet)
    if dest is None or dest >= len(units):
        return []
    return [str(units[0]["unit_id"]), str(units[dest]["unit_id"])]


def _integrity(packet: Mapping[str, Any], projected: Mapping[str, Any]) -> dict[str, Any]:
    steps = list(projected.get("actionability_before_each_step") or [])
    sequence = list(projected.get("projected_sequence") or [])
    suppressed = {
        str(row["op"]): str(row["reason"]) for row in projected.get("suppressed_actions") or []
    }
    scratch = deepcopy(dict(packet))
    included_ok = True
    suppressed_ok = True
    for step in steps:
        op = str(step["op"])
        now = actionable(scratch, op)
        if bool(step["included"]) != now:
            included_ok = False
        if bool(step["actionable"]) != now:
            included_ok = False
        if step["included"]:
            if not now:
                included_ok = False
            scratch = apply_operator(scratch, op)
        elif op in suppressed and now:
            suppressed_ok = False
    replay = deepcopy(dict(packet))
    for op in sequence:
        if not actionable(replay, op):
            included_ok = False
        replay = apply_operator(replay, op)
    replay_ids = _unit_ids(replay)
    plan_ids = _unit_ids(scratch)
    return {
        "included_actionable_at_fire": included_ok,
        "suppressed_non_actionable_at_fire": suppressed_ok,
        "replay_equals_plan": replay_ids == plan_ids,
        "no_actionability_drift": replay_ids == plan_ids,
        "ok": included_ok and suppressed_ok and replay_ids == plan_ids,
    }


def _channel_row(surface: Mapping[str, Any]) -> dict[str, Any]:
    payload = str(surface["document"])
    v1 = measure_v1({"payload": payload, "text": payload})
    v2 = measure_v2({"payload": payload, "text": payload})
    mean = float(v2.features["mean_reference_edge_distance"])
    n_ref = float(v2.features["n_reference_edges"])
    expect_n = surface.get("n_reference_edges")
    expect_d = surface.get("distance")
    if expect_n == 0:
        n_ok = n_ref == 0.0
        mean_ok = mean == 0.0
    elif expect_d is not None:
        n_ok = n_ref == 1.0
        mean_ok = mean == float(expect_d)
    else:
        n_ok = False
        mean_ok = False
    v1_n = float(v1.features["n_edges"])
    v1_mean = float(v1.features["mean_edge_distance"])
    reference_only = surface.get("perturbation") == "none" and expect_n == 1
    match = (not v1.fail_closed) and (not v2.fail_closed) and v1_n == n_ref and v1_mean == mean
    return {
        "surface_id": surface["surface_id"],
        "case_id": surface["case_id"],
        "format": surface["format"],
        "perturbation": surface.get("perturbation"),
        "expect_distance": expect_d,
        "v1_n_edges": v1_n,
        "v1_mean": v1_mean,
        "n_reference_edges": n_ref,
        "mean_reference_edge_distance": mean,
        "v2_fail_closed": v2.fail_closed,
        "mean_ok": mean_ok,
        "n_ok": n_ok,
        "reference_only": reference_only,
        "v1_v2_exact": match if reference_only else None,
        "ok": mean_ok and n_ok and (not v2.fail_closed),
    }


def _planner_row(
    surface: Mapping[str, Any],
    policy: ConditionalTexturePolicyV3,
    *,
    connect_policy: bool,
) -> dict[str, Any]:
    cid = str(surface["case_id"])
    fmt = str(surface["format"])
    packet = packet_from_document(str(surface["document"]), case_id=cid, fmt=fmt)
    assert_no_annotation_leak(packet)
    assert_policy_gold_isolated(packet)
    projected = project_plan(packet)
    expect = list(surface.get("expected_sequence") or TRACK_B_EXPECT.get(cid) or [])
    integrity = _integrity(packet, projected)
    if connect_policy:
        after = policy.apply(packet)
        actual = _tau_sequence(after)
    else:
        after = dict(packet)
        actual = []
    safety = composition_safety_v2(
        packet,
        after,
        gold_ids=_gold_ids(cid, packet),
        sequence=actual,
    )
    plan_seq = list(projected["projected_sequence"])
    if cid in _UNGATED:
        plan_ok = True
        policy_seq_ok = actual == []
        replay_ok = True
    elif not connect_policy:
        plan_ok = plan_seq == expect
        policy_seq_ok = True
        replay_ok = True
    else:
        plan_ok = plan_seq == expect
        policy_seq_ok = actual == expect
        replay_ok = actual == plan_seq
    ok = plan_ok and policy_seq_ok and integrity["ok"] and bool(safety["ok"]) and replay_ok
    return {
        "surface_id": surface["surface_id"],
        "case_id": cid,
        "format": fmt,
        "projected_sequence": plan_seq,
        "expected_sequence": expect,
        "policy_sequence": actual,
        "suppressed_actions": list(projected["suppressed_actions"]),
        "initial_actionability": dict(projected["initial_actionability"]),
        "actionability_before_each_step": list(projected["actionability_before_each_step"]),
        "integrity": integrity,
        "safety_ok": bool(safety["ok"]),
        "safety": safety,
        "plan_ok": plan_ok,
        "policy_seq_ok": policy_seq_ok,
        "ok": ok,
    }


def _split_surface_id(surface_id: str) -> tuple[str, str]:
    for fmt in sorted(FORMATS, key=len, reverse=True):
        suffix = f"-{fmt}"
        if surface_id.endswith(suffix):
            return surface_id[: -len(suffix)], fmt
    raise ValueError(f"unknown surface {surface_id}")


def _secondary() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for surface_id in REPRODUCTION_SURFACES:
        refuse_p3f_evaluation(surface_id)
        cid, fmt = _split_surface_id(surface_id)
        ext = "txt" if fmt == "key_value" else "json"
        path = XFER2_DIR / f"{cid}.{fmt}.{ext}"
        document = path.read_text(encoding="utf-8")
        packet = packet_from_document(document, case_id=cid, fmt=fmt)
        v2 = measure_v2({"payload": document, "text": document})
        mean = float(v2.features["mean_reference_edge_distance"])
        n_ref = float(v2.features["n_reference_edges"])
        gated = n_ref > 0.0 and mean >= CARRY_FORWARD_T and not v2.fail_closed
        seq = list(project_plan(packet)["projected_sequence"])
        if cid == "xfer2-q014":
            expect_ok = mean == 3.0 and not gated
        elif cid == "xfer2-q027":
            expect_ok = seq == ["REDUCE_v2"]
        elif cid == "xfer2-q028":
            expect_ok = seq == ["UNTANGLE"]
        else:
            expect_ok = False
        rows.append(
            {
                "surface_id": surface_id,
                "case_id": cid,
                "format": fmt,
                "primary": False,
                "mean_reference_edge_distance": mean,
                "n_reference_edges": n_ref,
                "gated": gated,
                "projected_sequence": seq,
                "ok": expect_ok,
            }
        )
    return {
        "schema": REPRO_SCHEMA_ID,
        "primary": False,
        "phase3q_remains": PHASE3Q_REMAINS,
        "phase3q_verdict": PREMISE,
        "n_ok": sum(1 for row in rows if row["ok"]),
        "rows": rows,
    }


def run_evaluation() -> dict[str, Any]:
    blocked = _premise_errors()
    channel_rows: list[dict[str, Any]] = []
    planner_rows: list[dict[str, Any]] = []
    secondary = _empty_secondary()
    carry = False
    ref_only: list[dict[str, Any]] = []
    try:
        surfaces = development_surfaces()
        for surface in surfaces:
            refuse_p3f_evaluation(str(surface["case_id"]))
            hits = forbidden_hits(str(surface["document"]))
            if hits:
                raise PolicyLeakError(f"gold leak in {surface['case_id']}: {hits}")
        track_a = [row for row in surfaces if row["track"] == "A"]
        track_b = [row for row in surfaces if row["track"] == "B"]
        if len(track_a) != 56:
            blocked.append(f"track A surfaces {len(track_a)} != 56")
        for surface in track_a:
            channel_rows.append(_channel_row(surface))
        ref_only = [row for row in channel_rows if row["reference_only"]]
        carry = bool(ref_only) and all(row.get("v1_v2_exact") for row in ref_only)
        policy = ConditionalTexturePolicyV3()
        for surface in track_b:
            planner_rows.append(_planner_row(surface, policy, connect_policy=carry))
        secondary = _secondary()
    except (PolicyLeakError, PlannerLeakError, UnitizerError, Exception) as exc:  # noqa: BLE001
        blocked.append(f"{type(exc).__name__}: {exc}")

    by_dist: dict[int, set[float]] = {}
    hop_distances = set(DISTANCES.values())
    for row in channel_rows:
        expect_d = row.get("expect_distance")
        if not isinstance(expect_d, (int, float)):
            continue
        dist_i = int(expect_d)
        if dist_i in hop_distances and row.get("n_ok") and row.get("mean_ok"):
            by_dist.setdefault(dist_i, set()).add(float(row["mean_reference_edge_distance"]))
    invariance = set(by_dist) == set(DISTANCES.values()) and all(
        len(vals) == 1 and next(iter(vals)) == float(dist) for dist, vals in by_dist.items()
    )
    track_a_ok = bool(channel_rows) and all(row["ok"] for row in channel_rows) and len(channel_rows) == 56
    ref_eq = bool(ref_only) and all(row.get("v1_v2_exact") for row in ref_only)
    track_b_ok = bool(planner_rows) and all(row["ok"] for row in planner_rows)
    integrity_ok = bool(planner_rows) and all(row["integrity"]["ok"] for row in planner_rows)
    safety_ok = bool(planner_rows) and all(row["safety_ok"] for row in planner_rows)
    blob = json.dumps({"a": channel_rows, "b": planner_rows}, sort_keys=True)
    if "p3f-" in blob:
        blocked.append("p3f identifier leaked")
    checks = {
        "track_a_56": track_a_ok,
        "reference_only_v1_v2_exact": ref_eq,
        "join_perturbation_invariance": invariance,
        "t_high_carry_forward": carry,
        "track_b_projected_sequence": track_b_ok,
        "planner_integrity": integrity_ok,
        "composition_safety": safety_ok,
        "frozen_unchanged": not any("blob drifted" in item for item in blocked),
        "phase3q_failed_unchanged": not any("Phase 3Q" in item for item in blocked),
        "p3f_sealed": not any("p3f" in item.lower() for item in blocked),
        "reproduction_not_primary": secondary.get("primary") is False,
    }
    if blocked:
        verdict = VERDICT_BLOCKED
    elif all(checks.values()):
        verdict = VERDICT_VALIDATED
    else:
        verdict = VERDICT_PARTIAL
    if verdict not in R1_VERDICTS:
        verdict = VERDICT_BLOCKED
        blocked.append("verdict not in frozen set")
    safety_rows = [
        {
            "surface_id": row["surface_id"],
            "case_id": row["case_id"],
            "format": row["format"],
            "sequence": row["policy_sequence"],
            **row["safety"],
        }
        for row in planner_rows
    ]
    return {
        "schema": SCHEMA_ID,
        "revision": "phase3r-channel-planner-v0.1",
        "protocol_revision": "phase3r-channel-planner-freeze-v0.1",
        "protocol_commit_sha": PROTOCOL_COMMIT_SHA,
        "phase3q_q0_sha": Q0_SHA,
        "phase3o_o0_sha": O0_SHA,
        "verdict": verdict,
        "blocked_reasons": blocked,
        "paid_api": False,
        "offline": True,
        "synthetic": True,
        "research_conclusion": False,
        "p3f_evaluation_holdout_used": False,
        "calibration": False,
        "no_threshold_grid": True,
        "no_new_ak_threshold": True,
        "no_operator_semantic_change": True,
        "t_high_carry_forward": carry,
        "t_high_reference": CARRY_FORWARD_T if carry else None,
        "policy_name": "conditional_texture_policy_v3" if carry else None,
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "Phase3Q TRANSFER_CONFIRMED",
            "new calibration of T_high",
            "real-world corpus generalization",
            "BITE superiority",
        ],
        "frozen_unchanged": list(FROZEN_UNCHANGED),
        "phase3q_remains": PHASE3Q_REMAINS,
        "phase3o_verdict_unchanged": True,
        "token_reduction": "diagnostic_only",
        "no_winner_score": True,
        "cut_forbidden": True,
        "checks": checks,
        "n_track_a": len(channel_rows),
        "n_track_a_ok": sum(1 for row in channel_rows if row["ok"]),
        "n_track_b": len(planner_rows),
        "n_track_b_ok": sum(1 for row in planner_rows if row["ok"]),
        "channel_separation": {
            "schema": CHANNEL_SCHEMA_ID,
            "n_ok": sum(1 for row in channel_rows if row["ok"]),
            "n_surfaces": len(channel_rows),
            "rows": channel_rows,
        },
        "planner_integrity": {
            "schema": PLANNER_SCHEMA_ID,
            "n_ok": sum(1 for row in planner_rows if row["ok"]),
            "n_surfaces": len(planner_rows),
            "rows": [
                {key: row[key] for key in row if key != "safety"} for row in planner_rows
            ],
        },
        "composition_safety": {
            "schema": SAFETY_SCHEMA_ID,
            "n_ok": sum(1 for row in safety_rows if row.get("ok")),
            "rows": safety_rows,
        },
        "xfer2_regression": secondary,
        "formats": list(FORMATS),
    }


def validate_phase3r_result(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("protocol_commit_sha") != PROTOCOL_COMMIT_SHA:
        errs.append("protocol commit SHA mismatch")
    if doc.get("verdict") not in R1_VERDICTS:
        errs.append("verdict not in frozen set")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation opened")
    if doc.get("calibration") is not False:
        errs.append("calibration ran")
    if doc.get("no_threshold_grid") is not True:
        errs.append("threshold grid ran")
    if doc.get("no_new_ak_threshold") is not True:
        errs.append("new a/k threshold")
    blob = json.dumps(doc, sort_keys=True)
    if "p3f-" in blob:
        errs.append("p3f identifier leaked")
    if doc.get("phase3q_remains") != PHASE3Q_REMAINS:
        errs.append("Phase 3Q remains line drifted")
    for row in doc.get("xfer2_regression", {}).get("rows") or []:
        if row.get("primary") is not False:
            errs.append("3Q regression marked primary")
    return errs


def render_md(doc: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 3R reference-channel and projected planner",
        "",
        f"verdict: `{doc.get('verdict')}`",
        f"R0 SHA: `{doc.get('protocol_commit_sha')}`",
        f"track A: {doc.get('n_track_a_ok')}/{doc.get('n_track_a')}",
        f"track B: {doc.get('n_track_b_ok')}/{doc.get('n_track_b')}",
        f"T_high carry-forward: `{doc.get('t_high_carry_forward')}`",
        f"phase3q: `{doc.get('phase3q_remains')}`",
        "p3f evaluation: sealed",
        "",
        "## Checks",
        "",
    ]
    for key, ok in dict(doc.get("checks") or {}).items():
        lines.append(f"- {key}: `{ok}`")
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
    CHANNEL_PATH.write_text(
        json.dumps(doc["channel_separation"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    PLANNER_PATH.write_text(
        json.dumps(doc["planner_integrity"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    SAFETY_PATH.write_text(
        json.dumps(doc["composition_safety"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    REPRO_PATH.write_text(
        json.dumps(doc["xfer2_regression"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return RESULT_PATH, CHANNEL_PATH, PLANNER_PATH, SAFETY_PATH, REPRO_PATH


if __name__ == "__main__":
    write_artifacts()
