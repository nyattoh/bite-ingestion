"""Phase 4J retrospective reference-schema compatibility audit.

Does not rerun arms or the tokenizer. Does not retune BITE or length_pi_v1.
Does not rewrite Phase 4I artifacts. Does not open p3f.
Not a new first-open, confirmatory comparison, or BITE-superiority claim.
"""

from __future__ import annotations

import json
import statistics
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4i import (
    ARMS,
    LOCKED_T_HIGH,
    PRIMARY_IDS,
)
from bite_bench.phase4j import (
    ARM_ROWS_BLOB,
    AUGMENTED_ANNOTATIONS_BLOB,
    CLAIM_BOUNDARY,
    FREEZE_PATH,
    HISTORICAL_GOLD_READER_BLOB,
    I0_FREEZE_BLOB,
    LEGACY_PAIRED_REF_BLOB,
    MECHANISM_DIAGNOSTIC_BLOB,
    MODEL_VISIBLE_COST_BLOB,
    PAIRED_UNIQUE_BLOB,
    PHASE4I_HEAD,
    PHASE4I_RESULT_BLOB,
    PREMISE,
    PROTOCOL_FROZEN,
    VERDICT_AUDITED,
    VERDICT_BLOCKED,
    VERDICT_PARTIAL,
    freeze_manifest,
    validate_phase4j_freeze,
)
from bite_bench.realstruct1 import sha256_bytes
from bite_eval.atom_aware_reference import (
    GoldTriple,
    atom_aware_predictions,
    gold_triples,
    score_triples,
)
from bite_eval.gold_triples_v2 import GoldSchemaError, gold_triples_v2
from bite_eval.phase4f_metrics import serialize_routing
from bite_ingestion.adapters.realstruct1_adapter_v1 import AdapterError, adapt
from bite_ingestion.profilers.dependency_dispersion_v4 import measure as measure_v4

SCHEMA_ID = "bite-phase4j-reference-schema-audit/v0.1"
REVISION = "phase4j-reference-schema-audit-v0.1"
J0_COMMIT_SHA = "8e0ed24213238ae089fdba937b56082c02ad72be"
J0_FREEZE_BLOB = "731ffbc7db9652ad03928c3defdb775ca0b83c8e"
LEGACY_WHY = (
    "Phase4D reader expected dest_lines; REALSTRUCT-2 annotation uses dest_line."
)
_REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = _REPO / "artifacts" / "phase4j"
RESULT_PATH = ARTIFACT_DIR / "reference-schema-audit.json"
COMPAT_PATH = ARTIFACT_DIR / "annotation-compatibility.json"
PAIRED_PATH = ARTIFACT_DIR / "legacy-vs-corrected-paired-reference.json"
SENSOR_PATH = ARTIFACT_DIR / "sensor-replay.json"
ATOM_PATH = ARTIFACT_DIR / "corrected-atom-aware.json"
ARM_ROWS_PATH = _REPO / "artifacts" / "phase4i" / "arm-rows.json"
LEGACY_PAIRED_PATH = _REPO / "artifacts" / "phase4i" / "paired-reference-retention.json"
MECHANISM_PATH = _REPO / "artifacts" / "phase4i" / "mechanism-diagnostic.json"
ANNOTATIONS_PATH = _REPO / "corpora" / "realstruct-2" / "augmented-annotations.json"
RS2_RAW = _REPO / "corpora" / "realstruct-2" / "raw"
WINNER_KEYS = (
    "overall_score",
    "overall_winner",
    "best_arm",
    "arm_ranking",
    "win_rate",
    "superiority",
)
PHASE4I_LOCKED_RESULT_BLOBS = {
    "artifacts/phase4i/first-open.json": PHASE4I_RESULT_BLOB,
    "artifacts/phase4i/arm-rows.json": ARM_ROWS_BLOB,
    "artifacts/phase4i/paired-reference-retention.json": LEGACY_PAIRED_REF_BLOB,
    "artifacts/phase4i/paired-unique-identity.json": PAIRED_UNIQUE_BLOB,
    "artifacts/phase4i/model-visible-cost.json": MODEL_VISIBLE_COST_BLOB,
    "artifacts/phase4i/mechanism-diagnostic.json": MECHANISM_DIAGNOSTIC_BLOB,
    "corpora/realstruct-2/augmented-annotations.json": AUGMENTED_ANNOTATIONS_BLOB,
    "src/bite_eval/atom_aware_reference.py": HISTORICAL_GOLD_READER_BLOB,
    "benchmarks/spec/phase4i-first-open-freeze.json": I0_FREEZE_BLOB,
}


