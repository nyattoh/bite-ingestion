"""Phase 3S evaluation of frozen dependency_dispersion_v2 reference-edge specificity.

Does not change Phase 3R/3Q, v2 sensor, planner, policy v3, or operators.
Does not open p3f. Does not repair _key_side_atoms or retune thresholds.
"""

from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bite_bench.phase3s import (
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
    PHASE3R_PATH,
    PREMISE,
    PROTOCOL_FROZEN,
    R0_SHA,
    S1_VERDICTS,
    VERDICT_BLOCKED,
    VERDICT_CONFIRMED,
    VERDICT_FAILED,
    forbidden_hits,
    freeze_manifest,
    gate_expected,
    intended_mean,
    intended_reference_edges,
    refuse_p3f_evaluation,
    render_records,
    validate_phase3s_freeze,
)
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
from bite_ingestion.profilers.dependency_dispersion_v2 import measure as measure_v2

SCHEMA_ID = "bite-phase3s-reference-specificity/v0.1"
EDGE_SCHEMA_ID = "bite-phase3s-edge-rows/v0.1"
PREC_SCHEMA_ID = "bite-phase3s-edge-precision/v0.1"
GATE_SCHEMA_ID = "bite-phase3s-gate/v0.1"
POLICY_SCHEMA_ID = "bite-phase3s-policy-consequence/v0.1"
CROSS_SCHEMA_ID = "bite-phase3s-cross-format/v0.1"
PROTOCOL_COMMIT_SHA = "3525506c4601f4471489a15f78d013900c05eda1"
_REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = _REPO / "artifacts" / "phase3s"
RESULT_PATH = ARTIFACT_DIR / "reference-specificity.json"
RESULT_MD_PATH = ARTIFACT_DIR / "reference-specificity.md"
EDGE_PATH = ARTIFACT_DIR / "edge-rows.json"
PREC_PATH = ARTIFACT_DIR / "edge-precision.json"
GATE_PATH = ARTIFACT_DIR / "gate.json"
POLICY_PATH = ARTIFACT_DIR / "policy-consequence.json"
CROSS_PATH = ARTIFACT_DIR / "cross-format.json"


def _git_blob(path: str) -> str:
    return subprocess.check_output(
        ["git", "hash-object", path],
        cwd=_REPO,
        text=True,
    ).strip()


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
    return sorted(([int(a), int(b)] if a <= b else [int(b), int(a)] for a, b in pairs), key=lambda item: (item[0], item[1]))


def _premise_errors() -> list[str]:
    errs: list[str] = []
    if not FREEZE_PATH.is_file():
        return ["S0 freeze missing"]
    committed = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    errs.extend(validate_phase3s_freeze(committed))
    if committed.get("verdict") != PROTOCOL_FROZEN:
        errs.append("protocol not frozen")
    if freeze_manifest() != committed:
        errs.append("freeze drifted from generator")
    if not PHASE3R_PATH.is_file():
        errs.append("Phase 3R artifact missing")
    else:
        phase3r = json.loads(PHASE3R_PATH.read_text(encoding="utf-8"))
        if phase3r.get("verdict") != PREMISE:
            errs.append("Phase 3R verdict rewritten")
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


