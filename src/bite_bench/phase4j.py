"""Phase 4J J0 REALSTRUCT-2 reference-schema compatibility audit contract.

Freezes the retrospective gold-reader audit before introducing
gold_triples_v2. Does not rerun arms or the tokenizer. Does not retune
BITE or length_pi_v1. Does not rewrite Phase 4I artifacts. Does not
open p3f.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4i import LOCKED_BLOBS as PHASE4I_LOCKED_BLOBS
from bite_bench.phase4i import LOCKED_T_HIGH, PRIMARY_IDS

SCHEMA_ID = "bitebench-phase4j-reference-schema-freeze/v0.1"
REVISION = "phase4j-reference-schema-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE4J_REFERENCE_SCHEMA_PROTOCOL_FROZEN"
VERDICT_AUDITED = "PHASE4J_REFERENCE_SCHEMA_AUDITED"
VERDICT_PARTIAL = "PHASE4J_REFERENCE_SCHEMA_PARTIAL"
VERDICT_BLOCKED = "PHASE4J_REFERENCE_SCHEMA_BLOCKED"
J1_VERDICTS = (VERDICT_AUDITED, VERDICT_PARTIAL, VERDICT_BLOCKED)
PREMISE = "PHASE4I_PROSPECTIVE_COMPARISON_MEASURED"
PHASE4I_HEAD = "88f3b26d32c96e17cbb001179953a7ad0c235068"
I0_FREEZE_BLOB = "260c5ae4847776c33d27ea6718466d1dd814abdf"
PHASE4I_RESULT_BLOB = "144a4ca3c2e44d8f0abbd32d0bb8b2f2b5b7b149"
ARM_ROWS_BLOB = "d8d43669fa00f94b86e3cd5d26feb6d8072eb99f"
LEGACY_PAIRED_REF_BLOB = "455b8d3e95ced9c17e9d096f7dc334fe480d14c3"
PAIRED_UNIQUE_BLOB = "eeb2941399d11817bd0d4c16b2737b43d4344d0b"
MODEL_VISIBLE_COST_BLOB = "044325494109fcb0910ec1195bd7836a77d253cf"
MECHANISM_DIAGNOSTIC_BLOB = "3500b26b1f0fe2c61301b97656e5628c4dae7004"
AUGMENTED_ANNOTATIONS_BLOB = "dbb0f20bef4d76dd1d8bfc8b3edee946ad088eb7"
HISTORICAL_GOLD_READER_BLOB = "1c24b419cba83adb205eb1bce16d60ad451ffa17"
CLAIM_BOUNDARY = (
    "retrospective correction of annotation-schema compatibility "
    "for Phase4I reference metrics"
)
LOCKED_PHASE4I = {
    "benchmarks/spec/phase4i-first-open-freeze.json": I0_FREEZE_BLOB,
    "artifacts/phase4i/first-open.json": PHASE4I_RESULT_BLOB,
    "artifacts/phase4i/arm-rows.json": ARM_ROWS_BLOB,
    "artifacts/phase4i/paired-reference-retention.json": LEGACY_PAIRED_REF_BLOB,
    "artifacts/phase4i/paired-unique-identity.json": PAIRED_UNIQUE_BLOB,
    "artifacts/phase4i/model-visible-cost.json": MODEL_VISIBLE_COST_BLOB,
    "artifacts/phase4i/mechanism-diagnostic.json": MECHANISM_DIAGNOSTIC_BLOB,
    "corpora/realstruct-2/augmented-annotations.json": AUGMENTED_ANNOTATIONS_BLOB,
    "src/bite_eval/atom_aware_reference.py": HISTORICAL_GOLD_READER_BLOB,
}
LOCKED_BLOBS = {**PHASE4I_LOCKED_BLOBS, **LOCKED_PHASE4I}

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase4j-reference-schema-freeze.json"
PHASE4I_RESULT = _REPO / "artifacts" / "phase4i" / "first-open.json"
LEGACY_PAIRED_REF = _REPO / "artifacts" / "phase4i" / "paired-reference-retention.json"
GOLD_READER = _REPO / "src" / "bite_eval" / "atom_aware_reference.py"


def _git_blob(path: str) -> str:
    return subprocess.check_output(["git", "hash-object", path], cwd=_REPO, text=True).strip()


def freeze_manifest() -> dict[str, Any]:
    return {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "verdict": PROTOCOL_FROZEN,
        "paid_api": False,
        "offline_core_tests": True,
        "research_conclusion": False,
        "premise": PREMISE,
        "phase4i_head_sha": PHASE4I_HEAD,
        "i0_freeze_blob": I0_FREEZE_BLOB,
        "phase4i_result_blob": PHASE4I_RESULT_BLOB,
        "arm_rows_blob": ARM_ROWS_BLOB,
        "legacy_paired_reference_blob": LEGACY_PAIRED_REF_BLOB,
        "paired_unique_blob": PAIRED_UNIQUE_BLOB,
        "model_visible_cost_blob": MODEL_VISIBLE_COST_BLOB,
        "mechanism_diagnostic_blob": MECHANISM_DIAGNOSTIC_BLOB,
        "augmented_annotations_blob": AUGMENTED_ANNOTATIONS_BLOB,
        "historical_gold_reader_blob": HISTORICAL_GOLD_READER_BLOB,
        "p3f_evaluation_holdout_used": False,
        "no_xfer3": True,
        "no_arm_rerun": True,
        "no_tokenizer_rerun": True,
        "no_bite_retune": True,
        "no_length_pi_retune": True,
        "no_corpus_change": True,
        "no_phase4i_rewrite": True,
        "no_winner_score": True,
        "t_high_reference": LOCKED_T_HIGH,
        "primary_ids": list(PRIMARY_IDS),
        "gold_triples_v2": {
            "rs1_shape": ["source_line", "name", "dest_lines"],
            "rs2_shape": ["source_line", "name", "dest_line"],
            "canonical": "(source_line, name, dest_line)",
            "fail_closed_if_both_dest_fields": True,
            "fail_closed_if_neither_dest_field": True,
            "fail_closed_on_gold_identity_mismatch": True,
            "do_not_silently_repair": True,
        },
        "track_a": {
            "inputs": [
                "artifacts/phase4i/arm-rows.json",
                "corpora/realstruct-2/augmented-annotations.json",
            ],
            "visible_ids": "Phase4I recorded visible_source_record_ids_v2",
            "output": "retrospective corrected reference-retention audit",
            "not_new_first_open": True,
            "preserve_phase4i_n0_as": "phase4i_legacy_schema_reader_result",
        },
        "track_f": {
            "sensor_only_replay": True,
            "require_exact_n_reference_edges": True,
            "require_exact_mean_reference_edge_distance": True,
            "require_exact_gate_result": True,
            "no_policy": True,
            "no_operators": True,
            "no_tokenizer": True,
        },
        "do_not_recompute": [
            "paired unique identity",
            "model-visible token cost",
            "recovery accounting",
            "safety",
            "planner integrity",
            "route frequencies",
        ],
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "new holdout",
            "confirmatory comparison",
            "generalization",
            "BITE superiority",
        ],
        "locked_blobs": dict(LOCKED_BLOBS),
        "j1_verdicts": list(J1_VERDICTS),
        "verdict_rule": {
            VERDICT_AUDITED: (
                "fresh reader tests pass; RS1/RS2 canonicalize; annotation-count "
                "invariants pass; Phase4I arms not rerun; paired-reference "
                "reproducibly rescored; sensor replay exact before corrected "
                "atom-aware scoring; Phase4I artifacts unchanged; BITE/baseline "
                "unchanged; p3f unopened"
            ),
            VERDICT_PARTIAL: (
                "comparison A can be rescored but sensor replay / atom-aware "
                "diagnostic cannot be reproduced exactly"
            ),
            VERDICT_BLOCKED: (
                "historical arm records insufficient, schema cannot be "
                "canonicalized without ambiguity, or frozen artifacts drift"
            ),
        },
    }


def validate_phase4j_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("J0 protocol not frozen")
    if doc.get("premise") != PREMISE:
        errs.append("Phase 4I premise drifted")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("no_arm_rerun") is not True or doc.get("no_tokenizer_rerun") is not True:
        errs.append("arm/tokenizer rerun must stay forbidden")
    if doc.get("no_phase4i_rewrite") is not True:
        errs.append("Phase 4I rewrite must stay forbidden")
    if doc.get("no_bite_retune") is not True or doc.get("no_length_pi_retune") is not True:
        errs.append("BITE/length_pi retune must stay forbidden")
    if doc.get("t_high_reference") != LOCKED_T_HIGH:
        errs.append("T_high drifted")
    if list(doc.get("primary_ids") or []) != list(PRIMARY_IDS):
        errs.append("primary IDs drifted")
    phase4i = json.loads(PHASE4I_RESULT.read_text(encoding="utf-8"))
    if phase4i.get("verdict") != PREMISE:
        errs.append("Phase 4I verdict rewritten")
    legacy = json.loads(LEGACY_PAIRED_REF.read_text(encoding="utf-8"))
    if int(legacy.get("n") or 0) != 0 or legacy.get("status") != "not_observed":
        errs.append("Phase 4I legacy paired-reference rewritten")
    reader = GOLD_READER.read_text(encoding="utf-8")
    if 'edge.get("dest_lines")' not in reader:
        errs.append("historical gold reader dest_lines contract drifted")
    if "gold_triples_v2" in reader:
        errs.append("historical gold reader must not grow gold_triples_v2")
    for path, expected in LOCKED_PHASE4I.items():
        if _git_blob(path) != expected:
            errs.append(f"frozen blob drifted: {path}")
    try:
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
        errs.append("p3f seal did not fire")
    except EvaluationSealError:
        pass
    return errs


def write_freeze() -> Path:
    FREEZE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FREEZE_PATH.write_bytes(
        (json.dumps(freeze_manifest(), indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    return FREEZE_PATH


if __name__ == "__main__":
    write_freeze()
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    print(freeze["verdict"], "premise", freeze["premise"])
    print("errors", validate_phase4j_freeze(freeze))
