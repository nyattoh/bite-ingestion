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

SCHEMA_ID_V01 = "bitebench-phase3f-routing-calibration-freeze/v0.1"
SCHEMA_ID_V02 = "bitebench-phase3f-routing-calibration-freeze/v0.2"
SCHEMA_ID = "bitebench-phase3f-routing-calibration-freeze/v0.3"
REVISION_V01 = "phase3f-routing-calibration-freeze-v0.1"
REVISION_V02 = "phase3f-routing-calibration-freeze-v0.2"
REVISION = "phase3f-routing-calibration-freeze-v0.3"
VERDICT_FROZEN = "PHASE3F_ROUTING_CALIBRATION_PROTOCOL_FROZEN"
VERDICT_BLOCKED = "PHASE3F_PROTOCOL_BLOCKED"
VERDICTS = (VERDICT_FROZEN, VERDICT_BLOCKED)
COLLAPSE_FRACTION = 0.95
_BIN_RANK = {"low": 0, "mid": 1, "high": 2}

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
V01_FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase3f-routing-calibration-freeze.json"
V02_FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase3f-routing-calibration-freeze-v0.2.json"
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase3f-routing-calibration-freeze-v0.3.json"
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


def strict_dispersion_order(near: float, medium: float, far: float) -> bool:
    return near < medium < far


def candidate_ordering_holds(
    candidate_id: str,
    *,
    raw_near: float,
    raw_medium: float,
    raw_far: float,
    norm_near: float,
    norm_medium: float,
    norm_far: float,
) -> bool:
    raw_ok = strict_dispersion_order(raw_near, raw_medium, raw_far)
    norm_ok = strict_dispersion_order(norm_near, norm_medium, norm_far)
    if candidate_id == "A_mean_edge_distance":
        return raw_ok
    if candidate_id == "B_mean_edge_distance_norm":
        return norm_ok
    if candidate_id == "C_raw_and_norm":
        return raw_ok and norm_ok
    raise ValueError(candidate_id)


def scale_stability_holds(
    candidate_id: str,
    *,
    raw_one_hop_medium: Mapping[str, float],
    norm_one_hop_far: Mapping[str, float],
) -> bool:
    a_ok = (
        raw_one_hop_medium["small"]
        == raw_one_hop_medium["medium"]
        == raw_one_hop_medium["large"]
    )
    b_ok = (
        norm_one_hop_far["small"]
        == norm_one_hop_far["medium"]
        == norm_one_hop_far["large"]
    )
    if candidate_id == "A_mean_edge_distance":
        return a_ok
    if candidate_id == "B_mean_edge_distance_norm":
        return b_ok
    if candidate_id == "C_raw_and_norm":
        return a_ok and b_ok
    raise ValueError(candidate_id)


def bin_ordering_holds(near: str, medium: str, far: str) -> bool:
    try:
        n_rank, m_rank, f_rank = _BIN_RANK[near], _BIN_RANK[medium], _BIN_RANK[far]
    except KeyError:
        return False
    return n_rank <= m_rank <= f_rank and n_rank < f_rank


def is_negative_adversarial_case(intended_edges: object) -> bool:
    return intended_edges == [] or intended_edges == ()


def bin_is_elevated(bin_label: str) -> bool:
    return bin_label in {"mid", "high"}


def _grid_tie_tuple(point: Mapping[str, Any]) -> tuple[float, ...]:
    if "T_raw_high" in point:
        return (
            float(point["T_raw_high"]),
            float(point["T_norm_high"]),
            float(point["T_raw_low"]),
            float(point["T_norm_low"]),
        )
    return (float(point["T_high"]), float(point["T_low"]))