def _surface_row(spec: Mapping[str, Any], fmt: str, policy: ConditionalTexturePolicyV3) -> dict[str, Any]:
    case_id = str(spec["case_id"])
    refuse_p3f_evaluation(case_id)
    records = [(str(key), str(value)) for key, value in spec["records"]]
    document = render_records(records, fmt)
    hits = forbidden_hits(document)
    if hits:
        raise PolicyLeakError(f"gold leak in {case_id}: {hits}")
    intended = _pairs_key(intended_reference_edges(case_id))
    expect_gate = gate_expected(case_id)
    report = measure_v2({"payload": document, "text": document})
    observed = _pairs_key(_undirected_pairs(report.edges))
    n_ref = float(report.features["n_reference_edges"])
    mean = float(report.features["mean_reference_edge_distance"])
    extra = [pair for pair in observed if pair not in intended]
    missing = [pair for pair in intended if pair not in observed]
    if not intended:
        edge_ok = n_ref == 0.0 and observed == []
    else:
        edge_ok = observed == intended and n_ref == float(len(intended))
    gated = (not report.fail_closed) and n_ref > 0.0 and mean >= LOCKED_T_HIGH
    packet = packet_from_document(document, case_id=case_id, fmt=fmt)
    if "intended_reference_edges" in packet:
        raise PolicyLeakError("intended_reference_edges leaked into packet")
    assert_no_annotation_leak(packet)
    assert_policy_gold_isolated(packet)
    after = policy.apply(packet)
    actual = _tau_sequence(after)
    expect_seq = list(spec.get("policy_sequence_expected") or [])
    act_family = spec["family"] == "suffix_collision_plus_actionability"
    seq_ok = actual == expect_seq
    gate_ok = gated is expect_gate
    return {
        "surface_id": f"{case_id}-{fmt}",
        "case_id": case_id,
        "family": spec["family"],
        "format": fmt,
        "distance": spec["distance"],
        "fail_closed": report.fail_closed,
        "intended_reference_edges": intended,
        "intended_mean": intended_mean(intended),
        "observed_edges": observed,
        "raw_edge_rows": list(report.edges),
        "n_reference_edges": n_ref,
        "mean_reference_edge_distance": mean,
        "extra_edges": extra,
        "missing_edges": missing,
        "false_reference_edges": len(extra),
        "edge_set_exact": edge_ok,
        "gate_expected": expect_gate,
        "gate_observed": gated,
        "gate_ok": gate_ok,
        "policy_sequence_expected": expect_seq,
        "policy_sequence": actual,
        "policy_seq_ok": seq_ok,
        "actionability_family": act_family,
        "ok": edge_ok and gate_ok and seq_ok and (not report.fail_closed),
    }


def run_evaluation() -> dict[str, Any]:
    blocked = _premise_errors()
    rows: list[dict[str, Any]] = []
    try:
        committed = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
        policy = ConditionalTexturePolicyV3()
        for spec in committed["planned_cases"]:
            for fmt in spec["formats"]:
                rows.append(_surface_row(spec, str(fmt), policy))
        if len(rows) != N_SURFACES:
            blocked.append(f"surfaces {len(rows)} != {N_SURFACES}")
        blob = json.dumps(rows, sort_keys=True)
        if "p3f-" in blob:
            blocked.append("p3f identifier leaked")
    except (PolicyLeakError, UnitizerError, Exception) as exc:  # noqa: BLE001
        blocked.append(f"{type(exc).__name__}: {exc}")

    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_case[str(row["case_id"])].append(row)
    cross_rows: list[dict[str, Any]] = []
    for case_id, group in sorted(by_case.items()):
        edges = [row["observed_edges"] for row in group]
        gates = [row["gate_observed"] for row in group]
        seqs = [row["policy_sequence"] for row in group]
        exact = (
            len(group) == len(FORMATS)
            and all(item == edges[0] for item in edges)
            and all(item == gates[0] for item in gates)
            and all(item == seqs[0] for item in seqs)
        )
        cross_rows.append(
            {
                "case_id": case_id,
                "family": group[0]["family"],
                "observed_edges": edges[0] if edges else [],
                "gate_observed": gates[0] if gates else None,
                "policy_sequence": seqs[0] if seqs else [],
                "ok": exact,
            }
        )
    edge_ok = bool(rows) and all(row["edge_set_exact"] for row in rows)
    false_zero = bool(rows) and all(row["false_reference_edges"] == 0 for row in rows)
    gate_ok = bool(rows) and all(row["gate_ok"] for row in rows)
    seq_ok = bool(rows) and all(row["policy_seq_ok"] for row in rows)
    cross_ok = bool(cross_rows) and all(row["ok"] for row in cross_rows)
    checks = {
        "edge_set_exact": edge_ok,
        "false_reference_edges_zero": false_zero,
        "gate_expectation_exact": gate_ok,
        "policy_consequence": seq_ok,
        "cross_format_exact": cross_ok,
        "phase3r_validated_unchanged": not any("Phase 3R" in item for item in blocked),
        "phase3q_failed_unchanged": not any("Phase 3Q" in item for item in blocked),
        "p3f_sealed": not any("p3f" in item.lower() for item in blocked),
        "frozen_unchanged": not any("blob drifted" in item for item in blocked),
        "no_repair": True,
    }
    n_ok = sum(1 for row in rows if row["ok"])
    if blocked:
        verdict = VERDICT_BLOCKED
    elif all(checks.values()) and n_ok == N_SURFACES:
        verdict = VERDICT_CONFIRMED
    else:
        verdict = VERDICT_FAILED
    if verdict not in S1_VERDICTS:
        verdict = VERDICT_BLOCKED
        blocked.append("verdict not in frozen set")
    extra_rows = [row for row in rows if row["false_reference_edges"] or row["missing_edges"]]
    act_rows = [row for row in rows if row["actionability_family"]]
    by_family = {
        family: {
            "n": sum(1 for row in rows if row["family"] == family),
            "n_ok": sum(1 for row in rows if row["family"] == family and row["ok"]),
        }
        for family in FAMILIES
    }
    return {
        "schema": SCHEMA_ID,
        "revision": "phase3s-reference-specificity-v0.1",
        "protocol_revision": "phase3s-reference-specificity-freeze-v0.1",
        "protocol_commit_sha": PROTOCOL_COMMIT_SHA,
        "phase3r_r0_sha": R0_SHA,
        "verdict": verdict,
        "blocked_reasons": blocked,
        "paid_api": False,
        "offline": True,
        "synthetic": True,
        "research_conclusion": False,
        "p3f_evaluation_holdout_used": False,
        "calibration": False,
        "no_threshold_grid": True,
        "no_repair": True,
        "no_key_side_atoms_change": True,
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "routing generalization",
            "real-world corpus generalization",
            "BITE superiority",
        ],
        "phase3q_remains": PHASE3Q_REMAINS,
        "phase3r_verdict_unchanged": True,
        "token_reduction": "diagnostic_only",
        "no_winner_score": True,
        "cut_forbidden": True,
        "checks": checks,
        "n_surfaces": len(rows),
        "n_ok": n_ok,
        "by_family": by_family,
        "edge_rows": {"schema": EDGE_SCHEMA_ID, "rows": rows},
        "edge_precision": {
            "schema": PREC_SCHEMA_ID,
            "n_extra": sum(row["false_reference_edges"] for row in rows),
            "n_missing": sum(len(row["missing_edges"]) for row in rows),
            "rows": extra_rows,
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
            "primary_family": "suffix_collision_plus_actionability",
            "n_ok": sum(1 for row in act_rows if row["policy_seq_ok"]),
            "rows": [
                {
                    "surface_id": row["surface_id"],
                    "gate_observed": row["gate_observed"],
                    "policy_sequence": row["policy_sequence"],
                    "ok": row["policy_seq_ok"] and not row["gate_observed"],
                }
                for row in act_rows
            ],
        },
        "cross_format": {
            "schema": CROSS_SCHEMA_ID,
            "n_ok": sum(1 for row in cross_rows if row["ok"]),
            "rows": cross_rows,
        },
        "formats": list(FORMATS),
    }


