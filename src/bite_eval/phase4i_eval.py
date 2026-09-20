"""Phase 4I REALSTRUCT-2 first-open harness.

Preflight may run on frozen synthetic fixtures and REALSTRUCT-1 only.
REALSTRUCT-2 tokenizer/arms run only after I0, exactly once, with no retune.
Does not open p3f. Does not emit a winner score.
"""

from __future__ import annotations

import json
import statistics
import subprocess
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4d import AUDIT_SOURCE_IDS
from bite_bench.phase4f import TOKENIZER_JSON_SHA256
from bite_bench.phase4i import (
    ARMS,
    AUGMENTED_MANIFEST,
    CLAIM_BOUNDARY,
    FREEZE_PATH,
    HISTORICAL_MANIFEST,
    LOCKED_BLOBS,
    LOCKED_T_HIGH,
    N_PRIMARY,
    PHASE4H2_HEAD,
    PREMISE,
    PRIMARY_IDS,
    PROTOCOL_FROZEN,
    VERDICT_BLOCKED,
    VERDICT_FAILED,
    VERDICT_MEASURED,
    freeze_manifest,
    planned_preflight_cases,
    validate_phase4i_freeze,
)
from bite_bench.realstruct1 import RAW_DIR as RS1_RAW
from bite_bench.realstruct1 import sha256_bytes
from bite_eval.atom_aware_reference import atom_aware_predictions, gold_triples, score_triples
from bite_eval.composition_safety_v2 import composition_safety_v2
from bite_eval.length_pi_v1 import apply_length_pi_v1
from bite_eval.phase4f_metrics import complete_prefix_indices, serialize_routing
from bite_eval.recovery_bundle_v1 import (
    RecoveryError,
    account_bundle,
    build_recovery_bundle,
    flatten_visible_units,
    reconstruct,
)
from bite_eval.reference_tokenizer import (
    TokenizerError,
    load_reference_tokenizer,
    tokenizer_lock_record,
)
from bite_eval.visibility_metrics_v2 import (
    duplicate_diagnostic_v2,
    unique_assignment_identity_retention_v2,
    visible_reference_retention_v2,
    visible_source_record_ids_v2,
)
from bite_ingestion.adapters.realstruct1_adapter_v1 import (
    AdapterError,
    adapt,
    merge_full_source_after,
)
from bite_ingestion.packet_contract import visible_evidence_from_units
from bite_ingestion.policies.conditional_texture_policy_v5 import (
    ConditionalTexturePolicyV5,
    PolicyLeakError,
    assert_policy_gold_isolated,
)
from bite_ingestion.profilers.dependency_dispersion_v4 import measure as measure_v4

SCHEMA_ID = "bite-phase4i-first-open/v0.1"
REVISION = "phase4i-first-open-v0.1"
I0_FREEZE_BLOB = "260c5ae4847776c33d27ea6718466d1dd814abdf"
_REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = _REPO / "artifacts" / "phase4i"
RESULT_PATH = ARTIFACT_DIR / "first-open.json"
ARM_ROWS_PATH = ARTIFACT_DIR / "arm-rows.json"
PAIRED_REF_PATH = ARTIFACT_DIR / "paired-reference-retention.json"
PAIRED_ID_PATH = ARTIFACT_DIR / "paired-unique-identity.json"
COST_PATH = ARTIFACT_DIR / "model-visible-cost.json"
RECOVERY_PATH = ARTIFACT_DIR / "recovery-accounting.json"
SAFETY_PATH = ARTIFACT_DIR / "safety.json"
MECHANISM_PATH = ARTIFACT_DIR / "mechanism-diagnostic.json"
FAILURE_PATH = ARTIFACT_DIR / "failure-classification.json"
PREFLIGHT_PATH = ARTIFACT_DIR / "preflight.json"
RS2_RAW = _REPO / "corpora" / "realstruct-2" / "raw"
RS2_ANNOTATIONS = _REPO / "corpora" / "realstruct-2" / "augmented-annotations.json"
RS1_ANNOTATIONS = _REPO / "corpora" / "realstruct-1" / "annotations-v2.json"
RS1_MANIFEST = _REPO / "corpora" / "realstruct-1" / "manifest.json"
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


def i0_commit_sha() -> str:
    return subprocess.check_output(
        [
            "git",
            "log",
            "-1",
            "--format=%H",
            "--",
            "benchmarks/spec/phase4i-first-open-freeze.json",
        ],
        cwd=_REPO,
        text=True,
    ).strip()


def _dump(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(dict(doc), indent=2, sort_keys=True) + "\n").encode("utf-8"))


