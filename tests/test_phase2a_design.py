"""Phase 2A factorial benchmark design tests.

These tests validate benchmark construction only.  They do not import or run
BITE profiler/routing/operator code and therefore cannot tune the benchmark to
current routing behaviour.
"""

from __future__ import annotations

import json
from pathlib import Path

from bite_bench.phase2a import (
    PHASE2A_REVISION,
    SCALE_DISTRACTOR_COUNTS,
    Phase2ACell,
    design_cells,
    design_manifest,
    generate_phase2a_bundle,
    make_phase2a_case,
    surface_profiles,
)
from bite_ingestion.packet_contract import validate_units

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks" / "spec" / "phase2a-design.json"


def _cell(scale: str, dependency: str, replica: int) -> Phase2ACell:
    for cell in design_cells():
        if (
            cell.scale == scale
            and cell.dependency == dependency
            and cell.replica == replica
        ):
            return cell
    raise AssertionError((scale, dependency, replica))


def test_design_is_fixed_24_case_split() -> None:
    cells = design_cells()
    assert len(cells) == 24
    assert len(design_cells("calibration")) == 12
    assert len(design_cells("evaluation")) == 12
    assert {c.replica for c in design_cells("calibration")} == {0, 1}
    assert {c.replica for c in design_cells("evaluation")} == {2, 3}
    assert not (
        {c.case_id for c in design_cells("calibration")}
        & {c.case_id for c in design_cells("evaluation")}
    )


def test_surface_design_is_full_2x2x2_factorial() -> None:
    profiles = surface_profiles()
    assert len(profiles) == 8
    triples = {
        (p.structure, p.dispersion, p.redundancy)
        for p in profiles
    }
    assert len(triples) == 8


def test_static_manifest_matches_code_manifest() -> None:
    committed = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert committed == design_manifest()
    assert committed["status"] == "DESIGN_READY_NOT_FROZEN"
    assert committed["locks"]["token_length_matching_frozen"] is False


def test_phase2a_module_does_not_depend_on_bite_eval() -> None:
    source = (ROOT / "src" / "bite_bench" / "phase2a.py").read_text(encoding="utf-8")
    assert "from bite_eval" not in source
    assert "import bite_eval" not in source


def test_each_bundle_has_same_identity_across_eight_surfaces() -> None:
    bundle = generate_phase2a_bundle(_cell("medium", "chain3", 0))
    assert bundle["phase2a_revision"] == PHASE2A_REVISION
    assert len(bundle["surfaces"]) == 8
    canonical = bundle["canonical"]
    assert len(canonical["required_evidence_ids"]) == 3

    for surface in bundle["surfaces"].values():
        validate_units(surface["units"], document=surface["text"])
        assert surface["length_match_status"] == "not_frozen"
        assert bundle["facts_id"] not in surface["text"]


def test_dependency_axis_changes_required_evidence_without_changing_scale() -> None:
    direct = make_phase2a_case(_cell("medium", "direct", 0))
    chain = make_phase2a_case(_cell("medium", "chain3", 0))
    assert len(direct.required_evidence_ids) == 1
    assert len(chain.required_evidence_ids) == 3
    assert direct.meta["distractor_count"] == chain.meta["distractor_count"] == 32


def test_scale_axis_is_monotonic_and_declared() -> None:
    counts = []
    for scale in ("small", "medium", "large"):
        case = make_phase2a_case(_cell(scale, "direct", 0))
        counts.append(int(case.meta["distractor_count"]))
    assert counts == [8, 32, 96]
    assert counts == [
        SCALE_DISTRACTOR_COUNTS["small"],
        SCALE_DISTRACTOR_COUNTS["medium"],
        SCALE_DISTRACTOR_COUNTS["large"],
    ]


def test_redundancy_axis_repeats_only_non_gold_material() -> None:
    bundle = generate_phase2a_bundle(_cell("small", "direct", 0))
    low = bundle["surfaces"]["p2a_flat_clustered_low"]
    high = bundle["surfaces"]["p2a_flat_clustered_high"]
    required = set(bundle["canonical"]["required_evidence_ids"])

    assert len(high["units"]) > len(low["units"])
    for surface in (low, high):
        gold_occurrences = [
            u for u in surface["units"] if str(u.get("fact_id")) in required
        ]
        assert len(gold_occurrences) == len(required)
    assert high["char_len"] > low["char_len"]


def test_dispersion_axis_spreads_chain_evidence() -> None:
    bundle = generate_phase2a_bundle(_cell("medium", "chain3", 0))
    clustered = bundle["surfaces"]["p2a_flat_clustered_low"]
    dispersed = bundle["surfaces"]["p2a_flat_dispersed_low"]
    required = set(bundle["canonical"]["required_evidence_ids"])

    def spread(surface: dict) -> int:
        spans = [
            u["span"]
            for u in surface["units"]
            if str(u.get("fact_id")) in required
        ]
        return max(int(s["end"]) for s in spans) - min(int(s["start"]) for s in spans)

    assert spread(dispersed) > spread(clustered)


def test_structure_axis_changes_surface_without_changing_fact_ids() -> None:
    bundle = generate_phase2a_bundle(_cell("small", "direct", 1))
    flat = bundle["surfaces"]["p2a_flat_clustered_low"]
    nested = bundle["surfaces"]["p2a_nested_clustered_low"]
    assert flat["surface_sha256"] != nested["surface_sha256"]
    assert {u["fact_id"] for u in flat["units"]} == {
        u["fact_id"] for u in nested["units"]
    }


def test_no_route_expectation_or_architecture_claim() -> None:
    bundle = generate_phase2a_bundle(_cell("large", "chain3", 2))
    assert bundle["notes"]["route_expectation"] is None
    assert bundle["notes"]["architecture_claim"] is False
    assert "pending" in bundle["notes"]["token_length_matching"]
