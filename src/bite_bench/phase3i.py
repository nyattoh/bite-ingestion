"""Phase 3I multi-source provenance contract freeze (I0).

Spec only. Does not change INTEGRATE, v1, thresholds, or routing.
Does not reopen p3f evaluation. Does not rewrite Phase 3H.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA_ID = "bitebench-phase3i-composite-provenance-freeze/v0.1"
REVISION = "phase3i-composite-provenance-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE3I_COMPOSITE_PROVENANCE_FROZEN"
VERDICT_VALIDATED = "PHASE3I_COMPOSITE_PROVENANCE_VALIDATED"
VERDICT_PARTIAL = "PHASE3I_COMPOSITE_PROVENANCE_PARTIAL"
VERDICT_BLOCKED = "PHASE3I_COMPOSITE_PROVENANCE_BLOCKED"
MAP_VERDICTS = (VERDICT_VALIDATED, VERDICT_PARTIAL, VERDICT_BLOCKED)
GENERATION = "p3i"
SPLIT = "development"
KIND_SOURCE = "source"
KIND_COMPOSITE = "composite"
SPAN_SOURCE_EXACT = "source_exact"
SPAN_ENVELOPE = "envelope"
SOURCE_RECORD_KEYS = ("unit_id", "source_uri", "byte_or_token_span", "renderer_id")
LOCKED_CANDIDATE = "A_mean_edge_distance"
LOCKED_T_LOW = 1
LOCKED_T_HIGH = 4

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase3i-composite-provenance-freeze.json"
PHASE3H_ARTIFACT = _REPO / "artifacts" / "phase3h" / "operator-map-experiment.json"


def planned_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "p3i-same-uri-2way",
            "join": "explicit_id",
            "n_join_members": 2,
            "source_uris": ["bitebench://p3i/a"],
            "contiguous": False,
            "expect_join": True,
        },
        {
            "case_id": "p3i-three-way",
            "join": "explicit_id",
            "n_join_members": 3,
            "source_uris": ["bitebench://p3i/a"],
            "contiguous": False,
            "expect_join": True,
        },
        {
            "case_id": "p3i-mixed-uri",
            "join": "explicit_id",
            "n_join_members": 2,
            "source_uris": ["bitebench://p3i/a", "bitebench://p3i/b"],
            "contiguous": False,
            "expect_join": True,
        },
        {
            "case_id": "p3i-passthrough",
            "join": None,
            "n_join_members": 0,
            "source_uris": ["bitebench://p3i/a"],
            "contiguous": True,
            "expect_join": False,
        },
        {
            "case_id": "p3i-dep-edge",
            "join": "dependency_edge",
            "n_join_members": 2,
            "source_uris": ["bitebench://p3i/a"],
            "contiguous": False,
            "expect_join": True,
        },
        {
            "case_id": "p3i-explicit-key",
            "join": "explicit_key",
            "n_join_members": 2,
            "source_uris": ["bitebench://p3i/a"],
            "contiguous": False,
            "expect_join": True,
        },
        {
            "case_id": "p3i-malformed-joined-from-only",
            "join": "malformed",
            "fail_closed": True,
            "defect": "joined_from_without_composite_provenance",
        },
        {
            "case_id": "p3i-malformed-fake-span",
            "join": "malformed",
            "fail_closed": True,
            "defect": "composite_with_source_exact_span",
        },
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
        "p3f_evaluation_holdout_used": False,
        "p3f_evaluation_replicas_sealed": [2, 3],
        "phase3h_artifact_immutable": True,
        "phase3h_verdict_unchanged": "PHASE3H_CONDITIONAL_MAP_REQUIRED",
        "reuse_p3h_to_strengthen_conclusion": False,
        "locked_from_phase3g": {
            "selected_candidate": LOCKED_CANDIDATE,
            "T_low": LOCKED_T_LOW,
            "T_high": LOCKED_T_HIGH,
            "v1_sensor_unchanged": True,
            "thresholds_unchanged": True,
            "candidate_unchanged": True,
        },
        "routing": {
            "rule_policy_changed": False,
            "routing_connected": False,
            "implement_conditional_map": False,
            "validated_required_before_routing": True,
        },
        "operators": {
            "integrate_must_emit_composite": True,
            "cut_untangle_reduce_semantics_unchanged": True,
        },
        "fields": {
            "provenance.kind": [KIND_SOURCE, KIND_COMPOSITE],
            "legacy_missing_kind": KIND_SOURCE,
            "provenance.sources": "array of source records, required when kind=composite",
            "source_record": list(SOURCE_RECORD_KEYS),
            "joined_from": "derivation links only; not complete provenance",
            "span.kind": [SPAN_SOURCE_EXACT, SPAN_ENVELOPE],
            "legacy_missing_span_kind": SPAN_SOURCE_EXACT,
            "composite_span": SPAN_ENVELOPE,
            "envelope.contiguous": False,
            "envelope_is_not_source_exact": True,
            "top_level_source_uri_on_mixed_join": None,
        },
        "completeness": {
            "source": (
                "provenance.unit_id and provenance.source_uri and "
                "provenance.byte_or_token_span and source-exact span.end"
            ),
            "composite": (
                "kind=composite and len(sources)>=2 and each source has "
                "unit_id, source_uri, byte_or_token_span"
            ),
            "joined_from_alone": False,
        },
        "validator_distinction": {
            "source": "kind is source or omitted",
            "composite": "kind is composite",
            "malformed": "joined multi-source without composite kind, or envelope/source_exact mismatch",
        },
        "invariants_after_integrate": [
            "provenance_completeness == 1.0",
            "required_evidence_lineage_recall == 1.0",
            "conservation_untraced(...) == []",
            "joined source ids resolve in root lineage",
            "silent_loss == 0",
            "join_plan unit_ids == composite provenance.sources unit_ids",
            "deterministic output / stable id",
        ],
        "gold": "scorer only; not passed to the operator",
        "malformed_fail_closed": True,
        "planned_cases": planned_cases(),
        "i1_verdicts": list(MAP_VERDICTS),
        "on_not_validated": "do not connect conditional routing",
    }


def validate_phase3i_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("revision") != REVISION:
        errs.append("revision mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("protocol not frozen")
    if doc.get("generation") != GENERATION:
        errs.append("generation must be p3i")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("reuse_p3h_to_strengthen_conclusion") is not False:
        errs.append("must not reuse p3h to strengthen the conclusion")
    if doc.get("phase3h_verdict_unchanged") != "PHASE3H_CONDITIONAL_MAP_REQUIRED":
        errs.append("Phase 3H verdict must remain CONDITIONAL_MAP_REQUIRED")
    routing = dict(doc.get("routing") or {})
    if routing.get("rule_policy_changed") is not False:
        errs.append("routing must stay disconnected")
    if routing.get("implement_conditional_map") is not False:
        errs.append("must not implement the conditional map")
    fields = dict(doc.get("fields") or {})
    if fields.get("joined_from") == "complete provenance":
        errs.append("joined_from must not count as complete provenance")
    if doc.get("completeness", {}).get("joined_from_alone") is not False:
        errs.append("joined_from alone is not completeness")
    ids = [row["case_id"] for row in doc.get("planned_cases") or []]
    if ids != [row["case_id"] for row in planned_cases()]:
        errs.append("planned cases drifted")
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
