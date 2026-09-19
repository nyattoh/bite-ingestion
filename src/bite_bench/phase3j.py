"""Phase 3J gold-free texture observability protocol (J0).

Fresh p3j generation. Does not measure profiler values in this module.
Does not change deterministic_v0, v1, thresholds, or routing.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from itertools import product
from pathlib import Path
from typing import Any, Literal

from bite_bench.models import CanonicalCase, Fact

SCHEMA_ID = "bitebench-phase3j-texture-observability-freeze/v0.1"
REVISION = "phase3j-texture-observability-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE3J_TEXTURE_OBSERVABILITY_PROTOCOL_FROZEN"
VERDICT_SUFFICIENT = "PHASE3J_EXISTING_FEATURES_SUFFICIENT"
VERDICT_REVISION = "PHASE3J_TEXTURE_SENSOR_REVISION_REQUIRED"
VERDICT_BLOCKED = "PHASE3J_OBSERVABILITY_BLOCKED"
MAP_VERDICTS = (VERDICT_SUFFICIENT, VERDICT_REVISION, VERDICT_BLOCKED)
LOCKED_CANDIDATE = "A_mean_edge_distance"
LOCKED_FEATURE = "mean_edge_distance"
LOCKED_T_LOW = 1
LOCKED_T_HIGH = 4
PROFILER_FEATURES = ("b", "r", "s", "k", "a", "l", "p", "u")
PAD_COUNT = 24
REDUNDANT_PAIRS = 12
ANOMALY_MARKERS = ("ERROR", "FATAL", "EXCEPTION", "TRACEBACK")
ANOMALY_PAD_INDEXES = (3, 7, 11, 15)
N_SURFACES = 24
GENERATION = "p3j"
SPLIT = "development"
DISPERSION = "far"
SHAPE = "one_hop"
SCALE = "medium"

Texture = Literal["redundant", "unique_reference", "anomalous", "neutral"]
Fmt = Literal["key_value", "compact_json", "pretty_json"]

TEXTURES: tuple[Texture, ...] = ("redundant", "unique_reference", "anomalous", "neutral")
FORMATS: tuple[Fmt, ...] = ("key_value", "compact_json", "pretty_json")
REPLICAS: tuple[int, ...] = (0, 1)

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase3j-texture-observability-freeze.json"


class EvaluationSealError(RuntimeError):
    """p3f evaluation replicas stay sealed."""


def refuse_p3f_evaluation(case_id: str) -> None:
    cid = str(case_id)
    if cid.startswith("p3f-") and ("-r2" in cid or "-r3" in cid):
        raise EvaluationSealError(f"p3f evaluation sealed: refused {cid}")


def core_case_id(replica: int) -> str:
    return f"p3j-core-r{replica}"


def surface_id(texture: Texture, replica: int, fmt: Fmt) -> str:
    return f"p3j-{texture}-r{replica}-{fmt}"


def bin_univariate(x: float, t_low: float = LOCKED_T_LOW, t_high: float = LOCKED_T_HIGH) -> str:
    if x <= t_low:
        return "low"
    if x >= t_high:
        return "high"
    return "mid"


def _dep_facts(replica: int) -> tuple[Fact, Fact, str, str]:
    case_id = core_case_id(replica)
    token = f"hop_p3j_core_r{replica}"
    answer = f"ans_p3j_core_r{replica}"
    origin = Fact(f"{case_id}-d0", f"origin_p3j_core_r{replica}", token)
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
        key = f"padk_{replica}_{index:03d}"
        value = f"padv_{replica}_{index:03d}"
        if texture == "unique_reference":
            tag = f"ref_p3j_{replica}_{index:03d}"
            value = f"{value} id={tag} key={tag} ref:{tag}"
        elif texture == "anomalous" and index in ANOMALY_PAD_INDEXES:
            marker = ANOMALY_MARKERS[ANOMALY_PAD_INDEXES.index(index)]
            value = f"{value} {marker}"
        pads.append(Fact(f"{case_id}-n{index:03d}", key, value))
    return tuple(pads)


def ordered_facts(replica: int, texture: Texture) -> tuple[Fact, ...]:
    origin, dest, _token, _answer = _dep_facts(replica)
    return (origin, *_pad_facts(replica, texture), dest)


def render_payload(facts: Sequence[Fact], fmt: Fmt) -> str:
    if fmt == "key_value":
        return "\n".join(f"{fact.key}={fact.value}" for fact in facts)
    records = [{"k": fact.key, "v": fact.value} for fact in facts]
    if fmt == "pretty_json":
        return json.dumps(records, indent=2)
    return json.dumps(records, separators=(",", ":"))


def make_canonical(replica: int, texture: Texture) -> CanonicalCase:
    origin, dest, token, answer = _dep_facts(replica)
    return CanonicalCase(
        case_id=core_case_id(replica),
        question=f"What result is stored after {token}?",
        answer=answer,
        required_evidence_ids=(origin.fact_id, dest.fact_id),
        facts=ordered_facts(replica, texture),
        task_family="p3j_texture",
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


def profiler_source_unit(payload: str) -> dict[str, str]:
    """The only object deterministic_v0 / v1 may see. No gold / texture / operator labels."""
    return {"payload": payload, "text": payload}


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
        "payload": render_payload(facts, fmt),
        "n_facts": len(facts),
        "gold_unit_ids": [origin.fact_id, dest.fact_id],
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
        "p3f_evaluation_holdout_used": False,
        "p3f_evaluation_replicas_sealed": [2, 3],
        "reuse_p3h_fixtures": False,
        "phase3h_verdict_unchanged": "PHASE3H_CONDITIONAL_MAP_REQUIRED",
        "phase3i_verdict_unchanged": "PHASE3I_COMPOSITE_PROVENANCE_VALIDATED",
        "locked_from_phase3g": {
            "selected_candidate": LOCKED_CANDIDATE,
            "feature": LOCKED_FEATURE,
            "T_low": LOCKED_T_LOW,
            "T_high": LOCKED_T_HIGH,
            "v1_sensor_unchanged": True,
            "profiler_unchanged": True,
            "thresholds_unchanged": True,
        },
        "routing": {
            "rule_policy_changed": False,
            "rule_policy_executed": False,
            "routing_connected": False,
            "connect_on_sufficient": False,
            "fix_profiler_on_revision": False,
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
            "intervening_texture_only": True,
            "anomaly_markers": list(ANOMALY_MARKERS),
            "unique_reference_overlay": "id= and key= and ref: on pad values only",
        },
        "profiler_input": {
            "allowed_keys": ["payload", "text"],
            "forbidden_keys": [
                "gold",
                "gold_evidence_ids",
                "texture",
                "operator",
                "route",
                "answer",
                "query",
            ],
        },
        "features_recorded": {
            "deterministic_v0": list(PROFILER_FEATURES),
            "dependency_dispersion_v1": [LOCKED_FEATURE, "bin"],
        },
        "no_new_absolute_threshold": True,
        "primary": "pairwise_ordering",
        "preregistered_contrasts": {
            "redundancy": {
                "feature": "r",
                "expect": ["r(redundant) > r(neutral)", "r(redundant) > r(unique_reference)"],
            },
            "anomaly": {
                "feature": "a",
                "expect": ["a(anomalous) > a(neutral)"],
            },
            "reference": {
                "feature": "k",
                "expect": ["k(unique_reference) > k(neutral)"],
            },
        },
        "format_stability": {
            "require_absolute_value_match": False,
            "require_contrast_direction_match_across_formats": True,
        },
        "high_bin_confirmation": "pre-measure mean_edge_distance >= T_high on every surface",
        "n_planned_surfaces": N_SURFACES,
        "planned_surface_ids": planned_surface_ids(),
        "j1_verdicts": list(MAP_VERDICTS),
        "on_sufficient": "do not connect routing in this phase",
        "on_revision_required": "do not patch deterministic_v0 in this phase",
    }


def validate_phase3j_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("revision") != REVISION:
        errs.append("revision mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("protocol not frozen")
    if doc.get("generation") != GENERATION:
        errs.append("generation must be p3j")
    if doc.get("reuse_p3h_fixtures") is not False:
        errs.append("must not reuse p3h fixtures")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("no_new_absolute_threshold") is not True:
        errs.append("must not add absolute thresholds")
    routing = dict(doc.get("routing") or {})
    if routing.get("rule_policy_executed") is not False:
        errs.append("must not execute routing")
    if routing.get("fix_profiler_on_revision") is not False:
        errs.append("must not patch the profiler in this phase")
    if list(doc.get("planned_surface_ids") or []) != planned_surface_ids():
        errs.append("planned surface ids drifted")
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
