"""Phase 4K documentation-only evidence ledger.

Reads frozen Phase 4A-4J JSON artifacts. Does not run tokenizer, arms,
sensors, policies, or operators. Does not rewrite historical artifacts.
Does not open p3f. Does not merge.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4k import (
    CITED_BLOBS,
    CLAIM_BOUNDARY,
    EVIDENCE_CATEGORIES,
    FREEZE_PATH,
    HISTORICAL_VERDICTS,
    PHASE3Q_VERDICT,
    PHASE3S_VERDICT,
    PHASE4_CONCLUSION,
    PHASE4J_HEAD,
    PREMISE,
    PROTOCOL_FROZEN,
    SUPPORTED_CLAIMS,
    UNSUPPORTED_CLAIMS,
    VERDICT_BLOCKED,
    VERDICT_FROZEN,
    freeze_manifest,
    validate_phase4k_freeze,
)

SCHEMA_ID = "bite-phase4k-evidence-ledger/v0.1"
REVISION = "phase4k-evidence-ledger-v0.1"
K0_COMMIT_SHA = "4b2adc2523f8eec73888cfbec75fbf413fa21631"
K0_FREEZE_BLOB = "86e83ff7f43e45721c7a436f1f21865f4342362e"
_REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = _REPO / "artifacts" / "phase4k"
RESULT_PATH = ARTIFACT_DIR / "phase4-closure.json"
LEDGER_PATH = ARTIFACT_DIR / "evidence-ledger.json"
CLAIMS_PATH = ARTIFACT_DIR / "claim-matrix.json"
TIMELINE_PATH = ARTIFACT_DIR / "historical-verdict-timeline.json"
COMPARE_PATH = ARTIFACT_DIR / "prospective-vs-retrospective.json"
LIMITS_PATH = ARTIFACT_DIR / "known-limitations.json"
WORDING_PATH = ARTIFACT_DIR / "publication-safe-wording.json"
WINNER_KEYS = (
    "overall_score",
    "overall_winner",
    "best_arm",
    "arm_ranking",
    "win_rate",
    "superiority",
)


def _git_blob(path: str) -> str:
    return subprocess.check_output(["git", "hash-object", path], cwd=_REPO, text=True).strip()


def _dump(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(dict(doc), indent=2, sort_keys=True) + "\n").encode("utf-8"))


def _load(rel: str) -> dict[str, Any]:
    payload = json.loads((_REPO / rel).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{rel} must be an object")
    return payload


def _winner_leak(payload: object) -> bool:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if str(key) in WINNER_KEYS:
                return True
            if _winner_leak(value):
                return True
    elif isinstance(payload, list):
        return any(_winner_leak(item) for item in payload)
    return False


def _blob_errors() -> list[str]:
    errs: list[str] = []
    if not FREEZE_PATH.is_file():
        return ["K0 freeze missing"]
    committed = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    errs.extend(validate_phase4k_freeze(committed))
    if freeze_manifest() != committed:
        errs.append("K0 freeze drifted from generator")
    if committed.get("verdict") != PROTOCOL_FROZEN:
        errs.append("K0 not frozen")
    if _git_blob("benchmarks/spec/phase4k-evidence-ledger-freeze.json") != K0_FREEZE_BLOB:
        errs.append("K0 freeze blob drifted")
    for path, expected in CITED_BLOBS.items():
        if _git_blob(path) != expected:
            errs.append(f"cited blob drifted: {path}")
    return errs


def _verify_source_facts() -> list[str]:
    errs: list[str] = []
    freeze = freeze_manifest()
    facts = freeze["prospective_realstruct2_facts"]
    first = _load("artifacts/phase4i/first-open.json")
    if first.get("verdict") != "PHASE4I_PROSPECTIVE_COMPARISON_MEASURED":
        errs.append("Phase4I verdict rewritten")
    if int(first.get("n_documents") or 0) != facts["primary_documents"]:
        errs.append("primary document count drifted")
    if int(first.get("n_arm_rows") or 0) != facts["four_arms_rows"]:
        errs.append("arm-row count drifted")
    if first.get("raw_reconstruction_exact") is not True:
        errs.append("raw reconstruction flag drifted")
    if first.get("bite_safety_ok") is not True:
        errs.append("BITE safety flag drifted")
    if first.get("planner_integrity_ok") is not True:
        errs.append("planner integrity flag drifted")
    safety = _load("artifacts/phase4i/safety.json")
    if int(safety.get("n_arm_reconstruction_exact") or 0) != 72:
        errs.append("reconstruction 72/72 drifted")
    if int(safety.get("n_bite_safety_pass") or 0) != 18:
        errs.append("BITE safety 18/18 drifted")
    if int(safety.get("n_planner_integrity_pass") or 0) != 18:
        errs.append("planner integrity 18/18 drifted")
    cost = _load("artifacts/phase4i/model-visible-cost.json")
    if int(cost.get("bite_reduction_incidence") or 0) != 1:
        errs.append("reduction incidence drifted")
    if cost.get("not_a_win_rate") is not True:
        errs.append("cost artifact win-rate flag drifted")
    unique = _load("artifacts/phase4i/paired-unique-identity.json")
    locked = facts["matched_budget_unique_identity"]
    if int(unique.get("n") or 0) != 1:
        errs.append("matched-budget n drifted")
    docs = list(unique.get("documents") or [])
    if len(docs) != 1 or docs[0].get("source_id") != locked["source_id"]:
        errs.append("matched-budget source drifted")
    else:
        same_values = (
            docs[0].get("bite_v5") == locked["BITE_v5"]
            and docs[0].get("length_pi_v1") == locked["length_pi_v1"]
            and docs[0].get("delta") == locked["delta"]
        )
        if not same_values:
            errs.append("matched-budget values drifted")
    legacy = _load("artifacts/phase4i/paired-reference-retention.json")
    hist = facts["historical_reference_retention"]
    if int(legacy.get("n") or 0) != hist["n"] or legacy.get("status") != hist["status"]:
        errs.append("Phase4I historical reference retention rewritten")
    mech = _load("artifacts/phase4i/mechanism-diagnostic.json")
    routes = {json.dumps(row.get("sequence")): int(row.get("n") or 0) for row in mech.get("route_sequence_frequency") or []}
    if routes.get("[]") != 17 or routes.get('["REDUCE_v2"]') != 1:
        errs.append("mechanism route frequencies drifted")
    if int(mech.get("gate_incidence") or 0) != 4:
        errs.append("gate incidence drifted")
    corrected = _load("artifacts/phase4j/legacy-vs-corrected-paired-reference.json")
    legacy_copy = corrected.get("phase4i_legacy_schema_reader_result") or {}
    if int(legacy_copy.get("n") or 0) != 0 or legacy_copy.get("status") != "not_observed":
        errs.append("Phase4J did not preserve Phase4I n=0/not_observed")
    corr = corrected.get("corrected") or {}
    retro = freeze["retrospective_corrections"]["reference_retention"]
    if int(corr.get("n") or 0) != retro["n"] or corr.get("tie") != retro["tie"]:
        errs.append("Phase4J corrected reference n/tie drifted")
    corr_docs = list(corr.get("documents") or [])
    if (
        len(corr_docs) != 1
        or corr_docs[0].get("source_id") != retro["source_id"]
        or corr_docs[0].get("bite_v5") != retro["BITE_v5"]
        or corr_docs[0].get("length_pi_v1") != retro["length_pi_v1"]
        or corr_docs[0].get("delta") != retro["delta"]
    ):
        errs.append("Phase4J corrected reference values drifted")
    atom = _load("artifacts/phase4j/corrected-atom-aware.json")
    sensor = freeze["retrospective_corrections"]["reference_sensor_ahuacate"]
    ahuacate = next(
        (
            row
            for row in atom.get("documents") or []
            if isinstance(row, Mapping)
            and row.get("source_id") == "rs2-ini-ahuacate-pve-medialab"
        ),
        None,
    )
    if not isinstance(ahuacate, Mapping):
        errs.append("corrected ahuacate diagnostic missing")
    elif (
        ahuacate.get("atom_aware_precision") != sensor["precision"]
        or ahuacate.get("atom_aware_recall") != sensor["recall"]
        or ahuacate.get("unadjudicated_extra_edges") != sensor["unadjudicated"]
    ):
        errs.append("corrected ahuacate diagnostic drifted")
    phase4c = _load("artifacts/phase4c/real-holdout.json")
    if int(phase4c.get("n_eval") or 0) != 9 or int(phase4c.get("n_ok") or 0) != 9:
        errs.append("Phase4C 9/9 safety count drifted")
    return errs


def _mechanism_evidence() -> dict[str, Any]:
    return {
        "category": "mechanism_evidence",
        "pooled_with_other_categories": False,
        "historical_failures_preserved": [
            {
                "phase": "3Q",
                "verdict": PHASE3Q_VERDICT,
                "note": "FAILED remains; later versions repaired mechanisms without erasing this verdict",
            },
            {
                "phase": "3S",
                "verdict": PHASE3S_VERDICT,
                "note": "FAILED remains; later versions repaired mechanisms without erasing this verdict",
            },
        ],
        "later_repairs_by_version": [
            {
                "phase": "3T",
                "verdict": "PHASE3T_EXACT_REFERENCE_VALIDATED",
                "version_label": "exact-reference identity v3",
                "does_not_erase": PHASE3S_VERDICT,
            },
            {
                "phase": "4E",
                "verdict": "PHASE4E_FULL_KEY_REFERENCE_VALIDATED",
                "version_label": "full-key reference identity v2 / dependency_dispersion_v4",
                "does_not_erase": PHASE3S_VERDICT,
            },
        ],
        "phase4i_mechanism_incidence": {
            "n_documents": 18,
            "route_empty": {"n": 17, "n_of": "17/18"},
            "REDUCE_v2": {"n": 1, "n_of": "1/18"},
            "gate_incidence": {"n": 4, "n_of": "4/18"},
            "gate_is_not_successful_transformation_incidence": True,
            "source_blob": CITED_BLOBS["artifacts/phase4i/mechanism-diagnostic.json"],
        },
        "negative_null_evidence": (
            "Natural convenience sample produced sparse transformation: "
            "17/18 documents had no BITE operator sequence."
        ),
        "result_not_protocol_failure": True,
    }


def _safety_evidence() -> dict[str, Any]:
    return {
        "category": "real_corpus_safety_evidence",
        "pooled_with_other_categories": False,
        "phase4c_realstruct1": {
            "n_eval": 9,
            "phrase": "full-source conservation safety 9/9",
            "source_blob": CITED_BLOBS["artifacts/phase4c/real-holdout.json"],
        },
        "phase4i_realstruct2": {
            "n_documents": 18,
            "n_arm_rows": 72,
            "raw_reconstruction_exact": "72/72",
            "bite_safety": "18/18",
            "planner_integrity": "18/18",
            "not_a_weighted_score": True,
            "source_blob": CITED_BLOBS["artifacts/phase4i/safety.json"],
        },
    }


def _prospective_evidence() -> dict[str, Any]:
    facts = freeze_manifest()["prospective_realstruct2_facts"]
    ident = facts["matched_budget_unique_identity"]
    hist = facts["historical_reference_retention"]
    return {
        "category": "prospective_realstruct2_comparison_evidence",
        "pooled_with_other_categories": False,
        "not_a_new_experiment": True,
        "n_primary_documents": facts["primary_documents"],
        "n_arm_rows": facts["four_arms_rows"],
        "raw_reconstruction_exact": facts["raw_reconstruction_exact"],
        "bite_safety": facts["bite_safety"],
        "planner_integrity": facts["planner_integrity"],
        "bite_model_visible_reduction_incidence": {
            "n": 1,
            "n_of": facts["bite_model_visible_reduction_incidence"],
            "not_a_win_rate": True,
            "source_blob": CITED_BLOBS["artifacts/phase4i/model-visible-cost.json"],
        },
        "matched_budget_unique_identity": {
            "n": ident["n"],
            "n_prominence": "n=1",
            "source_id": ident["source_id"],
            "BITE_v5": ident["BITE_v5"],
            "length_pi_v1": ident["length_pi_v1"],
            "delta": ident["delta"],
            "source_blob": CITED_BLOBS["artifacts/phase4i/paired-unique-identity.json"],
        },
        "historical_reference_retention_phase4i": {
            "n": hist["n"],
            "status": hist["status"],
            "reason": hist["reason"],
            "preserved_verbatim": True,
            "source_blob": CITED_BLOBS["artifacts/phase4i/paired-reference-retention.json"],
        },
        "claim_boundary": (
            "prospective four-arm measurement on the frozen two-wave "
            "REALSTRUCT-2 convenience sample"
        ),
    }


def _retrospective_evidence() -> dict[str, Any]:
    freeze = freeze_manifest()
    retro = freeze["retrospective_corrections"]
    retention = retro["reference_retention"]
    sensor = retro["reference_sensor_ahuacate"]
    return {
        "category": "retrospective_measurement_corrections",
        "pooled_with_other_categories": False,
        "not_a_new_first_open": True,
        "not_confirmatory": True,
        "phase4d": {
            "verdict": "PHASE4D_MEASUREMENT_SEMANTICS_AUDITED",
            "note": "retrospective atom-aware metric + safety-check decomposition on REALSTRUCT-1",
            "source_blob": CITED_BLOBS["artifacts/phase4d/measurement-semantics.json"],
        },
        "phase4j_reference_retention": {
            "n": retention["n"],
            "source_id": retention["source_id"],
            "BITE_v5": retention["BITE_v5"],
            "length_pi_v1": retention["length_pi_v1"],
            "delta": retention["delta"],
            "tie": retention["tie"],
            "does_not_rewrite_phase4i_n0": True,
            "source_blob": CITED_BLOBS[
                "artifacts/phase4j/legacy-vs-corrected-paired-reference.json"
            ],
        },
        "phase4j_reference_sensor": {
            "source_id": "rs2-ini-ahuacate-pve-medialab",
            "n_gold_bearing_documents": 1,
            "precision": sensor["precision"],
            "recall": sensor["recall"],
            "unadjudicated": sensor["unadjudicated"],
            "do_not_generalize_from_one_gold_document": True,
            "source_blob": CITED_BLOBS["artifacts/phase4j/corrected-atom-aware.json"],
        },
    }


def _claim_matrix() -> dict[str, Any]:
    return {
        "schema": "bite-phase4k-claim-matrix/v0.1",
        "supported": [
            {
                "claim": SUPPORTED_CLAIMS[0],
                "evidence_category": "real_corpus_safety_evidence",
                "n": "18/18",
            },
            {
                "claim": SUPPORTED_CLAIMS[1],
                "evidence_category": "prospective_realstruct2_comparison_evidence",
                "n": "1/18",
                "not_a_win_rate": True,
            },
            {
                "claim": SUPPORTED_CLAIMS[2],
                "evidence_category": "prospective_realstruct2_comparison_evidence",
                "n": 1,
                "n_prominence": "n=1",
            },
            {
                "claim": SUPPORTED_CLAIMS[3],
                "evidence_category": "retrospective_measurement_corrections",
                "n": 1,
                "n_prominence": "n=1",
                "not_a_new_first_open": True,
            },
        ],
        "unsupported": [{"claim": claim, "allowed": False} for claim in UNSUPPORTED_CLAIMS],
        "do_not_infer_unsupported_from_supported": True,
    }


def _timeline() -> dict[str, Any]:
    return {
        "schema": "bite-phase4k-historical-verdict-timeline/v0.1",
        "phase3q_remains": PHASE3Q_VERDICT,
        "phase3s_remains": PHASE3S_VERDICT,
        "later_repairs_do_not_erase_failures": True,
        "entries": [dict(row) for row in HISTORICAL_VERDICTS],
    }


def _compare_table() -> dict[str, Any]:
    facts = freeze_manifest()["prospective_realstruct2_facts"]
    retro = freeze_manifest()["retrospective_corrections"]
    return {
        "schema": "bite-phase4k-prospective-vs-retrospective/v0.1",
        "do_not_pool": True,
        "do_not_rewrite_historical_phase4i": True,
        "reference_retention": {
            "prospective_phase4i": {
                "n": facts["historical_reference_retention"]["n"],
                "status": facts["historical_reference_retention"]["status"],
                "reason": facts["historical_reference_retention"]["reason"],
            },
            "retrospective_phase4j": {
                "n": retro["reference_retention"]["n"],
                "source_id": retro["reference_retention"]["source_id"],
                "BITE_v5": retro["reference_retention"]["BITE_v5"],
                "length_pi_v1": retro["reference_retention"]["length_pi_v1"],
                "delta": retro["reference_retention"]["delta"],
                "tie": retro["reference_retention"]["tie"],
                "not_a_new_first_open": True,
            },
        },
        "reference_sensor_ahuacate": {
            "prospective_phase4i_recorded": {
                "atom_aware_precision": 0.0,
                "atom_aware_recall": "NA",
                "note": "legacy dest_lines reader; n_gold=0 under Phase4I scorer",
            },
            "retrospective_phase4j_corrected": {
                "precision": retro["reference_sensor_ahuacate"]["precision"],
                "recall": retro["reference_sensor_ahuacate"]["recall"],
                "unadjudicated": retro["reference_sensor_ahuacate"]["unadjudicated"],
                "not_a_new_first_open": True,
            },
        },
        "matched_budget_unique_identity": {
            "kind": "prospective_only",
            "n": facts["matched_budget_unique_identity"]["n"],
            "n_prominence": "n=1",
            "source_id": facts["matched_budget_unique_identity"]["source_id"],
            "BITE_v5": facts["matched_budget_unique_identity"]["BITE_v5"],
            "length_pi_v1": facts["matched_budget_unique_identity"]["length_pi_v1"],
            "delta": facts["matched_budget_unique_identity"]["delta"],
            "not_recomputed_in_phase4j": True,
        },
    }


def _limitations() -> dict[str, Any]:
    return {
        "schema": "bite-phase4k-known-limitations/v0.1",
        "items": [
            "REALSTRUCT-2 is a frozen convenience sample, not a representative population.",
            "Natural convenience sample produced sparse transformation: 17/18 documents had no BITE operator sequence.",
            "Reference-retention comparison was effectively n=1.",
            "Matched-budget evidence comparison was effectively n=1.",
            "Corrected atom-aware diagnostic rests on one gold-bearing document; do not generalize.",
            "These sparse-n observations are results, not protocol failures.",
            "Phase3Q FAILED and Phase3S FAILED remain; later versioned repairs do not erase them.",
            "p3f stays sealed and is not used to strengthen Phase 4 claims.",
            "Phase 4 does not support production-readiness, RAG superiority, or answer-quality claims.",
        ],
    }


def _wording() -> dict[str, Any]:
    return {
        "schema": "bite-phase4k-publication-safe-wording/v0.1",
        "allowed": list(SUPPORTED_CLAIMS),
        "phase4_conclusion": PHASE4_CONCLUSION,
        "forbidden": list(UNSUPPORTED_CLAIMS),
        "do_not_call_reduction_incidence_win_rate": True,
        "do_not_add_winner_conclusion": True,
        "do_not_state_p3f_result": True,
        "show_n_beside_every_comparative_result": True,
    }


def write_ledger(*, write: bool = True) -> dict[str, Any]:
    blocked = _blob_errors()
    try:
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
        blocked.append("p3f seal did not fire")
    except EvaluationSealError:
        pass
    blocked.extend(_verify_source_facts())
    ledger = {
        "schema": "bite-phase4k-evidence-ledger-body/v0.1",
        "do_not_pool_evidence_categories": True,
        "evidence_categories": list(EVIDENCE_CATEGORIES),
        "mechanism_evidence": _mechanism_evidence(),
        "real_corpus_safety_evidence": _safety_evidence(),
        "prospective_realstruct2_comparison_evidence": _prospective_evidence(),
        "retrospective_measurement_corrections": _retrospective_evidence(),
    }
    claims = _claim_matrix()
    timeline = _timeline()
    compare = _compare_table()
    limits = _limitations()
    wording = _wording()
    leak = any(
        _winner_leak(item) for item in (ledger, claims, timeline, compare, limits, wording)
    )
    if leak:
        blocked.append("winner key leaked")
    verdict = VERDICT_FROZEN if not blocked else VERDICT_BLOCKED
    result = {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "protocol_commit_sha": K0_COMMIT_SHA,
        "k0_freeze_blob": K0_FREEZE_BLOB,
        "phase4j_head_sha": PHASE4J_HEAD,
        "verdict": verdict,
        "paid_api": False,
        "offline": True,
        "documentation_only": True,
        "no_new_experiment": True,
        "research_conclusion": False,
        "premise": PREMISE,
        "p3f_evaluation_holdout_used": False,
        "no_p3f_result_statement": True,
        "no_arm_rerun": True,
        "no_tokenizer_execution": True,
        "no_sensor_replay": True,
        "no_bite_retune": True,
        "no_phase4a_to_4j_rewrite": True,
        "no_merge": True,
        "no_winner_score": True,
        "do_not_pool_evidence_categories": True,
        "phase4_conclusion": PHASE4_CONCLUSION,
        "claim_boundary": CLAIM_BOUNDARY,
        "cited_blobs_verified": not any("blob drifted" in err for err in blocked),
        "historical_verdicts_preserved": not any("verdict drifted" in err for err in blocked),
        "errors": blocked,
    }
    if write:
        _dump(LEDGER_PATH, ledger)
        _dump(CLAIMS_PATH, claims)
        _dump(TIMELINE_PATH, timeline)
        _dump(COMPARE_PATH, compare)
        _dump(LIMITS_PATH, limits)
        _dump(WORDING_PATH, wording)
        _dump(RESULT_PATH, result)
    return result


def validate_phase4k_result(doc: Mapping[str, Any]) -> list[str]:
    errs = _blob_errors()
    if doc.get("protocol_commit_sha") != K0_COMMIT_SHA:
        errs.append("K0 commit drifted")
    if doc.get("k0_freeze_blob") != K0_FREEZE_BLOB:
        errs.append("K0 freeze blob drifted")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f opened")
    if doc.get("no_p3f_result_statement") is not True:
        errs.append("p3f result statement flag drifted")
    if doc.get("documentation_only") is not True or doc.get("no_new_experiment") is not True:
        errs.append("documentation-only flag drifted")
    if doc.get("no_arm_rerun") is not True or doc.get("no_tokenizer_execution") is not True:
        errs.append("execution flags drifted")
    if doc.get("no_sensor_replay") is not True:
        errs.append("sensor replay flag drifted")
    if doc.get("no_phase4a_to_4j_rewrite") is not True:
        errs.append("rewrite flag drifted")
    if doc.get("no_merge") is not True:
        errs.append("merge flag drifted")
    if doc.get("no_winner_score") is not True:
        errs.append("winner score flag drifted")
    if _winner_leak(doc):
        errs.append("winner key leaked")
    if doc.get("phase4_conclusion") != PHASE4_CONCLUSION:
        errs.append("Phase 4 conclusion drifted")
    if doc.get("verdict") not in (VERDICT_FROZEN, VERDICT_BLOCKED):
        errs.append("unknown verdict")
    if doc.get("verdict") == VERDICT_FROZEN and doc.get("errors"):
        errs.append("FROZEN with errors")
    if LEDGER_PATH.is_file():
        ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
        if list(ledger.get("evidence_categories") or []) != list(EVIDENCE_CATEGORIES):
            errs.append("ledger categories drifted")
        if ledger.get("do_not_pool_evidence_categories") is not True:
            errs.append("ledger pooled categories")
        if _winner_leak(ledger):
            errs.append("ledger winner key leaked")
        for key in EVIDENCE_CATEGORIES:
            if key not in ledger:
                errs.append(f"missing evidence category: {key}")
    if COMPARE_PATH.is_file():
        compare = json.loads(COMPARE_PATH.read_text(encoding="utf-8"))
        hist = (compare.get("reference_retention") or {}).get("prospective_phase4i") or {}
        if hist.get("n") != 0 or hist.get("status") != "not_observed":
            errs.append("prospective-vs-retrospective rewrote Phase4I n=0")
        retro = (compare.get("reference_retention") or {}).get("retrospective_phase4j") or {}
        if retro.get("n") != 1:
            errs.append("retrospective reference n missing")
    if CLAIMS_PATH.is_file():
        claims = json.loads(CLAIMS_PATH.read_text(encoding="utf-8"))
        forbidden = {row["claim"] for row in claims.get("unsupported") or [] if isinstance(row, Mapping)}
        if forbidden != set(UNSUPPORTED_CLAIMS):
            errs.append("claim matrix unsupported set drifted")
    try:
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
        errs.append("p3f seal did not fire")
    except EvaluationSealError:
        pass
    return errs


if __name__ == "__main__":
    payload = write_ledger()
    print(payload["verdict"], "errors", payload["errors"])
