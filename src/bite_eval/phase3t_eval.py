"""Phase 3T evaluation of exact-reference v3.

Does not change Phase 3S/3Q, v2 sensor, policy v3, planner, or operators.
Does not open p3f. Does not retune thresholds.
"""

from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bite_bench import phase3s as p3s
from bite_bench.phase3t import (
    CLAIM_BOUNDARY,
    FAMILIES,
    FORMATS,
    FREEZE_PATH,
    LOCKED_BLOBS,
    LOCKED_T_HIGH,
    N_SURFACES,
    PHASE3Q_PATH,
    PHASE3Q_REMAINS,
    PHASE3Q_VERDICT,
    PHASE3S_PATH,
    PHASE3S_REMAINS,
    PREMISE,
    PROTOCOL_FROZEN,
    S0_SHA,
    SECONDARY_SURFACES,
    T1_VERDICTS,
    VERDICT_BLOCKED,
    VERDICT_PARTIAL,
    VERDICT_VALIDATED,
    dest_index_for,
    forbidden_hits,
    freeze_manifest,
    gate_expected,
    intended_mean,
    intended_reference_edges,
    refuse_p3f_evaluation,
    render_records,
    validate_phase3t_freeze,
)
from bite_eval.composition_safety_v2 import composition_safety_v2
from bite_ingestion.adapters.bite_xfer2 import (
    UnitizerError,
    assert_no_annotation_leak,
    packet_from_document,
)
from bite_ingestion.policies.conditional_texture_policy_v4 import (
    ConditionalTexturePolicyV4,
    PolicyLeakError,
    assert_policy_gold_isolated,
)
from bite_ingestion.profilers.dependency_dispersion_v2 import measure as measure_v2
from bite_ingestion.profilers.dependency_dispersion_v3 import measure as measure_v3

SCHEMA_ID = "bite-phase3t-exact-reference/v0.1"
EDGE_SCHEMA_ID = "bite-phase3t-exact-edge/v0.1"
BRIDGE_SCHEMA_ID = "bite-phase3t-threshold-bridge/v0.1"
GATE_SCHEMA_ID = "bite-phase3t-gate/v0.1"
POLICY_SCHEMA_ID = "bite-phase3t-policy-consequence/v0.1"
REPRO_SCHEMA_ID = "bite-phase3t-phase3s-regression/v0.1"
PROTOCOL_COMMIT_SHA = "70a3f7792a5baee1382b890fb7021dc7fb234ce1"
_REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = _REPO / "artifacts" / "phase3t"
RESULT_PATH = ARTIFACT_DIR / "exact-reference.json"
RESULT_MD_PATH = ARTIFACT_DIR / "exact-reference.md"
EDGE_PATH = ARTIFACT_DIR / "exact-edge.json"
BRIDGE_PATH = ARTIFACT_DIR / "threshold-bridge.json"
GATE_PATH = ARTIFACT_DIR / "gate.json"
POLICY_PATH = ARTIFACT_DIR / "policy-consequence.json"
REPRO_PATH = ARTIFACT_DIR / "phase3s-regression.json"


def _git_blob(path: str) -> str:
    return subprocess.check_output(
        ["git", "hash-object", path], cwd=_REPO, text=True
    ).strip()


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


def _split_surface_id(surface_id: str) -> tuple[str, str]:
    for fmt in sorted(FORMATS, key=len, reverse=True):
        suffix = f"-{fmt}"
        if surface_id.endswith(suffix):
            return surface_id[: -len(suffix)], fmt
    raise ValueError(f"unknown surface {surface_id}")


def _p3s_parse(case_id: str) -> tuple[str, int]:
    slug = case_id.removeprefix("p3s-")
    fam_slug, dist_slug = slug.rsplit("-", 1)
    family = next(name for name, item in p3s.FAMILY_SLUG.items() if item == fam_slug)
    return family, int(dist_slug[1:])


