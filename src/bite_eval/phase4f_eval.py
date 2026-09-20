"""Phase 4F prospective comparison protocol development smoke.

Does not retune BITE. Does not acquire REALSTRUCT-2. Does not open p3f.
Does not emit a winner score.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4b import DEV_SOURCE_IDS, EVAL_SOURCE_IDS
from bite_bench.phase4d import AUDIT_SOURCE_IDS
from bite_bench.phase4f import (
    ARMS,
    CLAIM_BOUNDARY,
    E0_FREEZE_BLOB,
    FREEZE_PATH,
    LOCKED_BLOBS,
    LOCKED_T_HIGH,
    PHASE3Q_VERDICT,
    PHASE3S_VERDICT,
    PHASE3T_VERDICT,
    PHASE4C_VERDICT,
    PHASE4D_VERDICT,
    PHASE4E_HEAD,
    PREMISE,
    PROTOCOL_FROZEN,
    TOKENIZER_JSON_SHA256,
    VERDICT_BLOCKED,
    VERDICT_PARTIAL,
    VERDICT_READY,
    freeze_manifest,
    validate_phase4f_freeze,
)
from bite_bench.realstruct1 import RAW_DIR, sha256_bytes
from bite_eval.atom_aware_reference import atom_aware_predictions, gold_triples, score_triples
from bite_eval.composition_safety_v2 import composition_safety_v2
from bite_eval.length_pi_v1 import apply_length_pi_v1
from bite_eval.phase4f_metrics import (
    bite_complete_lines,
    complete_prefix_indices,
    duplicate_diagnostic,
    prefix_complete_lines,
    serialize_routing,
    unique_assignment_identity_retention,
    visible_reference_retention,
)
from bite_eval.reference_tokenizer import (
    TokenizerError,
    load_reference_tokenizer,
    tokenizer_lock_record,
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

SCHEMA_ID = "bite-phase4f-prospective-comparison/v0.1"
REVISION = "phase4f-prospective-comparison-v0.1"
F0_COMMIT_SHA = "ee8d190567e0ce055d7ffa2b7163cffa8d94912a"
F0_FREEZE_BLOB = "9f4e957af859432036e9d150c85b5066892dad8f"
_REPO = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = _REPO / "artifacts" / "phase4f"
RESULT_PATH = ARTIFACT_DIR / "prospective-comparison.json"
TOKEN_PATH = ARTIFACT_DIR / "token-accounting.json"
DEV_PATH = ARTIFACT_DIR / "realstruct1-development.json"
SIDECAR_PATH = ARTIFACT_DIR / "length-pi-sidecar.json"
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


def _tau_sequence(packet: Mapping[str, Any]) -> list[str]:
    tau = packet.get("tau")
    if isinstance(tau, Mapping):
        return [str(item) for item in list(tau.get("sequence") or [])]
    return []


def _blob_errors() -> list[str]:
    errs: list[str] = []
    if not FREEZE_PATH.is_file():
        return ["F0 freeze missing"]
    committed = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    errs.extend(validate_phase4f_freeze(committed))
    if freeze_manifest() != committed:
        errs.append("F0 freeze drifted from generator")
    if committed.get("verdict") != PROTOCOL_FROZEN:
        errs.append("F0 not frozen")
    if _git_blob("benchmarks/spec/phase4f-prospective-comparison-freeze.json") != F0_FREEZE_BLOB:
        errs.append("F0 freeze blob drifted")
    if _git_blob("benchmarks/spec/phase4e-full-key-reference-freeze.json") != E0_FREEZE_BLOB:
        errs.append("E0 freeze blob drifted")
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


def _audit(text: str, tokenizer: Any) -> dict[str, int]:
    encoded = text.encode("utf-8")
    return {
        "audit_sidecar_bytes": len(encoded),
        "audit_sidecar_tokens": int(tokenizer.payload_tokens(text)) if text else 0,
    }


def _arm_row(
    *,
    arm: str,
    visible: str,
    tokenizer: Any,
    extra: Mapping[str, Any],
) -> dict[str, Any]:
    row = {
        "arm": arm,
        "model_visible_tokens": int(tokenizer.payload_tokens(visible)),
        "model_visible_chars": len(visible),
        "model_visible_sha256": sha256_bytes(visible.encode("utf-8")),
    }
    row.update(dict(extra))
    return row


def _document_row(
    source_id: str,
    gold: Mapping[str, Any],
    policy: ConditionalTexturePolicyV5,
    tokenizer: Any,
) -> dict[str, Any]:
    refuse_p3f_evaluation(source_id)
    raw = (RAW_DIR / source_id).read_bytes()
    adapted = adapt(raw, source_id=source_id)
    source_doc = str(adapted["source"]["document"])
    routing = list(adapted["routing_packet"]["units"])
    adapter_visible = serialize_routing(routing)
    source_texts = [str(unit.get("text", "")) for unit in routing]
    gold_list = gold_triples(gold)

    assert_policy_gold_isolated(adapted["routing_packet"])
    after = policy.apply(adapted["routing_packet"])
    bite_units = _units(after)
    bite_visible = serialize_routing(bite_units)
    payload = adapter_visible
    v4 = measure_v4({"payload": payload, "text": payload})
    pred, unadj = atom_aware_predictions(v4.edges, routing)
    sensor = score_triples(gold_list, pred)
    actual = _tau_sequence(after)
    source_units = list(adapted["source"]["units"])
    full_after_units, full_r = merge_full_source_after(source_units, after)
    full_after = {
        "units": full_after_units,
        "visible_evidence": visible_evidence_from_units(full_after_units),
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
        for unit in full_after_units
        if unit.get("line_kind") and unit.get("line_kind") != "assignment"
    ]
    unsupported_lost = adapted["n_unsupported_passthrough"] - len(unsupported_after)
    bite_ok = _conservation_ok(safety, unsupported_lost)
    joined = "".join(str(unit["text"]) for unit in source_units)
    source_roundtrip = joined.encode(str(adapted["encoding"])) == raw

    bite_tokens = int(tokenizer.payload_tokens(bite_visible))
    length_row = apply_length_pi_v1(
        adapter_visible,
        bite_tokens,
        payload_tokens=tokenizer.payload_tokens,
        prefix_char_end=tokenizer.prefix_char_end,
    )
    length_visible = str(length_row["visible"])
    length_sidecar = str(length_row["sidecar"])
    length_ok = (
        length_visible + length_sidecar == adapter_visible
        and adapter_visible.startswith(length_visible)
        and bool(length_row["adapter_payload_reconstructed"])
    )

    omitted_source = "".join(
        str(unit.get("text", ""))
        for unit in source_units
        if unit.get("line_kind") != "assignment"
    )
    r_blob = after.get("R") if isinstance(after.get("R"), Mapping) else {}
    r_json = json.dumps(r_blob, sort_keys=True, ensure_ascii=False)
    bite_omitted = "\n".join(
        str((row.get("extra") or {}).get("original_text") or "")
        for row in list((r_blob or {}).get("entries") or [])
        if isinstance(row, Mapping)
    )

    raw_lines = {int(unit["line_no"]) for unit in routing if unit.get("line_no") is not None}
    adapter_lines = set(raw_lines)
    length_lines = prefix_complete_lines(routing, length_visible)
    bite_lines = bite_complete_lines(routing, bite_units)

    def evidence(arm: str, visible: str, lines: set[int], visible_texts: list[str]) -> dict[str, Any]:
        return {
            "visible_reference_retention": visible_reference_retention(gold_list, lines),
            "unique_assignment_identity_retention": unique_assignment_identity_retention(
                source_texts, visible_texts
            ),
            **duplicate_diagnostic(source_texts, visible_texts),
            "visible_is_source_exact_prefix": arm != "BITE_v5"
            and (
                visible == source_doc
                or adapter_visible.startswith(visible)
                or visible == adapter_visible
            ),
        }

    raw_arm = _arm_row(
        arm="raw_full",
        visible=source_doc,
        tokenizer=tokenizer,
        extra={
            **_audit("", tokenizer),
            "full_source_recoverable": source_roundtrip,
            "role": "identity_reference",
            **evidence("raw_full", source_doc, raw_lines, source_texts),
        },
    )
    adapter_arm = _arm_row(
        arm="adapter_only",
        visible=adapter_visible,
        tokenizer=tokenizer,
        extra={
            **_audit(omitted_source, tokenizer),
            "full_source_recoverable": source_roundtrip,
            "n_routing_assignments": len(routing),
            **evidence("adapter_only", adapter_visible, adapter_lines, source_texts),
        },
    )
    length_texts = [source_texts[i] for i in complete_prefix_indices(source_texts, length_visible)]
    length_arm = _arm_row(
        arm="length_pi_v1",
        visible=length_visible,
        tokenizer=tokenizer,
        extra={
            **_audit(length_sidecar, tokenizer),
            "full_source_recoverable": source_roundtrip and length_ok,
            "adapter_payload_reconstructed": length_ok,
            "target_budget_tokens": length_row["target_budget_tokens"],
            "actual_visible_tokens": length_row["actual_visible_tokens"],
            "budget_slack_tokens": length_row["budget_slack_tokens"],
            "visible_char_boundary": length_row["visible_char_boundary"],
            "sidecar_sha256": sha256_bytes(length_sidecar.encode("utf-8")),
            "budget_match_applicable": length_row["budget_match_applicable"],
            "bite_expanded_or_no_reduction": length_row["bite_expanded_or_no_reduction"],
            **evidence("length_pi_v1", length_visible, length_lines, length_texts),
        },
    )
    bite_texts = [
        str(unit.get("text", ""))
        for unit in bite_units
        if original_text_match(routing, unit)
    ]
    bite_arm = _arm_row(
        arm="BITE_v5",
        visible=bite_visible,
        tokenizer=tokenizer,
        extra={
            **_audit(r_json if not bite_omitted else bite_omitted, tokenizer),
            "full_source_recoverable": bite_ok and source_roundtrip,
            "provenance_completeness": safety["provenance_completeness"],
            "lineage_recall": safety["lineage_recall"],
            "silent_loss": safety["silent_loss"],
            "conservation_untraced": list(safety["conservation_untraced"] or []),
            "unsupported_lost": unsupported_lost,
            "no_unrelated_overmerge": bool(safety["no_unrelated_overmerge"]),
            "route_sequence": actual,
            "atom_aware_recall": sensor["atom_aware_recall"],
            "atom_aware_precision": sensor["atom_aware_precision"],
            "n_unadjudicated_extra_edges": unadj,
            **evidence("BITE_v5", bite_visible, bite_lines, bite_texts),
        },
    )
    split_role = "development" if source_id in DEV_SOURCE_IDS else "evaluation"
    return {
        "source_id": source_id,
        "split_role": split_role,
        "arms": [raw_arm, adapter_arm, length_arm, bite_arm],
        "length_pi_reconstruct_ok": length_ok,
        "bite_conservation_ok": bite_ok,
        "source_roundtrip_ok": source_roundtrip,
        "no_winner_score": True,
    }


def _sidecar_doc(row: Mapping[str, Any]) -> dict[str, Any]:
    length_arm = next(arm for arm in row["arms"] if arm["arm"] == "length_pi_v1")
    keys = (
        "budget_match_applicable",
        "bite_expanded_or_no_reduction",
        "target_budget_tokens",
        "actual_visible_tokens",
        "budget_slack_tokens",
        "visible_char_boundary",
        "audit_sidecar_bytes",
        "audit_sidecar_tokens",
        "sidecar_sha256",
    )
    out = {
        "source_id": row["source_id"],
        "reconstruct_ok": row["length_pi_reconstruct_ok"],
    }
    out.update({key: length_arm[key] for key in keys})
    return out


def original_text_match(routing: Sequence[Mapping[str, Any]], unit: Mapping[str, Any]) -> bool:
    wanted = str(unit.get("text", ""))
    uid = str(unit.get("unit_id"))
    for row in routing:
        if str(row.get("unit_id")) == uid:
            return str(row.get("text", "")) == wanted
    return False


def run_evaluation() -> dict[str, Any]:
    blocked = _blob_errors()
    overlay = json.loads(V2_PATH.read_text(encoding="utf-8"))
    gold_map = {str(row["source_id"]): row for row in overlay["documents"]}
    sha_map = {
        str(row["source_id"]): str(row["sha256"])
        for row in json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["sources"]
    }
    tokenizer = None
    tok_error = None
    try:
        tokenizer = load_reference_tokenizer()
    except TokenizerError as exc:
        tok_error = str(exc)
        blocked.append(str(exc))
    tok_lock = tokenizer_lock_record(tokenizer, tok_error)
    rows: list[dict[str, Any]] = []
    policy = ConditionalTexturePolicyV5()
    if tokenizer is not None:
        try:
            for source_id in AUDIT_SOURCE_IDS:
                if sha256_bytes((RAW_DIR / source_id).read_bytes()) != sha_map[source_id]:
                    raise PolicyLeakError(f"{source_id}: raw sha256 drifted")
                rows.append(_document_row(source_id, gold_map[source_id], policy, tokenizer))
        except (EvalProtocolError, EvaluationSealError, AdapterError, PolicyLeakError) as exc:
            blocked.append(str(exc))
    reconstruct_ok = bool(rows) and all(row["length_pi_reconstruct_ok"] for row in rows)
    conservation_ok = bool(rows) and all(row["bite_conservation_ok"] for row in rows)
    hash_ok = bool(tok_lock["hash_verified"])
    n_docs = len(rows)
    n_arms = sum(len(row["arms"]) for row in rows)
    winner_leak = any("overall_score" in json.dumps(row) for row in rows)
    if winner_leak:
        blocked.append("winner score present")
    if (
        not blocked
        and hash_ok
        and n_docs == 12
        and n_arms == 48
        and reconstruct_ok
        and conservation_ok
        and tok_lock["observed_sha256"] == TOKENIZER_JSON_SHA256
    ):
        verdict = VERDICT_READY
    elif any("drift" in err or "sealed" in err or "REALSTRUCT-2" in err for err in blocked):
        verdict = VERDICT_BLOCKED
    else:
        verdict = VERDICT_PARTIAL
    result = {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "protocol_commit_sha": F0_COMMIT_SHA,
        "f0_freeze_blob": F0_FREEZE_BLOB,
        "phase4e_head_sha": PHASE4E_HEAD,
        "verdict": verdict,
        "paid_api": False,
        "offline": True,
        "research_conclusion": False,
        "premise": PREMISE,
        "phase4c_verdict": PHASE4C_VERDICT,
        "phase4d_verdict": PHASE4D_VERDICT,
        "phase4e_verdict": PREMISE,
        "phase3t_verdict": PHASE3T_VERDICT,
        "phase3s_verdict": PHASE3S_VERDICT,
        "phase3q_verdict": PHASE3Q_VERDICT,
        "p3f_evaluation_holdout_used": False,
        "no_realstruct2": True,
        "no_winner_score": True,
        "no_bite_retune_after_f0": True,
        "t_high_reference": LOCKED_T_HIGH,
        "arms": list(ARMS),
        "n_documents": n_docs,
        "n_arm_rows": n_arms,
        "tokenizer_hash_verified": hash_ok,
        "length_pi_reconstruct_ok": reconstruct_ok,
        "bite_conservation_ok": conservation_ok,
        "errors": blocked,
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "REALSTRUCT-2 evidence",
            "confirmatory comparison",
            "real-world generalization",
            "BITE superiority",
        ],
        "realstruct1_role": "post-open development diagnostic",
        "not_holdout": True,
        "not_confirmatory": True,
        "not_generalization": True,
    }
    _dump(TOKEN_PATH, {"schema": "bite-phase4f-token-accounting/v0.1", **tok_lock, "n_documents": n_docs})
    _dump(
        SIDECAR_PATH,
        {
            "schema": "bite-phase4f-length-pi-sidecar/v0.1",
            "not_model_visible": True,
            "ok": reconstruct_ok,
            "documents": [_sidecar_doc(row) for row in rows],
        },
    )
    _dump(
        DEV_PATH,
        {
            "schema": "bite-phase4f-realstruct1-development/v0.1",
            "role": "post-open development diagnostic",
            "not_holdout": True,
            "not_confirmatory": True,
            "not_generalization": True,
            "not_for_retuning": True,
            "eval_source_ids": list(EVAL_SOURCE_IDS),
            "documents": rows,
        },
    )
    _dump(RESULT_PATH, result)
    return result


class EvalProtocolError(RuntimeError):
    """Phase 4F protocol failure."""


def validate_phase4f_result(doc: Mapping[str, Any]) -> list[str]:
    errs = _blob_errors()
    if doc.get("protocol_commit_sha") != F0_COMMIT_SHA:
        errs.append("F0 commit drifted")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f opened")
    if doc.get("no_realstruct2") is not True:
        errs.append("REALSTRUCT-2 flag drifted")
    if doc.get("no_winner_score") is not True:
        errs.append("winner score flag drifted")
    if doc.get("t_high_reference") != LOCKED_T_HIGH:
        errs.append("T_high drifted")
    if doc.get("verdict") == VERDICT_READY:
        if doc.get("errors"):
            errs.append("READY with errors")
        if int(doc.get("n_documents") or 0) != 12:
            errs.append("READY without 12 documents")
        if doc.get("tokenizer_hash_verified") is not True:
            errs.append("READY without tokenizer hash")
        if doc.get("length_pi_reconstruct_ok") is not True:
            errs.append("READY without sidecar reconstruct")
        if doc.get("not_holdout") is not True:
            errs.append("READY must mark REALSTRUCT-1 as not holdout")
    return errs


if __name__ == "__main__":
    payload = run_evaluation()
    print(payload["verdict"], "docs", payload["n_documents"], "errors", payload["errors"])