def _units(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = packet.get("units") or []
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return [dict(unit) for unit in raw if isinstance(unit, Mapping)]
    return []


def _tau_sequence(packet: Mapping[str, Any]) -> list[str]:
    tau = packet.get("tau")
    if isinstance(tau, Mapping):
        return [str(item) for item in list(tau.get("sequence") or [])]
    return []


def _projected_sequence(packet: Mapping[str, Any]) -> list[str]:
    tau = packet.get("tau")
    if not isinstance(tau, Mapping):
        return []
    plan = tau.get("projected_plan")
    if isinstance(plan, Mapping):
        return [str(item) for item in list(plan.get("projected_sequence") or [])]
    return []


def _blob_errors() -> list[str]:
    errs: list[str] = []
    if not FREEZE_PATH.is_file():
        return ["I0 freeze missing"]
    committed = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    errs.extend(validate_phase4i_freeze(committed))
    if freeze_manifest() != committed:
        errs.append("I0 freeze drifted from generator")
    if committed.get("verdict") != PROTOCOL_FROZEN:
        errs.append("I0 not frozen")
    if _git_blob("benchmarks/spec/phase4i-first-open-freeze.json") != I0_FREEZE_BLOB:
        errs.append("I0 freeze blob drifted")
    for path, expected in LOCKED_BLOBS.items():
        if _git_blob(path) != expected:
            errs.append(f"frozen blob drifted: {path}")
    return errs


def _conservation_ok(safety: Mapping[str, Any], unsupported_lost: int) -> bool:
    return (
        safety["provenance_completeness"] == 1.0
        and safety["lineage_recall"] == 1.0
        and safety["silent_loss"] == 0
        and list(safety["conservation_untraced"] or []) == []
        and unsupported_lost == 0
        and bool(safety["no_unrelated_overmerge"])
    )


def _recovery_row(
    *,
    raw: bytes,
    encoding: str,
    source_units: Sequence[Mapping[str, Any]],
    visible: str,
    complete_records: Sequence[str],
    payload_tokens: Any,
) -> dict[str, Any]:
    try:
        bundle = build_recovery_bundle(
            raw=raw,
            encoding=encoding,
            source_units=source_units,
            visible=visible,
            complete_records=complete_records,
        )
        reconstructed = reconstruct(visible, bundle)
        accounted = account_bundle(bundle, payload_tokens)
        return {
            **accounted,
            "raw_reconstruction_exact": reconstructed == raw,
            "reconstruct_sha256": sha256_bytes(reconstructed),
            "bundle_empty": not bundle,
        }
    except RecoveryError as exc:
        return {
            "recovery_bundle_bytes": 0,
            "recovery_bundle_tokens": 0,
            "recovery_metadata_bytes": 0,
            "recovery_content_bytes": 0,
            "raw_reconstruction_exact": False,
            "reconstruct_sha256": "",
            "bundle_empty": False,
            "recovery_error": str(exc),
        }


def _arm_metrics(
    routing: Sequence[Mapping[str, Any]],
    visible_ids: set[str],
    gold: Sequence[Any],
) -> dict[str, Any]:
    return {
        "visible_source_record_ids_v2": sorted(visible_ids),
        "visible_reference_retention_v2": visible_reference_retention_v2(
            gold, visible_ids, routing
        ),
        "unique_assignment_identity_retention_v2": unique_assignment_identity_retention_v2(
            routing, visible_ids
        ),
        **duplicate_diagnostic_v2(routing, visible_ids),
    }


def _r_counts(after: Mapping[str, Any]) -> dict[str, int]:
    blob = after.get("R") if isinstance(after.get("R"), Mapping) else {}
    entries = list((blob or {}).get("entries") or [])
    recoverable = [
        row
        for row in entries
        if isinstance(row, Mapping) and row.get("recoverable") is True
    ]
    return {"n_r_entries": len(entries), "n_r_recoverable": len(recoverable)}


def _operator_effects(sequence: Sequence[str]) -> dict[str, Any]:
    counts = Counter(sequence)
    return {
        "untangle": int(counts.get("UNTANGLE", 0)),
        "reduce_v2": int(counts.get("REDUCE_v2", 0)),
        "integrate": int(counts.get("INTEGRATE", 0)),
        "sequence": list(sequence),
    }


def _document_row(
    *,
    source_id: str,
    raw: bytes,
    gold: Mapping[str, Any],
    policy: ConditionalTexturePolicyV5,
    tokenizer: Any,
    family: str,
    wave: int | None,
    expected_sha: str,
) -> dict[str, Any]:
    refuse_p3f_evaluation(source_id)
    if sha256_bytes(raw) != expected_sha:
        raise PolicyLeakError(f"{source_id}: raw sha256 drifted")
    adapted = adapt(raw, source_id=source_id)
    encoding = str(adapted["encoding"])
    source_doc = str(adapted["source"]["document"])
    source_units = list(adapted["source"]["units"])
    routing = list(adapted["routing_packet"]["units"])
    adapter_visible = serialize_routing(routing)
    gold_list = gold_triples(gold)
    assert_policy_gold_isolated(adapted["routing_packet"])
    after = policy.apply(adapted["routing_packet"])
    bite_units = _units(after)
    bite_visible = serialize_routing(bite_units)
    bite_tokens = int(tokenizer.payload_tokens(bite_visible))
    length_row = apply_length_pi_v1(
        adapter_visible,
        bite_tokens,
        payload_tokens=tokenizer.payload_tokens,
        prefix_char_end=tokenizer.prefix_char_end,
    )
    length_visible = str(length_row["visible"])
    source_texts = [str(unit.get("text", "")) for unit in routing]
    n_prefix = len(complete_prefix_indices(source_texts, length_visible))
    actual = _tau_sequence(after)
    projected = _projected_sequence(after)
    v4 = measure_v4({"payload": adapter_visible, "text": adapter_visible})
    pred, unadj = atom_aware_predictions(v4.edges, routing)
    sensor = score_triples(gold_list, pred)
    source_units_full, full_r = merge_full_source_after(source_units, after)
    full_after = {
        "units": source_units_full,
        "visible_evidence": visible_evidence_from_units(source_units_full),
        "R": full_r,
        "irreversible_loss_ledger": after.get("irreversible_loss_ledger") or [],
        "untangle": after.get("untangle"),
        "integrate": after.get("integrate"),
        "document": source_doc,
    }
    gold_ids = [str(unit["unit_id"]) for unit in source_units]
    safety = composition_safety_v2(
        adapted["source_packet"], full_after, gold_ids=gold_ids, sequence=actual
    )
    unsupported_after = [
        unit
        for unit in source_units_full
        if unit.get("line_kind") and unit.get("line_kind") != "assignment"
    ]
    unsupported_lost = adapted["n_unsupported_passthrough"] - len(unsupported_after)
    bite_ok = _conservation_ok(safety, unsupported_lost)
    planner_ok = actual == projected
    n_edges = float(v4.features.get("n_reference_edges") or 0.0)
    mean_d = float(v4.features.get("mean_reference_edge_distance") or 0.0)
    gated = (not v4.fail_closed) and n_edges > 0.0 and mean_d >= float(LOCKED_T_HIGH)

    raw_ids = {str(unit.get("unit_id")) for unit in routing}
    length_ids = visible_source_record_ids_v2(
        routing, None, complete_visible_texts=source_texts[:n_prefix]
    )
    bite_ids = visible_source_record_ids_v2(routing, bite_units)

    def rec(visible: str, complete: Sequence[str]) -> dict[str, Any]:
        return _recovery_row(
            raw=raw,
            encoding=encoding,
            source_units=source_units,
            visible=visible,
            complete_records=complete,
            payload_tokens=tokenizer.payload_tokens,
        )

    raw_rec = rec(source_doc, [])
    adapter_rec = rec(adapter_visible, flatten_visible_units(routing))
    length_rec = rec(length_visible, source_texts[:n_prefix])
    bite_rec = rec(bite_visible, flatten_visible_units(bite_units))

    def arm_row(arm: str, visible: str, rec_row: Mapping[str, Any], ids: set[str]) -> dict[str, Any]:
        row = {
            "arm": arm,
            "model_visible_tokens": int(tokenizer.payload_tokens(visible)),
            "model_visible_chars": len(visible),
            **rec_row,
            **_arm_metrics(routing, ids, gold_list),
        }
        if arm == "length_pi_v1":
            row.update(
                {
                    "target_budget_tokens": length_row["target_budget_tokens"],
                    "actual_visible_tokens": length_row["actual_visible_tokens"],
                    "budget_slack_tokens": length_row["budget_slack_tokens"],
                    "budget_match_applicable": length_row["budget_match_applicable"],
                    "bite_expanded_or_no_reduction": length_row["bite_expanded_or_no_reduction"],
                    "visible_char_boundary": length_row["visible_char_boundary"],
                }
            )
        if arm == "BITE_v5":
            row.update(
                {
                    "n_reference_edges": n_edges,
                    "mean_reference_edge_distance": mean_d,
                    "gate_result": gated,
                    "projected_sequence": projected,
                    "actual_sequence": actual,
                    "operator_effects": _operator_effects(actual),
                    **_r_counts(after),
                    "atom_aware_precision": sensor["atom_aware_precision"],
                    "atom_aware_recall": sensor["atom_aware_recall"],
                    "unadjudicated_extra_edges": unadj,
                    "provenance_completeness": safety["provenance_completeness"],
                    "lineage_recall": safety["lineage_recall"],
                    "silent_loss": safety["silent_loss"],
                    "conservation_untraced": list(safety["conservation_untraced"] or []),
                    "unsupported_loss": unsupported_lost,
                    "no_unrelated_overmerge": bool(safety["no_unrelated_overmerge"]),
                    "planner_integrity": planner_ok,
                }
            )
        return row

    arms = [
        arm_row("raw_full", source_doc, raw_rec, raw_ids),
        arm_row("adapter_only", adapter_visible, adapter_rec, raw_ids),
        arm_row("length_pi_v1", length_visible, length_rec, length_ids),
        arm_row("BITE_v5", bite_visible, bite_rec, bite_ids),
    ]
    reconstruct_ok = all(bool(item["raw_reconstruction_exact"]) for item in arms)
    return {
        "source_id": source_id,
        "family": family,
        "wave": wave,
        "raw_sha256": expected_sha,
        "n_gold_reference": len(gold_list),
        "arms": arms,
        "reconstruct_ok": reconstruct_ok,
        "bite_conservation_ok": bite_ok,
        "planner_integrity": planner_ok,
        "no_winner_score": True,
    }


def _fixture_gold(spec: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_id": spec["case_id"],
        "explicit_reference_edges": list(spec.get("gold_edges") or []),
    }


def _fixture_raw(spec: Mapping[str, Any]) -> bytes:
    return "".join(f"{key}={value}\n" for key, value in spec["records"]).encode("utf-8")


def paired_summary(deltas: Sequence[float]) -> dict[str, Any]:
    if not deltas:
        return {
            "n": 0,
            "mean": "not_observed",
            "median": "not_observed",
            "positive": 0,
            "tie": 0,
            "negative": 0,
            "status": "not_observed",
        }
    values = [float(item) for item in deltas]
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "positive": sum(1 for item in values if item > 0),
        "tie": sum(1 for item in values if item == 0),
        "negative": sum(1 for item in values if item < 0),
        "status": "observed",
    }