def _premise_errors() -> list[str]:
    errs: list[str] = []
    if not FREEZE_PATH.is_file():
        return ["T0 freeze missing"]
    committed = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    errs.extend(validate_phase3t_freeze(committed))
    if committed.get("verdict") != PROTOCOL_FROZEN:
        errs.append("protocol not frozen")
    if freeze_manifest() != committed:
        errs.append("freeze drifted from generator")
    if not PHASE3S_PATH.is_file():
        errs.append("Phase 3S artifact missing")
    else:
        phase3s = json.loads(PHASE3S_PATH.read_text(encoding="utf-8"))
        if phase3s.get("verdict") != PREMISE:
            errs.append("Phase 3S verdict rewritten")
    if not PHASE3Q_PATH.is_file():
        errs.append("Phase 3Q artifact missing")
    else:
        phase3q = json.loads(PHASE3Q_PATH.read_text(encoding="utf-8"))
        if phase3q.get("verdict") != PHASE3Q_VERDICT:
            errs.append("Phase 3Q verdict rewritten")
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


def _surface_row(
    spec: Mapping[str, Any],
    fmt: str,
    policy: ConditionalTexturePolicyV4,
    *,
    connect_policy: bool,
) -> dict[str, Any]:
    case_id = str(spec["case_id"])
    refuse_p3f_evaluation(case_id)
    records = [(str(key), str(value)) for key, value in spec["records"]]
    document = render_records(records, fmt)
    hits = forbidden_hits(document)
    if hits:
        raise PolicyLeakError(f"gold leak in {case_id}: {hits}")
    intended = _pairs_key(intended_reference_edges(case_id))
    expect_gate = gate_expected(case_id)
    v3 = measure_v3({"payload": document, "text": document})
    observed = _pairs_key(_undirected_pairs(v3.edges))
    n_ref = float(v3.features["n_reference_edges"])
    mean = float(v3.features["mean_reference_edge_distance"])
    extra = [pair for pair in observed if pair not in intended]
    missing = [pair for pair in intended if pair not in observed]
    if not intended:
        edge_ok = n_ref == 0.0 and observed == []
    else:
        edge_ok = observed == intended and n_ref == float(len(intended))
    gated = (not v3.fail_closed) and n_ref > 0.0 and mean >= LOCKED_T_HIGH
    packet = packet_from_document(document, case_id=case_id, fmt=fmt)
    if "intended_reference_edges" in packet:
        raise PolicyLeakError("intended_reference_edges leaked into packet")
    assert_no_annotation_leak(packet)
    assert_policy_gold_isolated(packet)
    if connect_policy:
        after = policy.apply(packet)
        actual = _tau_sequence(after)
    else:
        after = dict(packet)
        actual = []
    expect_seq = list(spec.get("policy_sequence_expected") or [])
    safety = composition_safety_v2(
        packet, after, gold_ids=_gold_ids(case_id, packet), sequence=actual
    )
    bridge = None
    if spec.get("bridge"):
        v2 = measure_v2({"payload": document, "text": document})
        v2_obs = _pairs_key(_undirected_pairs(v2.edges))
        v2_n = float(v2.features["n_reference_edges"])
        v2_mean = float(v2.features["mean_reference_edge_distance"])
        bridge = {
            "v2_edges": v2_obs,
            "v3_edges": observed,
            "v2_n": v2_n,
            "v3_n": n_ref,
            "v2_mean": v2_mean,
            "v3_mean": mean,
            "exact": v2_obs == observed and v2_n == n_ref and v2_mean == mean,
        }
    ok = (
        edge_ok
        and gated is expect_gate
        and actual == expect_seq
        and bool(safety["ok"])
        and (not v3.fail_closed)
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
        "raw_edge_rows": list(v3.edges),
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
        "ok": ok,
    }


