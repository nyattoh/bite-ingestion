"""Phase 2A factorial benchmark design.

This module intentionally does not import profiler, routing, threshold, or
operator code.  The benchmark factors are defined first; BITE behaviour is a
later measurement.

Canonical axes:
- scale: small / medium / large (number of neutral distractor facts)
- dependency: direct / chain3

Surface axes (full 2 x 2 x 2 factorial):
- structure: flat / nested
- dispersion: clustered / dispersed
- redundancy: low / high

The evaluation split is assigned up front but Phase 2A does not run routing on
it.  No route labels or expected BITE outcomes are stored in the cases.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from itertools import product
from typing import Any, Literal

from bite_ingestion.packet_contract import make_unit, validate_units

from .models import CanonicalCase, Fact

PHASE2A_REVISION = "phase2a-factorial-v0.1"

Scale = Literal["small", "medium", "large"]
Dependency = Literal["direct", "chain3"]
Structure = Literal["flat", "nested"]
Dispersion = Literal["clustered", "dispersed"]
Redundancy = Literal["low", "high"]

SCALE_DISTRACTOR_COUNTS: dict[Scale, int] = {
    "small": 8,
    "medium": 32,
    "large": 96,
}
DEPENDENCY_LEVELS: tuple[Dependency, ...] = ("direct", "chain3")
REPLICAS: tuple[int, ...] = (0, 1, 2, 3)
CALIBRATION_REPLICAS: tuple[int, ...] = (0, 1)
EVALUATION_REPLICAS: tuple[int, ...] = (2, 3)

SURFACE_STRUCTURES: tuple[Structure, ...] = ("flat", "nested")
SURFACE_DISPERSIONS: tuple[Dispersion, ...] = ("clustered", "dispersed")
SURFACE_REDUNDANCIES: tuple[Redundancy, ...] = ("low", "high")


@dataclass(frozen=True)
class Phase2ACell:
    scale: Scale
    dependency: Dependency
    replica: int
    split: str

    @property
    def case_id(self) -> str:
        return f"p2a-{self.scale}-{self.dependency}-r{self.replica}"


@dataclass(frozen=True)
class Phase2ASurfaceProfile:
    structure: Structure
    dispersion: Dispersion
    redundancy: Redundancy

    @property
    def family(self) -> str:
        return f"p2a_{self.structure}_{self.dispersion}_{self.redundancy}"


def _split_for_replica(replica: int) -> str:
    if replica in CALIBRATION_REPLICAS:
        return "calibration"
    if replica in EVALUATION_REPLICAS:
        return "evaluation"
    return "unassigned"


def design_cells(split: str | None = None) -> tuple[Phase2ACell, ...]:
    """Return the fixed 24-cell canonical design."""
    cells = tuple(
        Phase2ACell(
            scale=scale,
            dependency=dependency,
            replica=replica,
            split=_split_for_replica(replica),
        )
        for scale, dependency, replica in product(
            SCALE_DISTRACTOR_COUNTS,
            DEPENDENCY_LEVELS,
            REPLICAS,
        )
    )
    if split is None:
        return cells
    if split not in {"calibration", "evaluation"}:
        raise ValueError(f"unknown split: {split!r}")
    return tuple(cell for cell in cells if cell.split == split)


def surface_profiles() -> tuple[Phase2ASurfaceProfile, ...]:
    """Return the full 2x2x2 morphology factorial."""
    return tuple(
        Phase2ASurfaceProfile(
            structure=structure,
            dispersion=dispersion,
            redundancy=redundancy,
        )
        for structure, dispersion, redundancy in product(
            SURFACE_STRUCTURES,
            SURFACE_DISPERSIONS,
            SURFACE_REDUNDANCIES,
        )
    )


def _required_facts(cell: Phase2ACell) -> tuple[tuple[Fact, ...], str, str, tuple[str, ...]]:
    stem = cell.case_id.replace("-", "_")
    answer = f"ANS_{stem}"

    if cell.dependency == "direct":
        target = f"asset_{stem}"
        record = f"record_{stem}"
        f1 = Fact(
            fact_id=f"{cell.case_id}-gold-1",
            key=f"lookup_for_{target}",
            value=record,
        )
        f2 = Fact(
            fact_id=f"{cell.case_id}-gold-2",
            key=f"value_for_{record}",
            value=answer,
        )
        question = f"What value is recorded for {target}?"
        return (f1, f2), question, answer, (f1.fact_id, f2.fact_id)

    start = f"asset_{stem}"
    bridge = f"bridge_{stem}"
    target = f"target_{stem}"
    f1 = Fact(
        fact_id=f"{cell.case_id}-gold-1",
        key=f"next_for_{start}",
        value=bridge,
    )
    f2 = Fact(
        fact_id=f"{cell.case_id}-gold-2",
        key=f"next_for_{bridge}",
        value=target,
    )
    f3 = Fact(
        fact_id=f"{cell.case_id}-gold-3",
        key=f"value_for_{target}",
        value=answer,
    )
    question = (
        f"Starting at {start}, follow two next_for links and report "
        "the value_for the final target."
    )
    return (f1, f2, f3), question, answer, (f1.fact_id, f2.fact_id, f3.fact_id)


def make_phase2a_case(cell: Phase2ACell) -> CanonicalCase:
    """Create one canonical case without consulting any BITE routing code."""
    required, question, answer, required_ids = _required_facts(cell)
    n_distractors = SCALE_DISTRACTOR_COUNTS[cell.scale]
    distractors = tuple(
        Fact(
            fact_id=f"{cell.case_id}-d{i:03d}",
            key=f"neutral_key_{cell.replica}_{i:03d}",
            value=f"neutral_value_{cell.scale}_{cell.dependency}_{i:03d}",
        )
        for i in range(n_distractors)
    )
    facts = required + distractors
    return CanonicalCase(
        case_id=cell.case_id,
        question=question,
        answer=answer,
        required_evidence_ids=required_ids,
        facts=facts,
        task_family="phase2a_factorial",
        meta={
            "synthetic": True,
            "split": cell.split,
            "phase2a_revision": PHASE2A_REVISION,
            "scale": cell.scale,
            "dependency": cell.dependency,
            "replica": cell.replica,
            "distractor_count": n_distractors,
        },
    )


def _ordered_facts(
    case: CanonicalCase,
    *,
    dispersion: Dispersion,
) -> list[Fact]:
    required_ids = set(case.required_evidence_ids)
    required = [f for f in case.facts if f.fact_id in required_ids]
    distractors = [f for f in case.facts if f.fact_id not in required_ids]

    if dispersion == "clustered" or len(required) <= 1:
        return required + distractors

    # Spread required facts across the document at deterministic quantiles.
    slots = len(required)
    out: list[Fact] = []
    cursor = 0
    for i, fact in enumerate(required):
        target = round(i * len(distractors) / max(1, slots - 1))
        out.extend(distractors[cursor:target])
        out.append(fact)
        cursor = target
    out.extend(distractors[cursor:])
    return out


def _fact_text(fact: Fact, *, structure: Structure) -> str:
    if structure == "flat":
        return f"{fact.key}={fact.value}"
    payload = {"record": {"key": fact.key, "value": fact.value}}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _render_surface(
    case: CanonicalCase,
    profile: Phase2ASurfaceProfile,
) -> dict[str, Any]:
    ordered = _ordered_facts(case, dispersion=profile.dispersion)
    required_ids = set(case.required_evidence_ids)
    occurrences: list[Fact] = []

    for fact in ordered:
        occurrences.append(fact)
        # Redundancy is manipulated only through non-gold material.  Required
        # evidence occurs once so answer/evidence identity does not change.
        if profile.redundancy == "high" and fact.fact_id not in required_ids:
            occurrences.extend((fact, fact))

    parts: list[str] = []
    units: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    pos = 0
    source_uri = f"bitebench://{case.case_id}/{profile.family}"
    renderer_id = f"{profile.family}@{PHASE2A_REVISION}"

    for i, fact in enumerate(occurrences):
        if i:
            sep = "\n"
            parts.append(sep)
            pos += len(sep)
        text = _fact_text(fact, structure=profile.structure)
        start = pos
        end = start + len(text)
        parts.append(text)
        pos = end

        n = seen.get(fact.fact_id, 0)
        seen[fact.fact_id] = n + 1
        uid = fact.fact_id if n == 0 else f"{fact.fact_id}#{n}"
        unit = make_unit(
            unit_id=uid,
            text=text,
            start=start,
            end=end,
            source_uri=source_uri,
            renderer_id=renderer_id,
        )
        unit["fact_id"] = fact.fact_id
        unit["is_required_evidence"] = fact.fact_id in required_ids
        units.append(unit)

    document = "".join(parts)
    validate_units(units, document=document)
    return {
        "renderer_id": renderer_id,
        "family": profile.family,
        "text": document,
        "char_len": len(document),
        "surface_sha256": hashlib.sha256(document.encode("utf-8")).hexdigest(),
        "units": units,
        "morphology_factors": {
            "structure": profile.structure,
            "dispersion": profile.dispersion,
            "redundancy": profile.redundancy,
        },
        "length_match_status": "not_frozen",
    }


def _assert_no_leakage(case: CanonicalCase, surfaces: dict[str, dict[str, Any]]) -> None:
    required_ids = set(case.required_evidence_ids)
    for family, surface in surfaces.items():
        text = str(surface["text"])
        if case.question in text:
            raise ValueError(f"{family}: question leaked into surface")
        if case.case_id in text:
            raise ValueError(f"{family}: case id leaked into surface")
        for fact_id in required_ids:
            if fact_id in text:
                raise ValueError(f"{family}: evidence id leaked into surface: {fact_id}")

        answer_positions: list[int] = []
        idx = text.find(case.answer)
        while idx != -1:
            answer_positions.append(idx)
            idx = text.find(case.answer, idx + 1)

        required_spans = [
            (int(u["span"]["start"]), int(u["span"]["end"]))
            for u in surface["units"]
            if str(u.get("fact_id")) in required_ids
        ]
        for start in answer_positions:
            stop = start + len(case.answer)
            if not any(a <= start and stop <= b for a, b in required_spans):
                raise ValueError(f"{family}: answer occurs outside required evidence")


def generate_phase2a_bundle(cell: Phase2ACell) -> dict[str, Any]:
    """Render all eight morphology cells for one canonical case."""
    case = make_phase2a_case(cell)
    surfaces = {
        profile.family: _render_surface(case, profile)
        for profile in surface_profiles()
    }
    _assert_no_leakage(case, surfaces)
    return {
        "schema": "bitebench-phase2a-bundle/v0.1",
        "phase2a_revision": PHASE2A_REVISION,
        "benchmark_split": cell.split,
        "facts_id": case.case_id,
        "identity_sha256": case.identity_hash(),
        "canonical": case.identity_payload(),
        "design_axes": {
            "scale": cell.scale,
            "dependency": cell.dependency,
            "replica": cell.replica,
        },
        "surfaces": surfaces,
        "notes": {
            "route_expectation": None,
            "architecture_claim": False,
            "token_length_matching": "pending Phase 2B/2C; do not compare outcomes yet",
        },
    }


def design_manifest() -> dict[str, Any]:
    """Machine-readable design declaration, independent of observed routing."""
    cells = design_cells()
    return {
        "schema": "bitebench-phase2a-design/v0.1",
        "revision": PHASE2A_REVISION,
        "purpose": (
            "factorial benchmark generation independent of current BITE "
            "profiler/routing thresholds"
        ),
        "canonical_axes": {
            "scale": {
                "levels": list(SCALE_DISTRACTOR_COUNTS),
                "distractor_counts": dict(SCALE_DISTRACTOR_COUNTS),
            },
            "dependency": {"levels": list(DEPENDENCY_LEVELS)},
            "replica": {
                "levels": list(REPLICAS),
                "calibration": list(CALIBRATION_REPLICAS),
                "evaluation": list(EVALUATION_REPLICAS),
            },
        },
        "surface_axes": {
            "structure": list(SURFACE_STRUCTURES),
            "dispersion": list(SURFACE_DISPERSIONS),
            "redundancy": list(SURFACE_REDUNDANCIES),
            "full_factorial": True,
            "n_profiles": len(surface_profiles()),
        },
        "counts": {
            "canonical_cases": len(cells),
            "calibration_cases": len(design_cells("calibration")),
            "evaluation_cases": len(design_cells("evaluation")),
            "surfaces_per_case": len(surface_profiles()),
            "total_surfaces": len(cells) * len(surface_profiles()),
        },
        "case_ids": {
            "calibration": [c.case_id for c in design_cells("calibration")],
            "evaluation": [c.case_id for c in design_cells("evaluation")],
        },
        "locks": {
            "no_profiler_import": True,
            "no_routing_import": True,
            "no_threshold_import": True,
            "no_expected_route_labels": True,
            "evaluation_not_for_rule_tuning": True,
            "token_length_matching_frozen": False,
        },
        "status": "DESIGN_READY_NOT_FROZEN",
    }


__all__ = [
    "CALIBRATION_REPLICAS",
    "DEPENDENCY_LEVELS",
    "EVALUATION_REPLICAS",
    "PHASE2A_REVISION",
    "REPLICAS",
    "SCALE_DISTRACTOR_COUNTS",
    "SURFACE_DISPERSIONS",
    "SURFACE_REDUNDANCIES",
    "SURFACE_STRUCTURES",
    "Phase2ACell",
    "Phase2ASurfaceProfile",
    "design_cells",
    "design_manifest",
    "generate_phase2a_bundle",
    "make_phase2a_case",
    "surface_profiles",
]
