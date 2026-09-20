"""Phase 4G comparison-measurement amendment.

Does not rewrite Phase 4F artifacts. Does not retune BITE or length_pi_v1.
Does not open p3f. Does not acquire REALSTRUCT-2.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4d import AUDIT_SOURCE_IDS
from bite_bench.phase4f import TOKENIZER_JSON_SHA256
from bite_bench.phase4g import (
    ARMS,
    CLAIM_BOUNDARY,
    F0_FREEZE_BLOB,
    FIXTURE_FAMILIES,
    FREEZE_PATH,
    LOCKED_BLOBS,
    LOCKED_T_HIGH,
    PHASE3Q_VERDICT,
    PHASE3S_VERDICT,
    PHASE3T_VERDICT,
    PHASE4C_VERDICT,
    PHASE4D_VERDICT,
    PHASE4E_VERDICT,
    PHASE4F_HEAD,
    PREMISE,
    PROTOCOL_FROZEN,
    VERDICT_BLOCKED,
    VERDICT_PARTIAL,
    VERDICT_VALIDATED,
    freeze_manifest,
    planned_cases,
    validate_phase4g_freeze,
)
from bite_bench.realstruct1 import RAW_DIR, sha256_bytes
from bite_eval.atom_aware_reference import gold_triples
from bite_eval.length_pi_v1 import apply_length_pi_v1
from bite_eval.phase4f_metrics import complete_prefix_indices, serialize_routing
from bite_eval.recovery_bundle_v1 import (
    RecoveryError,
    account_bundle,
    build_recovery_bundle,
    flatten_visible_units,
    reconstruct,
)
from bite_eval.reference_tokenizer import TokenizerError, load_reference_tokenizer
from bite_eval.visibility_metrics_v2 import (
    duplicate_diagnostic_v2,
    unique_assignment_identity_retention_v2,
    visible_reference_retention_v2,
    visible_source_record_ids_v2,
)
from bite_ingestion.adapters.realstruct1_adapter_v1 import AdapterError, adapt
from bite_ingestion.operators.integrate import IntegrateOperator
from bite_ingestion.operators.reduce_v2 import LogicalReduceOperatorV2
from bite_ingestion.operators.untangle import UntangleOperator
from bite_ingestion.packet_contract import make_composite_provenance, make_envelope_span
from bite_ingestion.policies.conditional_texture_policy_v5 import (
    ConditionalTexturePolicyV5,
    PolicyLeakError,
    assert_policy_gold_isolated,
)
from bite_ingestion.profilers.dependency_dispersion_v4 import measure as measure_v4

SCHEMA_ID = "bite-phase4g-comparison-accounting/v0.1"
REVISION = "phase4g-comparison-accounting-v0.1"
G0_COMMIT_SHA = "df096829d7178e6d33094494e93712fde37580b5"
G0_FREEZE_BLOB = "b74b591f61a030134fb35272e20f01bceea295bf"
_REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = _REPO / "artifacts" / "phase4g"
RESULT_PATH = ARTIFACT_DIR / "comparison-accounting.json"
RECOVERY_PATH = ARTIFACT_DIR / "recovery-reconstruction.json"
INTEGRATE_PATH = ARTIFACT_DIR / "integrate-visibility.json"
RETRO_PATH = ARTIFACT_DIR / "realstruct1-retrospective.json"
MAP_PATH = ARTIFACT_DIR / "legacy-vs-v2.json"
PHASE4F_DEV = _REPO / "artifacts" / "phase4f" / "realstruct1-development.json"
V2_PATH = _REPO / "corpora" / "realstruct-1" / "annotations-v2.json"
MANIFEST_PATH = _REPO / "corpora" / "realstruct-1" / "manifest.json"


def _git_blob(path: str) -> str:
    return subprocess.check_output(["git", "hash-object", path], cwd=_REPO, text=True).strip()


def _dump(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(dict(doc), indent=2, sort_keys=True) + "\n").encode("utf-8"))


def _units(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = packet.get("units") or []
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return [dict(unit) for unit in raw if isinstance(unit, Mapping)]
    return []


def _blob_errors() -> list[str]:
    errs: list[str] = []
    if not FREEZE_PATH.is_file():
        return ["G0 freeze missing"]
    committed = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    errs.extend(validate_phase4g_freeze(committed))
    if freeze_manifest() != committed:
        errs.append("G0 freeze drifted from generator")
    if committed.get("verdict") != PROTOCOL_FROZEN:
        errs.append("G0 not frozen")
    if _git_blob("benchmarks/spec/phase4g-comparison-accounting-freeze.json") != G0_FREEZE_BLOB:
        errs.append("G0 freeze blob drifted")
    if _git_blob("benchmarks/spec/phase4f-prospective-comparison-freeze.json") != F0_FREEZE_BLOB:
        errs.append("F0 freeze blob drifted")
    for path, expected in LOCKED_BLOBS.items():
        if _git_blob(path) != expected:
            errs.append(f"frozen blob drifted: {path}")
    if (_REPO / "corpora" / "realstruct-2").exists():
        errs.append("REALSTRUCT-2 present")
    return errs


def _apply_sequence(packet: Mapping[str, Any], sequence: Sequence[str]) -> dict[str, Any]:
    out = dict(packet)
    for name in sequence:
        if name == "REDUCE_v2":
            out = dict(LogicalReduceOperatorV2().apply(out))
        elif name == "UNTANGLE":
            out = dict(UntangleOperator().apply(out))
        elif name == "INTEGRATE":
            out = dict(IntegrateOperator().apply(out))
        else:
            raise PolicyLeakError(f"forbidden fixture operator {name}")
    return out


def _recovery_row(
    *,
    raw: bytes,
    encoding: str,
    source_units: Sequence[Mapping[str, Any]],
    visible: str,
    complete_records: Sequence[str],
    payload_tokens: Any,
    legacy_bytes: int,
    legacy_tokens: int,
) -> dict[str, Any]:
    bundle = build_recovery_bundle(
        raw=raw,
        encoding=encoding,
        source_units=source_units,
        visible=visible,
        complete_records=complete_records,
    )
    accounted = account_bundle(bundle, payload_tokens)
    reconstructed = reconstruct(visible, bundle)
    return {
        **accounted,
        "arm_local_sidecar_bytes_legacy": legacy_bytes,
        "arm_local_sidecar_tokens_legacy": legacy_tokens,
        "reconstruct_sha256": sha256_bytes(reconstructed),
        "raw_sha256": sha256_bytes(raw),
        "reconstruct_ok": reconstructed == raw,
        "bundle_empty": not bundle,
    }


def _synthetic_visible(
    spec: Mapping[str, Any], routing: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    family = str(spec["family"])
    bodies = [str(unit.get("text", "")) for unit in routing]
    ids = [str(unit.get("unit_id")) for unit in routing]
    if family == "neg_partial_text":
        return [{"unit_id": ids[0], "text": str(spec.get("visible_text") or "")}]
    if family == "neg_lineage_without_text":
        records = [
            {"unit_id": ids[0], "source_uri": "p4g://neg", "byte_or_token_span": "char:0-1"},
            {"unit_id": ids[1], "source_uri": "p4g://neg", "byte_or_token_span": "char:2-3"},
        ]
        return [
            {
                "unit_id": "p4g-neg-join",
                "text": "not_the_source_records",
                "joined_from": ids[:2],
                "span": make_envelope_span(routing[:2]),
                "provenance": make_composite_provenance(records),
            }
        ]
    if family == "neg_text_without_lineage":
        return [{"unit_id": "p4g-neg-anon", "text": "\n".join(bodies)}]
    raise PolicyLeakError(f"unknown synthetic family {family}")


def _run_fixture(spec: Mapping[str, Any], payload_tokens: Any) -> dict[str, Any]:
    case_id = str(spec["case_id"])
    refuse_p3f_evaluation(case_id)
    records = [(str(left), str(right)) for left, right in spec["records"]]
    raw = "".join(f"{key}={value}\n" for key, value in records).encode("utf-8")
    adapted = adapt(raw, source_id=case_id)
    source_units = list(adapted["source"]["units"])
    routing = list(adapted["routing_packet"]["units"])
    expected = {str(routing[i]["unit_id"]) for i in spec["expected_visible_indices"]}
    encoding = str(adapted["encoding"])
    if spec["mode"] == "synthetic_visible":
        visible_units = _synthetic_visible(spec, routing)
        after_seq: list[str] = []
    else:
        after = _apply_sequence(adapted["routing_packet"], list(spec.get("sequence") or []))
        visible_units = _units(after)
        after_seq = list(spec.get("sequence") or [])
    visible = serialize_routing(visible_units)
    complete = flatten_visible_units(visible_units)
    visible_ids = visible_source_record_ids_v2(routing, visible_units)
    recovery = _recovery_row(
        raw=raw,
        encoding=encoding,
        source_units=source_units,
        visible=visible,
        complete_records=complete,
        payload_tokens=payload_tokens,
        legacy_bytes=0,
        legacy_tokens=0,
    )
    return {
        "case_id": case_id,
        "family": spec["family"],
        "sequence": after_seq,
        "expected_visible_indices": list(spec["expected_visible_indices"]),
        "observed_visible_ids": sorted(visible_ids),
        "visibility_ok": visible_ids == expected,
        "reconstruct_ok": recovery["reconstruct_ok"],
        "n_visible": len(visible_ids),
        "recovery_bundle_bytes": recovery["recovery_bundle_bytes"],
        "recovery_bundle_tokens": recovery["recovery_bundle_tokens"],
        "reconstruct_sha256": recovery["reconstruct_sha256"],
        "raw_sha256": recovery["raw_sha256"],
    }


def _arm_metrics(
    routing: Sequence[Mapping[str, Any]],
    visible_ids: set[str],
    gold: Sequence[Any],
) -> dict[str, Any]:
    return {
        "visible_source_record_ids_v2": sorted(visible_ids),
        "visible_reference_retention_v2": visible_reference_retention_v2(gold, visible_ids, routing),
        "unique_assignment_identity_retention_v2": unique_assignment_identity_retention_v2(
            routing, visible_ids
        ),
        **duplicate_diagnostic_v2(routing, visible_ids),
    }


def _document_row(
    source_id: str,
    gold: Mapping[str, Any],
    policy: ConditionalTexturePolicyV5,
    tokenizer: Any,
    expected_bite_sha: str,
) -> dict[str, Any]:
    refuse_p3f_evaluation(source_id)
    raw = (RAW_DIR / source_id).read_bytes()
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
    bite_sha = sha256_bytes(bite_visible.encode("utf-8"))
    length_row = apply_length_pi_v1(
        adapter_visible,
        int(tokenizer.payload_tokens(bite_visible)),
        payload_tokens=tokenizer.payload_tokens,
        prefix_char_end=tokenizer.prefix_char_end,
    )
    length_visible = str(length_row["visible"])
    length_sidecar = str(length_row["sidecar"])
    source_texts = [str(unit.get("text", "")) for unit in routing]
    n_prefix = len(complete_prefix_indices(source_texts, length_visible))
    omitted_source = "".join(
        str(unit.get("text", ""))
        for unit in source_units
        if unit.get("line_kind") != "assignment"
    )
    r_blob = after.get("R") if isinstance(after.get("R"), Mapping) else {}
    bite_omitted = "\n".join(
        str((row.get("extra") or {}).get("original_text") or "")
        for row in list((r_blob or {}).get("entries") or [])
        if isinstance(row, Mapping)
    )
    raw_ids = {str(unit.get("unit_id")) for unit in routing}
    length_ids = visible_source_record_ids_v2(
        routing, None, complete_visible_texts=source_texts[:n_prefix]
    )
    bite_ids = visible_source_record_ids_v2(routing, bite_units)

    def rec(visible: str, complete: Sequence[str], legacy_text: str) -> dict[str, Any]:
        return _recovery_row(
            raw=raw,
            encoding=encoding,
            source_units=source_units,
            visible=visible,
            complete_records=complete,
            payload_tokens=tokenizer.payload_tokens,
            legacy_bytes=len(legacy_text.encode("utf-8")),
            legacy_tokens=int(tokenizer.payload_tokens(legacy_text)) if legacy_text else 0,
        )

    raw_rec = rec(source_doc, [], "")
    adapter_rec = rec(adapter_visible, flatten_visible_units(routing), omitted_source)
    length_rec = rec(length_visible, source_texts[:n_prefix], length_sidecar)
    bite_rec = rec(bite_visible, flatten_visible_units(bite_units), bite_omitted)
    v4 = measure_v4({"payload": adapter_visible, "text": adapter_visible})
    tau = after.get("tau") if isinstance(after.get("tau"), Mapping) else {}
    return {
        "source_id": source_id,
        "bite_visible_sha256": bite_sha,
        "bite_output_unchanged": bite_sha == expected_bite_sha,
        "route_sequence": list((tau or {}).get("sequence") or []),
        "n_sensor_edges": len(v4.edges),
        "arms": {
            "raw_full": {**raw_rec, **_arm_metrics(routing, raw_ids, gold_list)},
            "adapter_only": {**adapter_rec, **_arm_metrics(routing, raw_ids, gold_list)},
            "length_pi_v1": {**length_rec, **_arm_metrics(routing, length_ids, gold_list)},
            "BITE_v5": {**bite_rec, **_arm_metrics(routing, bite_ids, gold_list)},
        },
        "reconstruct_ok": all(
            item["reconstruct_ok"] for item in (raw_rec, adapter_rec, length_rec, bite_rec)
        ),
    }


def run_evaluation() -> dict[str, Any]:
    blocked = _blob_errors()
    tokenizer = None
    try:
        tokenizer = load_reference_tokenizer()
    except TokenizerError as exc:
        blocked.append(str(exc))

    def _count(text: str) -> int:
        return int(tokenizer.payload_tokens(text)) if tokenizer is not None else len(text)

    fixtures = [_run_fixture(spec, _count) for spec in planned_cases()]
    fixtures_ok = bool(fixtures) and all(
        row["visibility_ok"] and row["reconstruct_ok"] for row in fixtures
    )
    if not fixtures_ok:
        blocked.append("fresh fixtures failed")
    overlay = json.loads(V2_PATH.read_text(encoding="utf-8"))
    gold_map = {str(row["source_id"]): row for row in overlay["documents"]}
    sha_map = {
        str(row["source_id"]): str(row["sha256"])
        for row in json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["sources"]
    }
    fourf = json.loads(PHASE4F_DEV.read_text(encoding="utf-8"))
    bite_sha = {}
    for doc in fourf.get("documents") or []:
        arm = next(item for item in doc["arms"] if item["arm"] == "BITE_v5")
        bite_sha[str(doc["source_id"])] = str(arm["model_visible_sha256"])
    rows: list[dict[str, Any]] = []
    policy = ConditionalTexturePolicyV5()
    if tokenizer is not None and fixtures_ok:
        try:
            for source_id in AUDIT_SOURCE_IDS:
                if sha256_bytes((RAW_DIR / source_id).read_bytes()) != sha_map[source_id]:
                    raise PolicyLeakError(f"{source_id}: raw sha256 drifted")
                rows.append(
                    _document_row(
                        source_id,
                        gold_map[source_id],
                        policy,
                        tokenizer,
                        bite_sha[source_id],
                    )
                )
        except (EvaluationSealError, AdapterError, PolicyLeakError, RecoveryError) as exc:
            blocked.append(str(exc))
    reconstruct_ok = bool(rows) and all(row["reconstruct_ok"] for row in rows)
    bite_unchanged = bool(rows) and all(row["bite_output_unchanged"] for row in rows)
    tok_ok = tokenizer is not None and tokenizer.tokenizer_json_sha256 == TOKENIZER_JSON_SHA256
    if (
        not blocked
        and fixtures_ok
        and reconstruct_ok
        and bite_unchanged
        and tok_ok
        and len(rows) == 12
    ):
        verdict = VERDICT_VALIDATED
    elif any("drift" in err or "sealed" in err or "REALSTRUCT-2" in err for err in blocked):
        verdict = VERDICT_BLOCKED
    else:
        verdict = VERDICT_PARTIAL
    result = {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "protocol_commit_sha": G0_COMMIT_SHA,
        "g0_freeze_blob": G0_FREEZE_BLOB,
        "phase4f_head_sha": PHASE4F_HEAD,
        "verdict": verdict,
        "paid_api": False,
        "offline": True,
        "research_conclusion": False,
        "premise": PREMISE,
        "phase4c_verdict": PHASE4C_VERDICT,
        "phase4d_verdict": PHASE4D_VERDICT,
        "phase4e_verdict": PHASE4E_VERDICT,
        "phase4f_verdict": PREMISE,
        "phase3t_verdict": PHASE3T_VERDICT,
        "phase3s_verdict": PHASE3S_VERDICT,
        "phase3q_verdict": PHASE3Q_VERDICT,
        "p3f_evaluation_holdout_used": False,
        "no_realstruct2": True,
        "no_winner_score": True,
        "no_bite_retune": True,
        "t_high_reference": LOCKED_T_HIGH,
        "arms": list(ARMS),
        "n_fixtures": len(fixtures),
        "fixtures_ok": fixtures_ok,
        "n_documents": len(rows),
        "reconstruct_ok": reconstruct_ok,
        "bite_output_unchanged": bite_unchanged,
        "tokenizer_hash_verified": tok_ok,
        "errors": blocked,
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "new BITE evidence",
            "new baseline evidence",
            "holdout",
            "confirmatory comparison",
            "generalization",
            "BITE superiority",
        ],
        "not_holdout": True,
        "not_confirmatory": True,
        "not_generalization": True,
    }
    _dump(
        RECOVERY_PATH,
        {
            "schema": "bite-phase4g-recovery-reconstruction/v0.1",
            "ok": fixtures_ok and reconstruct_ok,
            "fixtures": [
                {
                    "case_id": row["case_id"],
                    "reconstruct_ok": row["reconstruct_ok"],
                    "raw_sha256": row["raw_sha256"],
                }
                for row in fixtures
            ],
            "documents": [
                {
                    "source_id": row["source_id"],
                    "reconstruct_ok": row["reconstruct_ok"],
                    "arms": {
                        arm: {
                            "reconstruct_ok": payload["reconstruct_ok"],
                            "bundle_empty": payload["bundle_empty"],
                            "recovery_bundle_bytes": payload["recovery_bundle_bytes"],
                            "recovery_bundle_tokens": payload["recovery_bundle_tokens"],
                            "recovery_metadata_bytes": payload["recovery_metadata_bytes"],
                            "recovery_content_bytes": payload["recovery_content_bytes"],
                        }
                        for arm, payload in row["arms"].items()
                    },
                }
                for row in rows
            ],
        },
    )
    _dump(
        INTEGRATE_PATH,
        {
            "schema": "bite-phase4g-integrate-visibility/v0.1",
            "primary_for_track_b": True,
            "families": [
                name for name in FIXTURE_FAMILIES if "integrate" in name or name.startswith("neg_")
            ],
            "documents": fixtures,
        },
    )
    _dump(
        RETRO_PATH,
        {
            "schema": "bite-phase4g-realstruct1-retrospective/v0.1",
            "role": "development / retrospective diagnostic",
            "not_holdout": True,
            "not_confirmatory": True,
            "not_generalization": True,
            "not_for_retuning": True,
            "bite_output_unchanged": bite_unchanged,
            "documents": rows,
        },
    )
    _dump(
        MAP_PATH,
        {
            "schema": "bite-phase4g-legacy-vs-v2/v0.1",
            "legacy_fields": [
                "arm_local_sidecar_bytes_legacy",
                "arm_local_sidecar_tokens_legacy",
            ],
            "do_not_compare_legacy_across_arms": True,
            "v2_fields": [
                "recovery_bundle_bytes",
                "recovery_bundle_tokens",
                "visible_reference_retention_v2",
                "unique_assignment_identity_retention_v2",
            ],
            "phase4f_metrics_remain_historical": True,
        },
    )
    _dump(RESULT_PATH, result)
    return result


def validate_phase4g_result(doc: Mapping[str, Any]) -> list[str]:
    errs = _blob_errors()
    if doc.get("protocol_commit_sha") != G0_COMMIT_SHA:
        errs.append("G0 commit drifted")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f opened")
    if doc.get("no_realstruct2") is not True:
        errs.append("REALSTRUCT-2 flag drifted")
    if doc.get("verdict") == VERDICT_VALIDATED:
        if doc.get("errors"):
            errs.append("VALIDATED with errors")
        if doc.get("fixtures_ok") is not True:
            errs.append("VALIDATED without fixture pass")
        if int(doc.get("n_documents") or 0) != 12:
            errs.append("VALIDATED without 12 documents")
        if doc.get("reconstruct_ok") is not True:
            errs.append("VALIDATED without reconstruction")
        if doc.get("bite_output_unchanged") is not True:
            errs.append("VALIDATED with BITE output drift")
        if doc.get("not_holdout") is not True:
            errs.append("VALIDATED must mark retrospective as not holdout")
    return errs


if __name__ == "__main__":
    payload = run_evaluation()
    print(payload["verdict"], "fixtures", payload["n_fixtures"], "docs", payload["n_documents"])
    print("errors", payload["errors"])
