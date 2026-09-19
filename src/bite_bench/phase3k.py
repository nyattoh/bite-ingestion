"""Phase 3K structural-redundancy v1 protocol (K0).

Fresh p3k generation. Does not implement the sensor. Does not measure.
Does not change deterministic_v0, v1, thresholds, or routing.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from itertools import product
from pathlib import Path
from typing import Any, Literal

SCHEMA_ID = "bitebench-phase3k-structural-redundancy-freeze/v0.1"
SPLIT_SCHEMA_ID = "bitebench-phase3k-split-manifest/v0.1"
REVISION = "phase3k-structural-redundancy-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE3K_REDUNDANCY_SENSOR_PROTOCOL_FROZEN"
VERDICT_READY = "PHASE3K_REDUNDANCY_SENSOR_READY"
VERDICT_PARTIAL = "PHASE3K_REDUNDANCY_SENSOR_PARTIAL"
VERDICT_BLOCKED = "PHASE3K_REDUNDANCY_SENSOR_BLOCKED"
K1_VERDICTS = (VERDICT_READY, VERDICT_PARTIAL, VERDICT_BLOCKED)
SENSOR_NAME = "structural_redundancy_v1"
PRIMARY_FEATURE = "duplicate_unit_ratio"
GENERATION = "p3k"
LOCKED_CANDIDATE = "A_mean_edge_distance"
LOCKED_T_LOW = 1
LOCKED_T_HIGH = 4

Family = Literal[
    "exact_dup_pairs",
    "all_unique",
    "same_key_diff_value",
    "same_value_diff_key",
    "reordered_duplicates",
    "multiplicity_2",
    "multiplicity_3",
    "common_prefix",
    "common_suffix",
    "identifier_substring",
]
Contract = Literal["malformed_json", "nul", "json_object"]
Fmt = Literal["key_value", "compact_json", "pretty_json"]
Split = Literal["development", "evaluation"]

FAMILIES: tuple[Family, ...] = (
    "exact_dup_pairs",
    "all_unique",
    "same_key_diff_value",
    "same_value_diff_key",
    "reordered_duplicates",
    "multiplicity_2",
    "multiplicity_3",
    "common_prefix",
    "common_suffix",
    "identifier_substring",
)
CONTRACTS: tuple[Contract, ...] = ("malformed_json", "nul", "json_object")
FORMATS: tuple[Fmt, ...] = ("key_value", "compact_json", "pretty_json")
CALIBRATION_REPLICAS: tuple[int, ...] = (0, 1)
EVALUATION_REPLICAS: tuple[int, ...] = (2, 3)
ALL_REPLICAS: tuple[int, ...] = (0, 1, 2, 3)
DIAGNOSTICS = (
    "n_records",
    "n_unique_records",
    "n_duplicate_records",
    "max_multiplicity",
    "parsed_format",
    "fail_closed",
)
OUT_OF_SCOPE_FORMATS = ("prose", "csv", "yaml")

# Analytic expects. Frozen before measurement. No tolerance.
FAMILY_EXPECT: dict[Family, dict[str, float | int | bool]] = {
    "exact_dup_pairs": {
        "n_records": 6,
        "n_unique_records": 3,
        "n_duplicate_records": 3,
        "max_multiplicity": 2,
        "duplicate_unit_ratio": 0.5,
        "fail_closed": False,
    },
    "all_unique": {
        "n_records": 4,
        "n_unique_records": 4,
        "n_duplicate_records": 0,
        "max_multiplicity": 1,
        "duplicate_unit_ratio": 0.0,
        "fail_closed": False,
    },
    "same_key_diff_value": {
        "n_records": 3,
        "n_unique_records": 3,
        "n_duplicate_records": 0,
        "max_multiplicity": 1,
        "duplicate_unit_ratio": 0.0,
        "fail_closed": False,
    },
    "same_value_diff_key": {
        "n_records": 3,
        "n_unique_records": 3,
        "n_duplicate_records": 0,
        "max_multiplicity": 1,
        "duplicate_unit_ratio": 0.0,
        "fail_closed": False,
    },
    "reordered_duplicates": {
        "n_records": 6,
        "n_unique_records": 3,
        "n_duplicate_records": 3,
        "max_multiplicity": 2,
        "duplicate_unit_ratio": 0.5,
        "fail_closed": False,
    },
    "multiplicity_2": {
        "n_records": 4,
        "n_unique_records": 3,
        "n_duplicate_records": 1,
        "max_multiplicity": 2,
        "duplicate_unit_ratio": 0.25,
        "fail_closed": False,
    },
    "multiplicity_3": {
        "n_records": 4,
        "n_unique_records": 2,
        "n_duplicate_records": 2,
        "max_multiplicity": 3,
        "duplicate_unit_ratio": 0.5,
        "fail_closed": False,
    },
    "common_prefix": {
        "n_records": 2,
        "n_unique_records": 2,
        "n_duplicate_records": 0,
        "max_multiplicity": 1,
        "duplicate_unit_ratio": 0.0,
        "fail_closed": False,
    },
    "common_suffix": {
        "n_records": 2,
        "n_unique_records": 2,
        "n_duplicate_records": 0,
        "max_multiplicity": 1,
        "duplicate_unit_ratio": 0.0,
        "fail_closed": False,
    },
    "identifier_substring": {
        "n_records": 2,
        "n_unique_records": 2,
        "n_duplicate_records": 0,
        "max_multiplicity": 1,
        "duplicate_unit_ratio": 0.0,
        "fail_closed": False,
    },
}
CONTRACT_EXPECT: dict[Contract, dict[str, float | int | bool]] = {
    "malformed_json": {
        "n_records": 0,
        "n_unique_records": 0,
        "n_duplicate_records": 0,
        "max_multiplicity": 0,
        "duplicate_unit_ratio": 0.0,
        "fail_closed": True,
    },
    "nul": {
        "n_records": 0,
        "n_unique_records": 0,
        "n_duplicate_records": 0,
        "max_multiplicity": 0,
        "duplicate_unit_ratio": 0.0,
        "fail_closed": True,
    },
    "json_object": {
        "n_records": 0,
        "n_unique_records": 0,
        "n_duplicate_records": 0,
        "max_multiplicity": 0,
        "duplicate_unit_ratio": 0.0,
        "fail_closed": True,
    },
}

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase3k-structural-redundancy-freeze.json"
SPLIT_PATH = _REPO / "benchmarks" / "spec" / "phase3k-split-manifest.json"


class EvaluationSealError(RuntimeError):
    """p3k evaluation replicas 2/3 and p3f evaluation stay sealed."""


def refuse_p3f_evaluation(case_id: str) -> None:
    cid = str(case_id)
    if cid.startswith("p3f-") and ("-r2" in cid or "-r3" in cid):
        raise EvaluationSealError(f"p3f evaluation sealed: refused {cid}")


def refuse_p3k_evaluation(case_id: str) -> None:
    cid = str(case_id)
    if cid.startswith("p3k-") and (
        "-r2-" in cid or "-r3-" in cid or cid.endswith(("-r2", "-r3"))
    ):
        raise EvaluationSealError(f"p3k evaluation sealed: refused {cid}")


def refuse_evaluation(case_id: str) -> None:
    refuse_p3f_evaluation(case_id)
    refuse_p3k_evaluation(case_id)


def split_of_replica(replica: int) -> Split:
    return "development" if replica in CALIBRATION_REPLICAS else "evaluation"


def family_case_id(family: Family, replica: int, fmt: Fmt) -> str:
    return f"p3k-{family}-r{replica}-{fmt}"


def contract_case_id(kind: Contract, replica: int) -> str:
    return f"p3k-{kind}-r{replica}"


def records_for(family: Family, replica: int) -> tuple[tuple[str, str], ...]:
    tag = f"r{replica}"
    if family == "exact_dup_pairs":
        pairs = tuple((f"dupk_{tag}_{i:02d}", f"dupv_{tag}_{i:02d}") for i in range(3))
        return tuple(item for pair in pairs for item in (pair, pair))
    if family == "all_unique":
        return tuple((f"unik_{tag}_{i:02d}", f"univ_{tag}_{i:02d}") for i in range(4))
    if family == "same_key_diff_value":
        key = f"skdv_{tag}"
        return tuple((key, f"val_{chr(97 + i)}_{tag}") for i in range(3))
    if family == "same_value_diff_key":
        shared = f"shared_{tag}"
        return tuple((f"svdk_{chr(97 + i)}_{tag}", shared) for i in range(3))
    if family == "reordered_duplicates":
        a = (f"dupk_{tag}_00", f"dupv_{tag}_00")
        b = (f"dupk_{tag}_01", f"dupv_{tag}_01")
        c = (f"dupk_{tag}_02", f"dupv_{tag}_02")
        return (b, c, a, c, a, b)
    if family == "multiplicity_2":
        dup = (f"m2k_{tag}", f"m2v_{tag}")
        return (dup, dup, (f"m2x_{tag}", f"m2xv_{tag}"), (f"m2y_{tag}", f"m2yv_{tag}"))
    if family == "multiplicity_3":
        trip = (f"m3k_{tag}", f"m3v_{tag}")
        return (trip, trip, trip, (f"m3z_{tag}", f"m3zv_{tag}"))
    if family == "common_prefix":
        return (
            (f"pre_{tag}_alpha", f"pval_{tag}_1"),
            (f"pre_{tag}_alphabet", f"pval_{tag}_2"),
        )
    if family == "common_suffix":
        return (
            (f"alpha_{tag}_suf", f"sval_{tag}_1"),
            (f"beta_{tag}_suf", f"sval_{tag}_2"),
        )
    return (
        (f"item_{tag}", "rec_id_7"),
        (f"itemx_{tag}", "rec_id_70"),
    )


def render_payload(records: Sequence[tuple[str, str]], fmt: Fmt) -> str:
    if fmt == "key_value":
        return "\n".join(f"{key}={value}" for key, value in records)
    objs = [{"k": key, "v": value} for key, value in records]
    if fmt == "pretty_json":
        return json.dumps(objs, indent=2)
    return json.dumps(objs, separators=(",", ":"))


def contract_payload(kind: Contract) -> str:
    if kind == "malformed_json":
        return '[{"k":"alpha","v":"beta"'
    if kind == "nul":
        return "alpha=beta\x00gamma=delta"
    return '{"k":"alpha","v":"beta"}'


def sensor_source_unit(payload: str) -> dict[str, str]:
    return {"payload": payload, "text": payload}


def family_surface(family: Family, replica: int, fmt: Fmt) -> dict[str, Any]:
    refuse_evaluation(family_case_id(family, replica, fmt))
    records = records_for(family, replica)
    return {
        "case_id": family_case_id(family, replica, fmt),
        "generation": GENERATION,
        "family": family,
        "replica": replica,
        "format": fmt,
        "split": split_of_replica(replica),
        "payload": render_payload(records, fmt),
        "n_canonical_records": len(records),
        "expect": dict(FAMILY_EXPECT[family]),
    }


def contract_surface(kind: Contract, replica: int) -> dict[str, Any]:
    refuse_evaluation(contract_case_id(kind, replica))
    return {
        "case_id": contract_case_id(kind, replica),
        "generation": GENERATION,
        "family": kind,
        "replica": replica,
        "format": "contract",
        "split": split_of_replica(replica),
        "payload": contract_payload(kind),
        "n_canonical_records": 0,
        "expect": dict(CONTRACT_EXPECT[kind]),
    }


def planned_family_ids() -> list[str]:
    return [
        family_case_id(family, replica, fmt)
        for family, replica, fmt in product(FAMILIES, ALL_REPLICAS, FORMATS)
    ]


def planned_contract_ids() -> list[str]:
    return [
        contract_case_id(kind, replica)
        for kind, replica in product(CONTRACTS, CALIBRATION_REPLICAS)
    ]


def planned_case_ids() -> list[str]:
    return [*planned_family_ids(), *planned_contract_ids()]


def development_surfaces() -> list[dict[str, Any]]:
    rows = [
        family_surface(family, replica, fmt)
        for family, replica, fmt in product(FAMILIES, CALIBRATION_REPLICAS, FORMATS)
    ]
    rows.extend(
        contract_surface(kind, replica)
        for kind, replica in product(CONTRACTS, CALIBRATION_REPLICAS)
    )
    return rows


def split_manifest() -> dict[str, Any]:
    cases = []
    for family, replica, fmt in product(FAMILIES, ALL_REPLICAS, FORMATS):
        cases.append(
            {
                "case_id": family_case_id(family, replica, fmt),
                "family": family,
                "replica": replica,
                "format": fmt,
                "split": split_of_replica(replica),
            }
        )
    for kind, replica in product(CONTRACTS, CALIBRATION_REPLICAS):
        cases.append(
            {
                "case_id": contract_case_id(kind, replica),
                "family": kind,
                "replica": replica,
                "format": "contract",
                "split": "development",
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
        "premise": "PHASE3J_TEXTURE_SENSOR_REVISION_REQUIRED",
        "generation": GENERATION,
        "reuse_p3j_surfaces": False,
        "sensor_name": SENSOR_NAME,
        "does_not_overwrite_deterministic_v0_r": True,
        "a_unchanged": True,
        "k_unchanged": True,
        "v1_unchanged": True,
        "no_threshold": True,
        "no_per_format_threshold": True,
        "primary_feature": PRIMARY_FEATURE,
        "formula": "0 if n_records == 0 else 1 - n_unique_records / n_records",
        "equality": "exact_logical_record",
        "near_duplicate": False,
        "semantic_similarity": False,
        "formats": list(FORMATS),
        "out_of_scope_formats": list(OUT_OF_SCOPE_FORMATS),
        "fail_closed": ["malformed_structured", "nul"],
        "no_line_fallback_for_malformed_json": True,
        "logical_unit": {
            "key_value": (
                "each non-empty line is one record; split on first '='; "
                "strip only outer whitespace around the separator"
            ),
            "json": (
                "top-level array of objects; each {k, v} becomes the same "
                "(key, value) canonical record; indent and object key order "
                "do not affect identity; do not lowercase or fuzzy-normalize content"
            ),
        },
        "diagnostics": list(DIAGNOSTICS),
        "algorithm": "parse_once_then_counter",
        "forbids": ["pairwise_o_n2_duplicate_search"],
        "wall_time_slo": None,
        "locked_from_phase3g": {
            "selected_candidate": LOCKED_CANDIDATE,
            "T_low": LOCKED_T_LOW,
            "T_high": LOCKED_T_HIGH,
        },
        "routing": {
            "rule_policy_changed": False,
            "rule_policy_executed": False,
            "routing_connected": False,
            "connect_on_ready": False,
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
        "families": list(FAMILIES),
        "contracts": list(CONTRACTS),
        "family_expect": FAMILY_EXPECT,
        "contract_expect": CONTRACT_EXPECT,
        "calibration_replicas": list(CALIBRATION_REPLICAS),
        "evaluation_replicas": list(EVALUATION_REPLICAS),
        "evaluation_sealed": True,
        "p3f_evaluation_holdout_used": False,
        "p3f_evaluation_replicas_sealed": [2, 3],
        "planned_case_ids": planned_case_ids(),
        "n_planned_cases": len(planned_case_ids()),
        "k1_verdicts": list(K1_VERDICTS),
        "on_ready": "do not connect routing in this phase",
        "on_partial": "do not patch deterministic_v0 in this phase",
    }


def validate_phase3k_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("revision") != REVISION:
        errs.append("revision mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("protocol not frozen")
    if doc.get("generation") != GENERATION:
        errs.append("generation must be p3k")
    if doc.get("reuse_p3j_surfaces") is not False:
        errs.append("must not reuse p3j surfaces")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("no_threshold") is not True:
        errs.append("must not add thresholds")
    if doc.get("does_not_overwrite_deterministic_v0_r") is not True:
        errs.append("must not overwrite deterministic_v0.r")
    routing = dict(doc.get("routing") or {})
    if routing.get("rule_policy_executed") is not False:
        errs.append("must not execute routing")
    if routing.get("connect_on_ready") is not False:
        errs.append("must not connect routing on ready")
    if list(doc.get("planned_case_ids") or []) != planned_case_ids():
        errs.append("planned case ids drifted")
    return errs


def validate_phase3k_split(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SPLIT_SCHEMA_ID:
        errs.append("split schema mismatch")
    if doc.get("generation") != GENERATION:
        errs.append("split generation must be p3k")
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