def _git_blob(path: str) -> str:
    return subprocess.check_output(["git", "hash-object", path], cwd=_REPO, text=True).strip()


def _dump(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(dict(doc), indent=2, sort_keys=True) + "\n").encode("utf-8"))


def _json_eq(left: object, right: object) -> bool:
    return json.loads(json.dumps(left)) == json.loads(json.dumps(right))


def source_record_id(source_id: str, line: int) -> str:
    return f"{source_id}-s{line:04d}"


def retention_from_recorded_ids(
    source_id: str,
    gold: Sequence[GoldTriple],
    visible_ids: set[str],
) -> float | str:
    if not gold:
        return "NA"
    hits = sum(
        1
        for src, _name, dest in gold
        if source_record_id(source_id, src) in visible_ids
        and source_record_id(source_id, dest) in visible_ids
    )
    return hits / len(gold)


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


def _blob_errors() -> list[str]:
    errs: list[str] = []
    if not FREEZE_PATH.is_file():
        return ["J0 freeze missing"]
    committed = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    errs.extend(validate_phase4j_freeze(committed))
    if freeze_manifest() != committed:
        errs.append("J0 freeze drifted from generator")
    if committed.get("verdict") != PROTOCOL_FROZEN:
        errs.append("J0 not frozen")
    if _git_blob("benchmarks/spec/phase4j-reference-schema-freeze.json") != J0_FREEZE_BLOB:
        errs.append("J0 freeze blob drifted")
    for path, expected in PHASE4I_LOCKED_RESULT_BLOBS.items():
        if _git_blob(path) != expected:
            errs.append(f"frozen blob drifted: {path}")
    return errs


def annotation_count_errors(doc: Mapping[str, Any], triples: Sequence[GoldTriple]) -> list[str]:
    errs: list[str] = []
    source_id = str(doc.get("source_id") or "")
    if "n_explicit_reference_edges" not in doc:
        return errs
    n_explicit = doc["n_explicit_reference_edges"]
    if not isinstance(n_explicit, int) or isinstance(n_explicit, bool):
        return [f"{source_id}: n_explicit_reference_edges must be integer"]
    if len(triples) != n_explicit:
        errs.append(
            f"{source_id}: canonical triple count {len(triples)} != n_explicit_reference_edges {n_explicit}"
        )
    if n_explicit > 0 and not triples:
        errs.append(f"{source_id}: n_explicit_reference_edges > 0 but canonical reader returned zero")
    return errs


def _canonicalize_annotations(
    documents: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, list[GoldTriple]], list[dict[str, Any]], list[str]]:
    gold_map: dict[str, list[GoldTriple]] = {}
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for doc in documents:
        source_id = str(doc.get("source_id") or "")
        historical = gold_triples(doc)
        try:
            triples = gold_triples_v2(doc)
        except GoldSchemaError as exc:
            errors.append(str(exc))
            rows.append(
                {
                    "source_id": source_id,
                    "n_explicit_reference_edges": doc.get("n_explicit_reference_edges"),
                    "n_canonical_triples": None,
                    "n_historical_gold_triples": len(historical),
                    "canonicalized": False,
                    "invariant_ok": False,
                }
            )
            continue
        count_errs = annotation_count_errors(doc, triples)
        errors.extend(count_errs)
        gold_map[source_id] = triples
        rows.append(
            {
                "source_id": source_id,
                "n_explicit_reference_edges": doc.get("n_explicit_reference_edges"),
                "n_canonical_triples": len(triples),
                "n_historical_gold_triples": len(historical),
                "canonicalized": True,
                "invariant_ok": not count_errs,
            }
        )
    return gold_map, rows, errors