def _secondary() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    policy = ConditionalTexturePolicyV4()
    for surface_id in SECONDARY_SURFACES:
        refuse_p3f_evaluation(surface_id)
        cid, fmt = _split_surface_id(surface_id)
        family, dist = _p3s_parse(cid)
        document = p3s.render_records(p3s.records_for(cid), fmt)
        v3 = measure_v3({"payload": document, "text": document})
        observed = _pairs_key(_undirected_pairs(v3.edges))
        n_ref = float(v3.features["n_reference_edges"])
        mean = float(v3.features["mean_reference_edge_distance"])
        gated = (not v3.fail_closed) and n_ref > 0.0 and mean >= LOCKED_T_HIGH
        packet = packet_from_document(document, case_id=cid, fmt=fmt)
        seq = _tau_sequence(policy.apply(packet))
        intended = _pairs_key(p3s.intended_reference_edges(cid))
        if family == "suffix_collision_only":
            expect_ok = n_ref == 0.0 and not gated
        elif family == "true_reference_plus_suffix_collision":
            expect_ok = observed == intended
        elif family == "suffix_collision_plus_actionability" and dist in {4, 9}:
            expect_ok = (not gated) and seq == []
        elif family == "suffix_collision_plus_actionability":
            expect_ok = n_ref == 0.0 and seq == []
        else:
            expect_ok = False
        rows.append(
            {
                "surface_id": surface_id,
                "case_id": cid,
                "family": family,
                "format": fmt,
                "primary": False,
                "n_reference_edges": n_ref,
                "mean_reference_edge_distance": mean,
                "observed_edges": observed,
                "intended_reference_edges": intended,
                "gated": gated,
                "policy_sequence": seq,
                "ok": expect_ok,
            }
        )
    return {
        "schema": REPRO_SCHEMA_ID,
        "primary": False,
        "phase3s_remains": PHASE3S_REMAINS,
        "phase3s_verdict": PREMISE,
        "n_ok": sum(1 for row in rows if row["ok"]),
        "rows": rows,
    }