def _arm_of(row: Mapping[str, Any], name: str) -> dict[str, Any]:
    return next(dict(arm) for arm in row["arms"] if arm["arm"] == name)


def _as_float(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _winner_leak(payload: object) -> bool:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if str(key) in WINNER_KEYS:
                return True
            if _winner_leak(value):
                return True
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        return any(_winner_leak(item) for item in payload)
    return False


def run_preflight(*, include_realstruct1: bool = False) -> dict[str, Any]:
    blocked = _blob_errors()
    tokenizer = None
    tok_error = None
    try:
        tokenizer = load_reference_tokenizer()
    except TokenizerError as exc:
        tok_error = str(exc)
        blocked.append(str(exc))
    tok_lock = tokenizer_lock_record(tokenizer, tok_error)
    policy = ConditionalTexturePolicyV5()
    fixtures: list[dict[str, Any]] = []
    rs1_rows: list[dict[str, Any]] = []
    if tokenizer is not None:
        try:
            for spec in planned_preflight_cases():
                case_id = str(spec["case_id"])
                if case_id.startswith("rs2-") or "realstruct-2" in case_id:
                    raise PolicyLeakError("preflight leaked REALSTRUCT-2")
                raw = _fixture_raw(spec)
                fixtures.append(
                    _document_row(
                        source_id=case_id,
                        raw=raw,
                        gold=_fixture_gold(spec),
                        policy=policy,
                        tokenizer=tokenizer,
                        family=str(spec["family"]),
                        wave=None,
                        expected_sha=sha256_bytes(raw),
                    )
                )
            if include_realstruct1:
                gold_map = {
                    str(row["source_id"]): row
                    for row in json.loads(RS1_ANNOTATIONS.read_text(encoding="utf-8"))["documents"]
                }
                sha_map = {
                    str(row["source_id"]): str(row["sha256"])
                    for row in json.loads(RS1_MANIFEST.read_text(encoding="utf-8"))["sources"]
                }
                for source_id in AUDIT_SOURCE_IDS:
                    raw = (RS1_RAW / source_id).read_bytes()
                    rs1_rows.append(
                        _document_row(
                            source_id=source_id,
                            raw=raw,
                            gold=gold_map[source_id],
                            policy=policy,
                            tokenizer=tokenizer,
                            family="realstruct-1",
                            wave=None,
                            expected_sha=sha_map[source_id],
                        )
                    )
        except (EvaluationSealError, AdapterError, PolicyLeakError) as exc:
            blocked.append(str(exc))
    fixtures_ok = bool(fixtures) and all(
        row["reconstruct_ok"] and row["bite_conservation_ok"] and row["planner_integrity"]
        for row in fixtures
    )
    rs1_ok = (not include_realstruct1) or (
        bool(rs1_rows)
        and all(
            row["reconstruct_ok"] and row["bite_conservation_ok"] and row["planner_integrity"]
            for row in rs1_rows
        )
    )
    tok_ok = tokenizer is not None and tokenizer.tokenizer_json_sha256 == TOKENIZER_JSON_SHA256
    result = {
        "schema": "bite-phase4i-preflight/v0.1",
        "realstruct2_executed": False,
        "n_fixtures": len(fixtures),
        "n_realstruct1": len(rs1_rows),
        "fixtures_ok": fixtures_ok,
        "realstruct1_ok": rs1_ok,
        "tokenizer_hash_verified": tok_ok,
        "errors": blocked,
        "tokenizer": tok_lock,
        "fixtures": fixtures,
        "realstruct1": rs1_rows,
    }
    _dump(PREFLIGHT_PATH, result)
    return result


def _load_rs2_sources() -> list[dict[str, Any]]:
    aug = json.loads(AUGMENTED_MANIFEST.read_text(encoding="utf-8"))
    historical = json.loads(HISTORICAL_MANIFEST.read_text(encoding="utf-8"))
    if int(historical.get("n_primary") or 0) != 10:
        raise PolicyLeakError("historical 10-document manifest rewritten")
    rows = [
        dict(row)
        for row in aug.get("sources") or []
        if isinstance(row, Mapping) and row.get("stratum") == "primary"
    ]
    ids = [str(row["source_id"]) for row in rows]
    if ids != list(PRIMARY_IDS):
        raise PolicyLeakError("must use augmented-manifest primary IDs only")
    return rows


def run_first_open() -> dict[str, Any]:
    blocked = _blob_errors()
    i0_sha = i0_commit_sha()
    if not i0_sha:
        blocked.append("I0 freeze not committed; first-open is forbidden")
    tokenizer = None
    tok_error = None
    try:
        tokenizer = load_reference_tokenizer()
    except TokenizerError as exc:
        tok_error = str(exc)
        blocked.append(str(exc))
    tok_lock = tokenizer_lock_record(tokenizer, tok_error)
    if tok_lock.get("observed_sha256") != TOKENIZER_JSON_SHA256:
        blocked.append("tokenizer hash mismatch; abort before corpus execution")
        tokenizer = None
    gold_map = {
        str(row["source_id"]): row
        for row in json.loads(RS2_ANNOTATIONS.read_text(encoding="utf-8"))["documents"]
    }
    rows: list[dict[str, Any]] = []
    execution_failures: list[str] = []
    policy = ConditionalTexturePolicyV5()
    if tokenizer is not None and i0_sha:
        try:
            sources = _load_rs2_sources()
            for source in sources:
                source_id = str(source["source_id"])
                raw_path = RS2_RAW / source_id
                rows.append(
                    _document_row(
                        source_id=source_id,
                        raw=raw_path.read_bytes(),
                        gold=gold_map[source_id],
                        policy=policy,
                        tokenizer=tokenizer,
                        family=str(source["family"]),
                        wave=int(source["wave"]),
                        expected_sha=str(source["sha256"]),
                    )
                )
        except (EvaluationSealError, AdapterError, PolicyLeakError, OSError) as exc:
            execution_failures.append(str(exc))
            blocked.append(str(exc))
    n_docs = len(rows)
    n_arms = sum(len(row["arms"]) for row in rows)
    reconstruct_ok = bool(rows) and all(row["reconstruct_ok"] for row in rows)
    bite_ok = bool(rows) and all(row["bite_conservation_ok"] for row in rows)
    planner_ok = bool(rows) and all(row["planner_integrity"] for row in rows)
    tok_ok = tokenizer is not None and tok_lock.get("hash_verified") is True
    complete = n_docs == N_PRIMARY and n_arms == N_PRIMARY * len(ARMS)
    lock_drift = any(
        "drift" in err or "sealed" in err or "mismatch" in err or "rewritten" in err
        for err in blocked
    )
    if lock_drift or not i0_sha:
        verdict = VERDICT_BLOCKED
    elif complete and reconstruct_ok and bite_ok and planner_ok and tok_ok and not blocked:
        verdict = VERDICT_MEASURED
    else:
        verdict = VERDICT_FAILED

    paired_a, paired_b, cost, recovery, safety, mechanism = _summaries(rows)
    factual = _factual_statements(paired_a, paired_b, cost)
    failure = _failure_classification(
        verdict=verdict,
        reconstruct_ok=reconstruct_ok,
        bite_ok=bite_ok,
        planner_ok=planner_ok,
        complete=complete,
        blocked=blocked,
        execution_failures=execution_failures,
    )
    result = {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "protocol_commit_sha": i0_sha,
        "i0_freeze_blob": I0_FREEZE_BLOB,
        "phase4h2_head_sha": PHASE4H2_HEAD,
        "verdict": verdict,
        "paid_api": False,
        "offline": True,
        "research_conclusion": False,
        "premise": PREMISE,
        "p3f_evaluation_holdout_used": False,
        "no_winner_score": True,
        "no_wave1_vs_wave2_outcome": True,
        "no_bite_retune": True,
        "no_harness_modification_after_i0": True,
        "t_high_reference": LOCKED_T_HIGH,
        "arms": list(ARMS),
        "n_documents": n_docs,
        "n_arm_rows": n_arms,
        "tokenizer_hash_verified": tok_ok,
        "raw_reconstruction_exact": reconstruct_ok,
        "bite_safety_ok": bite_ok,
        "planner_integrity_ok": planner_ok,
        "errors": blocked,
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "representative real-world sample",
            "population generalization",
            "downstream answer-quality evidence",
            "BITE superiority",
        ],
        "factual_statements": factual,
        "acquisition_design": (
            "two-wave prospective acquisition; wave 2 added after quota shortfall, "
            "before any comparison-arm or tokenizer execution"
        ),
    }
    if _winner_leak(result) or _winner_leak(rows):
        blocked.append("winner score present")
        result["errors"] = blocked
        result["verdict"] = VERDICT_BLOCKED
    _dump(
        ARM_ROWS_PATH,
        {
            "schema": "bite-phase4i-arm-rows/v0.1",
            "n_documents": n_docs,
            "n_arm_rows": n_arms,
            "documents": rows,
        },
    )
    _dump(PAIRED_REF_PATH, paired_a)
    _dump(PAIRED_ID_PATH, paired_b)
    _dump(COST_PATH, cost)
    _dump(RECOVERY_PATH, recovery)
    _dump(SAFETY_PATH, safety)
    _dump(MECHANISM_PATH, mechanism)
    _dump(FAILURE_PATH, failure)
    _dump(RESULT_PATH, result)
    return result


