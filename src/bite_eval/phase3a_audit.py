"""Phase 3A post-hoc profiler mechanism audit.

Explains PHASE2D_OFFLINE_NO_SIGNAL from the current profiler/policy.
Does not retune features, thresholds, or routing. Not a confirmatory result.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bite_bench.phase2a import design_cells, generate_phase2a_bundle
from bite_bench.phase2c import confirmatory_pairs
from bite_ingestion.policies.rule_policy import ROUTING_FEATURES
from bite_ingestion.policies.thresholds import TBD_CALIBRATE
from bite_ingestion.profilers.deterministic import FEATURE_KEYS, DeterministicMorphologyProfiler

SCHEMA_ID = "bite-phase3a-profiler-mechanism-audit/v0.1"
BASE_MAIN_SHA = "dce759efbb94ae941a86c3358b1b717da3224c14"
PHASE2D_ARTIFACT = "artifacts/phase2d/confirmatory-offline.json"
VERDICT_UNOBSERVABLE = "PHASE3A_DISPERSION_UNOBSERVABLE"
VERDICT_OBSERVABLE_UNUSED = "PHASE3A_DISPERSION_OBSERVABLE_UNUSED"
VERDICT_OTHER = "PHASE3A_OTHER"
VERDICTS = (VERDICT_UNOBSERVABLE, VERDICT_OBSERVABLE_UNUSED, VERDICT_OTHER)
_QUERY_TOKEN = re.compile(r"[A-Za-z0-9_]+")

# Source of truth is deterministic.py. Copied here as audit labels only.
FEATURE_DISPERSION_DESIGN: dict[str, dict[str, Any]] = {
    "b": {
        "routing": True,
        "designed_to_move_with_dispersion": False,
        "why": "newline density and separator-character rate over the whole text",
    },
    "a": {
        "routing": True,
        "designed_to_move_with_dispersion": False,
        "why": "whole-text anomaly / malformed-JSON of the entire payload",
    },
    "r": {
        "routing": True,
        "designed_to_move_with_dispersion": False,
        "why": "duplicate stripped-line ratio (bag of lines)",
    },
    "k": {
        "routing": True,
        "designed_to_move_with_dispersion": False,
        "why": "ref-like token count over the whole text / line_count",
    },
    "l": {
        "routing": True,
        "designed_to_move_with_dispersion": False,
        "why": (
            "query-token substring hit mass on stripped lines; "
            "hits are sorted descending and the top min(3,n) / total is kept. "
            "Line order and inter-line distance are discarded. "
            "Not positional evidence locality."
        ),
        "permutation_invariant": True,
        "uses_gold_or_required_evidence_ids": False,
    },
    "u": {
        "routing": True,
        "used_for_routing": False,
        "designed_to_move_with_dispersion": False,
        "why": "derived from a and (1-l); rule-Π records u but does not route on it",
    },
    "s": {
        "routing": False,
        "designed_to_move_with_dispersion": False,
        "why": "JSON/CSV/code heuristics on the whole text",
    },
    "p": {
        "routing": False,
        "designed_to_move_with_dispersion": False,
        "why": "path/version/line-number regex hits on the whole text",
    },
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def permute_lines(text: str, order: Sequence[int]) -> str:
    lines = text.splitlines()
    if len(order) != len(lines):
        raise ValueError("order length must match splitlines()")
    return "\n".join(lines[i] for i in order)


def profile_payload(text: str, query: str) -> dict[str, float]:
    report = DeterministicMorphologyProfiler().profile({"payload": text, "query": query})
    return {k: float(report[k]) for k in FEATURE_KEYS}


def required_span_spread(units: Sequence[Mapping[str, Any]]) -> int:
    """Audit-only positional diagnostic. Not a profiler feature."""
    starts = [
        int(u["span"]["start"])
        for u in units
        if isinstance(u, Mapping) and u.get("is_required_evidence")
    ]
    if len(starts) < 2:
        return 0
    return max(starts) - min(starts)


def query_hit_line_index_span(text: str, query: str) -> int:
    """First-to-last stripped-line index among query-token hits. Audit-only."""
    q_tokens = [t.lower() for t in _QUERY_TOKEN.findall(query) if len(t) > 1]
    stripped = [ln.strip() for ln in text.splitlines() if ln.strip()]
    hits = [
        i
        for i, ln in enumerate(stripped)
        if any(tok in ln.lower() for tok in q_tokens)
    ]
    if len(hits) < 2:
        return 0
    return hits[-1] - hits[0]


def abs_delta(left: Mapping[str, float], right: Mapping[str, float]) -> dict[str, float]:
    return {k: abs(float(left[k]) - float(right[k])) for k in FEATURE_KEYS}


def decide_phase3a_verdict(
    *,
    n_pairs: int,
    n_routing_feature_nonzero: int,
    phase2d_n_signal: int | None,
) -> str:
    if n_pairs < 1:
        return VERDICT_OTHER
    if n_routing_feature_nonzero == 0:
        return VERDICT_UNOBSERVABLE
    if (phase2d_n_signal or 0) == 0:
        return VERDICT_OBSERVABLE_UNUSED
    return VERDICT_OTHER


def _morphology_from_phase2d_rows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, dict[str, float]]]:
    out: dict[str, dict[str, dict[str, float]]] = {}
    for row in rows:
        if row.get("method") != "rule_pi":
            continue
        pair_id = str(row.get("pair_id"))
        disp = str(row.get("dispersion"))
        morph = row.get("morphology") or {}
        if not isinstance(morph, Mapping):
            continue
        out.setdefault(pair_id, {})[disp] = {k: float(morph.get(k, 0.0)) for k in FEATURE_KEYS}
    return out


def _summarize_feature_deltas(pair_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    routing = set(ROUTING_FEATURES)
    for key in FEATURE_KEYS:
        vals = [float((p.get("abs_delta") or {}).get(key) or 0.0) for p in pair_rows]
        summary[key] = {
            "n_nonzero": sum(1 for v in vals if v != 0.0),
            "max_abs": max(vals) if vals else 0.0,
            "mean_abs": (sum(vals) / len(vals)) if vals else 0.0,
            "routing": key in routing,
            "designed_to_move_with_dispersion": bool(
                FEATURE_DISPERSION_DESIGN[key]["designed_to_move_with_dispersion"]
            ),
        }
    return summary


def build_phase3a_doc(*, phase2d_path: Path | None = None) -> dict[str, Any]:
    root = _repo_root()
    artifact = phase2d_path or (root / PHASE2D_ARTIFACT)
    phase2d = json.loads(artifact.read_text(encoding="utf-8"))
    stored = _morphology_from_phase2d_rows(list(phase2d.get("rows") or []))
    bundles = {cell.case_id: generate_phase2a_bundle(cell) for cell in design_cells("evaluation")}
    pair_rows: list[dict[str, Any]] = []
    for pair in confirmatory_pairs():
        bundle = bundles[str(pair["case_id"])]
        query = str(bundle["canonical"]["question"])
        left_fam = str(pair["left"]["family"])
        right_fam = str(pair["right"]["family"])
        left_surf = bundle["surfaces"][left_fam]
        right_surf = bundle["surfaces"][right_fam]
        live_left = profile_payload(str(left_surf["text"]), query)
        live_right = profile_payload(str(right_surf["text"]), query)
        stored_sides = stored.get(str(pair["pair_id"]), {})
        stored_left = stored_sides.get("clustered")
        stored_right = stored_sides.get("dispersed")
        pair_rows.append(
            {
                "pair_id": pair["pair_id"],
                "case_id": pair["case_id"],
                "scale": pair["scale"],
                "dependency": pair["dependency"],
                "replica": pair["replica"],
                "structure": pair["structure"],
                "redundancy": pair["redundancy"],
                "live": {
                    "clustered": live_left,
                    "dispersed": live_right,
                    "abs_delta": abs_delta(live_left, live_right),
                },
                "phase2d_stored": {
                    "clustered": stored_left,
                    "dispersed": stored_right,
                    "abs_delta": (
                        abs_delta(stored_left, stored_right)
                        if stored_left and stored_right
                        else None
                    ),
                    "matches_live": (
                        stored_left == live_left and stored_right == live_right
                        if stored_left and stored_right
                        else False
                    ),
                },
                "abs_delta": abs_delta(live_left, live_right),
                "required_span_spread": {
                    "clustered": required_span_spread(left_surf["units"]),
                    "dispersed": required_span_spread(right_surf["units"]),
                },
                "query_hit_line_index_span": {
                    "clustered": query_hit_line_index_span(str(left_surf["text"]), query),
                    "dispersed": query_hit_line_index_span(str(right_surf["text"]), query),
                },
            }
        )

    feature_summary = _summarize_feature_deltas(pair_rows)
    n_routing_nonzero = sum(
        int(feature_summary[k]["n_nonzero"]) for k in ROUTING_FEATURES
    )
    n_span_differs = sum(
        1
        for p in pair_rows
        if p["required_span_spread"]["clustered"] != p["required_span_spread"]["dispersed"]
    )
    n_hit_span_differs = sum(
        1
        for p in pair_rows
        if p["query_hit_line_index_span"]["clustered"]
        != p["query_hit_line_index_span"]["dispersed"]
    )
    n_live_identical = sum(
        1 for p in pair_rows if all(v == 0.0 for v in p["abs_delta"].values())
    )
    n_stored_match = sum(
        1 for p in pair_rows if p["phase2d_stored"].get("matches_live")
    )
    phase2d_n_signal = int(phase2d.get("n_signal") or 0)
    verdict = decide_phase3a_verdict(
        n_pairs=len(pair_rows),
        n_routing_feature_nonzero=n_routing_nonzero,
        phase2d_n_signal=phase2d_n_signal,
    )
    return {
        "schema": SCHEMA_ID,
        "offline": True,
        "paid_api": False,
        "synthetic": True,
        "research_conclusion": False,
        "confirmatory": False,
        "post_hoc": True,
        "purpose": (
            "post-hoc mechanism audit of why Phase 2D reported "
            "PHASE2D_OFFLINE_NO_SIGNAL; not a new confirmatory result and "
            "not a licence to retune profiler/thresholds on the spent holdout"
        ),
        "base_main_sha": BASE_MAIN_SHA,
        "phase2d_artifact": PHASE2D_ARTIFACT,
        "phase2d_verdict": phase2d.get("verdict"),
        "phase2d_n_signal": phase2d_n_signal,
        "phase2d_n_eligible": phase2d.get("n_eligible"),
        "profiler": "deterministic_v0",
        "routing_features": list(ROUTING_FEATURES),
        "all_features": list(FEATURE_KEYS),
        "thresholds_untouched": {
            "HIGH": TBD_CALIBRATE.HIGH,
            "LOW": TBD_CALIBRATE.LOW,
            "note": "recorded only; not recalibrated",
        },
        "l_definition": FEATURE_DISPERSION_DESIGN["l"],
        "dispersion_operator": {
            "what_it_changes": (
                "order of the same fact lines; required-evidence char-span positions"
            ),
            "what_it_does_not_change": (
                "fact texts, query, line-text multiset, separator character, gold ids"
            ),
            "routing_features_designed_to_observe_it": [],
        },
        "feature_dispersion_design": FEATURE_DISPERSION_DESIGN,
        "n_planned_pairs": 48,
        "n_pairs": len(pair_rows),
        "n_profiler_vectors_identical": n_live_identical,
        "n_phase2d_morphology_matches_live": n_stored_match,
        "n_required_span_spread_differs": n_span_differs,
        "n_query_hit_line_index_span_differs": n_hit_span_differs,
        "n_routing_feature_nonzero": n_routing_nonzero,
        "feature_deltas": feature_summary,
        "verdict": verdict,
        "blocked_reasons": [],
        "pairs": pair_rows,
    }


def render_phase3a_md(doc: Mapping[str, Any]) -> str:
    deltas = dict(doc.get("feature_deltas") or {})
    lines = [
        "# Phase 3A profiler mechanism audit",
        "",
        "post-hoc。confirmatory ではない。holdout を再評価していない。",
        "profiler / threshold / routing は未変更。有料 API 未使用。",
        "",
        f"- verdict: **{doc.get('verdict')}**",
        (
            f"- Phase 2D: {doc.get('phase2d_verdict')} "
            f"({doc.get('phase2d_n_signal')}/{doc.get('phase2d_n_eligible')})"
        ),
        (
            f"- profiler vectors identical: "
            f"{doc.get('n_profiler_vectors_identical')}/{doc.get('n_pairs')}"
        ),
        (
            f"- required-evidence span spread differs: "
            f"{doc.get('n_required_span_spread_differs')}/{doc.get('n_pairs')} "
            "(audit diagnostic, not a routing feature)"
        ),
        (
            f"- query-hit line-index span differs: "
            f"{doc.get('n_query_hit_line_index_span_differs')}/{doc.get('n_pairs')} "
            "(order-sensitive diagnostic; not `l`. On this benchmark many query "
            "tokens also substring-match distractor lines, so this is a weak proxy.)"
        ),
        "",
        "## `l` is not positional locality",
        "",
        str((doc.get("l_definition") or {}).get("why") or ""),
        "",
        "## Feature abs delta (clustered vs dispersed)",
        "",
    ]
    for key in FEATURE_KEYS:
        row = dict(deltas.get(key) or {})
        role = "routing" if row.get("routing") else "non-routing"
        lines.append(
            f"- `{key}` ({role}): n_nonzero={row.get('n_nonzero')} "
            f"max_abs={row.get('max_abs')} mean_abs={row.get('mean_abs')}"
        )
    lines += [
        "",
        "## Policy",
        "",
        f"- rule-Π routing keys: {list(doc.get('routing_features') or [])}",
        "- `u` is accepted but unused for routing (existing rule-Π note)",
        "- INTEGRATE needs `k≥HIGH` and `l≤LOW`; this audit does not retune that",
        "",
    ]
    return "\n".join(lines)


def validate_phase3a_doc(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("paid_api") is not False:
        errs.append("paid_api must be false")
    if doc.get("schema") != SCHEMA_ID:
        errs.append(f"bad schema: {doc.get('schema')!r}")
    if doc.get("confirmatory") is not False:
        errs.append("Phase 3A must be marked not confirmatory")
    if doc.get("post_hoc") is not True:
        errs.append("Phase 3A must be marked post_hoc")
    if doc.get("verdict") not in VERDICTS:
        errs.append(f"bad verdict: {doc.get('verdict')!r}")
    if int(doc.get("n_pairs") or 0) != 48:
        errs.append("expected 48 pairs")
    l_def = dict(doc.get("l_definition") or {})
    if l_def.get("permutation_invariant") is not True:
        errs.append("l must be recorded as permutation-invariant")
    if l_def.get("uses_gold_or_required_evidence_ids") is not False:
        errs.append("l must not be recorded as using gold ids")
    if list(doc.get("routing_features") or []) != list(ROUTING_FEATURES):
        errs.append("routing_features drifted")
    n_nonzero = int(doc.get("n_routing_feature_nonzero") or 0)
    verdict = doc.get("verdict")
    if n_nonzero == 0 and verdict != VERDICT_UNOBSERVABLE:
        errs.append("zero routing-feature delta must be UNOBSERVABLE")
    if n_nonzero > 0 and (doc.get("phase2d_n_signal") or 0) == 0 and (
        verdict != VERDICT_OBSERVABLE_UNUSED
    ):
        errs.append("nonzero unused routing delta must be OBSERVABLE_UNUSED")
    return errs
