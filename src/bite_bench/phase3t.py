"""Phase 3T exact-reference identity v3 protocol (T0).

Freezes the relation contract, fresh p3t fixtures, intended edges, gate
expectations, bridge rule, and verdicts. Does not implement v3 sensor or
policy v4. Does not change Phase 3S/3Q. Does not open p3f.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA_ID = "bitebench-phase3t-exact-reference-freeze/v0.1"
REVISION = "phase3t-exact-reference-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE3T_EXACT_REFERENCE_PROTOCOL_FROZEN"
VERDICT_VALIDATED = "PHASE3T_EXACT_REFERENCE_VALIDATED"
VERDICT_PARTIAL = "PHASE3T_EXACT_REFERENCE_PARTIAL"
VERDICT_BLOCKED = "PHASE3T_EXACT_REFERENCE_BLOCKED"
T1_VERDICTS = (VERDICT_VALIDATED, VERDICT_PARTIAL, VERDICT_BLOCKED)
PREMISE = "PHASE3S_REFERENCE_SPECIFICITY_FAILED"
PHASE3Q_REMAINS = "Phase3Q remains FAILED"
PHASE3S_REMAINS = "Phase3S remains FAILED"
PHASE3Q_VERDICT = "PHASE3Q_XFER2_TRANSFER_FAILED"
S0_SHA = "3525506c4601f4471489a15f78d013900c05eda1"
S1_SHA = "738d61f02fbd393ea4a24a3d04c4ab4784c00e4f"
Q0_SHA = "67bfd22f782c6663de6e977848a5a381cd62ae51"
GENERATION = "p3t"
FORMATS = ("key_value", "compact_json", "pretty_json", "reversed_order_json")
DISTANCES = (1, 3, 4, 9)
FAMILIES = (
    "exact_reference_only",
    "underscore_suffix_collision_only",
    "exact_reference_plus_suffix_collision",
    "suffix_collision_plus_actionability",
    "prefix_only",
    "suffix_text_only",
    "substring_only",
    "shared_generic_text",
)
FAMILY_SLUG = {
    "exact_reference_only": "ex",
    "underscore_suffix_collision_only": "suf",
    "exact_reference_plus_suffix_collision": "mix",
    "suffix_collision_plus_actionability": "act",
    "prefix_only": "pre",
    "suffix_text_only": "sst",
    "substring_only": "sub",
    "shared_generic_text": "gen",
}
N_CANONICAL = len(FAMILIES) * len(DISTANCES)
N_SURFACES = N_CANONICAL * len(FORMATS)
LOCKED_T_HIGH = 4.0
FAR_FILL = 8
CLAIM_BOUNDARY = "last synthetic-only mechanism repair: exact reference identity"
LOCKED_BLOBS = {
    "src/bite_ingestion/profilers/dependency_dispersion_v2.py": (
        "32c9016c86379561b1e915ee322184a19fe927cd"
    ),
    "src/bite_ingestion/policies/conditional_texture_policy_v3.py": (
        "dd8b24d0cb7f0e6c4d26834d3663044cbdb9e074"
    ),
    "src/bite_ingestion/policies/projected_actionability_plan_v1.py": (
        "af3737f078a6d91da38999885aea13860350526a"
    ),
    "src/bite_eval/composition_safety_v2.py": "85560279375b30f737eb3825cce72373be70488e",
    "artifacts/phase3s/reference-specificity.json": "f4bcaae86586c5f738954b78fda8427f3bb78694",
    "benchmarks/spec/phase3s-reference-specificity-freeze.json": (
        "78939ff84dd26dc53e7821d93b0fcea2b484a03d"
    ),
}
SECONDARY_SLUGS = ("suf", "mix", "act")
SECONDARY_SURFACES = tuple(
    f"p3s-{slug}-d{dist}-{fmt}"
    for slug in SECONDARY_SLUGS
    for dist in DISTANCES
    for fmt in FORMATS
)
FORBIDDEN_BODY = (
    "texture",
    "REDUCE",
    "UNTANGLE",
    "INTEGRATE",
    "expected_sequence",
    "intended_reference",
    "p3f-",
    "p3s-",
    "p3r-",
    "p3q-",
    "cider_press",
    "src_bough",
    "keg_",
    "note_orchard",
    "bin_grove",
    "tide_lock",
    "src_pier",
    "folio_",
)

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase3t-exact-reference-freeze.json"
PHASE3S_PATH = _REPO / "artifacts" / "phase3s" / "reference-specificity.json"
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
        (f"note_mill_{cid}_{i:02d}", f"yarn_mill_{cid}_{i:02d}")
        for i in range(start, start + n)
    ]


def _exact_hop(cid: str, distance: int) -> list[tuple[str, str]]:
    n_between = max(int(distance) - 1, 0)
    dest = f"loom_heddle_{cid}"
    return [
        (f"src_warp_{cid}", dest),
        *_fill(cid, n_between),
        (dest, f"weft_{cid}"),
    ]


def _suffix_hop(cid: str, distance: int) -> list[tuple[str, str]]:
    n_between = max(int(distance) - 1, 0)
    return [
        (f"src_warp_{cid}", f"heddle_{cid}"),
        *_fill(cid, n_between),
        (f"bin_shed_heddle_{cid}", f"yarn_{cid}"),
    ]


def _dup(cid: str) -> list[tuple[str, str]]:
    pair = (f"copy_reed_{cid}", f"same_reed_{cid}_row")
    return [pair, pair]


def _anomaly(cid: str) -> list[tuple[str, str]]:
    return [(f"alert_{cid}", "shuttle jam FATAL")]


def _join(cid: str) -> list[tuple[str, str]]:
    token = f"id=spool_{cid}"
    return [
        (f"mate_a_{cid}", f"bobbin_a_{cid} {token}"),
        (f"mate_b_{cid}", f"bobbin_b_{cid} {token}"),
    ]


def records_for(case_id: str) -> list[tuple[str, str]]:
    cid = _stem(case_id)
    family, dist = _parse_case(case_id)
    if family == "exact_reference_only":
        return _exact_hop(cid, dist)
    if family == "underscore_suffix_collision_only":
        return _suffix_hop(cid, dist)
    if family == "exact_reference_plus_suffix_collision":
        return [
            *_exact_hop(cid, dist),
            *_fill(cid, FAR_FILL, start=40),
            (f"aux_warp_{cid}", f"heddle_{cid}"),
            (f"bin_shed_heddle_{cid}", f"yarn_aux_{cid}"),
        ]
    if family == "suffix_collision_plus_actionability":
        return [*_suffix_hop(cid, dist), *_dup(cid), *_anomaly(cid), *_join(cid)]
    if family == "prefix_only":
        n_between = max(int(dist) - 1, 0)
        dest = f"loom_heddle_{cid}"
        return [
            (f"src_warp_{cid}", f"loom_heddle_west_{cid}"),
            *_fill(cid, n_between),
            (dest, f"weft_{cid}"),
        ]
    if family == "suffix_text_only":
        n_between = max(int(dist) - 1, 0)
        return [
            (f"src_warp_{cid}", f"ownheddle_{cid}"),
            *_fill(cid, n_between),
            (f"bin_shed_heddle_{cid}", f"yarn_{cid}"),
        ]
    if family == "substring_only":
        n_between = max(int(dist) - 1, 0)
        return [
            (f"src_warp_{cid}", "heddle"),
            *_fill(cid, n_between),
            (f"slot_heddle_{cid}", f"weft_{cid}"),
        ]
    if family == "shared_generic_text":
        n_between = max(int(dist) - 1, 0)
        return [
            (f"src_warp_{cid}", "spindle"),
            *_fill(cid, n_between),
            (f"slot_other_{cid}", "spindle"),
        ]
    raise KeyError(case_id)


def _parse_case(case_id: str) -> tuple[str, int]:
    slug = case_id.removeprefix("p3t-")
    fam_slug, dist_slug = slug.rsplit("-", 1)
    family = next(name for name, item in FAMILY_SLUG.items() if item == fam_slug)
    return family, int(dist_slug[1:])


def intended_reference_edges(case_id: str) -> list[list[int]]:
    family, dist = _parse_case(case_id)
    if family in {"exact_reference_only", "exact_reference_plus_suffix_collision"}:
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


def is_bridge(case_id: str) -> bool:
    family, _dist = _parse_case(case_id)
    return family == "exact_reference_only"


def dest_index_for(case_id: str) -> int | None:
    family, dist = _parse_case(case_id)
    if family in {"exact_reference_only", "exact_reference_plus_suffix_collision"}:
        return int(dist)
    return None


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
            case_id = f"p3t-{FAMILY_SLUG[family]}-d{dist}"
            records = records_for(case_id)
            edges = intended_reference_edges(case_id)
            cases.append(
                {
                    "case_id": case_id,
                    "family": family,
                    "distance": dist,
                    "bridge": is_bridge(case_id),
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
        "phase3s_s0_sha": S0_SHA,
        "phase3s_head_sha": S1_SHA,
        "phase3s_artifact_unchanged": True,
        "phase3s_verdict": PREMISE,
        "phase3s_remains": PHASE3S_REMAINS,
        "phase3q_q0_sha": Q0_SHA,
        "phase3q_remains": PHASE3Q_REMAINS,
        "phase3q_verdict_unchanged": True,
        "generation": GENERATION,
        "copy_p3s_content": False,
        "copy_p3f_cases": False,
        "p3f_evaluation_holdout_used": False,
        "calibration": False,
        "no_threshold_grid": True,
        "no_planner_change": True,
        "no_operator_semantic_change": True,
        "no_new_ak_threshold": True,
        "repair_target": "remove_underscore_suffix_expansion_from_reference_targets",
        "locked_t_high": LOCKED_T_HIGH,
        "locked_blobs": dict(LOCKED_BLOBS),
        "relation_contract": {
            "target": "maximal full identifier token of KV key / JSON k only",
            "source": "maximal identifier tokens of masked value",
            "edge": "exact equality only",
            "no_suffix_expansion": True,
            "no_fuzzy": True,
            "join_mask": "id=<token> and key=<token> in values",
        },
        "families": list(FAMILIES),
        "distances": list(DISTANCES),
        "formats": list(FORMATS),
        "n_canonical": N_CANONICAL,
        "n_surfaces": N_SURFACES,
        "planned_cases": cases,
        "bridge": {
            "family": "exact_reference_only",
            "requires_v2_v3_edge_set_n_and_mean_exact": True,
            "not_a_new_calibration": True,
            "candidate": LOCKED_T_HIGH,
        },
        "reproduction_only_surfaces": list(SECONDARY_SURFACES),
        "reproduction_not_primary_evidence": True,
        "reproduction_expect": {
            "suffix_collision_only": {"false_edge": False, "n_reference_edges": 0},
            "true_reference_plus_suffix_collision": {"observed": "intended_true_edge_only"},
            "suffix_collision_plus_actionability_d4_d9": {
                "gate": False,
                "policy_sequence": [],
            },
        },
        "primary_truth": "scorer-only intended_reference_edges; observed undirected set must match exactly",
        "no_mean_only_success": True,
        "t1_verdicts": list(T1_VERDICTS),
        "verdict_rule": {
            VERDICT_VALIDATED: (
                "fresh p3t: all edge/gate/policy/safety pass; v2/v3 bridge exact; T=4 carry-forward"
            ),
            VERDICT_PARTIAL: "specificity repaired but bridge / format / safety incomplete",
            VERDICT_BLOCKED: "protocol drift / leak / fair validation cannot run",
        },
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "routing generalization",
            "real-world corpus generalization",
            "BITE superiority",
            "Phase3S CONFIRMED",
            "Phase3Q TRANSFER_CONFIRMED",
        ],
        "token_reduction": "diagnostic_only",
        "no_winner_score": True,
        "cut_forbidden": True,
        "next_if_validated": "Phase 4 real-structured corpus; do not invent XFER-3",
    }


def validate_phase3t_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("revision") != REVISION:
        errs.append("revision mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("protocol not frozen")
    if doc.get("premise") != PREMISE:
        errs.append("Phase 3S premise drifted")
    if doc.get("copy_p3s_content") is not False:
        errs.append("must not copy p3s content")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("no_threshold_grid") is not True:
        errs.append("threshold grid forbidden")
    if doc.get("no_planner_change") is not True:
        errs.append("planner change forbidden")
    if doc.get("n_surfaces") != N_SURFACES:
        errs.append("n_surfaces drifted")
    if len(doc.get("planned_cases") or []) != N_CANONICAL:
        errs.append("planned_cases count drifted")
    if list(doc.get("reproduction_only_surfaces") or []) != list(SECONDARY_SURFACES):
        errs.append("secondary surfaces drifted")
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
    for spec in doc.get("planned_cases") or []:
        if not isinstance(spec, Mapping):
            errs.append("planned case not object")
            continue
        blob = json.dumps(spec.get("records") or [])
        hits = forbidden_hits(blob)
        if hits:
            errs.append(f"forbidden token in {spec.get('case_id')}: {hits}")
        if (
            spec.get("family") == "exact_reference_plus_suffix_collision"
            and spec.get("distance") == 4
            and spec.get("gate_expected") is not True
        ):
            errs.append("mix d4 must gate")
        if spec.get("family") == "suffix_collision_plus_actionability":
            if spec.get("gate_expected") is not False:
                errs.append(f"{spec.get('case_id')} act must not gate")
            if spec.get("policy_sequence_expected") != []:
                errs.append(f"{spec.get('case_id')} act sequence must be []")
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