def select_best_grid_point(
    points: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    """Pick one grid point. Does not look at calibration payloads."""
    eligible = [dict(point) for point in points if point.get("non_collapse") is True]
    if not eligible:
        return None

    def key(point: Mapping[str, Any]) -> tuple[Any, ...]:
        return (
            float(point["negative_adversarial_elevated_bin_rate"]),
            -float(point["bin_ordering_coverage"]),
            -float(point["format_consistency"]),
            *_grid_tie_tuple(point),
        )

    return min(eligible, key=key)


def select_best_candidate(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    """Compare A/B/C after each has one best grid point. Ignores sensor FP."""
    eligible = [dict(row) for row in rows if row.get("non_collapse") is True]
    if not eligible:
        return None
    order = {cid: index for index, cid in enumerate(CANDIDATES)}

    def key(row: Mapping[str, Any]) -> tuple[Any, ...]:
        return (
            -float(row["continuous_dispersion_ordering_coverage"]),
            -float(row["scale_stability"]),
            -float(row["format_consistency"]),
            order[str(row["id"])],
        )

    return min(eligible, key=key)


def metric_roles() -> dict[str, Any]:
    return {
        "sensor_level_diagnostic": {
            "edge_false_positive_rate": {
                "definition": (
                    "v1 extra-edge rate vs intended_edges; gold/intended_edges "
                    "are scorer-only and never sensor input"
                ),
                "used_in_threshold_grid_objective": False,
                "used_in_candidate_selection": False,
                "reason": "independent of A/B/C scores and of T_low/T_high",
                "sensor_revision_this_phase": False,
            },
            "true_dep_plus_misleading_suffix": {
                "in_negative_adversarial_elevated_bin_rate": False,
                "store_as_diagnostic": ["edge_precision", "extra_edge_count"],
            },
        },
        "candidate_level": {
            "used_in_threshold_grid_point_comparison": False,
            "measured_on": "continuous_score_before_threshold",
            "metrics": [
                {
                    "name": "continuous_dispersion_ordering_coverage",
                    "prefer": "higher",
                    "definition": (
                        "fraction of calibration primary cells where the "
                        "candidate score is strictly near < medium < far"
                    ),
                },
                {
                    "name": "scale_stability",
                    "prefer": "higher",
                    "definition": (
                        "one-hop medium (abs gap 3) keeps raw equal across "
                        "scales; one-hop far (endpoints) keeps norm equal "
                        "across scales"
                    ),
                },
            ],
        },
        "threshold_dependent": {
            "used_in_threshold_grid_point_comparison": True,
            "metrics": [
                {
                    "name": "bin_ordering_coverage",
                    "prefer": "higher",
                    "definition": (
                        "fraction of calibration primary cells where "
                        "bin(near) <= bin(medium) <= bin(far) and "
                        "bin(near) < bin(far)"
                    ),
                },
                {
                    "name": "negative_adversarial_elevated_bin_rate",
                    "prefer": "lower",
                    "definition": (
                        "among calibration adversarial surfaces with "
                        "intended_edges=[], fraction whose bin is mid or high"
                    ),
                    "excludes": "true_dep_plus_misleading_suffix",
                },
                {
                    "name": "format_consistency",
                    "prefer": "higher",
                    "definition": (
                        "fraction of calibration cells where key_value and "
                        "json receive the same low/mid/high bin"
                    ),
                },
                {
                    "name": "non_collapse",
                    "prefer": "eligible_only",
                    "threshold": COLLAPSE_FRACTION,
                    "definition": (
                        "no single bin may cover >= 0.95 of calibration "
                        "primary surfaces"
                    ),
                },
            ],
        },
    }


def candidate_level_v03() -> dict[str, Any]:
    return {
        "used_in_threshold_grid_point_comparison": False,
        "measured_on": "continuous_score_before_threshold",
        "no_new_scalar_for_C": True,
        "no_weighted_sum_of_raw_and_norm": True,
        "tolerance": "exact_equality_on_deterministic_synthetic_values",
        "do_not_add_tolerance_after_seeing_results": True,
        "continuous_dispersion_ordering_coverage": {
            "unit": "calibration_canonical_cell",
            "A_mean_edge_distance": {
                "continuous_score": "mean_edge_distance",
                "pass_if": "raw(near) < raw(medium) < raw(far)",
            },
            "B_mean_edge_distance_norm": {
                "continuous_score": "mean_edge_distance_norm",
                "pass_if": "norm(near) < norm(medium) < norm(far)",
            },
            "C_raw_and_norm": {
                "continuous_score": None,
                "pass_if": (
                    "raw(near) < raw(medium) < raw(far) AND "
                    "norm(near) < norm(medium) < norm(far)"
                ),
            },
        },
        "scale_stability": {
            "unit": "calibration_replica",
            "A_mean_edge_distance": {
                "contrast": "same_absolute_different_document_size",
                "pass_if": (
                    "one-hop medium mean_edge_distance identical across "
                    "small/medium/large"
                ),
            },
            "B_mean_edge_distance_norm": {
                "contrast": "same_relative_different_absolute",
                "pass_if": (
                    "one-hop far mean_edge_distance_norm identical across "
                    "small/medium/large"
                ),
            },
            "C_raw_and_norm": {
                "pass_if": "A_condition AND B_condition",
            },
        },
    }


def candidate_selection_v02() -> list[dict[str, Any]]:
    return [
        {
            "rank": 1,
            "name": "continuous_dispersion_ordering_coverage",
            "prefer": "higher",
            "threshold_dependent": False,
        },
        {
            "rank": 2,
            "name": "scale_stability",
            "prefer": "higher",
            "threshold_dependent": False,
        },
        {
            "rank": 3,
            "name": "format_consistency",
            "prefer": "higher",
            "threshold_dependent": True,
            "source": "best_grid_point",
        },
        {
            "rank": 4,
            "name": "non_collapse",
            "prefer": "eligible_only",
            "threshold_dependent": True,
            "source": "best_grid_point",
        },
        {
            "rank": 5,
            "name": "simplicity",
            "prefer": "A_then_B_then_C",
            "tie_order": list(CANDIDATES),
        },
    ]


def threshold_grid_objective_v02() -> dict[str, Any]:
    return {
        "eligibility": "non_collapse",
        "selection_order": [
            {
                "rank": 1,
                "name": "negative_adversarial_elevated_bin_rate",
                "prefer": "lower",
            },
            {"rank": 2, "name": "bin_ordering_coverage", "prefer": "higher"},
            {"rank": 3, "name": "format_consistency", "prefer": "higher"},
            {
                "rank": 4,
                "name": "complete_tie",
                "prefer": "smallest_T_high_then_smallest_T_low",
                "candidate_C": [
                    "T_raw_high",
                    "T_norm_high",
                    "T_raw_low",
                    "T_norm_low",
                ],
            },
        ],
        "applies_within": "each_candidate_separately",
        "do_not_extend_grid_after_seeing_calibration": True,
        "not_used": [
            "edge_false_positive_rate",
            "continuous_dispersion_ordering_coverage",
            "scale_stability",
            "n_signal",
            "INTEGRATE_rate",
        ],
    }


def candidate_protocol() -> dict[str, Any]:
    v01 = load_v01_freeze()
    return {
        "do_not_pick_by_n_signal": True,
        "do_not_pick_by_integrate_rate": True,
        "sensor_edge_fp_is_shared_diagnostic": True,
        "procedure": "pick_best_grid_point_per_candidate_then_compare",
        "candidates": list(v01["candidates"]["candidates"]),
        "selection_priority": candidate_selection_v02(),
        "do_not_add_candidates_after_seeing_calibration": True,
    }


def threshold_search_protocol() -> dict[str, Any]:
    v01 = load_v01_freeze()
    search = dict(v01["threshold_search"])
    search["objective"] = threshold_grid_objective_v02()
    search["not_objective"] = list(threshold_grid_objective_v02()["not_used"])
    search["do_not_extend_grid_after_seeing_calibration"] = True
    search["grids"] = v01["threshold_search"]["grids"]
    return search


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
        "revision": REVISION_V01,
        "evaluation_outcomes_open": False,
        "calibration_measured": False,
        "n_calibration": sum(1 for row in rows if row["split"] == "calibration"),
        "n_evaluation": sum(1 for row in rows if row["split"] == "evaluation"),
        "calibration_replicas": list(CALIBRATION_REPLICAS),
        "evaluation_replicas": list(EVALUATION_REPLICAS),
        "surfaces": rows,
    }


def load_v01_freeze() -> dict[str, Any]:
    if not V01_FREEZE_PATH.is_file():
        raise FileNotFoundError(f"v0.1 freeze missing: {V01_FREEZE_PATH}")
    return json.loads(V01_FREEZE_PATH.read_text(encoding="utf-8"))


def load_v02_freeze() -> dict[str, Any]:
    if not V02_FREEZE_PATH.is_file():
        raise FileNotFoundError(f"v0.2 freeze missing: {V02_FREEZE_PATH}")
    return json.loads(V02_FREEZE_PATH.read_text(encoding="utf-8"))


def freeze_manifest() -> dict[str, Any]:
    """Active freeze is v0.3. v0.2 generation/split/grids/threshold objective stay."""
    doc = json.loads(json.dumps(load_v02_freeze()))
    blocked = list(doc.get("blocked_reasons") or [])
    verdict = VERDICT_BLOCKED if blocked else VERDICT_FROZEN
    doc["schema"] = SCHEMA_ID
    doc["revision"] = REVISION
    doc["verdict"] = verdict
    doc["supersedes"] = REVISION_V02
    doc["supersession"] = {
        "previous": REVISION_V02,
        "previous_path": "benchmarks/spec/phase3f-routing-calibration-freeze-v0.2.json",
        "reason": "define C pre-threshold metrics and defer M1/M2 to Phase 3H",
        "v0_1_deleted": False,
        "v0_1_overwritten": False,
        "v0_2_deleted": False,
        "v0_2_overwritten": False,
        "unchanged": [
            "generation",
            "split",
            "surfaces",
            "adversarial_fixtures",
            "candidates",
            "grids",
            "threshold_objective",
        ],
        "changed": [
            "candidate_C_pre_threshold_metrics",
            "M1_M2_adoption_timing",
        ],
    }
    roles = dict(doc["metric_roles"])
    roles["candidate_level"] = candidate_level_v03()
    doc["metric_roles"] = roles
    maps = dict(doc["operator_maps"])
    maps["adoption"] = "phase3h_routing_semantics_freeze"
    maps["phase3g_selects"] = ["feature_candidate_A_B_C", "threshold_values"]
    maps["phase3g_does_not_select"] = [
        "M1_locality_for_integrate",
        "M2_spread_needs_gather",
    ]
    maps["not_selected_in_phase3g_because"] = (
        "M1/M2 do not change sensor score, threshold bin, or Phase 3G "
        "calibration metrics, so the current priority list cannot distinguish "
        "them from data"
    )
    maps["mapping_selection"] = (
        "deferred to phase3h_routing_semantics_freeze; "
        "Phase 3G does not choose M1 vs M2"
    )
    maps["rule_policy_unconnected"] = True
    doc["operator_maps"] = maps
    return doc


def _validate_shared(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
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


def _validate_v02(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID_V02:
        errs.append(f"bad schema: {doc.get('schema')!r}")
    if doc.get("revision") != REVISION_V02:
        errs.append(f"bad revision: {doc.get('revision')!r}")
    if doc.get("supersedes") != REVISION_V01:
        errs.append("v0.2 must supersede v0.1")
    supersession = dict(doc.get("supersession") or {})
    if supersession.get("v0_1_deleted") is not False:
        errs.append("v0.1 must not be recorded as deleted")
    if supersession.get("v0_1_overwritten") is not False:
        errs.append("v0.1 must not be recorded as overwritten")
    v01 = load_v01_freeze()
    for key in (
        "adversarial",
        "canonical_case_ids",
        "required_formats",
        "operator_maps",
        "n_primary_surfaces",
        "n_adversarial_surfaces",
        "generation",
        "distractor_counts",
        "shapes",
        "scale_levels",
        "dispersion_levels",
    ):
        if doc.get(key) != v01.get(key):
            errs.append(f"{key} drifted from v0.1")
    if (doc.get("candidates") or {}).get("candidates") != (v01.get("candidates") or {}).get(
        "candidates"
    ):
        errs.append("A/B/C candidate list drifted from v0.1")
    if (doc.get("threshold_search") or {}).get("grids") != (v01.get("threshold_search") or {}).get(
        "grids"
    ):
        errs.append("threshold grids drifted from v0.1")
    roles = dict(doc.get("metric_roles") or {})
    sensor = dict(roles.get("sensor_level_diagnostic") or {}).get("edge_false_positive_rate") or {}
    if dict(sensor).get("used_in_threshold_grid_objective") is not False:
        errs.append("edge_false_positive_rate must not drive the grid")
    if dict(sensor).get("used_in_candidate_selection") is not False:
        errs.append("edge_false_positive_rate must not pick A/B/C")
    cand_level = dict(roles.get("candidate_level") or {})
    if cand_level.get("used_in_threshold_grid_point_comparison") is not False:
        errs.append("continuous candidate metrics must not pick grid points")
    objective = dict((doc.get("threshold_search") or {}).get("objective") or {})
    names = [row.get("name") for row in list(objective.get("selection_order") or [])]
    if names[:3] != [
        "negative_adversarial_elevated_bin_rate",
        "bin_ordering_coverage",
        "format_consistency",
    ]:
        errs.append("grid selection order drifted")
    if "edge_false_positive_rate" in names or "continuous_dispersion_ordering_coverage" in names:
        errs.append("threshold-independent metric leaked into grid order")
    if objective.get("eligibility") != "non_collapse":
        errs.append("non_collapse must be grid eligibility")
    not_used = list(objective.get("not_used") or [])
    for banned in (
        "n_signal",
        "INTEGRATE_rate",
        "edge_false_positive_rate",
        "continuous_dispersion_ordering_coverage",
        "scale_stability",
    ):
        if banned not in not_used:
            errs.append(f"{banned} must be excluded from grid objective")
    priority = [
        row.get("name")
        for row in list((doc.get("candidates") or {}).get("selection_priority") or [])
    ]
    if priority[:2] != [
        "continuous_dispersion_ordering_coverage",
        "scale_stability",
    ]:
        errs.append("candidate selection order drifted")
    if priority and priority[0] == "adversarial_false_positive_rate":
        errs.append("v0.1 grid-confused FP must not rank candidates")
    return errs


def _validate_v03(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append(f"bad schema: {doc.get('schema')!r}")
    if doc.get("revision") != REVISION:
        errs.append(f"bad revision: {doc.get('revision')!r}")
    if doc.get("supersedes") != REVISION_V02:
        errs.append("v0.3 must supersede v0.2")
    supersession = dict(doc.get("supersession") or {})
    if supersession.get("v0_1_deleted") is not False:
        errs.append("v0.1 must not be recorded as deleted")
    if supersession.get("v0_1_overwritten") is not False:
        errs.append("v0.1 must not be recorded as overwritten")
    if supersession.get("v0_2_deleted") is not False:
        errs.append("v0.2 must not be recorded as deleted")
    if supersession.get("v0_2_overwritten") is not False:
        errs.append("v0.2 must not be recorded as overwritten")
    v02 = load_v02_freeze()
    for key in (
        "adversarial",
        "canonical_case_ids",
        "required_formats",
        "n_primary_surfaces",
        "n_adversarial_surfaces",
        "generation",
        "distractor_counts",
        "shapes",
        "scale_levels",
        "dispersion_levels",
        "candidates",
    ):
        if doc.get(key) != v02.get(key):
            errs.append(f"{key} drifted from v0.2")
    if (doc.get("threshold_search") or {}).get("grids") != (v02.get("threshold_search") or {}).get(
        "grids"
    ):
        errs.append("threshold grids drifted from v0.2")
    if (doc.get("threshold_search") or {}).get("objective") != (v02.get("threshold_search") or {}).get(
        "objective"
    ):
        errs.append("threshold objective drifted from v0.2")
    if (doc.get("operator_maps") or {}).get("candidates") != (v02.get("operator_maps") or {}).get(
        "candidates"
    ):
        errs.append("M1/M2 candidates drifted from v0.2")
    maps = dict(doc.get("operator_maps") or {})
    if maps.get("adoption") != "phase3h_routing_semantics_freeze":
        errs.append("M1/M2 adoption must be Phase 3H")
    if "M1_locality_for_integrate" not in list(maps.get("phase3g_does_not_select") or []):
        errs.append("Phase 3G must not select M1")
    if list(maps.get("phase3g_selects") or []) != [
        "feature_candidate_A_B_C",
        "threshold_values",
    ]:
        errs.append("Phase 3G may select only A/B/C and thresholds")
    cand_level = dict((doc.get("metric_roles") or {}).get("candidate_level") or {})
    if cand_level.get("no_new_scalar_for_C") is not True:
        errs.append("Candidate C must not get a new scalar score")
    if cand_level.get("no_weighted_sum_of_raw_and_norm") is not True:
        errs.append("must not invent a weighted raw+norm score")
    if cand_level.get("do_not_add_tolerance_after_seeing_results") is not True:
        errs.append("must not add scale_stability tolerance after seeing data")
    c_score = (
        dict(cand_level.get("continuous_dispersion_ordering_coverage") or {})
        .get("C_raw_and_norm")
        or {}
    )
    if dict(c_score).get("continuous_score") is not None:
        errs.append("Candidate C continuous_score must be null")
    return errs


def validate_phase3f_doc(doc: Mapping[str, Any]) -> list[str]:
    errs = _validate_shared(doc)
    rev = doc.get("revision")
    if rev == REVISION_V01:
        if doc.get("schema") != SCHEMA_ID_V01:
            errs.append(f"v0.1 bad schema: {doc.get('schema')!r}")
        return errs
    if rev == REVISION_V02:
        errs.extend(_validate_v02(doc))
        return errs
    if rev == REVISION:
        errs.extend(_validate_v03(doc))
        return errs
    errs.append(f"unknown freeze revision: {rev!r}")
    return errs


def write_freeze() -> Path:
    FREEZE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FREEZE_PATH.write_text(
        json.dumps(freeze_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return FREEZE_PATH