def run_evaluation() -> dict[str, Any]:
    blocked = _premise_errors()
    rows: list[dict[str, Any]] = []
    carry = False
    secondary = {
        "schema": REPRO_SCHEMA_ID,
        "primary": False,
        "phase3s_remains": PHASE3S_REMAINS,
        "phase3s_verdict": PREMISE,
        "n_ok": 0,
        "rows": [],
    }
    try:
        committed = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
        bridge_specs = [spec for spec in committed["planned_cases"] if spec.get("bridge")]
        policy = ConditionalTexturePolicyV4()
        # measure bridge first to decide policy connection
        carry = True
        for spec in bridge_specs:
            for fmt in spec["formats"]:
                probe = _surface_row(spec, str(fmt), policy, connect_policy=False)
                if not (probe.get("bridge_row") or {}).get("exact"):
                    carry = False
        if not bridge_specs:
            carry = False
        for spec in committed["planned_cases"]:
            for fmt in spec["formats"]:
                rows.append(_surface_row(spec, str(fmt), policy, connect_policy=carry))
        if len(rows) != N_SURFACES:
            blocked.append(f"surfaces {len(rows)} != {N_SURFACES}")
        secondary = _secondary()
        blob = json.dumps(rows, sort_keys=True)
        if "p3f-" in blob:
            blocked.append("p3f identifier leaked")
    except (PolicyLeakError, UnitizerError, Exception) as exc:  # noqa: BLE001
        blocked.append(f"{type(exc).__name__}: {exc}")
        carry = False

    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_case[str(row["case_id"])].append(row)
    cross_ok = bool(by_case) and all(
        len(group) == len(FORMATS)
        and all(item["observed_edges"] == group[0]["observed_edges"] for item in group)
        and all(item["gate_observed"] == group[0]["gate_observed"] for item in group)
        and all(item["policy_sequence"] == group[0]["policy_sequence"] for item in group)
        for group in by_case.values()
    )
    edge_ok = bool(rows) and all(row["edge_set_exact"] for row in rows)
    false_zero = bool(rows) and all(row["false_reference_edges"] == 0 for row in rows)
    gate_ok = bool(rows) and all(row["gate_ok"] for row in rows)
    seq_ok = bool(rows) and all(row["policy_seq_ok"] for row in rows)
    safety_ok = bool(rows) and all(row["safety_ok"] for row in rows)
    bridge_rows = [row["bridge_row"] for row in rows if row.get("bridge_row")]
    bridge_ok = bool(bridge_rows) and all(item["exact"] for item in bridge_rows)
    checks = {
        "edge_set_exact": edge_ok,
        "false_reference_edges_zero": false_zero,
        "exact_reference_distances": all(
            row["ok"] for row in rows if row["family"] == "exact_reference_only"
        ),
        "suffix_collision_no_edge": all(
            row["edge_set_exact"]
            for row in rows
            if row["family"] == "underscore_suffix_collision_only"
        ),
        "true_plus_collision_true_only": all(
            row["edge_set_exact"]
            for row in rows
            if row["family"] == "exact_reference_plus_suffix_collision"
        ),
        "gate_expectation_exact": gate_ok,
        "cross_format_exact": cross_ok,
        "policy_consequence": seq_ok,
        "composition_safety": safety_ok,
        "t_high_carry_forward": carry and bridge_ok,
        "phase3s_failed_unchanged": not any("Phase 3S" in item for item in blocked),
        "phase3q_failed_unchanged": not any("Phase 3Q" in item for item in blocked),
        "p3f_sealed": not any("p3f" in item.lower() for item in blocked),
        "frozen_unchanged": not any("blob drifted" in item for item in blocked),
        "reproduction_not_primary": secondary.get("primary") is False,
    }
    n_ok = sum(1 for row in rows if row["ok"])
    specificity = edge_ok and false_zero and gate_ok and seq_ok and cross_ok and safety_ok
    if blocked:
        verdict = VERDICT_BLOCKED
    elif specificity and carry and bridge_ok and n_ok == N_SURFACES:
        verdict = VERDICT_VALIDATED
    else:
        verdict = VERDICT_PARTIAL
    if verdict not in T1_VERDICTS:
        verdict = VERDICT_BLOCKED
        blocked.append("verdict not in frozen set")
    by_family = {
        family: {
            "n": sum(1 for row in rows if row["family"] == family),
            "n_ok": sum(1 for row in rows if row["family"] == family and row["ok"]),
        }
        for family in FAMILIES
    }
    return {
        "schema": SCHEMA_ID,
        "revision": "phase3t-exact-reference-v0.1",
        "protocol_revision": "phase3t-exact-reference-freeze-v0.1",
        "protocol_commit_sha": PROTOCOL_COMMIT_SHA,
        "phase3s_s0_sha": S0_SHA,
        "verdict": verdict,
        "blocked_reasons": blocked,
        "paid_api": False,
        "offline": True,
        "synthetic": True,
        "research_conclusion": False,
        "p3f_evaluation_holdout_used": False,
        "calibration": False,
        "no_threshold_grid": True,
        "no_planner_change": True,
        "t_high_carry_forward": carry and bridge_ok,
        "t_high_reference": LOCKED_T_HIGH if (carry and bridge_ok) else None,
        "policy_name": "conditional_texture_policy_v4" if (carry and bridge_ok) else None,
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "routing generalization",
            "real-world corpus generalization",
            "BITE superiority",
            "Phase3S CONFIRMED",
        ],
        "phase3s_remains": PHASE3S_REMAINS,
        "phase3q_remains": PHASE3Q_REMAINS,
        "token_reduction": "diagnostic_only",
        "no_winner_score": True,
        "cut_forbidden": True,
        "next_if_validated": "Phase 4 real-structured corpus; do not invent XFER-3",
        "checks": checks,
        "n_surfaces": len(rows),
        "n_ok": n_ok,
        "by_family": by_family,
        "exact_edge": {"schema": EDGE_SCHEMA_ID, "n_ok": n_ok, "rows": rows},
        "threshold_bridge": {
            "schema": BRIDGE_SCHEMA_ID,
            "ok": bridge_ok,
            "n_ok": sum(1 for item in bridge_rows if item["exact"]),
            "rows": bridge_rows,
        },
        "gate": {
            "schema": GATE_SCHEMA_ID,
            "n_ok": sum(1 for row in rows if row["gate_ok"]),
            "rows": [
                {
                    "surface_id": row["surface_id"],
                    "family": row["family"],
                    "gate_expected": row["gate_expected"],
                    "gate_observed": row["gate_observed"],
                    "ok": row["gate_ok"],
                }
                for row in rows
            ],
        },
        "policy_consequence": {
            "schema": POLICY_SCHEMA_ID,
            "n_ok": sum(1 for row in rows if row["policy_seq_ok"]),
            "rows": [
                {
                    "surface_id": row["surface_id"],
                    "family": row["family"],
                    "policy_sequence": row["policy_sequence"],
                    "ok": row["policy_seq_ok"],
                }
                for row in rows
                if row["family"]
                in {
                    "suffix_collision_plus_actionability",
                    "exact_reference_plus_suffix_collision",
                }
            ],
        },
        "phase3s_regression": secondary,
        "formats": list(FORMATS),
    }


