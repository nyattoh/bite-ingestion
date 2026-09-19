"""Phase 3H operator-map discriminating protocol (H0).

New development generation ``p3h``. Does not measure operators. Does not
open p3f evaluation. Does not change candidate A, thresholds, v1, or routing.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from itertools import product
from pathlib import Path
from typing import Any, Literal

from bite_bench.models import CanonicalCase, Fact

SCHEMA_ID = "bitebench-phase3h-operator-map-freeze/v0.1"
REVISION = "phase3h-operator-map-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE3H_PROTOCOL_FROZEN"
VERDICT_M1 = "PHASE3H_M1_SUPPORTED"
VERDICT_M2 = "PHASE3H_M2_SUPPORTED"
VERDICT_CONDITIONAL = "PHASE3H_CONDITIONAL_MAP_REQUIRED"
VERDICT_UNRESOLVED = "PHASE3H_MAP_UNRESOLVED"
MAP_VERDICTS = (VERDICT_M1, VERDICT_M2, VERDICT_CONDITIONAL, VERDICT_UNRESOLVED)
LOCKED_CANDIDATE = "A_mean_edge_distance"
LOCKED_T_LOW = 1
LOCKED_T_HIGH = 4
LOCKED_FEATURE = "mean_edge_distance"
PAD_COUNT = 24
REDUNDANT_PAIRS = 12
ANOMALY_PAD_INDEXES = (3, 7, 11, 15)
N_SURFACES = 12
N_ARMS = 4
N_ROWS = 48

Texture = Literal["redundant", "unique", "anomalous"]
Arm = Literal["CUT", "REDUCE", "INTEGRATE", "UNTANGLE"]
Fmt = Literal["key_value", "json"]

TEXTURES: tuple[Texture, ...] = ("redundant", "unique", "anomalous")
ARMS: tuple[Arm, ...] = ("CUT", "REDUCE", "INTEGRATE", "UNTANGLE")
FORMATS: tuple[Fmt, ...] = ("key_value", "json")
REPLICAS: tuple[int, ...] = (0, 1)
DISPERSION = "far"
SHAPE = "one_hop"
SCALE = "medium"
GENERATION = "p3h"
SPLIT = "development"

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase3h-operator-map-freeze.json"


class EvaluationSealError(RuntimeError):
    """p3f evaluation replicas stay sealed."""


def refuse_p3f_evaluation(case_id: str) -> None:
    cid = str(case_id)
    if cid.startswith("p3f-") and ("-r2" in cid or "-r3" in cid):
        raise EvaluationSealError(f"p3f evaluation sealed: refused {cid}")


def core_case_id(replica: int) -> str:
    return f"p3h-core-r{replica}"


def surface_id(texture: Texture, replica: int, fmt: Fmt) -> str:
    return f"p3h-{texture}-r{replica}-{fmt}"


def _dep_facts(replica: int) -> tuple[Fact, Fact, str, str]:
    case_id = core_case_id(replica)
    token = f"hop_p3h_core_r{replica}"
    answer = f"ans_p3h_core_r{replica}"
    origin = Fact(f"{case_id}-d0", f"origin_p3h_core_r{replica}", token)
    dest = Fact(f"{case_id}-d1", f"bin_{token}", answer)
    return origin, dest, token, answer


def _pad_facts(replica: int, texture: Texture) -> tuple[Fact, ...]:
    case_id = core_case_id(replica)
    pads: list[Fact] = []
    if texture == "redundant":
        for pair in range(REDUNDANT_PAIRS):
            key = f"padk_{replica}_{pair:03d}"
            value = f"padv_{replica}_{pair:03d}"
            pads.append(Fact(f"{case_id}-n{2 * pair:03d}", key, value))
            pads.append(Fact(f"{case_id}-n{2 * pair + 1:03d}", key, value))
        return tuple(pads)
    for index in range(PAD_COUNT):
        value = f"padv_{replica}_{index:03d}"
        if texture == "anomalous" and index in ANOMALY_PAD_INDEXES:
            value = f"{value} ERROR"
        pads.append(Fact(f"{case_id}-n{index:03d}", f"padk_{replica}_{index:03d}", value))
    return tuple(pads)


def _apply_texture_overlay(fact: Fact, texture: Texture, token: str) -> Fact:
    if texture != "unique":
        return fact
    if not fact.fact_id.endswith(("-d0", "-d1")):
        return fact
    return Fact(fact.fact_id, fact.key, f"{fact.value} id={token}")


def ordered_facts(replica: int, texture: Texture) -> tuple[Fact, ...]:
    origin, dest, token, _answer = _dep_facts(replica)
    origin = _apply_texture_overlay(origin, texture, token)
    dest = _apply_texture_overlay(dest, texture, token)
    pads = _pad_facts(replica, texture)
    return (origin, *pads, dest)


def render_payload(facts: Sequence[Fact], fmt: Fmt) -> str:
    if fmt == "key_value":
        return "\n".join(f"{fact.key}={fact.value}" for fact in facts)
    records = [{"k": fact.key, "v": fact.value} for fact in facts]
    return json.dumps(records, separators=(",", ":"))


def unit_text(fact: Fact, fmt: Fmt) -> str:
    if fmt == "key_value":
        return f"{fact.key}={fact.value}"
    return json.dumps({"k": fact.key, "v": fact.value}, separators=(",", ":"))


def make_canonical(replica: int, texture: Texture) -> CanonicalCase:
    origin, dest, token, answer = _dep_facts(replica)
    facts = ordered_facts(replica, texture)
    return CanonicalCase(
        case_id=core_case_id(replica),
        question=f"What result is stored after {token}?",
        answer=answer,
        required_evidence_ids=(origin.fact_id, dest.fact_id),
        facts=facts,
        task_family="p3h_texture",
        meta={
            "texture": texture,
            "dispersion": DISPERSION,
            "shape": SHAPE,
            "scale": SCALE,
            "replica": replica,
            "split": SPLIT,
            "generation": GENERATION,
        },
    )


def make_surface(texture: Texture, replica: int, fmt: Fmt) -> dict[str, Any]:
    refuse_p3f_evaluation(core_case_id(replica))
    canonical = make_canonical(replica, texture)
    facts = ordered_facts(replica, texture)
    origin, dest, _token, _answer = _dep_facts(replica)
    return {
        "surface_id": surface_id(texture, replica, fmt),
        "case_id": canonical.case_id,
        "split": SPLIT,
        "generation": GENERATION,
        "texture": texture,
        "dispersion": DISPERSION,
        "shape": SHAPE,
        "scale": SCALE,
        "replica": replica,
        "format": fmt,
        "question": canonical.question,
        "answer": canonical.answer,
        "gold_unit_ids": [origin.fact_id, dest.fact_id],
        "unit_ids": [fact.fact_id for fact in facts],
        "unit_texts": [unit_text(fact, fmt) for fact in facts],
        "payload": render_payload(facts, fmt),
        "n_facts": len(facts),
    }


def design_surfaces() -> list[dict[str, Any]]:
    return [
        make_surface(texture, replica, fmt)
        for texture, replica, fmt in product(TEXTURES, REPLICAS, FORMATS)
    ]


def planned_surface_ids() -> list[str]:
    return [
        surface_id(texture, replica, fmt)
        for texture, replica, fmt in product(TEXTURES, REPLICAS, FORMATS)
    ]


def bin_univariate(x: float, t_low: float = LOCKED_T_LOW, t_high: float = LOCKED_T_HIGH) -> str:
    if x <= t_low:
        return "low"
    if x >= t_high:
        return "high"
    return "mid"


def texture_arm_signal(texture: str, arm: str, row: Mapping[str, Any]) -> bool:
    """Predeclared helpfulness. Token counts are not consulted."""
    if float(row.get("recall_visible", 0.0)) != 1.0:
        return False
    if int(row.get("n_gold_removed", 1)) != 0:
        return False
    if texture == "redundant" and arm == "REDUCE":
        return int(row.get("n_nongold_removed", 0)) > 0
    if texture == "unique" and arm == "INTEGRATE":
        return int(row.get("n_gold_joined", 0)) >= 1
    if texture == "anomalous" and arm == "UNTANGLE":
        return (
            int(row.get("n_quarantined", 0)) > 0
            and int(row.get("n_gold_quarantined", 0)) == 0
        )
    return False


def consensus_signals(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, bool]]:
    out: dict[str, dict[str, bool]] = {}
    for texture in TEXTURES:
        flags: dict[str, bool] = {}
        for arm in ARMS:
            arm_rows = [
                row
                for row in rows
                if row.get("texture") == texture and row.get("arm") == arm
            ]
            flags[arm] = bool(arm_rows) and all(
                texture_arm_signal(texture, arm, row) for row in arm_rows
            )
        out[texture] = flags
    return out


def decide_verdict(
    *,
    blocked: bool,
    high_confirmed: bool,
    consensus: Mapping[str, Mapping[str, bool]],
) -> str:
    if blocked or not high_confirmed:
        return VERDICT_UNRESOLVED
    redundant_reduce = bool(consensus["redundant"]["REDUCE"])
    unique_integrate = bool(consensus["unique"]["INTEGRATE"])
    anomalous_untangle = bool(consensus["anomalous"]["UNTANGLE"])
    if redundant_reduce and unique_integrate and anomalous_untangle:
        return VERDICT_CONDITIONAL
    if (redundant_reduce or anomalous_untangle) and not unique_integrate:
        return VERDICT_M1
    if unique_integrate and not redundant_reduce and not anomalous_untangle:
        return VERDICT_M2
    return VERDICT_UNRESOLVED


def freeze_manifest() -> dict[str, Any]:
    return {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "verdict": PROTOCOL_FROZEN,
        "paid_api": False,
        "offline": True,
        "synthetic": True,
        "research_conclusion": False,
        "generation": GENERATION,
        "split": SPLIT,
        "replicas": list(REPLICAS),
        "p3f_evaluation_replicas_sealed": [2, 3],
        "p3f_evaluation_holdout_used": False,
        "locked_from_phase3g": {
            "selected_candidate": LOCKED_CANDIDATE,
            "feature": LOCKED_FEATURE,
            "T_low": LOCKED_T_LOW,
            "T_high": LOCKED_T_HIGH,
            "candidate_unchanged": True,
            "thresholds_unchanged": True,
            "v1_sensor_unchanged": True,
        },
        "routing": {
            "rule_policy_changed": False,
            "routing_connected": False,
            "operator_map_selected": False,
            "selected_operator_map": None,
            "high_bin_mapped_to_operator": False,
            "implement_map_on_conditional": False,
        },
        "design": {
            "dispersion": DISPERSION,
            "shape": SHAPE,
            "scale": SCALE,
            "n_pads": PAD_COUNT,
            "formats": list(FORMATS),
            "textures": list(TEXTURES),
            "layout": "gold_origin, pads, gold_dest",
            "canonical_gold_shared_across_textures": True,
            "unique_overlay": "append id=<hop> to both gold values only",
            "redundant_pads": "12 exact duplicate pairs, same n_units",
            "anomalous_pads": list(ANOMALY_PAD_INDEXES),
            "operators_see": "pre-split logical units",
        },
        "arms": {
            "isolated": list(ARMS),
            "no_composite_pipeline": True,
            "UNTANGLE_is_isolated_not_wired_as_preprocess": True,
        },
        "n_planned_surfaces": N_SURFACES,
        "n_planned_rows": N_ROWS,
        "planned_surface_ids": planned_surface_ids(),
        "metrics": {
            "evidence_recall_visible": True,
            "provenance_completeness": True,
            "no_op": True,
            "effective_dependency_span": LOCKED_FEATURE,
            "collateral_n_gold_removed": True,
            "collateral_n_nongold_removed": True,
            "n_gold_joined": True,
            "n_quarantined": True,
        },
        "not_objective": [
            "token_reduction",
            "n_signal",
            "INTEGRATE_rate",
            "T_total",
        ],
        "token_reduction_used_for_verdict": False,
        "must_pick_m1_or_m2": False,
        "map_verdicts": list(MAP_VERDICTS),
        "verdict_rules": {
            "helpful_requires": [
                "recall_visible == 1.0",
                "n_gold_removed == 0",
            ],
            "redundant_REDUCE": "n_nongold_removed > 0",
            "unique_INTEGRATE": "n_gold_joined >= 1",
            "anomalous_UNTANGLE": "n_quarantined > 0 and n_gold_quarantined == 0",
            "consensus": "all formats and replicas of a texture-arm pair",
            "PHASE3H_CONDITIONAL_MAP_REQUIRED": (
                "redundant REDUCE and unique INTEGRATE and anomalous UNTANGLE"
            ),
            "PHASE3H_M1_SUPPORTED": (
                "INTEGRATE unique-signal false, and REDUCE or UNTANGLE signal true"
            ),
            "PHASE3H_M2_SUPPORTED": (
                "unique INTEGRATE true, redundant REDUCE false, anomalous UNTANGLE false"
            ),
            "PHASE3H_MAP_UNRESOLVED": "blocked, high bin unconfirmed, or no matching rule",
            "on_conditional": "stop; do not implement a routing map",
        },
        "operator_map_candidates_unchanged": {
            "M1_locality_for_integrate": {
                "high": (
                    "must_not_fire_INTEGRATE_from_this_feature_alone; "
                    "CUT_or_REDUCE_candidate"
                )
            },
            "M2_spread_needs_gather": {
                "high": "may_contribute_toward_INTEGRATE_only_with_other_features"
            },
            "adoption": "phase3h_routing_semantics_freeze",
        },
        "high_bin_confirmation": "pre-operator mean_edge_distance >= T_high on every surface",
    }


def validate_phase3h_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("revision") != REVISION:
        errs.append("revision mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("protocol not frozen")
    if doc.get("generation") != GENERATION:
        errs.append("generation must be p3h")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    locked = dict(doc.get("locked_from_phase3g") or {})
    if locked.get("selected_candidate") != LOCKED_CANDIDATE:
        errs.append("candidate A must stay locked")
    if locked.get("T_low") != LOCKED_T_LOW or locked.get("T_high") != LOCKED_T_HIGH:
        errs.append("thresholds must stay locked")
    routing = dict(doc.get("routing") or {})
    if routing.get("rule_policy_changed") is not False:
        errs.append("routing map must not be rewritten in the freeze")
    if doc.get("token_reduction_used_for_verdict") is not False:
        errs.append("token reduction must not decide the winner")
    if doc.get("must_pick_m1_or_m2") is not False:
        errs.append("M1/M2 must remain optional")
    ids = list(doc.get("planned_surface_ids") or [])
    if ids != planned_surface_ids():
        errs.append("planned surface ids drifted")
    blob = json.dumps(doc, sort_keys=True)
    if "p3f-" in blob and "p3f_evaluation" not in blob:
        errs.append("unexpected p3f surface in freeze")
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
