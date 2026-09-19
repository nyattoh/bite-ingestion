"""Phase 3M conditional routing protocol (M0).

Fresh p3m generation. Does not implement the policy. Does not measure.
Does not rewrite RulePolicy. Does not open p3m/p3f evaluation.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from itertools import product
from pathlib import Path
from typing import Any, Literal

SCHEMA_ID = "bitebench-phase3m-conditional-routing-freeze/v0.1"
SPLIT_SCHEMA_ID = "bitebench-phase3m-split-manifest/v0.1"
REVISION = "phase3m-conditional-routing-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE3M_CONDITIONAL_ROUTING_PROTOCOL_FROZEN"
VERDICT_READY = "PHASE3M_CONDITIONAL_ROUTING_READY"
VERDICT_PARTIAL = "PHASE3M_CONDITIONAL_ROUTING_PARTIAL"
VERDICT_BLOCKED = "PHASE3M_CONDITIONAL_ROUTING_BLOCKED"
M1_VERDICTS = (VERDICT_READY, VERDICT_PARTIAL, VERDICT_BLOCKED)
POLICY_NAME = "conditional_texture_policy_v1"
GENERATION = "p3m"
LOCKED_CANDIDATE = "A_mean_edge_distance"
LOCKED_FEATURE = "mean_edge_distance"
LOCKED_T_LOW = 1
LOCKED_T_HIGH = 4
PAD_HIGH = 24
PAD_MID = 2
PAD_LOW_TRAIL = 4

Texture = Literal[
    "redundant",
    "explicit_join",
    "anomaly",
    "neutral",
    "redundant_join",
    "anomaly_redundant",
    "anomaly_join",
    "all_three",
]
Dispersion = Literal["high", "mid", "low"]
Split = Literal["development", "evaluation"]

TEXTURES: tuple[Texture, ...] = (
    "redundant",
    "explicit_join",
    "anomaly",
    "neutral",
    "redundant_join",
    "anomaly_redundant",
    "anomaly_join",
    "all_three",
)
DISPERSIONS: tuple[Dispersion, ...] = ("high", "mid", "low")
CALIBRATION_REPLICAS: tuple[int, ...] = (0, 1)
EVALUATION_REPLICAS: tuple[int, ...] = (2, 3)
ALL_REPLICAS: tuple[int, ...] = (0, 1, 2, 3)
JOIN_TEXTURES: frozenset[str] = frozenset(
    {"explicit_join", "redundant_join", "anomaly_join", "all_three"}
)
RED_TEXTURES: frozenset[str] = frozenset(
    {"redundant", "redundant_join", "anomaly_redundant", "all_three"}
)
ANOM_TEXTURES: frozenset[str] = frozenset(
    {"anomaly", "anomaly_redundant", "anomaly_join", "all_three"}
)
HIGH_SEQUENCES: dict[Texture, tuple[str, ...]] = {
    "redundant": ("REDUCE",),
    "explicit_join": ("INTEGRATE",),
    "anomaly": ("UNTANGLE",),
    "neutral": (),
    "redundant_join": ("REDUCE", "INTEGRATE"),
    "anomaly_redundant": ("UNTANGLE", "REDUCE"),
    "anomaly_join": ("UNTANGLE", "INTEGRATE"),
    "all_three": ("UNTANGLE", "REDUCE", "INTEGRATE"),
}
OPERATOR_ORDER = ("UNTANGLE", "REDUCE", "INTEGRATE")
SAFETY_KEYS = (
    "lineage_recall",
    "provenance_completeness",
    "conservation_untraced",
    "silent_loss",
    "quarantine_recoverable",
    "reduce_only_exact_duplicates",
    "integrate_explicit_join_composite",
    "no_unrelated_overmerge",
)

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase3m-conditional-routing-freeze.json"
SPLIT_PATH = _REPO / "benchmarks" / "spec" / "phase3m-split-manifest.json"


class EvaluationSealError(RuntimeError):
    """p3m evaluation replicas 2/3 and p3f evaluation stay sealed."""


def refuse_p3f_evaluation(case_id: str) -> None:
    cid = str(case_id)
    if cid.startswith("p3f-") and ("-r2" in cid or "-r3" in cid):
        raise EvaluationSealError(f"p3f evaluation sealed: refused {cid}")


def refuse_p3m_evaluation(case_id: str) -> None:
    cid = str(case_id)
    if cid.startswith("p3m-") and ("-r2" in cid or "-r3" in cid):
        raise EvaluationSealError(f"p3m evaluation sealed: refused {cid}")


def refuse_evaluation(case_id: str) -> None:
    refuse_p3f_evaluation(case_id)
    refuse_p3m_evaluation(case_id)


def split_of_replica(replica: int) -> Split:
    return "development" if replica in CALIBRATION_REPLICAS else "evaluation"


def case_id(texture: Texture, dispersion: Dispersion, replica: int) -> str:
    return f"p3m-{texture}-{dispersion}-r{replica}"


def expected_sequence(texture: Texture, dispersion: Dispersion) -> tuple[str, ...]:
    if dispersion != "high":
        return ()
    return HIGH_SEQUENCES[texture]


def hop_token(replica: int) -> str:
    return f"hop_p3m_core_r{replica}"


def join_tag(replica: int) -> str:
    return f"join_p3m_r{replica}"


def _with_join(value: str, replica: int, texture: Texture) -> str:
    if texture not in JOIN_TEXTURES:
        return value
    return f"{value} id={join_tag(replica)}"


def _pads(texture: Texture, replica: int, n: int, ns: str) -> list[tuple[str, str]]:
    if n <= 0:
        return []
    red = texture in RED_TEXTURES
    anom = texture in ANOM_TEXTURES

    def rec(index: int, *, exception: bool = False) -> tuple[str, str]:
        key = f"padk_{ns}_{replica}_{index:03d}"
        value = f"padv_{ns}_{replica}_{index:03d}"
        if exception:
            value = f"{value} EXCEPTION"
        return (key, value)

    if n == 2:
        if red and anom:
            row = rec(0, exception=True)
            return [row, row]
        if red:
            row = rec(0)
            return [row, row]
        if anom:
            return [rec(0, exception=True), rec(1)]
        return [rec(0), rec(1)]
    if n == 4:
        if red and anom:
            a = rec(0)
            return [a, a, rec(1, exception=True), rec(2)]
        if red:
            a, b = rec(0), rec(1)
            return [a, a, b, b]
        if anom:
            return [rec(0, exception=True), rec(1), rec(2), rec(3)]
        return [rec(i) for i in range(4)]
    # n == 24
    out: list[tuple[str, str]] = []
    index = 0
    if red and anom:
        for _ in range(8):
            row = rec(index)
            out.extend([row, row])
            index += 1
        for _ in range(4):
            out.append(rec(index, exception=True))
            index += 1
        while len(out) < 24:
            out.append(rec(index))
            index += 1
        return out[:24]
    if red:
        for _ in range(12):
            row = rec(index)
            out.extend([row, row])
            index += 1
        return out[:24]
    if anom:
        for i in range(24):
            out.append(rec(index, exception=i in (3, 7, 11, 15)))
            index += 1
        return out
    return [rec(i) for i in range(24)]


def records_for(
    texture: Texture, dispersion: Dispersion, replica: int
) -> tuple[tuple[str, str], ...]:
    origin = (f"origin_p3m_r{replica}", _with_join(hop_token(replica), replica, texture))
    dest = (
        f"bin_{hop_token(replica)}",
        _with_join(f"ans_p3m_r{replica}", replica, texture),
    )
    if dispersion == "high":
        return (origin, *_pads(texture, replica, PAD_HIGH, "n"), dest)
    if dispersion == "mid":
        return (origin, *_pads(texture, replica, PAD_MID, "n"), dest)
    return (origin, dest, *_pads(texture, replica, PAD_LOW_TRAIL, "t"))


def gold_unit_ids(replica: int) -> list[str]:
    return [f"p3m-core-r{replica}-d0", f"p3m-core-r{replica}-d1"]


def unit_id_for(replica: int, index: int, *, trailing: bool) -> str:
    prefix = "t" if trailing else "u"
    return f"p3m-core-r{replica}-{prefix}{index:03d}"


def make_surface(texture: Texture, dispersion: Dispersion, replica: int) -> dict[str, Any]:
    refuse_evaluation(case_id(texture, dispersion, replica))
    records = records_for(texture, dispersion, replica)
    dest_index = 1 if dispersion == "low" else len(records) - 1
    ids: list[str] = []
    for index, _row in enumerate(records):
        if index == 0:
            ids.append(gold_unit_ids(replica)[0])
        elif index == dest_index:
            ids.append(gold_unit_ids(replica)[1])
        else:
            ids.append(unit_id_for(replica, index, trailing=dispersion == "low" and index > dest_index))
    texts = [f"{key}={value}" for key, value in records]
    return {
        "case_id": case_id(texture, dispersion, replica),
        "generation": GENERATION,
        "texture": texture,
        "dispersion": dispersion,
        "replica": replica,
        "split": split_of_replica(replica),
        "format": "key_value",
        "unit_ids": ids,
        "unit_texts": texts,
        "payload": "\n".join(texts),
        "gold_unit_ids": gold_unit_ids(replica),
        "expected_sequence": list(expected_sequence(texture, dispersion)),
        "n_records": len(records),
    }


def planned_case_ids() -> list[str]:
    return [
        case_id(texture, dispersion, replica)
        for texture, dispersion, replica in product(TEXTURES, DISPERSIONS, ALL_REPLICAS)
    ]


def development_surfaces() -> list[dict[str, Any]]:
    return [
        make_surface(texture, dispersion, replica)
        for texture, dispersion, replica in product(TEXTURES, DISPERSIONS, CALIBRATION_REPLICAS)
    ]


def split_manifest() -> dict[str, Any]:
    cases = []
    for texture, dispersion, replica in product(TEXTURES, DISPERSIONS, ALL_REPLICAS):
        cases.append(
            {
                "case_id": case_id(texture, dispersion, replica),
                "texture": texture,
                "dispersion": dispersion,
                "replica": replica,
                "split": split_of_replica(replica),
                "expected_sequence": list(expected_sequence(texture, dispersion)),
            }
        )
    return {
        "schema": SPLIT_SCHEMA_ID,
        "generation": GENERATION,
        "calibration_replicas": list(CALIBRATION_REPLICAS),
        "evaluation_replicas": list(EVALUATION_REPLICAS),
        "evaluation_sealed": True,
        "p3f_evaluation_replicas_sealed": [2, 3],
        "n_cases": len(cases),
        "case_ids": [row["case_id"] for row in cases],
        "cases": cases,
    }


def freeze_manifest() -> dict[str, Any]:
    return {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "verdict": PROTOCOL_FROZEN,
        "paid_api": False,
        "offline": True,
        "synthetic": True,
        "research_conclusion": False,
        "premise": [
            "PHASE3H_CONDITIONAL_MAP_REQUIRED",
            "PHASE3I_COMPOSITE_PROVENANCE_VALIDATED",
            "PHASE3L_REDUNDANCY_HOLDOUT_CONFIRMED",
        ],
        "generation": GENERATION,
        "reuse_p3h_p3j_p3k_surfaces": False,
        "policy_name": POLICY_NAME,
        "rule_policy_unchanged": True,
        "cut_in_conditional_map": False,
        "operator_order": list(OPERATOR_ORDER),
        "locked_from_phase3g": {
            "selected_candidate": LOCKED_CANDIDATE,
            "feature": LOCKED_FEATURE,
            "T_low": LOCKED_T_LOW,
            "T_high": LOCKED_T_HIGH,
        },
        "gate": {
            "n_edges_gt_0": True,
            "mean_edge_distance_gte": LOCKED_T_HIGH,
            "n_edges_eq_0": "no_dependency_dispersion_contribution",
            "high_dispersion_alone_does_not_select_operator": True,
        },
        "predicates": {
            "REDUCE": "structural_redundancy_v1 fail_closed==false AND duplicate_unit_ratio>0",
            "UNTANGLE": (
                "at least one unit is injection_suspect or malformed or "
                "anomaly_candidate; dependency_edge alone does not fire"
            ),
            "INTEGRATE": "at least one explicit id=/key= join cluster of size>=2",
            "no_a_threshold": True,
            "no_k_threshold": True,
            "no_v1_edges_as_integrate_context": True,
        },
        "high_sequences": {key: list(value) for key, value in HIGH_SEQUENCES.items()},
        "mid_low_sequence": [],
        "composition_safety": list(SAFETY_KEYS),
        "token_reduction": "diagnostic_only",
        "gold_isolation": {
            "scorer_only": ["gold_unit_ids", "expected_sequence", "texture"],
            "forbidden_on_sensors_preflight_policy": [
                "gold",
                "gold_unit_ids",
                "expected_sequence",
                "texture",
                "operator",
                "route",
                "answer",
            ],
        },
        "formats": ["key_value"],
        "textures": list(TEXTURES),
        "dispersions": list(DISPERSIONS),
        "calibration_replicas": list(CALIBRATION_REPLICAS),
        "evaluation_replicas": list(EVALUATION_REPLICAS),
        "evaluation_sealed": True,
        "p3f_evaluation_holdout_used": False,
        "planned_case_ids": planned_case_ids(),
        "n_planned_cases": len(planned_case_ids()),
        "n_development_cases": 48,
        "routing": {
            "rule_policy_changed": False,
            "routing_connected": True,
            "policy": POLICY_NAME,
        },
        "m1_verdicts": list(M1_VERDICTS),
        "on_partial_or_blocked": "do not retune predicates or thresholds in this PR",
    }


def validate_phase3m_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("revision") != REVISION:
        errs.append("revision mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("protocol not frozen")
    if doc.get("generation") != GENERATION:
        errs.append("generation must be p3m")
    if doc.get("reuse_p3h_p3j_p3k_surfaces") is not False:
        errs.append("must not reuse prior surfaces")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("cut_in_conditional_map") is not False:
        errs.append("CUT must stay out of the conditional map")
    if doc.get("rule_policy_unchanged") is not True:
        errs.append("RulePolicy must stay unchanged")
    if list(doc.get("planned_case_ids") or []) != planned_case_ids():
        errs.append("planned case ids drifted")
    return errs


def validate_phase3m_split(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SPLIT_SCHEMA_ID:
        errs.append("split schema mismatch")
    if doc.get("evaluation_sealed") is not True:
        errs.append("evaluation must stay sealed")
    if list(doc.get("case_ids") or []) != planned_case_ids():
        errs.append("split case ids drifted")
    return errs


def write_freeze() -> tuple[Path, Path]:
    FREEZE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FREEZE_PATH.write_text(
        json.dumps(freeze_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    SPLIT_PATH.write_text(
        json.dumps(split_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return FREEZE_PATH, SPLIT_PATH


if __name__ == "__main__":
    write_freeze()
