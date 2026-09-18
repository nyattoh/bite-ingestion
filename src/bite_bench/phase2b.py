"""Phase 2B calibration-only length control.

Measures whether Phase 2A morphology contrasts are naturally token-length
matched under the frozen Phase 1C criterion.  Does not run profiler, routing,
or operators.  Evaluation/holdout is sealed.
"""

from __future__ import annotations

import json
import statistics
from collections.abc import Mapping, Sequence
from typing import Any

from bite_bench.phase2a import (
    PHASE2A_REVISION,
    Phase2ACell,
    design_cells,
    surface_profiles,
)
from bite_bench.token_match import (
    TOKEN_MATCH_MAX_ABS_DELTA,
    TOKEN_MATCH_MAX_RELATIVE_DELTA,
    relative_token_delta,
    token_length_match,
)

SCHEMA_ID = "bitebench-phase2b-length-control/v0.1"
BASE_MAIN_SHA = "dce759efbb94ae941a86c3358b1b717da3224c14"
VERDICT_READY = "PHASE2B_LENGTH_CONTROL_READY"
VERDICT_PARTIAL = "PHASE2B_LENGTH_CONTROL_PARTIAL"
VERDICT_BLOCKED = "PHASE2B_BLOCKED"
VERDICTS = (VERDICT_READY, VERDICT_PARTIAL, VERDICT_BLOCKED)

AXIS_LEVELS: dict[str, tuple[str, str]] = {
    "structure": ("flat", "nested"),
    "dispersion": ("clustered", "dispersed"),
    "redundancy": ("low", "high"),
}

#: Inspection-only wider bands. Never mixed into the Phase 1C official result
#: and never applied to evaluation.
CANDIDATE_ALTERNATIVE_TOLERANCES: tuple[dict[str, Any], ...] = (
    {
        "label": "abs10_rel10pct",
        "max_abs_delta": 10,
        "max_relative_delta": 0.10,
        "note": "calibration inspection only; not a freeze; not applied to evaluation",
    },
    {
        "label": "abs25_rel15pct",
        "max_abs_delta": 25,
        "max_relative_delta": 0.15,
        "note": "calibration inspection only; not a freeze; not applied to evaluation",
    },
)


def require_calibration(split: str) -> None:
    """Fail closed before any evaluation surface is generated or counted."""
    if split != "calibration":
        raise ValueError(
            "Phase 2B is calibration-only; evaluation/holdout is sealed "
            f"(got {split!r})"
        )


def evaluation_case_ids() -> frozenset[str]:
    return frozenset(cell.case_id for cell in design_cells("evaluation"))


def calibration_cells() -> tuple[Phase2ACell, ...]:
    return design_cells("calibration")


def _required_spread(surface: Mapping[str, Any], required_ids: set[str]) -> int:
    spans = [
        u["span"]
        for u in surface["units"]
        if str(u.get("fact_id")) in required_ids
    ]
    if not spans:
        return 0
    return max(int(s["end"]) for s in spans) - min(int(s["start"]) for s in spans)


def _non_gold_occurrences(surface: Mapping[str, Any], required_ids: set[str]) -> int:
    return sum(1 for u in surface["units"] if str(u.get("fact_id")) not in required_ids)


