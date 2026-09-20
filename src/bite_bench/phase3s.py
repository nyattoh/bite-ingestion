"""Phase 3S reference-edge specificity audit protocol (S0).

Freezes fresh fixtures, intended reference edges, gate expectations, and
verdict rules. Does not run sensors, planners, or policy. Does not change
Phase 3R/3Q artifacts. Does not open p3f. Does not repair v2.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA_ID = "bitebench-phase3s-reference-specificity-freeze/v0.1"
REVISION = "phase3s-reference-specificity-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE3S_REFERENCE_SPECIFICITY_PROTOCOL_FROZEN"
VERDICT_CONFIRMED = "PHASE3S_REFERENCE_SPECIFICITY_CONFIRMED"
VERDICT_FAILED = "PHASE3S_REFERENCE_SPECIFICITY_FAILED"
VERDICT_BLOCKED = "PHASE3S_REFERENCE_SPECIFICITY_BLOCKED"
S1_VERDICTS = (VERDICT_CONFIRMED, VERDICT_FAILED, VERDICT_BLOCKED)
PREMISE = "PHASE3R_CHANNEL_PLANNER_VALIDATED"
PHASE3Q_REMAINS = "Phase3Q remains FAILED"
PHASE3Q_VERDICT = "PHASE3Q_XFER2_TRANSFER_FAILED"
R0_SHA = "d1f39ed6dd43180c132510a1723f7c884b6e693c"
R1_SHA = "2ff6ec667bdbe44797a6a1351e118e3fcdaac4d8"
Q0_SHA = "67bfd22f782c6663de6e977848a5a381cd62ae51"
GENERATION = "p3s"
FORMATS = ("key_value", "compact_json", "pretty_json", "reversed_order_json")
DISTANCES = (1, 3, 4, 9)
FAMILIES = (
    "true_reference_only",
    "suffix_collision_only",
    "true_reference_plus_suffix_collision",
    "suffix_collision_plus_actionability",
    "shared_prefix_only",
    "shared_suffix_text_only",
    "substring_only",
)
FAMILY_SLUG = {
    "true_reference_only": "true",
    "suffix_collision_only": "suf",
    "true_reference_plus_suffix_collision": "mix",
    "suffix_collision_plus_actionability": "act",
    "shared_prefix_only": "pre",
    "shared_suffix_text_only": "sst",
    "substring_only": "sub",
}
N_CANONICAL = len(FAMILIES) * len(DISTANCES)
N_SURFACES = N_CANONICAL * len(FORMATS)
LOCKED_T_HIGH = 4.0
FAR_FILL = 8
CLAIM_BOUNDARY = "reference-edge specificity audit only"
LOCKED_BLOBS = {
    "src/bite_ingestion/profilers/dependency_dispersion_v2.py": (
        "32c9016c86379561b1e915ee322184a19fe927cd"
    ),
    "src/bite_ingestion/policies/projected_actionability_plan_v1.py": (
        "af3737f078a6d91da38999885aea13860350526a"
    ),
    "src/bite_ingestion/policies/conditional_texture_policy_v3.py": (
        "dd8b24d0cb7f0e6c4d26834d3663044cbdb9e074"
    ),
    "artifacts/phase3r/channel-planner.json": "3b5df18761ce9a0749deca453338b5276744d43f",
    "benchmarks/spec/phase3r-channel-planner-freeze.json": (
        "5515b06200ed4b07652a05a9dd31732e3dc137e7"
    ),
}
FORBIDDEN_BODY = (
    "texture",
    "REDUCE",
    "UNTANGLE",
    "INTEGRATE",
    "expected_sequence",
    "intended_reference",
    "p3f-",
    "p3r-",
    "p3q-",
    "p3p-",
    "p3m-",
    "xfer2-",
    "hop_p3m",
    "tide_lock",
    "src_pier",
    "folio_",
    "vitrine_lock",
    "star_lock",
)

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase3s-reference-specificity-freeze.json"
PHASE3R_PATH = _REPO / "artifacts" / "phase3r" / "channel-planner.json"
PHASE3Q_PATH = _REPO / "artifacts" / "phase3q" / "xfer2-transfer.json"


class EvaluationSealError(RuntimeError):
    """p3f evaluation replicas 2/3 stay sealed."""


def refuse_p3f_evaluation(case_id: str) -> None:
    cid = str(case_id)
    if cid.startswith("p3f-") and ("-r2" in cid or "-r3" in cid):
        raise EvaluationSealError(f"p3f evaluation sealed: refused {cid}")


def _stem(case_id: str) -> str:
    return case_id.replace("-", "_")


def _fill(cid: str, n: int, start: int = 0) -> list[tuple[str, str]]:
    return [
        (f"note_orchard_{cid}_{i:02d}", f"pulp_orchard_{cid}_{i:02d}")
        for i in range(start, start + n)
    ]


def _true_hop(cid: str, distance: int) -> list[tuple[str, str]]:
    n_between = max(int(distance) - 1, 0)
    return [
        (f"src_bough_{cid}", f"cider_press_{cid}"),
        *_fill(cid, n_between),
        (f"dst_cider_press_{cid}", f"mash_{cid}"),
    ]


def _suffix_hop(cid: str, distance: int) -> list[tuple[str, str]]:
    n_between = max(int(distance) - 1, 0)
    return [
        (f"src_bough_{cid}", f"keg_{cid}"),
        *_fill(cid, n_between),
        (f"bin_grove_keg_{cid}", f"pulp_{cid}"),
    ]


def _dup(cid: str) -> list[tuple[str, str]]:
    pair = (f"copy_vat_{cid}", f"same_vat_{cid}_row")
    return [pair, pair]


def _anomaly(cid: str) -> list[tuple[str, str]]:
    return [(f"alert_{cid}", "press kettle FATAL")]


def _join(cid: str) -> list[tuple[str, str]]:
    token = f"id=cask_{cid}"
    return [
        (f"mate_a_{cid}", f"barrel_a_{cid} {token}"),
        (f"mate_b_{cid}", f"barrel_b_{cid} {token}"),
    ]


def records_for(case_id: str) -> list[tuple[str, str]]:
    cid = _stem(case_id)
    family, dist = _parse_case(case_id)
    if family == "true_reference_only":
        return _true_hop(cid, dist)
    if family == "suffix_collision_only":
        return _suffix_hop(cid, dist)
    if family == "true_reference_plus_suffix_collision":
        return [
            *_true_hop(cid, dist),
            *_fill(cid, FAR_FILL, start=40),
            (f"aux_bough_{cid}", f"keg_{cid}"),
            (f"bin_grove_keg_{cid}", f"pulp_aux_{cid}"),
        ]
    if family == "suffix_collision_plus_actionability":
        return [*_suffix_hop(cid, dist), *_dup(cid), *_anomaly(cid), *_join(cid)]
    if family == "shared_prefix_only":
        n_between = max(int(dist) - 1, 0)
        return [
            (f"src_bough_{cid}", f"cider_press_west_{cid}"),
            *_fill(cid, n_between),
            (f"dst_cider_press_{cid}", f"mash_{cid}"),
        ]
    if family == "shared_suffix_text_only":
        n_between = max(int(dist) - 1, 0)
        return [
            (f"src_bough_{cid}", f"ownkeg_{cid}"),
            *_fill(cid, n_between),
            (f"bin_grove_keg_{cid}", f"pulp_{cid}"),
        ]
    if family == "substring_only":
        n_between = max(int(dist) - 1, 0)
        return [
            (f"src_bough_{cid}", "amber"),
            *_fill(cid, n_between),
            (f"slot_amber_{cid}", f"mash_{cid}"),
        ]
    raise KeyError(case_id)


def _parse_case(case_id: str) -> tuple[str, int]:
    slug = case_id.removeprefix("p3s-")
    fam_slug, dist_slug = slug.rsplit("-", 1)
    family = next(name for name, item in FAMILY_SLUG.items() if item == fam_slug)
    return family, int(dist_slug[1:])


def intended_reference_edges(case_id: str) -> list[list[int]]:
    family, dist = _parse_case(case_id)
    if family in {"true_reference_only", "true_reference_plus_suffix_collision"}:
        return [[0, int(dist)]]
    return []


def intended_mean(edges: list[list[int]]) -> float:
    if not edges:
        return 0.0
    return float(sum(abs(dst - src) for src, dst in edges) / len(edges))


def gate_expected(case_id: str) -> bool:
    edges = intended_reference_edges(case_id)
    mean = intended_mean(edges)
    return bool(edges) and mean >= LOCKED_T_HIGH


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


def planned_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for family in FAMILIES:
        for dist in DISTANCES:
            case_id = f"p3s-{FAMILY_SLUG[family]}-d{dist}"
            records = records_for(case_id)
            edges = intended_reference_edges(case_id)
            cases.append(
                {
                    "case_id": case_id,
                    "family": family,
                    "distance": dist,
                    "n_records": len(records),
                    "records": [[key, value] for key, value in records],
                    "intended_reference_edges": edges,
                    "intended_mean": intended_mean(edges),
                    "gate_expected": gate_expected(case_id),
                    "policy_sequence_expected": [],
                    "formats": list(FORMATS),
                }
            )
    return cases


def forbidden_hits(text: str) -> list[str]:
    return [token for token in FORBIDDEN_BODY if token in text]


def freeze_manifest() -> dict[str, Any]:
    cases = planned_cases()
    return {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "verdict": PROTOCOL_FROZEN,
        "paid_api": False,
        "offline": True,
        "synthetic": True,
        "research_conclusion": False,
        "premise": PREMISE,
        "phase3r_r0_sha": R0_SHA,
        "phase3r_head_sha": R1_SHA,
        "phase3r_artifact_unchanged": True,
        "phase3r_verdict": PREMISE,
        "phase3q_q0_sha": Q0_SHA,
        "phase3q_remains": PHASE3Q_REMAINS,
        "phase3q_verdict_unchanged": True,
        "generation": GENERATION,
        "copy_p3f_cases": False,
        "copy_p3r_cases": False,
        "p3f_evaluation_holdout_used": False,
        "calibration": False,
        "no_threshold_grid": True,
        "no_repair": True,
        "no_key_side_atoms_change": True,
        "no_format_exception": True,
        "no_new_ak_threshold": True,
        "no_operator_semantic_change": True,
        "locked_t_high": LOCKED_T_HIGH,
        "locked_blobs": dict(LOCKED_BLOBS),
        "families": list(FAMILIES),
        "distances": list(DISTANCES),
        "formats": list(FORMATS),
        "n_canonical": N_CANONICAL,
        "n_surfaces": N_SURFACES,
        "planned_cases": cases,
        "primary_truth": "scorer-only intended_reference_edges; observed undirected set must match exactly",
        "gate_rule": (
            "intended empty -> false; intended mean < 4 -> false; intended mean >= 4 -> true"
        ),
        "policy_consequence": "suffix_collision_plus_actionability sequence is always []",
        "invariants": {
            "edge_set_exact": True,
            "false_reference_edges": 0,
            "gate_expectation_exact": True,
            "cross_format_exact": True,
            "no_mean_only_success": True,
        },
        "s1_verdicts": list(S1_VERDICTS),
        "verdict_rule": {
            VERDICT_CONFIRMED: (
                "all fresh surfaces: edge set exact, false reference edge 0, "
                "gate expectation exact, cross-format exact"
            ),
            VERDICT_FAILED: "one or more false edges or false gates from suffix/prefix/substring collision",
            VERDICT_BLOCKED: "protocol drift / leak / fair audit cannot run",
        },
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "routing generalization",
            "real-world corpus generalization",
            "BITE superiority",
            "Phase3Q TRANSFER_CONFIRMED",
        ],
        "token_reduction": "diagnostic_only",
        "no_winner_score": True,
        "cut_forbidden": True,
    }


def validate_phase3s_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("revision") != REVISION:
        errs.append("revision mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("protocol not frozen")
    if doc.get("premise") != PREMISE:
        errs.append("Phase 3R premise drifted")
    if doc.get("copy_p3f_cases") is not False:
        errs.append("must not copy p3f cases")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("no_repair") is not True:
        errs.append("repair forbidden")
    if doc.get("n_surfaces") != N_SURFACES:
        errs.append("n_surfaces drifted")
    if len(doc.get("planned_cases") or []) != N_CANONICAL:
        errs.append("planned_cases count drifted")
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
    for spec in doc.get("planned_cases") or []:
        if not isinstance(spec, Mapping):
            errs.append("planned case not object")
            continue
        blob = json.dumps(spec.get("records") or [])
        hits = forbidden_hits(blob)
        if hits:
            errs.append(f"forbidden token in {spec.get('case_id')}: {hits}")
        if "intended_reference_edges" not in spec:
            errs.append(f"{spec.get('case_id')} missing intended_reference_edges")
        if "gate_expected" not in spec:
            errs.append(f"{spec.get('case_id')} missing gate_expected")
    return errs


def write_freeze() -> Path:
    FREEZE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FREEZE_PATH.write_text(
        json.dumps(freeze_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return FREEZE_PATH


if __name__ == "__main__":
    write_freeze()