def _summaries(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    ref_docs: list[dict[str, Any]] = []
    ref_deltas: list[float] = []
    for row in rows:
        if int(row.get("n_gold_reference") or 0) <= 0:
            continue
        bite = _arm_of(row, "BITE_v5")
        length = _arm_of(row, "length_pi_v1")
        bite_v = _as_float(bite.get("visible_reference_retention_v2"))
        length_v = _as_float(length.get("visible_reference_retention_v2"))
        if bite_v is None or length_v is None:
            continue
        delta = bite_v - length_v
        ref_docs.append(
            {
                "source_id": row["source_id"],
                "wave": row.get("wave"),
                "bite_v5": bite_v,
                "length_pi_v1": length_v,
                "delta": delta,
            }
        )
        ref_deltas.append(delta)
    paired_a = {
        "schema": "bite-phase4i-paired-reference-retention/v0.1",
        "metric": "visible_reference_retention_v2",
        "delta": "BITE_v5 - length_pi_v1",
        "eligible": "primary documents with reference gold > 0",
        "wave_is_provenance_only": True,
        "documents": ref_docs,
        **paired_summary(ref_deltas),
    }

    ident_docs: list[dict[str, Any]] = []
    ident_deltas: list[float] = []
    matched_ids: list[str] = []
    for row in rows:
        length = _arm_of(row, "length_pi_v1")
        if length.get("budget_match_applicable") is not True:
            continue
        matched_ids.append(str(row["source_id"]))
        bite = _arm_of(row, "BITE_v5")
        bite_v = _as_float(bite.get("unique_assignment_identity_retention_v2"))
        length_v = _as_float(length.get("unique_assignment_identity_retention_v2"))
        if bite_v is None or length_v is None:
            continue
        delta = bite_v - length_v
        ident_docs.append(
            {
                "source_id": row["source_id"],
                "wave": row.get("wave"),
                "bite_v5": bite_v,
                "length_pi_v1": length_v,
                "delta": delta,
            }
        )
        ident_deltas.append(delta)
    paired_b = {
        "schema": "bite-phase4i-paired-unique-identity/v0.1",
        "metric": "unique_assignment_identity_retention_v2",
        "delta": "BITE_v5 - length_pi_v1",
        "matched_budget_subset": matched_ids,
        "matched_budget_definition": (
            "primary documents where length_pi_v1.budget_match_applicable == true; "
            "do not redefine after results"
        ),
        "wave_is_provenance_only": True,
        "documents": ident_docs,
        **paired_summary(ident_deltas),
    }

    cost_docs = []
    reduction = 0
    for row in rows:
        tokens = {arm["arm"]: int(arm["model_visible_tokens"]) for arm in row["arms"]}
        if tokens["BITE_v5"] < tokens["adapter_only"]:
            reduction += 1
        cost_docs.append(
            {
                "source_id": row["source_id"],
                "family": row["family"],
                "wave": row.get("wave"),
                "raw_full": tokens["raw_full"],
                "adapter_only": tokens["adapter_only"],
                "length_pi_v1": tokens["length_pi_v1"],
                "BITE_v5": tokens["BITE_v5"],
            }
        )
    cost = {
        "schema": "bite-phase4i-model-visible-cost/v0.1",
        "unit": "reference-tokenizer payload tokens",
        "bite_reduction_incidence": reduction,
        "bite_reduction_incidence_definition": (
            "count of primary documents where BITE_v5 tokens < adapter_only tokens"
        ),
        "not_a_win_rate": True,
        "n_primary": len(rows),
        "documents": cost_docs,
    }

    recovery_docs = []
    for row in rows:
        recovery_docs.append(
            {
                "source_id": row["source_id"],
                "arms": {
                    arm["arm"]: {
                        "recovery_bundle_bytes": arm["recovery_bundle_bytes"],
                        "recovery_bundle_tokens": arm["recovery_bundle_tokens"],
                        "recovery_metadata_bytes": arm["recovery_metadata_bytes"],
                        "recovery_content_bytes": arm["recovery_content_bytes"],
                    }
                    for arm in row["arms"]
                },
            }
        )
    recovery = {
        "schema": "bite-phase4i-recovery-accounting/v0.1",
        "do_not_combine_with_visible_cost": True,
        "documents": recovery_docs,
    }

    safety_docs = []
    n_recon = 0
    n_bite = 0
    n_plan = 0
    n_arm_slots = 0
    for row in rows:
        per_arm = {}
        for arm in row["arms"]:
            n_arm_slots += 1
            exact = bool(arm["raw_reconstruction_exact"])
            if exact:
                n_recon += 1
            entry = {"raw_reconstruction_exact": exact}
            if arm["arm"] == "BITE_v5":
                bite_pass = (
                    exact
                    and arm["provenance_completeness"] == 1.0
                    and arm["lineage_recall"] == 1.0
                    and arm["silent_loss"] == 0
                    and list(arm["conservation_untraced"] or []) == []
                    and arm["unsupported_loss"] == 0
                    and arm["no_unrelated_overmerge"] is True
                    and arm["actual_sequence"] == arm["projected_sequence"]
                )
                if bite_pass:
                    n_bite += 1
                if arm["planner_integrity"] is True:
                    n_plan += 1
                entry.update(
                    {
                        "provenance_completeness": arm["provenance_completeness"],
                        "lineage_recall": arm["lineage_recall"],
                        "silent_loss": arm["silent_loss"],
                        "conservation_untraced": arm["conservation_untraced"],
                        "unsupported_loss": arm["unsupported_loss"],
                        "no_unrelated_overmerge": arm["no_unrelated_overmerge"],
                        "planner_integrity": arm["planner_integrity"],
                    }
                )
            per_arm[arm["arm"]] = entry
        safety_docs.append({"source_id": row["source_id"], "arms": per_arm})
    safety = {
        "schema": "bite-phase4i-safety/v0.1",
        "n_arm_reconstruction_exact": n_recon,
        "n_arm_slots": n_arm_slots,
        "n_bite_safety_pass": n_bite,
        "n_planner_integrity_pass": n_plan,
        "not_a_weighted_score": True,
        "documents": safety_docs,
    }

    routes = Counter()
    gates = 0
    reduce_descriptive = []
    sensor_rows = []
    for row in rows:
        bite = _arm_of(row, "BITE_v5")
        seq = tuple(bite.get("actual_sequence") or [])
        routes[json.dumps(list(seq))] += 1
        if bite.get("gate_result") is True:
            gates += 1
        dup = bite.get("duplicate_groups_collapsed") or 0
        reduce_descriptive.append(
            {
                "source_id": row["source_id"],
                "reduce_in_sequence": "REDUCE_v2" in list(bite.get("actual_sequence") or []),
                "source_exact_duplicate_groups": bite.get("source_exact_duplicate_groups"),
                "visible_duplicate_excess": bite.get("visible_duplicate_excess"),
                "duplicate_groups_collapsed": dup,
            }
        )
        sensor_rows.append(
            {
                "source_id": row["source_id"],
                "atom_aware_precision": bite.get("atom_aware_precision"),
                "atom_aware_recall": bite.get("atom_aware_recall"),
                "unadjudicated_extra_edges": bite.get("unadjudicated_extra_edges"),
            }
        )
    mechanism = {
        "schema": "bite-phase4i-mechanism-diagnostic/v0.1",
        "not_a_comparison_outcome": True,
        "route_sequence_frequency": [
            {"sequence": json.loads(key), "n": count} for key, count in sorted(routes.items())
        ],
        "gate_incidence": gates,
        "atom_aware_sensor": sensor_rows,
        "exact_duplicate_reduce_descriptive": reduce_descriptive,
        "do_not_add_reduce_to_overall_score": True,
    }
    return paired_a, paired_b, cost, recovery, safety, mechanism


def _factual_statements(
    paired_a: Mapping[str, Any],
    paired_b: Mapping[str, Any],
    cost: Mapping[str, Any],
) -> list[str]:
    n_primary = int(cost.get("n_primary") or 0)
    incidence = int(cost.get("bite_reduction_incidence") or 0)
    statements = [
        f"BITE used fewer model-visible tokens on {incidence}/{n_primary} documents."
    ]
    n_ref = int(paired_a.get("n") or 0)
    if n_ref == 0:
        statements.append(
            "On the n eligible reference-gold documents, the observed retention delta was not_observed."
        )
    else:
        statements.append(
            "On the n eligible reference-gold documents, "
            f"the observed retention delta was n={n_ref} mean={paired_a['mean']} "
            f"median={paired_a['median']} "
            f"positive={paired_a['positive']} tie={paired_a['tie']} "
            f"negative={paired_a['negative']}."
        )
    n_id = int(paired_b.get("n") or 0)
    if n_id == 0:
        statements.append(
            "At matched budget, unique identity retention differed by not_observed."
        )
    else:
        statements.append(
            "At matched budget, unique identity retention differed by "
            f"n={n_id} mean={paired_b['mean']} median={paired_b['median']} "
            f"positive={paired_b['positive']} tie={paired_b['tie']} "
            f"negative={paired_b['negative']}."
        )
    return statements


def _failure_classification(
    *,
    verdict: str,
    reconstruct_ok: bool,
    bite_ok: bool,
    planner_ok: bool,
    complete: bool,
    blocked: Sequence[str],
    execution_failures: Sequence[str],
) -> dict[str, Any]:
    failures: list[str] = []
    classification = "none"
    if verdict == VERDICT_BLOCKED:
        classification = "protocol"
        failures.extend(blocked)
    elif verdict == VERDICT_FAILED:
        if not complete or execution_failures:
            classification = "arm_incomplete"
            failures.extend(execution_failures or ["arm/document incomplete"])
        elif not reconstruct_ok:
            classification = "reconstruction"
            failures.append("raw reconstruction not exact")
        elif not bite_ok:
            classification = "safety_invariant"
            failures.append("BITE safety invariant failed")
        elif not planner_ok:
            classification = "planner"
            failures.append("planner integrity failed")
        else:
            classification = "arm_incomplete"
            failures.extend(blocked or ["unclassified failure"])
    return {
        "schema": "bite-phase4i-failure-classification/v0.1",
        "verdict": verdict,
        "classification": classification,
        "failures": failures,
    }


def validate_phase4i_result(doc: Mapping[str, Any]) -> list[str]:
    errs = _blob_errors()
    committed_i0 = i0_commit_sha()
    if committed_i0 and doc.get("protocol_commit_sha") != committed_i0:
        errs.append("I0 commit drifted")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f opened")
    if doc.get("no_winner_score") is not True:
        errs.append("winner score flag drifted")
    if doc.get("no_wave1_vs_wave2_outcome") is not True:
        errs.append("wave comparison flag drifted")
    if doc.get("t_high_reference") != LOCKED_T_HIGH:
        errs.append("T_high drifted")
    if doc.get("verdict") == VERDICT_MEASURED:
        if doc.get("errors"):
            errs.append("MEASURED with errors")
        if int(doc.get("n_documents") or 0) != N_PRIMARY:
            errs.append("MEASURED without 18 documents")
        if int(doc.get("n_arm_rows") or 0) != N_PRIMARY * len(ARMS):
            errs.append("MEASURED without 18x4 arm rows")
        if doc.get("tokenizer_hash_verified") is not True:
            errs.append("MEASURED without tokenizer hash")
        if doc.get("raw_reconstruction_exact") is not True:
            errs.append("MEASURED without reconstruction")
        if doc.get("bite_safety_ok") is not True:
            errs.append("MEASURED without BITE safety")
        if doc.get("planner_integrity_ok") is not True:
            errs.append("MEASURED without planner integrity")
    return errs


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "preflight"
    if mode == "first-open":
        payload = run_first_open()
        print(payload["verdict"], "docs", payload["n_documents"], "errors", payload["errors"])
    else:
        include_rs1 = mode == "preflight-rs1"
        payload = run_preflight(include_realstruct1=include_rs1)
        print(
            "preflight",
            "fixtures",
            payload["n_fixtures"],
            "rs1",
            payload["n_realstruct1"],
            "ok",
            payload["fixtures_ok"],
            "errors",
            payload["errors"],
        )