def morphology_coverage(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Check declared Phase 2A factors move on the surface. No BITE features."""
    required = {str(x) for x in bundle["canonical"]["required_evidence_ids"]}
    identity = str(bundle["identity_sha256"])
    violations: list[str] = []
    structure_hash_diffs = 0
    dispersion_spread_diffs = 0
    redundancy_count_diffs = 0

    surfaces = bundle["surfaces"]
    required_sets = [
        {
            str(u.get("fact_id"))
            for u in surface["units"]
            if u.get("is_required_evidence")
        }
        for surface in surfaces.values()
    ]
    identity_stable = bool(required_sets) and all(ids == required for ids in required_sets)
    if not identity_stable:
        violations.append(
            f"{bundle['facts_id']}: canonical required evidence changed across surfaces"
        )

    for other_disp in ("clustered", "dispersed"):
        for other_red in ("low", "high"):
            flat = surfaces[f"p2a_flat_{other_disp}_{other_red}"]
            nested = surfaces[f"p2a_nested_{other_disp}_{other_red}"]
            if flat["surface_sha256"] != nested["surface_sha256"]:
                structure_hash_diffs += 1
            else:
                violations.append(
                    f"{bundle['facts_id']}: structure hash identical at "
                    f"{other_disp}/{other_red}"
                )
    for other_struct in ("flat", "nested"):
        for other_red in ("low", "high"):
            clustered = surfaces[f"p2a_{other_struct}_clustered_{other_red}"]
            dispersed = surfaces[f"p2a_{other_struct}_dispersed_{other_red}"]
            if _required_spread(dispersed, required) > _required_spread(clustered, required):
                dispersion_spread_diffs += 1
            else:
                violations.append(
                    f"{bundle['facts_id']}: dispersion did not increase required "
                    f"span distance at {other_struct}/{other_red}"
                )
    for other_struct in ("flat", "nested"):
        for other_disp in ("clustered", "dispersed"):
            low = surfaces[f"p2a_{other_struct}_{other_disp}_low"]
            high = surfaces[f"p2a_{other_struct}_{other_disp}_high"]
            if _non_gold_occurrences(high, required) > _non_gold_occurrences(low, required):
                redundancy_count_diffs += 1
            else:
                violations.append(
                    f"{bundle['facts_id']}: redundancy did not increase non-gold "
                    f"repetition at {other_struct}/{other_disp}"
                )

    return {
        "facts_id": bundle["facts_id"],
        "canonical_identity_sha256": identity,
        "identity_stable": identity_stable,
        "structure_hash_diffs": structure_hash_diffs,
        "dispersion_spread_diffs": dispersion_spread_diffs,
        "redundancy_count_diffs": redundancy_count_diffs,
        "ok": not violations,
        "violations": violations,
    }


def paired_contrasts(surfaces: Mapping[str, Mapping[str, Any]], axis: str) -> list[dict[str, Any]]:
    """Within-case paired contrast: one axis differs, the other two stay fixed."""
    left_level, right_level = AXIS_LEVELS[axis]
    others = [name for name in AXIS_LEVELS if name != axis]
    rows: list[dict[str, Any]] = []
    for profile in surface_profiles():
        factors: dict[str, str] = {
            "structure": profile.structure,
            "dispersion": profile.dispersion,
            "redundancy": profile.redundancy,
        }
        if factors[axis] != left_level:
            continue
        right_factors = dict(factors)
        right_factors[axis] = right_level
        left_family = (
            f"p2a_{factors['structure']}_{factors['dispersion']}_{factors['redundancy']}"
        )
        right_family = (
            f"p2a_{right_factors['structure']}_{right_factors['dispersion']}_"
            f"{right_factors['redundancy']}"
        )
        left = surfaces[left_family]
        right = surfaces[right_family]
        rows.append(
            {
                "axis": axis,
                "held_fixed": {name: factors[name] for name in others},
                "left_level": left_level,
                "right_level": right_level,
                "left_family": left_family,
                "right_family": right_family,
                "left_char_len": int(left["char_len"]),
                "right_char_len": int(right["char_len"]),
            }
        )
    return rows


def _match_with(abs_max: int, rel_max: float, left: int, right: int) -> bool:
    return abs(left - right) <= abs_max and relative_token_delta(left, right) <= rel_max


def attach_token_counts(
    contrast: Mapping[str, Any],
    token_by_family: Mapping[str, int],
) -> dict[str, Any]:
    left_tokens = int(token_by_family[str(contrast["left_family"])])
    right_tokens = int(token_by_family[str(contrast["right_family"])])
    abs_delta = abs(left_tokens - right_tokens)
    rel_delta = relative_token_delta(left_tokens, right_tokens)
    row = dict(contrast)
    row.update(
        {
            "left_tokens": left_tokens,
            "right_tokens": right_tokens,
            "abs_delta": abs_delta,
            "relative_delta": rel_delta,
            "phase1c_length_matched": token_length_match(left_tokens, right_tokens),
        }
    )
    return row


def _rate(n_matched: int, n: int) -> float:
    return n_matched / n if n else 0.0


def summarize_contrasts(contrasts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    n = len(contrasts)
    matched = [c for c in contrasts if c.get("phase1c_length_matched")]
    abs_d = [int(c["abs_delta"]) for c in contrasts]
    rel_d = [float(c["relative_delta"]) for c in contrasts]

    def _group(key: str) -> dict[str, Any]:
        buckets: dict[str, list[Mapping[str, Any]]] = {}
        for row in contrasts:
            buckets.setdefault(str(row[key]), []).append(row)
        return {
            name: {
                "n_contrasts": len(rows),
                "n_matched": sum(1 for r in rows if r.get("phase1c_length_matched")),
                "match_rate": _rate(
                    sum(1 for r in rows if r.get("phase1c_length_matched")),
                    len(rows),
                ),
            }
            for name, rows in sorted(buckets.items())
        }

    return {
        "n_contrasts": n,
        "n_matched": len(matched),
        "match_rate": _rate(len(matched), n),
        "mean_abs_delta": statistics.fmean(abs_d) if abs_d else None,
        "median_abs_delta": statistics.median(abs_d) if abs_d else None,
        "max_abs_delta": max(abs_d) if abs_d else None,
        "mean_relative_delta": statistics.fmean(rel_d) if rel_d else None,
        "median_relative_delta": statistics.median(rel_d) if rel_d else None,
        "max_relative_delta": max(rel_d) if rel_d else None,
        "by_scale": _group("scale"),
        "by_dependency": _group("dependency"),
    }


def candidate_alternative_report(contrasts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Separate from the Phase 1C official table. Calibration inspection only."""
    out: list[dict[str, Any]] = []
    by_axis: dict[str, list[Mapping[str, Any]]] = {}
    for row in contrasts:
        by_axis.setdefault(str(row["axis"]), []).append(row)
    for spec in CANDIDATE_ALTERNATIVE_TOLERANCES:
        abs_max = int(spec["max_abs_delta"])
        rel_max = float(spec["max_relative_delta"])
        per_axis: dict[str, Any] = {}
        for axis, rows in sorted(by_axis.items()):
            n = len(rows)
            n_ok = sum(
                1
                for r in rows
                if _match_with(abs_max, rel_max, int(r["left_tokens"]), int(r["right_tokens"]))
            )
            per_axis[axis] = {
                "n_contrasts": n,
                "n_matched": n_ok,
                "match_rate": _rate(n_ok, n),
            }
        out.append({**spec, "by_axis": per_axis})
    return out


def decide_verdict(axis_summaries: Mapping[str, Mapping[str, Any]]) -> str:
    """Offline construction result. Not a BITE win/loss claim."""
    rates = {
        axis: float(summary.get("match_rate") or 0.0)
        for axis, summary in axis_summaries.items()
    }
    if not rates:
        return VERDICT_BLOCKED
    usable = [axis for axis, rate in rates.items() if rate > 0.0]
    if len(usable) == len(AXIS_LEVELS) and min(rates.values()) >= 0.5:
        return VERDICT_READY
    return VERDICT_PARTIAL


def build_matrix(
    *,
    counted_cases: Sequence[Mapping[str, Any]],
    tokenizer_reference: Mapping[str, Any],
    blocked_reasons: Sequence[str] | None = None,
    prompt_contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    blocked = list(blocked_reasons or [])
    eval_ids = evaluation_case_ids()
    surfaces: list[dict[str, Any]] = []
    contrasts: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []

    for case in counted_cases:
        case_id = str(case["case_id"])
        if case_id in eval_ids or str(case.get("split")) == "evaluation":
            blocked.append(f"evaluation case leaked into Phase 2B: {case_id}")
            continue
        if case.get("replica") not in (0, 1):
            blocked.append(f"non-calibration replica in Phase 2B: {case_id}")
            continue
        token_by_family = {
            str(row["family"]): int(row["prompt_tokens"]) for row in case["surfaces"]
        }
        for row in case["surfaces"]:
            surfaces.append(
                {
                    "case_id": case_id,
                    "scale": case["scale"],
                    "dependency": case["dependency"],
                    "replica": case["replica"],
                    "structure": row["structure"],
                    "dispersion": row["dispersion"],
                    "redundancy": row["redundancy"],
                    "family": row["family"],
                    "char_len": row["char_len"],
                    "prompt_tokens": row["prompt_tokens"],
                    "surface_sha256": row["surface_sha256"],
                }
            )
        coverage.append(dict(case["morphology_coverage"]))
        for axis in AXIS_LEVELS:
            for contrast in paired_contrasts(
                {str(row["family"]): row for row in case["surfaces"]},
                axis,
            ):
                attached = attach_token_counts(contrast, token_by_family)
                attached["case_id"] = case_id
                attached["scale"] = case["scale"]
                attached["dependency"] = case["dependency"]
                attached["replica"] = case["replica"]
                contrasts.append(attached)

    if any(not c.get("ok") for c in coverage):
        blocked.append("morphology coverage failed on a calibration case")

    axis_summaries = {
        axis: summarize_contrasts([c for c in contrasts if c["axis"] == axis])
        for axis in AXIS_LEVELS
    }
    if blocked:
        verdict = VERDICT_BLOCKED
    else:
        verdict = decide_verdict(axis_summaries)

    leaked = sorted({s["case_id"] for s in surfaces} & set(eval_ids))
    if leaked:
        blocked.append(f"evaluation ids present: {leaked}")
        verdict = VERDICT_BLOCKED

    return {
        "schema": SCHEMA_ID,
        "offline": True,
        "paid_api": False,
        "research_conclusion": False,
        "phase2a_revision": PHASE2A_REVISION,
        "base_main_sha": BASE_MAIN_SHA,
        "split": "calibration",
        "evaluation_sealed": True,
        "padding": False,
        "purpose": (
            "calibration-only natural length-control measurement; "
            "not a BITE performance result"
        ),
        "tokenizer_reference": dict(tokenizer_reference),
        "prompt_contract": dict(prompt_contract)
        if prompt_contract is not None
        else {
            "source": "scripts/measure_phase1c_token_lengths.py",
            "note": "same system + user wrapper + generation prompt as Phase 1C",
        },
        "phase1c_match_rule": {
            "max_abs_delta": TOKEN_MATCH_MAX_ABS_DELTA,
            "max_relative_delta": TOKEN_MATCH_MAX_RELATIVE_DELTA,
            "no_padding": True,
            "applied_to": "calibration only",
        },
        "blocked_reasons": blocked,
        "verdict": verdict,
        "n_canonical_cases": len(counted_cases),
        "n_surfaces": len(surfaces),
        "surfaces": surfaces,
        "contrasts": contrasts,
        "axis_summaries": axis_summaries,
        "morphology_coverage": coverage,
        "candidate_alternative_tolerance": candidate_alternative_report(contrasts),
    }


def render_length_control_md(doc: Mapping[str, Any]) -> str:
    summaries = dict(doc.get("axis_summaries") or {})
    lines = [
        "# Phase 2B calibration length control",
        "",
        "BITE の性能評価ではない。profiler / routing / operator は走らせていない。",
        "evaluation/holdout は封印。padding なし。",
        "",
        f"- base main SHA: `{doc.get('base_main_sha')}`",
        f"- verdict: **{doc.get('verdict')}**",
        f"- paid_api: {doc.get('paid_api')}",
        (
            f"- Phase 1C criterion: abs <= {TOKEN_MATCH_MAX_ABS_DELTA}, "
            f"rel <= {TOKEN_MATCH_MAX_RELATIVE_DELTA}, no padding"
        ),
        f"- calibration cases: {doc.get('n_canonical_cases')} surfaces: {doc.get('n_surfaces')}",
        "",
        "## Axis summaries (Phase 1C criterion only)",
        "",
        "| axis | n | matched | match rate | mean abs | median abs | max abs |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for axis in AXIS_LEVELS:
        s = dict(summaries.get(axis) or {})
        lines.append(
            f"| {axis} | {s.get('n_contrasts')} | {s.get('n_matched')} | "
            f"{s.get('match_rate')} | {s.get('mean_abs_delta')} | "
            f"{s.get('median_abs_delta')} | {s.get('max_abs_delta')} |"
        )
    lines += ["", "### Scale / dependency match rates", ""]
    for axis in AXIS_LEVELS:
        s = dict(summaries.get(axis) or {})
        lines.append(f"**{axis}**")
        lines.append("")
        for label, bucket in (("scale", "by_scale"), ("dependency", "by_dependency")):
            rows = dict(s.get(bucket) or {})
            bits = [
                f"{name}: {row.get('n_matched')}/{row.get('n_contrasts')} "
                f"({row.get('match_rate')})"
                for name, row in rows.items()
            ]
            lines.append(f"- {label}: " + "; ".join(bits))
        lines.append("")

    alts = list(doc.get("candidate_alternative_tolerance") or [])
    lines += [
        "## Candidate alternative tolerances (not mixed, not frozen, not evaluation)",
        "",
    ]
    if not alts:
        lines += ["なし", ""]
    for spec in alts:
        lines.append(
            f"- `{spec.get('label')}` abs<={spec.get('max_abs_delta')} "
            f"rel<={spec.get('max_relative_delta')}: {spec.get('note')}"
        )
        by_axis = dict(spec.get("by_axis") or {})
        for axis, row in by_axis.items():
            lines.append(
                f"  - {axis}: {row.get('n_matched')}/{row.get('n_contrasts')} "
                f"({row.get('match_rate')})"
            )
        lines.append("")

    cov = list(doc.get("morphology_coverage") or [])
    n_ok = sum(1 for c in cov if c.get("ok"))
    lines += [
        "## Morphology coverage (not BITE profiler features)",
        "",
        f"- calibration cases checked: {len(cov)}; ok: {n_ok}",
        "",
        "## What we wanted to know",
        "",
        "- dispersion: can it stay near equal token length?",
        f"  match_rate={ (summaries.get('dispersion') or {}).get('match_rate') }",
        "- structure: can it match naturally?",
        f"  match_rate={ (summaries.get('structure') or {}).get('match_rate') }",
        "- redundancy: separable from length, or covariant?",
        f"  match_rate={ (summaries.get('redundancy') or {}).get('match_rate') }",
        "",
    ]
    blocked = list(doc.get("blocked_reasons") or [])
    if blocked:
        lines += ["## BLOCKED reasons", ""]
        for reason in blocked:
            lines.append(f"- {reason}")
        lines.append("")
    return "\n".join(lines)


def validate_phase2b_doc(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("paid_api") is not False:
        errs.append("paid_api must be false")
    if doc.get("schema") != SCHEMA_ID:
        errs.append(f"bad schema id: {doc.get('schema')!r}")
    if doc.get("split") != "calibration":
        errs.append("split must be calibration")
    if doc.get("evaluation_sealed") is not True:
        errs.append("evaluation_sealed must be true")
    if doc.get("padding") is not False:
        errs.append("padding must be false")
    if doc.get("research_conclusion") is not False:
        errs.append("research_conclusion must be false")
    if doc.get("verdict") not in VERDICTS:
        errs.append(f"bad verdict: {doc.get('verdict')!r}")
    eval_ids = evaluation_case_ids()
    blob = json.dumps(doc, sort_keys=True)
    for case_id in sorted(eval_ids):
        if case_id in blob:
            errs.append(f"evaluation case id leaked: {case_id}")
    for row in list(doc.get("surfaces") or []) + list(doc.get("contrasts") or []):
        if not isinstance(row, Mapping):
            continue
        cid = str(row.get("case_id"))
        if cid in eval_ids:
            errs.append(f"row uses evaluation case_id {cid}")
        if row.get("replica") in {2, 3}:
            errs.append(f"row uses evaluation replica: {cid}")
    if int(doc.get("n_canonical_cases") or 0) != 12 and doc.get("verdict") != VERDICT_BLOCKED:
        errs.append("calibration must have 12 canonical cases")
    if int(doc.get("n_surfaces") or 0) != 96 and doc.get("verdict") != VERDICT_BLOCKED:
        errs.append("calibration must have 96 surfaces")
    return errs


def draft_spec(doc: Mapping[str, Any]) -> dict[str, Any]:
    """Machine-readable draft. Not a freeze. Calibration only."""
    return {
        "schema": "bitebench-phase2b-length-control-draft/v0.1",
        "status": "draft_calibration_only_not_frozen",
        "phase2a_revision": PHASE2A_REVISION,
        "base_main_sha": BASE_MAIN_SHA,
        "split": "calibration",
        "evaluation_sealed": True,
        "padding": False,
        "official_match_rule": {
            "source": "phase1c-token-match-v0.1",
            "max_abs_delta": TOKEN_MATCH_MAX_ABS_DELTA,
            "max_relative_delta": TOKEN_MATCH_MAX_RELATIVE_DELTA,
            "no_padding": True,
            "widened_after_seeing_results": False,
        },
        "verdict": doc.get("verdict"),
        "axis_summaries": doc.get("axis_summaries"),
        "candidate_alternative_tolerance": doc.get("candidate_alternative_tolerance"),
        "note": (
            "Draft only. Do not treat this as an evaluation freeze. "
            "Do not apply candidate tolerances to holdout."
        ),
        "paid_api": False,
        "research_conclusion": False,
    }


__all__ = [
    "AXIS_LEVELS",
    "BASE_MAIN_SHA",
    "SCHEMA_ID",
    "VERDICTS",
    "VERDICT_BLOCKED",
    "VERDICT_PARTIAL",
    "VERDICT_READY",
    "build_matrix",
    "calibration_cells",
    "decide_verdict",
    "draft_spec",
    "evaluation_case_ids",
    "morphology_coverage",
    "paired_contrasts",
    "render_length_control_md",
    "require_calibration",
    "validate_phase2b_doc",
]