def validate_phase3t_result(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("protocol_commit_sha") != PROTOCOL_COMMIT_SHA:
        errs.append("protocol commit SHA mismatch")
    if doc.get("verdict") not in T1_VERDICTS:
        errs.append("verdict not in frozen set")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation opened")
    if doc.get("calibration") is not False:
        errs.append("calibration ran")
    if doc.get("no_threshold_grid") is not True:
        errs.append("threshold grid ran")
    blob = json.dumps(doc, sort_keys=True)
    if "p3f-" in blob:
        errs.append("p3f identifier leaked")
    if doc.get("phase3s_remains") != PHASE3S_REMAINS:
        errs.append("Phase 3S remains line drifted")
    if doc.get("phase3q_remains") != PHASE3Q_REMAINS:
        errs.append("Phase 3Q remains line drifted")
    for row in doc.get("phase3s_regression", {}).get("rows") or []:
        if row.get("primary") is not False:
            errs.append("3S regression marked primary")
    return errs


def render_md(doc: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 3T exact reference identity v3",
        "",
        f"verdict: `{doc.get('verdict')}`",
        f"T0 SHA: `{doc.get('protocol_commit_sha')}`",
        f"ok: {doc.get('n_ok')}/{doc.get('n_surfaces')}",
        f"T_high carry-forward: `{doc.get('t_high_carry_forward')}`",
        f"phase3s: `{doc.get('phase3s_remains')}`",
        f"phase3q: `{doc.get('phase3q_remains')}`",
        "p3f evaluation: sealed",
        "",
        "## Checks",
        "",
    ]
    for key, ok in dict(doc.get("checks") or {}).items():
        lines.append(f"- {key}: `{ok}`")
    lines.extend(["", "## Families", ""])
    for family, stats in dict(doc.get("by_family") or {}).items():
        lines.append(f"- {family}: {stats.get('n_ok')}/{stats.get('n')}")
    lines.extend(
        [
            "",
            "routing / real-world generalization / BITE superiority ではない。",
            "VALIDATED なら次は Phase 4 real-structured corpus。XFER-3 は作らない。",
            "",
        ]
    )
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
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    RESULT_PATH.write_text(payload, encoding="utf-8")
    RESULT_MD_PATH.write_text(render_md(doc), encoding="utf-8")
    EDGE_PATH.write_text(
        json.dumps(doc["exact_edge"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    BRIDGE_PATH.write_text(
        json.dumps(doc["threshold_bridge"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    GATE_PATH.write_text(json.dumps(doc["gate"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    POLICY_PATH.write_text(
        json.dumps(doc["policy_consequence"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    REPRO_PATH.write_text(
        json.dumps(doc["phase3s_regression"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return RESULT_PATH, EDGE_PATH, BRIDGE_PATH, GATE_PATH, POLICY_PATH, REPRO_PATH


if __name__ == "__main__":
    write_artifacts()
