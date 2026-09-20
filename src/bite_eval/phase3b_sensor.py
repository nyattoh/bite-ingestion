"""Phase 3B sensor evaluation on development fixtures. No routing. No holdout."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bite_eval.phase3b_fixtures import EXPECTED_DISTANCE_ORDER, development_cases
from bite_ingestion.profilers.dependency_dispersion import (
    PRIMARY_FEATURE,
    QUERY_SENSOR_NAME,
    SENSOR_NAME,
    measure,
    query_identifier_span,
)
from bite_ingestion.profilers.deterministic import FEATURE_KEYS, DeterministicMorphologyProfiler

SCHEMA_ID = "bite-phase3b-sensor-evaluation/v0.1"
VERDICT_READY = "PHASE3B_SENSOR_READY"
VERDICT_PARTIAL = "PHASE3B_SENSOR_PARTIAL"
VERDICT_NOT_READY = "PHASE3B_SENSOR_NOT_READY"
VERDICTS = (VERDICT_READY, VERDICT_PARTIAL, VERDICT_NOT_READY)


def _row(case: Mapping[str, Any]) -> dict[str, Any]:
    unit = {
        "payload": case["text"],
        "text": case["text"],
        "query": case["query"],
    }
    report = measure(unit)
    v0 = DeterministicMorphologyProfiler().profile(unit)
    q_generic = query_identifier_span(unit)
    q_ident = query_identifier_span({**unit, "query": case["query_with_identifier"]})
    return {
        "case_id": case["case_id"],
        "family": case["family"],
        "kind": case["kind"],
        "surface": case["surface"],
        "sensor": report.features,
        "query_generic": q_generic,
        "query_identifier": q_ident,
        "v0": {k: float(v0[k]) for k in FEATURE_KEYS},
        "fail_closed": report.fail_closed,
        "n_edges_recorded": len(report.edges),
        "notes": list(report.notes),
    }


def _ordered_primary(rows: list[dict[str, Any]], family: str) -> list[float]:
    by_kind = {r["kind"]: r for r in rows if r["family"] == family}
    return [float(by_kind[k]["sensor"][PRIMARY_FEATURE]) for k in EXPECTED_DISTANCE_ORDER]


def _strict_increase(vals: list[float]) -> bool:
    return len(vals) == 3 and vals[0] < vals[1] < vals[2]


def decide_phase3b_verdict(checks: Mapping[str, bool]) -> str:
    needed = (
        "one_hop_monotone",
        "one_hop_edge_count_stable",
        "v0_invariant",
        "no_reference_zero",
        "false_positive_zero",
        "unrelated_perm_stable",
        "nested_monotone",
        "malformed_fail_closed",
        "deterministic",
    )
    if all(checks[k] for k in needed):
        if checks.get("duplicate_raw_stable") and checks.get("two_hop_chain_monotone"):
            return VERDICT_READY
        return VERDICT_PARTIAL
    if checks.get("one_hop_monotone"):
        return VERDICT_PARTIAL
    return VERDICT_NOT_READY


def build_phase3b_doc() -> dict[str, Any]:
    rows = [_row(case) for case in development_cases()]
    by_id = {r["case_id"]: r for r in rows}
    one_hop = _ordered_primary(rows, "one_hop")
    nested = _ordered_primary(rows, "one_hop_nested")
    two = {r["kind"]: r for r in rows if r["family"] == "two_hop"}
    two_span = [float(two[k]["sensor"]["chain_span"]) for k in EXPECTED_DISTANCE_ORDER]
    v0_vecs = [
        tuple(by_id[f"one_hop_{k}"]["v0"][f] for f in FEATURE_KEYS)
        for k in EXPECTED_DISTANCE_ORDER
    ]
    near_d = by_id["one_hop_near"]["sensor"][PRIMARY_FEATURE]
    far_text = next(c["text"] for c in development_cases() if c["case_id"] == "one_hop_far")
    checks = {
        "one_hop_monotone": _strict_increase(one_hop),
        "one_hop_edge_count_stable": all(
            by_id[f"one_hop_{k}"]["sensor"]["n_edges"] == 1.0 for k in EXPECTED_DISTANCE_ORDER
        ),
        "v0_invariant": len(set(v0_vecs)) == 1,
        "no_reference_zero": by_id["no_reference"]["sensor"]["n_edges"] == 0.0,
        "false_positive_zero": by_id["false_positive"]["sensor"]["n_edges"] == 0.0,
        "unrelated_perm_stable": by_id["unrelated_perm"]["sensor"][PRIMARY_FEATURE] == near_d,
        "duplicate_raw_stable": (
            by_id["duplicate_noise"]["sensor"][PRIMARY_FEATURE] == near_d
            and by_id["duplicate_noise"]["sensor"]["n_edges"] == 1.0
        ),
        "nested_monotone": _strict_increase(nested),
        "two_hop_chain_monotone": _strict_increase(two_span),
        "malformed_fail_closed": measure({"payload": "x\x00y"}).fail_closed is True,
        "deterministic": (
            measure({"payload": far_text}).features == measure({"payload": far_text}).features
        ),
        "generic_query_idle": by_id["one_hop_far"]["query_generic"]["q_hits"] == 0.0,
        "identifier_query_moves": by_id["one_hop_far"]["query_identifier"]["q_span"] > 0.0,
    }
    verdict = decide_phase3b_verdict(checks)
    return {
        "schema": SCHEMA_ID,
        "offline": True,
        "paid_api": False,
        "synthetic": True,
        "research_conclusion": False,
        "confirmatory": False,
        "routing_connected": False,
        "evaluation_holdout_used": False,
        "v0_overwritten": False,
        "purpose": (
            "development-fixture evaluation of a gold-free dependency-dispersion "
            "sensor; not a Phase 2D rescore and not a routing rule"
        ),
        "sensor_name": SENSOR_NAME,
        "query_sensor_name": QUERY_SENSOR_NAME,
        "primary_feature": PRIMARY_FEATURE,
        "expected_distance_order": list(EXPECTED_DISTANCE_ORDER),
        "one_hop_mean_edge_distance": one_hop,
        "one_hop_nested_mean_edge_distance": nested,
        "two_hop_chain_span": two_span,
        "checks": checks,
        "verdict": verdict,
        "rows": rows,
    }


def render_phase3b_md(doc: Mapping[str, Any]) -> str:
    checks = dict(doc.get("checks") or {})
    lines = [
        "# Phase 3B dispersion sensor evaluation",
        "",
        "development fixtures only。Phase 2 evaluation は未使用。routing 未接続。",
        "deterministic_v0 は未変更。有料 API 未使用。",
        "",
        f"- verdict: **{doc.get('verdict')}**",
        f"- sensor: `{doc.get('sensor_name')}` primary `{doc.get('primary_feature')}`",
        f"- expected order: {doc.get('expected_distance_order')}",
        f"- one-hop mean_edge_distance: {doc.get('one_hop_mean_edge_distance')}",
        f"- nested one-hop: {doc.get('one_hop_nested_mean_edge_distance')}",
        f"- two-hop chain_span: {doc.get('two_hop_chain_span')}",
        "",
        "## Checks",
        "",
    ]
    for key, ok in checks.items():
        mark = "yes" if ok else "no"
        lines.append(f"- {key}: {mark}")
    lines += [
        "",
        "## Candidates",
        "",
        "- reference-graph (primary): value-identifier reappears in another non-identical line",
        "- query-identifier span (secondary): idle on generic questions; moves if the query carries a rare identifier",
        "- v0 `l`: permutation-invariant on these fixtures",
        "",
    ]
    return "\n".join(lines)


def validate_phase3b_doc(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("paid_api") is not False:
        errs.append("paid_api must be false")
    if doc.get("schema") != SCHEMA_ID:
        errs.append(f"bad schema: {doc.get('schema')!r}")
    if doc.get("routing_connected") is not False:
        errs.append("Phase 3B must not connect routing")
    if doc.get("evaluation_holdout_used") is not False:
        errs.append("Phase 2 evaluation must not be used")
    if doc.get("v0_overwritten") is not False:
        errs.append("v0 must not be overwritten")
    if doc.get("verdict") not in VERDICTS:
        errs.append(f"bad verdict: {doc.get('verdict')!r}")
    if list(doc.get("expected_distance_order") or []) != list(EXPECTED_DISTANCE_ORDER):
        errs.append("expected order drifted")
    return errs
