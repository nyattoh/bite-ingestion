"""Phase 3R channel-separation and projected-planner protocol (R0).

Freezes repair semantics before implementation. Does not implement
sensors, planners, or policy v3. Does not change Phase 3Q/3O artifacts.
Does not open p3f. Does not retune thresholds. Does not change operators.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA_ID = "bitebench-phase3r-channel-planner-freeze/v0.1"
REVISION = "phase3r-channel-planner-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE3R_CHANNEL_PLANNER_PROTOCOL_FROZEN"
VERDICT_VALIDATED = "PHASE3R_CHANNEL_PLANNER_VALIDATED"
VERDICT_PARTIAL = "PHASE3R_CHANNEL_PLANNER_PARTIAL"
VERDICT_BLOCKED = "PHASE3R_CHANNEL_PLANNER_BLOCKED"
R1_VERDICTS = (VERDICT_VALIDATED, VERDICT_PARTIAL, VERDICT_BLOCKED)
PREMISE = "PHASE3Q_XFER2_TRANSFER_FAILED"
PHASE3O_VERDICT = "PHASE3O_XFER1_TRANSFER_FAILED"
PHASE3Q_REMAINS = "Phase3Q remains FAILED"
PHASE3O_REMAINS = "Phase3O remains FAILED; known failures are repaired in development"
Q0_SHA = "67bfd22f782c6663de6e977848a5a381cd62ae51"
Q1_SHA = "1dab2d07a3a79b682e37f74b1265ab5eaef2cbef"
O0_SHA = "76998156d3cbf67fc0a53e151688e46bd3c26dc7"
GENERATION = "p3r"
FORMATS = ("key_value", "compact_json", "pretty_json", "reversed_order_json")
OPERATOR_ORDER = ("UNTANGLE", "REDUCE_v2", "INTEGRATE")
DISTANCES = {"near": 1, "mid": 3, "high": 9}
PERTURBATIONS = ("none", "adj", "far", "mix")
CARRY_FORWARD_T = 4.0
CLAIM_BOUNDARY = (
    "development repair of reference-channel separation and projected actionability"
)
FROZEN_UNCHANGED = (
    "dependency_dispersion_v1",
    "conditional_texture_policy_v2",
    "composition_safety_v2",
    "structural_redundancy_v2",
    "LogicalReduceOperatorV2",
    "UntangleOperator",
    "IntegrateOperator",
    "preflight",
    "RulePolicy",
)
REPRODUCTION_SURFACES = (
    "xfer2-q014-key_value",
    "xfer2-q014-compact_json",
    "xfer2-q014-pretty_json",
    "xfer2-q014-reversed_order_json",
    "xfer2-q027-key_value",
    "xfer2-q027-compact_json",
    "xfer2-q027-pretty_json",
    "xfer2-q027-reversed_order_json",
    "xfer2-q028-key_value",
    "xfer2-q028-compact_json",
    "xfer2-q028-pretty_json",
    "xfer2-q028-reversed_order_json",
)
TRACK_B_EXPECT = {
    "p3r-b-disj": ["REDUCE_v2", "INTEGRATE"],
    "p3r-b-eq2": ["REDUCE_v2"],
    "p3r-b-sub3": ["REDUCE_v2", "INTEGRATE"],
    "p3r-b-an2": ["UNTANGLE"],
    "p3r-b-an3": ["UNTANGLE", "INTEGRATE"],
    "p3r-b-adup": ["UNTANGLE"],
    "p3r-b-alld": ["UNTANGLE", "REDUCE_v2", "INTEGRATE"],
    "p3r-b-twoj": ["UNTANGLE", "INTEGRATE"],
    "p3r-b-mid": [],
    "p3r-b-zero": [],
}
SUPPRESSION_REASONS = (
    "blocked_by_quarantine",
    "subsumed_by_reduce",
    "no_longer_actionable",
)

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase3r-channel-planner-freeze.json"
PHASE3Q_PATH = _REPO / "artifacts" / "phase3q" / "xfer2-transfer.json"
PHASE3O_PATH = _REPO / "artifacts" / "phase3o" / "xfer1-transfer.json"


class EvaluationSealError(RuntimeError):
    """p3f evaluation replicas 2/3 stay sealed."""


def refuse_p3f_evaluation(case_id: str) -> None:
    cid = str(case_id)
    if cid.startswith("p3f-") and ("-r2" in cid or "-r3" in cid):
        raise EvaluationSealError(f"p3f evaluation sealed: refused {cid}")


def planned_track_a_cases() -> list[dict[str, Any]]:
    cases = []
    for dist, distance in DISTANCES.items():
        for pert in PERTURBATIONS:
            cases.append(
                {
                    "case_id": f"p3r-a-{dist}-{pert}",
                    "track": "A",
                    "distance": distance,
                    "perturbation": pert,
                    "n_reference_edges": 1,
                    "formats": list(FORMATS),
                }
            )
    cases.append(
        {
            "case_id": "p3r-a-zfil",
            "track": "A",
            "distance": 0,
            "perturbation": "none",
            "n_reference_edges": 0,
            "formats": list(FORMATS),
        }
    )
    cases.append(
        {
            "case_id": "p3r-a-zjoin",
            "track": "A",
            "distance": 0,
            "perturbation": "join_only",
            "n_reference_edges": 0,
            "formats": list(FORMATS),
        }
    )
    return cases


def planned_track_b_cases() -> list[dict[str, Any]]:
    roles = {
        "p3r-b-disj": "disjoint_duplicate_and_join",
        "p3r-b-eq2": "duplicate_equals_two_way_join",
        "p3r-b-sub3": "duplicate_subset_of_three_way_join",
        "p3r-b-an2": "anomaly_in_two_way_join",
        "p3r-b-an3": "anomaly_in_three_way_join",
        "p3r-b-adup": "anomaly_in_two_way_duplicate",
        "p3r-b-alld": "anomaly_duplicate_join_disjoint",
        "p3r-b-twoj": "two_joins_quarantine_destroys_one",
        "p3r-b-mid": "mid_reference_control",
        "p3r-b-zero": "zero_reference_edge_control",
    }
    out = []
    for case_id, role in roles.items():
        high = case_id not in {"p3r-b-mid", "p3r-b-zero"}
        out.append(
            {
                "case_id": case_id,
                "track": "B",
                "role": role,
                "high_reference": high,
                "expected_sequence": list(TRACK_B_EXPECT[case_id]),
                "formats": list(FORMATS),
            }
        )
    return out


def freeze_manifest() -> dict[str, Any]:
    return {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "verdict": PROTOCOL_FROZEN,
        "paid_api": False,
        "offline": True,
        "synthetic": True,
        "research_conclusion": False,
        "premise": PREMISE,
        "phase3q_q0_sha": Q0_SHA,
        "phase3q_head_sha": Q1_SHA,
        "phase3q_artifact_unchanged": True,
        "phase3q_verdict_unchanged": True,
        "phase3q_remains": PHASE3Q_REMAINS,
        "phase3o_verdict": PHASE3O_VERDICT,
        "phase3o_o0_sha": O0_SHA,
        "phase3o_remains": PHASE3O_REMAINS,
        "generation": GENERATION,
        "copy_xfer2_cases": False,
        "p3f_evaluation_holdout_used": False,
        "calibration": False,
        "no_threshold_grid": True,
        "no_operator_semantic_change": True,
        "no_new_ak_threshold": True,
        "repair_targets": [
            "reference_vs_explicit_join_channel_separation",
            "projected_actionability_operator_sequence",
        ],
        "frozen_unchanged": list(FROZEN_UNCHANGED),
        "track_a": {
            "sensor": "dependency_dispersion_v2",
            "does_not_change_v1": True,
            "primary": ["n_reference_edges", "mean_reference_edge_distance"],
            "mask": "id=<token> and key=<token> spans in KV value / JSON v only",
            "no_rewrite_of_records": True,
            "fail_closed": ["malformed", "nul"],
            "fuzzy": False,
            "join_not_in_dependency_score": True,
            "distances": dict(DISTANCES),
            "perturbations": list(PERTURBATIONS),
            "n_surfaces": 56,
            "carry_forward": {
                "candidate": CARRY_FORWARD_T,
                "not_a_new_calibration": True,
                "requires_v1_v2_exact_match_on_reference_only": True,
                "fields": ["edge_count", "raw_mean_distance"],
            },
        },
        "track_b": {
            "planner": "projected_actionability_plan_v1",
            "policy": "conditional_texture_policy_v3",
            "does_not_change_v2": True,
            "order": list(OPERATOR_ORDER),
            "cut_forbidden": True,
            "project_on_scratch": True,
            "initial_integrate_not_sufficient": True,
            "suppression_reasons": list(SUPPRESSION_REASONS),
            "gate": "n_reference_edges>0 AND mean_reference_edge_distance>=4",
            "gate_requires_carry_forward": True,
            "expected_sequences": {key: list(val) for key, val in TRACK_B_EXPECT.items()},
        },
        "formats": list(FORMATS),
        "planned_track_a": planned_track_a_cases(),
        "planned_track_b": planned_track_b_cases(),
        "reproduction_only_surfaces": list(REPRODUCTION_SURFACES),
        "reproduction_not_primary_evidence": True,
        "reproduction_expect": {
            "xfer2-q014": {"mean_reference_edge_distance": 3, "gated": False},
            "xfer2-q027": {"projected_sequence": ["REDUCE_v2"]},
            "xfer2-q028": {"projected_sequence": ["UNTANGLE"]},
        },
        "invariants": {
            "join_perturbation_invariance": True,
            "reference_only_v1_v2_exact": True,
            "projected_sequence_exact": True,
            "included_actionable_at_fire": True,
            "suppressed_non_actionable_at_fire": True,
            "replay_equals_plan": True,
            "no_actionability_drift": True,
            "lineage_recall": 1.0,
            "provenance_completeness": 1.0,
            "conservation_untraced": [],
            "silent_loss": 0,
            "r_recoverable": True,
            "no_unrelated_overmerge": True,
        },
        "r1_verdicts": list(R1_VERDICTS),
        "verdict_rule": {
            VERDICT_VALIDATED: (
                "fresh p3r: Track A 56/56; reference-only v1/v2 exact; join perturbation "
                "invariance; T_high=4 carry-forward; Track B projected sequence exact; "
                "planner integrity; composition safety; frozen components unchanged"
            ),
            VERDICT_PARTIAL: (
                "one track only, or threshold carry-forward cannot be established"
            ),
            VERDICT_BLOCKED: "protocol drift / fair validation cannot run / provenance failure",
        },
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "Phase3Q TRANSFER_CONFIRMED",
            "Phase3O TRANSFER_CONFIRMED",
            "new calibration of T_high",
            "real-world corpus generalization",
            "BITE superiority",
        ],
        "token_reduction": "diagnostic_only",
        "no_winner_score": True,
        "cut_forbidden": True,
        "rule_policy_unchanged": True,
    }


def validate_phase3r_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("revision") != REVISION:
        errs.append("revision mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("protocol not frozen")
    if doc.get("premise") != PREMISE:
        errs.append("Phase 3Q premise drifted")
    if doc.get("phase3q_verdict_unchanged") is not True:
        errs.append("Phase 3Q verdict must stay unchanged")
    if doc.get("copy_xfer2_cases") is not False:
        errs.append("must not copy XFER-2 cases")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("no_threshold_grid") is not True:
        errs.append("threshold grid forbidden")
    if doc.get("no_operator_semantic_change") is not True:
        errs.append("operator semantic change forbidden")
    if list(doc.get("reproduction_only_surfaces") or []) != list(REPRODUCTION_SURFACES):
        errs.append("reproduction surfaces drifted")
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
    return errs


def write_freeze() -> Path:
    FREEZE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FREEZE_PATH.write_text(
        json.dumps(freeze_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return FREEZE_PATH


FORBIDDEN_BODY = (
    "texture",
    "REDUCE",
    "UNTANGLE",
    "INTEGRATE",
    "expected_sequence",
    "xfer2-",
    "p3q-",
    "p3p-",
    "p3m-",
    "p3f-",
    "hop_p3m",
)


def _stem(case_id: str) -> str:
    return case_id.replace("-", "_")


def _fill(cid: str, n: int, start: int = 0) -> list[tuple[str, str]]:
    return [
        (f"note_canal_{cid}_{i:02d}", f"blob_canal_{cid}_{i:02d}")
        for i in range(start, start + n)
    ]


def _hop(cid: str, distance: int) -> list[tuple[str, str]]:
    n_between = max(int(distance) - 1, 0)
    return [
        (f"src_pier_{cid}", f"tide_lock_{cid}"),
        *_fill(cid, n_between),
        (f"dst_tide_lock_{cid}", f"wake_{cid}"),
    ]


def _id_join(cid: str, n: int = 2, *, fatal_index: int | None = None) -> list[tuple[str, str]]:
    token = f"id=folio_{cid}"
    rows = []
    for i in range(n):
        value = f"crate_{chr(97 + i)}_{cid} {token}"
        if fatal_index == i:
            value = f"{value} CCD readout FATAL"
        rows.append((f"mate_{chr(97 + i)}_{cid}", value))
    return rows


def _key_join(cid: str, n: int = 2) -> list[tuple[str, str]]:
    token = f"key=vat_{cid}"
    return [
        (f"alt_{chr(97 + i)}_{cid}", f"hold_{chr(97 + i)}_{cid} {token}") for i in range(n)
    ]


def _dup(cid: str, tag: str = "main") -> list[tuple[str, str]]:
    pair = (f"copy_{tag}_{cid}", f"same_{tag}_{cid}_row")
    return [pair, pair]


def records_for(case_id: str) -> list[tuple[str, str]]:
    cid = _stem(case_id)
    if case_id == "p3r-a-zfil":
        return _fill(cid, 6)
    if case_id == "p3r-a-zjoin":
        return [*_id_join(cid), *_key_join(cid)]
    if case_id.startswith("p3r-a-"):
        rest = case_id.removeprefix("p3r-a-")
        dist, pert = rest.split("-", 1)
        rows = _hop(cid, DISTANCES[dist])
        if pert == "adj":
            rows.extend(_id_join(cid))
        elif pert == "far":
            rows.extend(_fill(cid, 5, start=20))
            rows.extend(_key_join(cid))
        elif pert == "mix":
            rows.extend(_id_join(cid))
            rows.extend(_fill(cid, 5, start=20))
            rows.extend(_key_join(cid))
        return rows
    if case_id == "p3r-b-mid":
        rows = _hop(cid, 3)
        rows.extend(_dup(cid))
        rows.extend(_id_join(cid))
        return rows
    if case_id == "p3r-b-zero":
        return [*_fill(cid, 6), *_id_join(cid)]
    rows = _hop(cid, 9)
    if case_id == "p3r-b-disj":
        rows.extend(_dup(cid))
        rows.extend(_id_join(cid))
        return rows
    if case_id == "p3r-b-eq2":
        token = f"id=folio_{cid}"
        pair = (f"copy_ov_{cid}", f"{token} same_{cid}_row")
        rows.extend([pair, pair])
        return rows
    if case_id == "p3r-b-sub3":
        token = f"id=folio_{cid}"
        pair = (f"copy_sub_{cid}", f"{token} same_{cid}_row")
        rows.extend([pair, pair, (f"mate_c_{cid}", f"crate_c_{cid} {token}")])
        return rows
    if case_id == "p3r-b-an2":
        rows.extend(_id_join(cid, fatal_index=0))
        return rows
    if case_id == "p3r-b-an3":
        rows.extend(_id_join(cid, n=3, fatal_index=0))
        return rows
    if case_id == "p3r-b-adup":
        pair = (f"copy_al_{cid}", "CCD readout FATAL same_al_row")
        rows.extend([pair, pair])
        return rows
    if case_id == "p3r-b-alld":
        rows.extend(_dup(cid))
        rows.append((f"alert_{cid}", "CCD readout FATAL"))
        rows.extend(_id_join(cid))
        return rows
    if case_id == "p3r-b-twoj":
        rows.extend(_id_join(cid, fatal_index=0))
        rows.extend(_key_join(cid))
        return rows
    raise KeyError(case_id)


def render_records(records: list[tuple[str, str]], fmt: str) -> str:
    if fmt == "key_value":
        return "\n".join(f"{key}={value}" for key, value in records) + "\n"
    if fmt == "reversed_order_json":
        objs = [{"v": value, "k": key} for key, value in records]
        return json.dumps(objs, separators=(",", ":"))
    objs = [{"k": key, "v": value} for key, value in records]
    if fmt == "pretty_json":
        return json.dumps(objs, indent=2)
    if fmt == "compact_json":
        return json.dumps(objs, separators=(",", ":"))
    raise ValueError(f"unknown format {fmt}")


def dest_index_for(case_id: str) -> int | None:
    if case_id in {"p3r-a-zfil", "p3r-a-zjoin", "p3r-b-zero"}:
        return None
    if case_id == "p3r-b-mid":
        return 3
    if case_id.startswith("p3r-a-"):
        dist = case_id.removeprefix("p3r-a-").split("-", 1)[0]
        return DISTANCES[dist]
    return 9


def development_surfaces() -> list[dict[str, Any]]:
    surfaces: list[dict[str, Any]] = []
    for spec in planned_track_a_cases() + planned_track_b_cases():
        case_id = str(spec["case_id"])
        records = records_for(case_id)
        for fmt in spec["formats"]:
            body = render_records(records, str(fmt))
            surfaces.append(
                {
                    "surface_id": f"{case_id}-{fmt}",
                    "case_id": case_id,
                    "track": spec["track"],
                    "format": fmt,
                    "document": body,
                    "n_records": len(records),
                    "distance": spec.get("distance"),
                    "perturbation": spec.get("perturbation"),
                    "n_reference_edges": spec.get("n_reference_edges"),
                    "expected_sequence": list(spec.get("expected_sequence") or []),
                    "dest_index": dest_index_for(case_id),
                }
            )
    return surfaces


def forbidden_hits(text: str) -> list[str]:
    return [token for token in FORBIDDEN_BODY if token in text]


if __name__ == "__main__":
    write_freeze()