def _track_a(
    arm_rows: Sequence[Mapping[str, Any]],
    gold_map: Mapping[str, Sequence[GoldTriple]],
    legacy: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    per_document: list[dict[str, Any]] = []
    ref_docs: list[dict[str, Any]] = []
    ref_deltas: list[float] = []
    ids = [str(row["source_id"]) for row in arm_rows]
    if ids != list(PRIMARY_IDS):
        errors.append("arm-rows primary IDs drifted")
    for row in arm_rows:
        source_id = str(row["source_id"])
        gold = list(gold_map.get(source_id) or [])
        arms_out: dict[str, float | str] = {}
        for arm in row.get("arms") or []:
            if not isinstance(arm, Mapping):
                errors.append(f"{source_id}: malformed arm row")
                continue
            arm_name = str(arm.get("arm") or "")
            if "visible_source_record_ids_v2" not in arm:
                errors.append(f"{source_id}/{arm_name}: missing visible_source_record_ids_v2")
                continue
            visible = {str(item) for item in arm["visible_source_record_ids_v2"]}
            arms_out[arm_name] = retention_from_recorded_ids(source_id, gold, visible)
        missing = [name for name in ARMS if name not in arms_out]
        if missing:
            errors.append(f"{source_id}: missing arms {missing}")
        per_document.append(
            {
                "source_id": source_id,
                "wave": row.get("wave"),
                "n_gold_triples": len(gold),
                "visible_reference_retention_v2": arms_out,
            }
        )
        if not gold or missing:
            continue
        bite_v = _as_float(arms_out.get("BITE_v5"))
        length_v = _as_float(arms_out.get("length_pi_v1"))
        if bite_v is None or length_v is None:
            continue
        delta = bite_v - length_v
        ref_docs.append(
            {
                "source_id": source_id,
                "wave": row.get("wave"),
                "bite_v5": bite_v,
                "length_pi_v1": length_v,
                "delta": delta,
            }
        )
        ref_deltas.append(delta)
    corrected = {
        "schema": "bite-phase4j-corrected-paired-reference-retention/v0.1",
        "metric": "visible_reference_retention_v2",
        "delta": "BITE_v5 - length_pi_v1",
        "eligible": "primary documents with gold_triples_v2 count > 0",
        "kind": "retrospective corrected reference-retention audit",
        "not_new_first_open": True,
        "not_confirmatory": True,
        "wave_is_provenance_only": True,
        "documents": ref_docs,
        **paired_summary(ref_deltas),
    }
    payload = {
        "schema": "bite-phase4j-legacy-vs-corrected-paired-reference/v0.1",
        "kind": "retrospective corrected reference-retention audit",
        "not_new_first_open": True,
        "not_confirmatory": True,
        "why": LEGACY_WHY,
        "phase4i_legacy_schema_reader_result": dict(legacy),
        "corrected": corrected,
        "per_document": per_document,
    }
    return payload, errors


def _track_f(
    arm_rows: Sequence[Mapping[str, Any]],
    gold_map: Mapping[str, Sequence[GoldTriple]],
    mechanism: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    errors: list[str] = []
    replay_docs: list[dict[str, Any]] = []
    atom_docs: list[dict[str, Any]] = []
    exact = True
    legacy_sensor = {
        str(row["source_id"]): dict(row)
        for row in mechanism.get("atom_aware_sensor") or []
        if isinstance(row, Mapping)
    }
    for row in arm_rows:
        source_id = str(row["source_id"])
        bite = _arm_of(row, "BITE_v5")
        recorded_n = bite.get("n_reference_edges")
        recorded_mean = bite.get("mean_reference_edge_distance")
        recorded_gate = bite.get("gate_result")
        if recorded_n is None or recorded_mean is None or recorded_gate is None:
            errors.append(f"{source_id}: BITE_v5 sensor fields missing")
            exact = False
            continue
        raw_path = RS2_RAW / source_id
        if not raw_path.is_file():
            errors.append(f"{source_id}: frozen raw missing")
            exact = False
            continue
        raw = raw_path.read_bytes()
        expected_sha = str(row.get("raw_sha256") or "")
        if expected_sha and sha256_bytes(raw) != expected_sha:
            errors.append(f"{source_id}: frozen raw sha256 drifted")
            exact = False
            continue
        try:
            adapted = adapt(raw, source_id=source_id)
        except AdapterError as exc:
            errors.append(f"{source_id}: adapter replay failed: {exc}")
            exact = False
            continue
        routing = list(adapted["routing_units"])
        adapter_visible = serialize_routing(routing)
        v4 = measure_v4({"payload": adapter_visible, "text": adapter_visible})
        replay_n = float(v4.features.get("n_reference_edges") or 0.0)
        replay_mean = float(v4.features.get("mean_reference_edge_distance") or 0.0)
        replay_gate = (not v4.fail_closed) and replay_n > 0.0 and replay_mean >= float(LOCKED_T_HIGH)
        match = (
            _json_eq(replay_n, recorded_n)
            and _json_eq(replay_mean, recorded_mean)
            and replay_gate is bool(recorded_gate)
        )
        if not match:
            exact = False
        replay_docs.append(
            {
                "source_id": source_id,
                "recorded_n_reference_edges": recorded_n,
                "replay_n_reference_edges": replay_n,
                "recorded_mean_reference_edge_distance": recorded_mean,
                "replay_mean_reference_edge_distance": replay_mean,
                "recorded_gate_result": recorded_gate,
                "replay_gate_result": replay_gate,
                "match": match,
            }
        )
        if not match:
            continue
        gold = list(gold_map.get(source_id) or [])
        pred, unadj = atom_aware_predictions(v4.edges, routing)
        sensor = score_triples(gold, pred)
        legacy = legacy_sensor.get(source_id) or {}
        atom_docs.append(
            {
                "source_id": source_id,
                "n_gold_triples": sensor["n_gold_triples"],
                "n_adjudicated_predictions": sensor["n_adjudicated_predictions"],
                "atom_aware_precision": sensor["atom_aware_precision"],
                "atom_aware_recall": sensor["atom_aware_recall"],
                "unadjudicated_extra_edges": unadj,
                "phase4i_legacy_atom_aware": {
                    "atom_aware_precision": legacy.get("atom_aware_precision"),
                    "atom_aware_recall": legacy.get("atom_aware_recall"),
                    "unadjudicated_extra_edges": legacy.get("unadjudicated_extra_edges"),
                },
            }
        )
    n_match = sum(1 for item in replay_docs if item["match"] is True)
    if n_match != len(PRIMARY_IDS) or len(replay_docs) != len(PRIMARY_IDS):
        exact = False
    sensor_payload = {
        "schema": "bite-phase4j-sensor-replay/v0.1",
        "sensor": "dependency_dispersion_v4",
        "no_policy": True,
        "no_operators": True,
        "no_tokenizer": True,
        "n_documents": len(replay_docs),
        "n_exact": n_match,
        "exact": exact and not errors,
        "documents": replay_docs,
    }
    if sensor_payload["exact"] is True:
        atom_payload = {
            "schema": "bite-phase4j-corrected-atom-aware/v0.1",
            "produced": True,
            "gold_reader": "gold_triples_v2",
            "sensor_replay_exact": True,
            "kind": "retrospective corrected atom-aware diagnostic",
            "not_new_first_open": True,
            "documents": atom_docs,
        }
    else:
        atom_payload = {
            "schema": "bite-phase4j-corrected-atom-aware/v0.1",
            "produced": False,
            "gold_reader": "gold_triples_v2",
            "sensor_replay_exact": False,
            "reason": "sensor replay not exact; corrected atom-aware scores withheld",
            "documents": [],
        }
    return sensor_payload, atom_payload, errors


def run_audit(*, write: bool = True) -> dict[str, Any]:
    blocked = _blob_errors()
    try:
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
        blocked.append("p3f seal did not fire")
    except EvaluationSealError:
        pass
    annotations = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    arm_blob = json.loads(ARM_ROWS_PATH.read_text(encoding="utf-8"))
    legacy = json.loads(LEGACY_PAIRED_PATH.read_text(encoding="utf-8"))
    mechanism = json.loads(MECHANISM_PATH.read_text(encoding="utf-8"))
    gold_map, compat_rows, schema_errors = _canonicalize_annotations(
        list(annotations.get("documents") or [])
    )
    blocked.extend(schema_errors)
    if int(legacy.get("n") or 0) != 0 or legacy.get("status") != "not_observed":
        blocked.append("Phase 4I legacy paired-reference rewritten")
    ids = [str(row["source_id"]) for row in arm_blob.get("documents") or []]
    if ids != list(PRIMARY_IDS):
        blocked.append("arm-rows document order drifted")
    if len(arm_blob.get("documents") or []) != len(PRIMARY_IDS):
        blocked.append("arm-rows incomplete")

    track_a_ok = False
    freeze_drift = any("drift" in err or "rewritten" in err for err in blocked)
    paired: dict[str, Any] = {
        "schema": "bite-phase4j-legacy-vs-corrected-paired-reference/v0.1",
        "produced": False,
        "why": LEGACY_WHY,
        "phase4i_legacy_schema_reader_result": dict(legacy),
        "corrected": {},
        "per_document": [],
    }
    sensor: dict[str, Any] = {
        "schema": "bite-phase4j-sensor-replay/v0.1",
        "exact": False,
        "documents": [],
    }
    atom: dict[str, Any] = {
        "schema": "bite-phase4j-corrected-atom-aware/v0.1",
        "produced": False,
        "documents": [],
        "reason": "withheld",
    }
    if not schema_errors:
        paired, a_errors = _track_a(list(arm_blob.get("documents") or []), gold_map, legacy)
        blocked.extend(a_errors)
        track_a_ok = not a_errors
        if track_a_ok and not freeze_drift:
            sensor, atom, f_errors = _track_f(
                list(arm_blob.get("documents") or []), gold_map, mechanism
            )
            blocked.extend(f_errors)

    sensor_exact = bool(sensor.get("exact") is True) and bool(atom.get("produced") is True)
    freeze_or_schema_blocked = (
        any("drift" in err or "rewritten" in err or "insufficient" in err for err in blocked)
        or bool(schema_errors)
        or not track_a_ok
    )
    if freeze_or_schema_blocked:
        verdict = VERDICT_BLOCKED
    elif sensor_exact:
        verdict = VERDICT_AUDITED
    elif track_a_ok:
        verdict = VERDICT_PARTIAL
    else:
        verdict = VERDICT_BLOCKED

    compat = {
        "schema": "bite-phase4j-annotation-compatibility/v0.1",
        "gold_reader": "gold_triples_v2",
        "historical_gold_reader": "gold_triples",
        "n_documents": len(compat_rows),
        "n_canonicalized": sum(1 for row in compat_rows if row["canonicalized"] is True),
        "invariant_ok": all(row["invariant_ok"] is True for row in compat_rows) and not schema_errors,
        "errors": schema_errors,
        "documents": compat_rows,
    }
    result = {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "protocol_commit_sha": J0_COMMIT_SHA,
        "j0_freeze_blob": J0_FREEZE_BLOB,
        "phase4i_head_sha": PHASE4I_HEAD,
        "verdict": verdict,
        "paid_api": False,
        "offline": True,
        "research_conclusion": False,
        "premise": PREMISE,
        "p3f_evaluation_holdout_used": False,
        "no_arm_rerun": True,
        "no_tokenizer_rerun": True,
        "no_bite_retune": True,
        "no_length_pi_retune": True,
        "no_corpus_change": True,
        "no_phase4i_rewrite": True,
        "no_winner_score": True,
        "phase4i_artifacts_unchanged": all(
            _git_blob(path) == expected for path, expected in PHASE4I_LOCKED_RESULT_BLOBS.items()
        ),
        "track_a_rescored": track_a_ok,
        "sensor_replay_exact": sensor_exact,
        "atom_aware_corrected_produced": bool(atom.get("produced") is True),
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "new holdout",
            "confirmatory comparison",
            "generalization",
            "BITE superiority",
        ],
        "errors": blocked,
    }
    if write:
        _dump(COMPAT_PATH, compat)
        _dump(PAIRED_PATH, paired)
        _dump(SENSOR_PATH, sensor)
        _dump(ATOM_PATH, atom)
        _dump(RESULT_PATH, result)
    return result


def validate_phase4j_result(doc: Mapping[str, Any]) -> list[str]:
    errs = _blob_errors()
    if doc.get("protocol_commit_sha") != J0_COMMIT_SHA:
        errs.append("J0 commit drifted")
    if doc.get("j0_freeze_blob") != J0_FREEZE_BLOB:
        errs.append("J0 freeze blob drifted")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f opened")
    if doc.get("no_arm_rerun") is not True or doc.get("no_tokenizer_rerun") is not True:
        errs.append("arm/tokenizer rerun flags drifted")
    if doc.get("no_phase4i_rewrite") is not True:
        errs.append("Phase 4I rewrite flag drifted")
    if doc.get("no_winner_score") is not True:
        errs.append("winner score flag drifted")
    if _winner_leak(doc):
        errs.append("winner key leaked")
    if doc.get("verdict") not in (VERDICT_AUDITED, VERDICT_PARTIAL, VERDICT_BLOCKED):
        errs.append("unknown verdict")
    if doc.get("verdict") == VERDICT_AUDITED:
        if doc.get("errors"):
            errs.append("AUDITED with errors")
        if doc.get("track_a_rescored") is not True:
            errs.append("AUDITED without Track A rescore")
        if doc.get("sensor_replay_exact") is not True:
            errs.append("AUDITED without exact sensor replay")
        if doc.get("atom_aware_corrected_produced") is not True:
            errs.append("AUDITED without corrected atom-aware")
        if doc.get("phase4i_artifacts_unchanged") is not True:
            errs.append("AUDITED while Phase 4I artifacts changed")
    if PAIRED_PATH.is_file():
        paired = json.loads(PAIRED_PATH.read_text(encoding="utf-8"))
        legacy = paired.get("phase4i_legacy_schema_reader_result") or {}
        if int(legacy.get("n") or 0) != 0 or legacy.get("status") != "not_observed":
            errs.append("legacy paired-reference not preserved")
        if paired.get("why") != LEGACY_WHY:
            errs.append("legacy why-text drifted")
        if _winner_leak(paired):
            errs.append("paired artifact winner key leaked")
    if ATOM_PATH.is_file():
        atom = json.loads(ATOM_PATH.read_text(encoding="utf-8"))
        if doc.get("verdict") == VERDICT_PARTIAL and atom.get("produced") is True:
            errs.append("PARTIAL must not emit corrected atom-aware scores")
        if doc.get("verdict") == VERDICT_AUDITED and atom.get("produced") is not True:
            errs.append("AUDITED missing corrected atom-aware")
    try:
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
        errs.append("p3f seal did not fire")
    except EvaluationSealError:
        pass
    return errs


if __name__ == "__main__":
    payload = run_audit()
    print(payload["verdict"], "track_a", payload["track_a_rescored"], "errors", payload["errors"])
