"""Phase 3F routing-calibration protocol freeze.

New benchmark generation for dependency_dispersion_v1. Does not measure
sensor/routing values. Does not open Phase 2 evaluation. Does not change
routing policy or v1.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path
from typing import Any, Literal

from bite_bench.models import CanonicalCase, Fact

SCHEMA_ID = "bitebench-phase3f-routing-calibration-freeze/v0.1"
REVISION = "phase3f-routing-calibration-freeze-v0.1"
VERDICT_FROZEN = "PHASE3F_ROUTING_CALIBRATION_PROTOCOL_FROZEN"
VERDICT_BLOCKED = "PHASE3F_PROTOCOL_BLOCKED"
VERDICTS = (VERDICT_FROZEN, VERDICT_BLOCKED)

Scale = Literal["small", "medium", "large"]
Shape = Literal["one_hop", "two_hop", "branch"]
Dispersion = Literal["near", "medium", "far"]
Fmt = Literal["key_value", "json"]

SCALES: tuple[Scale, ...] = ("small", "medium", "large")
SHAPES: tuple[Shape, ...] = ("one_hop", "two_hop", "branch")
DISPERSIONS: tuple[Dispersion, ...] = ("near", "medium", "far")
FORMATS: tuple[Fmt, ...] = ("key_value", "json")
REPLICAS: tuple[int, ...] = (0, 1, 2, 3)
CALIBRATION_REPLICAS: tuple[int, ...] = (0, 1)
EVALUATION_REPLICAS: tuple[int, ...] = (2, 3)
DISTRACTOR_COUNTS: dict[Scale, int] = {"small": 8, "medium": 24, "large": 48}
MEDIUM_GAP = 3
ADVERSARIAL_KINDS: tuple[str, ...] = (
    "key_suffix_matches_value",
    "shared_prefix",
    "shared_suffix",
    "substring_not_dependency",
    "unrelated_same_value",
    "true_dep_plus_misleading_suffix",
)

CANDIDATES: tuple[str, ...] = ("A_mean_edge_distance", "B_mean_edge_distance_norm", "C_raw_and_norm")

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase3f-routing-calibration-freeze.json"
SPLIT_PATH = _REPO / "benchmarks" / "spec" / "phase3f-split-manifest.json"


@dataclass(frozen=True)
class Phase3FCell:
    scale: Scale
    shape: Shape
    replica: int
    split: str

    @property
    def case_id(self) -> str:
        return f"p3f-{self.scale}-{self.shape}-r{self.replica}"


def split_for_replica(replica: int) -> str:
    if replica in CALIBRATION_REPLICAS:
        return "calibration"
    if replica in EVALUATION_REPLICAS:
        return "evaluation"
    raise ValueError(replica)


def design_cells(split: str | None = None) -> tuple[Phase3FCell, ...]:
    cells = tuple(
        Phase3FCell(scale, shape, replica, split_for_replica(replica))
        for scale, shape, replica in product(SCALES, SHAPES, REPLICAS)
    )
    if split is None:
        return cells
    return tuple(cell for cell in cells if cell.split == split)


def surface_id(case_id: str, dispersion: str, fmt: str) -> str:
    return f"{case_id}-{dispersion}-{fmt}"


def _noise(cell: Phase3FCell) -> tuple[Fact, ...]:
    n = DISTRACTOR_COUNTS[cell.scale]
    return tuple(
        Fact(
            fact_id=f"{cell.case_id}-n{i:03d}",
            key=f"padk_{cell.replica}_{i:03d}",
            value=f"padv_{cell.scale}_{cell.shape}_{i:03d}",
        )
        for i in range(n)
    )


def _dep_facts(cell: Phase3FCell) -> tuple[tuple[Fact, ...], str, str, tuple[str, ...]]:
    stem = cell.case_id.replace("-", "_")
    answer = f"ans_{stem}"
    if cell.shape == "one_hop":
        token = f"hop_{stem}"
        f0 = Fact(f"{cell.case_id}-d0", f"origin_{stem}", token)
        f1 = Fact(f"{cell.case_id}-d1", f"bin_{token}", answer)
        q = f"What result is stored after {token}?"
        return (f0, f1), q, answer, (f0.fact_id, f1.fact_id)
    if cell.shape == "two_hop":
        a = f"hop_{stem}_a"
        b = f"hop_{stem}_b"
        f0 = Fact(f"{cell.case_id}-d0", f"origin_{stem}", a)
        f1 = Fact(f"{cell.case_id}-d1", f"bin_{a}", b)
        f2 = Fact(f"{cell.case_id}-d2", f"bin_{b}", answer)
        q = f"What result follows {a} then {b}?"
        return (f0, f1, f2), q, answer, (f0.fact_id, f1.fact_id, f2.fact_id)
    left = f"hop_{stem}_l"
    right = f"hop_{stem}_r"
    token = f"hop_{stem}"
    f0 = Fact(f"{cell.case_id}-d0", f"origin_{stem}", token)
    f1 = Fact(f"{cell.case_id}-d1", f"left_{token}", left)
    f2 = Fact(f"{cell.case_id}-d2", f"right_{token}", right)
    q = f"What are the two branches of {token}?"
    answer = f"{left}|{right}"
    return (f0, f1, f2), q, answer, (f0.fact_id, f1.fact_id, f2.fact_id)


def make_canonical(cell: Phase3FCell) -> CanonicalCase:
    dep, question, answer, required = _dep_facts(cell)
    facts = dep + _noise(cell)
    return CanonicalCase(
        case_id=cell.case_id,
        question=question,
        answer=answer,
        required_evidence_ids=required,
        facts=facts,
        task_family="p3f_dispersion",
        meta={
            "scale": cell.scale,
            "shape": cell.shape,
            "replica": cell.replica,
            "split": cell.split,
            "n_distractors": DISTRACTOR_COUNTS[cell.scale],
        },
    )


def layout_facts(
    dep: Sequence[Fact], noise: Sequence[Fact], shape: Shape, dispersion: Dispersion
) -> tuple[Fact, ...]:
    nse = list(noise)
    if shape == "one_hop":
        a, b = dep
        if dispersion == "near":
            return (a, b, *nse)
        if dispersion == "medium":
            gap = nse[:MEDIUM_GAP]
            return (a, *gap, b, *nse[MEDIUM_GAP:])
        return (a, *nse, b)
    if shape == "two_hop":
        a, mid, b = dep
        if dispersion == "near":
            return (a, mid, b, *nse)
        if dispersion == "medium":
            return (a, *nse[:2], mid, *nse[2:4], b, *nse[4:])
        half = len(nse) // 2
        return (a, *nse[:half], mid, *nse[half:], b)
    origin, left, right = dep
    if dispersion == "near":
        return (origin, left, right, *nse)
    if dispersion == "medium":
        return (origin, *nse[:MEDIUM_GAP], left, right, *nse[MEDIUM_GAP:])
    return (origin, *nse, left, right)


def render_payload(facts: Sequence[Fact], fmt: Fmt) -> str:
    if fmt == "key_value":
        return "\n".join(f"{fact.key}={fact.value}" for fact in facts)
    records = [{"k": fact.key, "v": fact.value} for fact in facts]
    return json.dumps(records, separators=(",", ":"))


def sensor_source_unit(payload: str) -> dict[str, str]:
    """The only object v1 may see. Gold fields are not present."""
    return {"payload": payload, "text": payload}


def make_surface(
    cell: Phase3FCell, dispersion: Dispersion, fmt: Fmt
) -> dict[str, Any]:
    canonical = make_canonical(cell)
    dep = [f for f in canonical.facts if f.fact_id.startswith(f"{cell.case_id}-d")]
    noise = [f for f in canonical.facts if f.fact_id.startswith(f"{cell.case_id}-n")]
    ordered = layout_facts(dep, noise, cell.shape, dispersion)
    payload = render_payload(ordered, fmt)
    return {
        "surface_id": surface_id(cell.case_id, dispersion, fmt),
        "case_id": cell.case_id,
        "split": cell.split,
        "scale": cell.scale,
        "shape": cell.shape,
        "replica": cell.replica,
        "dispersion": dispersion,
        "format": fmt,
        "payload": payload,
        "n_facts": len(ordered),
    }


def intended_edges(cell: Phase3FCell) -> list[list[str]]:
    dep, _q, _a, _ids = _dep_facts(cell)
    if cell.shape == "one_hop":
        return [[dep[0].fact_id, dep[1].fact_id]]
    if cell.shape == "two_hop":
        return [[dep[0].fact_id, dep[1].fact_id], [dep[1].fact_id, dep[2].fact_id]]
    return [[dep[0].fact_id, dep[1].fact_id], [dep[0].fact_id, dep[2].fact_id]]


def adversarial_case(kind: str, replica: int) -> dict[str, Any]:
    split = split_for_replica(replica)
    case_id = f"p3f-adv-{kind}-r{replica}"
    tag = f"r{replica}"
    facts: tuple[Fact, ...]
    if kind == "key_suffix_matches_value":
        tok = f"tok_zeta_{tag}"
        facts = (
            Fact(f"{case_id}-a", f"anchor_{tag}", tok),
            Fact(f"{case_id}-b", f"misc_{tok}", f"plain_{tag}"),
        )
        intended: list[list[str]] = []
    elif kind == "shared_prefix":
        facts = (
            Fact(f"{case_id}-a", f"grp_alpha_{tag}", f"val_one_{tag}"),
            Fact(f"{case_id}-b", f"grp_bravo_{tag}", f"val_two_{tag}"),
        )
        intended = []
    elif kind == "shared_suffix":
        facts = (
            Fact(f"{case_id}-a", f"head_tok_tail_{tag}", f"val_a_{tag}"),
            Fact(f"{case_id}-b", f"other_tok_tail_{tag}", f"val_b_{tag}"),
        )
        intended = []
    elif kind == "substring_not_dependency":
        facts = (
            Fact(f"{case_id}-a", f"row_{tag}", "idab"),
            Fact(f"{case_id}-b", "xidabx", f"other_{tag}"),
        )
        intended = []
    elif kind == "unrelated_same_value":
        shared = f"env_prod_{tag}"
        facts = (
            Fact(f"{case_id}-a", f"row_alpha_{tag}", shared),
            Fact(f"{case_id}-b", f"row_beta_{tag}", shared),
        )
        intended = []
    elif kind == "true_dep_plus_misleading_suffix":
        tok = f"hop_mu_{tag}"
        ans = f"ans_mu_{tag}"
        facts = (
            Fact(f"{case_id}-a", f"origin_{tag}", tok),
            Fact(f"{case_id}-b", f"bin_{tok}", ans),
            Fact(f"{case_id}-c", f"trap_{tok}", f"noise_{tag}"),
        )
        intended = [[f"{case_id}-a", f"{case_id}-b"]]
    else:
        raise ValueError(kind)
    return {
        "case_id": case_id,
        "kind": kind,
        "replica": replica,
        "split": split,
        "facts": [asdict(f) for f in facts],
        "intended_edges": intended,
        "note": "gold/intended_edges are scorer-only; not sensor input",
    }


def adversarial_surface(kind: str, replica: int, fmt: Fmt) -> dict[str, Any]:
    spec = adversarial_case(kind, replica)
    facts = tuple(Fact(**row) for row in spec["facts"])
    payload = render_payload(facts, fmt)
    return {
        "surface_id": f"{spec['case_id']}-{fmt}",
        "case_id": spec["case_id"],
        "kind": kind,
        "split": spec["split"],
        "format": fmt,
        "payload": payload,
    }


def candidate_protocol() -> dict[str, Any]:
    return {
        "do_not_pick_by_n_signal": True,
        "candidates": [
            {
                "id": "A_mean_edge_distance",
                "feature": "mean_edge_distance",
                "meaning": "absolute_logical_unit_separation",
                "simplicity_rank": 1,
            },
            {
                "id": "B_mean_edge_distance_norm",
                "feature": "mean_edge_distance_norm",
                "meaning": "relative_logical_unit_separation",
                "simplicity_rank": 2,
            },
            {
                "id": "C_raw_and_norm",
                "features": ["mean_edge_distance", "mean_edge_distance_norm"],
                "rule": (
                    "high if raw>=T_raw_high AND norm>=T_norm_high; "
                    "low if raw<=T_raw_low AND norm<=T_norm_low; else mid"
                ),
                "simplicity_rank": 3,
            },
        ],
        "selection_priority": [
            {
                "rank": 1,
                "name": "adversarial_false_positive_rate",
                "prefer": "lower",
                "definition": (
                    "on calibration adversarial surfaces, fraction of cases with "
                    "a v1 edge that is not in intended_edges"
                ),
            },
            {
                "rank": 2,
                "name": "dispersion_ordering_coverage",
                "prefer": "higher",
                "definition": (
                    "fraction of calibration primary cells where the candidate "
                    "score is strictly near < medium < far"
                ),
            },
            {
                "rank": 3,
                "name": "scale_stability",
                "prefer": "higher",
                "definition": (
                    "one-hop medium (abs gap 3) keeps raw equal across scales; "
                    "one-hop far (endpoints) keeps norm equal across scales"
                ),
            },
            {
                "rank": 4,
                "name": "format_consistency",
                "prefer": "higher",
                "definition": (
                    "fraction of calibration cells where key_value and json "
                    "get the same low/mid/high bin"
                ),
            },
            {
                "rank": 5,
                "name": "non_collapse",
                "prefer": "eligible_only",
                "definition": (
                    "after binning, no single bin may cover >= 0.95 of "
                    "calibration primary surfaces"
                ),
            },
            {
                "rank": 6,
                "name": "simplicity",
                "prefer": "lower_simplicity_rank",
                "tie_order": list(CANDIDATES),
            },
        ],
        "do_not_add_candidates_after_seeing_calibration": True,
    }


def threshold_search_protocol() -> dict[str, Any]:
    return {
        "phase": "3G_calibration_only",
        "evaluation_sealed_until_locked": True,
        "do_not_edit_after_seeing_evaluation": True,
        "values_not_set_in_phase3f": True,
        "bin_rule": (
            "x <= T_low -> low; T_low < x < T_high -> mid; x >= T_high -> high"
        ),
        "grids": {
            "A_mean_edge_distance": {
                "T_low": [1, 2, 3, 4, 5],
                "T_high": [4, 5, 6, 7, 8, 9, 10],
                "constraint": "T_low < T_high",
            },
            "B_mean_edge_distance_norm": {
                "T_low": [0.05, 0.10, 0.15, 0.20, 0.25],
                "T_high": [0.30, 0.40, 0.50, 0.60, 0.75, 0.90],
                "constraint": "T_low < T_high",
            },
            "C_raw_and_norm": {
                "T_raw_low": [1, 2, 4],
                "T_raw_high": [4, 9],
                "T_norm_low": [0.10, 0.25],
                "T_norm_high": [0.50, 0.75],
                "constraint": "T_raw_low < T_raw_high and T_norm_low < T_norm_high",
            },
        },
        "objective": (
            "among grid points that minimize adversarial FP on calibration "
            "and pass non_collapse, maximize dispersion_ordering_coverage; "
            "tie -> smallest T_high then smallest T_low"
        ),
        "not_objective": ["n_signal", "INTEGRATE_rate"],
    }


def operator_map_candidates() -> dict[str, Any]:
    return {
        "dispersion_feature_does_not_auto_integrate": True,
        "existing_rule_policy_unchanged_in_phase3f": True,
        "bins": ["low", "mid", "high"],
        "candidates": [
            {
                "id": "M1_locality_for_integrate",
                "low": "may_contribute_toward_INTEGRATE_only_with_other_features",
                "mid": "candidate_to_prepend_UNTANGLE_then_existing_rule_pi",
                "high": "must_not_fire_INTEGRATE_from_this_feature_alone; CUT_or_REDUCE_candidate",
            },
            {
                "id": "M2_spread_needs_gather",
                "low": "no_extra_operator_from_this_feature",
                "mid": "candidate_to_prepend_UNTANGLE",
                "high": "may_contribute_toward_INTEGRATE_only_with_other_features",
            },
        ],
        "mapping_selection": (
            "after feature candidate is locked, pick M1 vs M2 with the same "
            "priority list; neither may auto-INTEGRATE; tie -> M1"
        ),
        "adoption": "phase3g_calibration_only",
    }


def _surface_catalog() -> list[dict[str, Any]]:
    rows = []
    for cell in design_cells():
        for dispersion, fmt in product(DISPERSIONS, FORMATS):
            rows.append(
                {
                    "surface_id": surface_id(cell.case_id, dispersion, fmt),
                    "case_id": cell.case_id,
                    "split": cell.split,
                    "scale": cell.scale,
                    "shape": cell.shape,
                    "replica": cell.replica,
                    "dispersion": dispersion,
                    "format": fmt,
                    "family": "primary",
                }
            )
    for kind, replica, fmt in product(ADVERSARIAL_KINDS, REPLICAS, FORMATS):
        spec = adversarial_case(kind, replica)
        rows.append(
            {
                "surface_id": f"{spec['case_id']}-{fmt}",
                "case_id": spec["case_id"],
                "split": spec["split"],
                "kind": kind,
                "replica": replica,
                "format": fmt,
                "family": "adversarial",
            }
        )
    return rows


def split_manifest() -> dict[str, Any]:
    rows = _surface_catalog()
    return {
        "schema": "bitebench-phase3f-split-manifest/v0.1",
        "revision": REVISION,
        "evaluation_outcomes_open": False,
        "calibration_measured": False,
        "n_calibration": sum(1 for row in rows if row["split"] == "calibration"),
        "n_evaluation": sum(1 for row in rows if row["split"] == "evaluation"),
        "calibration_replicas": list(CALIBRATION_REPLICAS),
        "evaluation_replicas": list(EVALUATION_REPLICAS),
        "surfaces": rows,
    }


def freeze_manifest() -> dict[str, Any]:
    blocked: list[str] = []
    if "prose" in FORMATS or "csv" in FORMATS or "yaml" in FORMATS:
        blocked.append("unsupported_format_in_required_set")
    if CALIBRATION_REPLICAS == EVALUATION_REPLICAS:
        blocked.append("split_not_disjoint")
    verdict = VERDICT_BLOCKED if blocked else VERDICT_FROZEN
    catalog = _surface_catalog()
    return {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "verdict": verdict,
        "blocked_reasons": blocked,
        "offline": True,
        "paid_api": False,
        "synthetic": True,
        "research_conclusion": False,
        "routing_connected": False,
        "evaluation_holdout_used": False,
        "v1_sensor_changed": False,
        "v0_overwritten": False,
        "rule_policy_changed": False,
        "thresholds_set": False,
        "calibration_measured": False,
        "evaluation_outcomes_open": False,
        "premise": "PHASE3E_V1_VALIDATED",
        "generation": "p3f",
        "not_phase2": True,
        "required_formats": list(FORMATS),
        "out_of_scope_formats": ["csv", "yaml", "prose"],
        "primary_axis": "dependency_dispersion",
        "dispersion_levels": list(DISPERSIONS),
        "scale_levels": list(SCALES),
        "shapes": list(SHAPES),
        "distractor_counts": dict(DISTRACTOR_COUNTS),
        "medium_intervening_units": MEDIUM_GAP,
        "length_control": (
            "near/medium/far of one canonical cell are permutations of the "
            "same logical units; no padding"
        ),
        "scale_contrasts": {
            "same_absolute_different_size": "one_hop medium (gap=3) across small/medium/large",
            "same_relative_different_absolute": "one_hop far (endpoints) across small/medium/large",
        },
        "gold_leakage": "forbidden_in_sensor_input",
        "n_canonical_cells": len(design_cells()),
        "n_primary_surfaces": sum(1 for row in catalog if row["family"] == "primary"),
        "n_adversarial_surfaces": sum(1 for row in catalog if row["family"] == "adversarial"),
        "canonical_case_ids": [cell.case_id for cell in design_cells()],
        "adversarial": [adversarial_case(kind, replica) for kind, replica in product(ADVERSARIAL_KINDS, REPLICAS)],
        "candidates": candidate_protocol(),
        "threshold_search": threshold_search_protocol(),
        "operator_maps": operator_map_candidates(),
        "phase3g": "calibration_split_only",
        "purpose": (
            "freeze how v1 would be chosen for routing before seeing any "
            "calibration numbers; not a routing connection"
        ),
    }


def validate_phase3f_doc(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append(f"bad schema: {doc.get('schema')!r}")
    if doc.get("paid_api") is not False:
        errs.append("paid_api must be false")
    if doc.get("routing_connected") is not False:
        errs.append("must not connect routing")
    if doc.get("evaluation_holdout_used") is not False:
        errs.append("must not use Phase 2 holdout")
    if doc.get("calibration_measured") is not False:
        errs.append("must not measure calibration in Phase 3F")
    if doc.get("evaluation_outcomes_open") is not False:
        errs.append("must not open evaluation outcomes")
    if doc.get("thresholds_set") is not False:
        errs.append("must not set threshold values")
    if doc.get("v1_sensor_changed") is not False:
        errs.append("must not change v1")
    if doc.get("rule_policy_changed") is not False:
        errs.append("must not change routing policy")
    if doc.get("verdict") not in VERDICTS:
        errs.append(f"bad verdict: {doc.get('verdict')!r}")
    if list(doc.get("required_formats") or []) != list(FORMATS):
        errs.append("required formats drifted")
    blob = json.dumps(doc)
    if "operator_sequence" in blob or "T_profiler" in blob:
        errs.append("evaluation routing/profiler outcome leaked")
    case_ids = list(doc.get("canonical_case_ids") or [])
    if any(not str(cid).startswith("p3f-") for cid in case_ids):
        errs.append("canonical ids must be p3f generation")
    cands = (doc.get("candidates") or {}).get("candidates") or []
    ids = [row.get("id") for row in cands]
    if ids != list(CANDIDATES):
        errs.append("candidates drifted")
    if not (doc.get("candidates") or {}).get("do_not_pick_by_n_signal"):
        errs.append("must not pick by n_signal")
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