def validate_phase3s_result(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("protocol_commit_sha") != PROTOCOL_COMMIT_SHA:
        errs.append("protocol commit SHA mismatch")
    if doc.get("verdict") not in S1_VERDICTS:
        errs.append("verdict not in frozen set")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation opened")
    if doc.get("no_repair") is not True:
        errs.append("repair ran")
    if doc.get("calibration") is not False:
        errs.append("calibration ran")
    blob = json.dumps(doc, sort_keys=True)
    if "p3f-" in blob:
        errs.append("p3f identifier leaked")
    if doc.get("phase3q_remains") != PHASE3Q_REMAINS:
        errs.append("Phase 3Q remains line drifted")
    return errs


def render_md(doc: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 3S reference-edge specificity",
        "",
        f"verdict: `{doc.get('verdict')}`",
        f"S0 SHA: `{doc.get('protocol_commit_sha')}`",
        f"ok: {doc.get('n_ok')}/{doc.get('n_surfaces')}",
        f"phase3q: `{doc.get('phase3q_remains')}`",
        "p3f evaluation: sealed",
        "repair: none",
        "",
        "## Checks",
        "",
    ]
    for key, ok in dict(doc.get("checks") or {}).items():
        lines.append(f"- {key}: `{ok}`")
    lines.extend(["", "## Families", ""])
    for family, stats in dict(doc.get("by_family") or {}).items():
        lines.append(f"- {family}: {stats.get('n_ok')}/{stats.get('n')}")
    lines.extend(["", "routing / real-world generalization / BITE superiority ではない。", ""])
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
    EDGE_PATH.write_text(json.dumps(doc["edge_rows"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    PREC_PATH.write_text(
        json.dumps(doc["edge_precision"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    GATE_PATH.write_text(json.dumps(doc["gate"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    POLICY_PATH.write_text(
        json.dumps(doc["policy_consequence"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    CROSS_PATH.write_text(
        json.dumps(doc["cross_format"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return RESULT_PATH, EDGE_PATH, PREC_PATH, GATE_PATH, POLICY_PATH, CROSS_PATH


if __name__ == "__main__":
    write_artifacts()
