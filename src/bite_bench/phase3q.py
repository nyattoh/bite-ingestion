"""Phase 3Q BITE-XFER-2 transfer protocol (Q0).

Freezes corpus, annotations, unitization, derivation, safety, and verdicts.
Does not run policy. Does not import XFER-1/p3p/p3m generators. Does not
open p3f evaluation. Does not rewrite Phase 3O or Phase 3P artifacts.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bite_bench.xfer2_corpus import (
    ANNOTATIONS_PATH,
    CASES_PATH,
    CORPUS_DIR,
    CORPUS_ID,
    FORMATS,
    MANIFEST_PATH,
    N_CANONICAL,
    N_SURFACES,
    annotations_doc,
    sha256_text,
    write_corpus,
)

SCHEMA_ID = "bitebench-phase3q-xfer2-freeze/v0.1"
REVISION = "phase3q-xfer2-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE3Q_XFER2_PROTOCOL_FROZEN"
VERDICT_CONFIRMED = "PHASE3Q_XFER2_TRANSFER_CONFIRMED"
VERDICT_FAILED = "PHASE3Q_XFER2_TRANSFER_FAILED"
VERDICT_BLOCKED = "PHASE3Q_XFER2_TRANSFER_BLOCKED"
Q1_VERDICTS = (VERDICT_CONFIRMED, VERDICT_FAILED, VERDICT_BLOCKED)
PREMISE = "PHASE3P_RECORD_ALIGNMENT_VALIDATED"
PHASE3O_VERDICT = "PHASE3O_XFER1_TRANSFER_FAILED"
PHASE3O_REMAINS = "Phase3O remains FAILED; known failures are repaired in development"
P3P_HEAD_SHA = "833bb56eec52260bc9a424e6d0ad8af397eb2604"
P3P_FREEZE_SHA = "4756acbb09e3df59dbe4832e2888c35a9cd9c37b"
O0_SHA = "76998156d3cbf67fc0a53e151688e46bd3c26dc7"
OPERATOR_ORDER = ("UNTANGLE", "REDUCE_v2", "INTEGRATE")
SAFETY_KEYS = (
    "lineage_recall",
    "provenance_completeness",
    "conservation_untraced",
    "silent_loss",
    "quarantine_recoverable",
    "no_unrelated_overmerge",
    "reduce_realizes_logical_duplicates",
    "untangle_quarantines_anomaly",
    "integrate_makes_explicit_cluster",
)
FAILURE_CLASSES = (
    "gate_format_dependence",
    "predicate_format_dependence",
    "sensor_operator_mismatch",
    "operator_interference",
    "composition_safety",
    "other",
)
CLAIM_BOUNDARY = (
    "fresh independently-authored synthetic cross-corpus / cross-serialization transfer for v2"
)
UNITIZATION_CONTRACT = (
    "KV: each source line exact char span. "
    "JSON: each top-level array object source-exact substring span. "
    "Do not replace with canonical text. Fail closed if spans cannot be made."
)
DERIVATION_RULE = (
    "If intended_dispersion==high, sequence is UNTANGLE? then REDUCE_v2? then "
    "INTEGRATE? from anomaly_unit_ids / duplicate_groups / explicit_join_groups. "
    "Otherwise []. CUT never. low/mid are []. high with no actionable texture is []."
)
LOCKED_BLOBS = {
    "src/bite_ingestion/logical_record.py": "c6f8cdd455cbc6814141fdb95458a72cc47b7af0",
    "src/bite_ingestion/profilers/structural_redundancy_v2.py": (
        "8960396c9a91872a1bfb0ccdaeae834d872cf12e"
    ),
    "src/bite_ingestion/operators/reduce_v2.py": "d4bafba7dfdd048a0ccad404a8f706202e2157b5",
    "src/bite_ingestion/policies/conditional_texture_policy_v2.py": (
        "848e1e65bf370fb7203be038630b95c61fc763cb"
    ),
    "src/bite_eval/composition_safety_v2.py": "85560279375b30f737eb3825cce72373be70488e",
    "src/bite_ingestion/operators/preflight.py": "b3cc6946f515b3ca6f025500a4ffdad45c111eea",
    "src/bite_ingestion/operators/untangle.py": "2951b7542f96674930e750e438891ca772b46896",
    "src/bite_ingestion/operators/integrate.py": "68e34becd80e7e803f511ec57ea7a23c2aaa1240",
    "src/bite_ingestion/profilers/dependency_dispersion_v1.py": (
        "890d777bb8179df27c8aeba35f1efebc133dd8eb"
    ),
    "src/bite_ingestion/packet_contract.py": "ffd059958bb154c70218715d81fd37d577c55367",
}
P3P_PRIMARY_PATH = "artifacts/phase3p/record-alignment.json"
P3P_PRIMARY_BLOB = "e45d6255be3495cadfbad11cd64e206d92a17c38"
ANNOTATION_KEYS = (
    "required_evidence_ids",
    "intended_dispersion",
    "duplicate_groups",
    "anomaly_unit_ids",
    "explicit_join_groups",
)

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase3q-xfer2-freeze.json"
LOCKED_BLOBS_PATH = _REPO / "benchmarks" / "spec" / "phase3q-locked-blobs.json"
PHASE3O_PATH = _REPO / "artifacts" / "phase3o" / "xfer1-transfer.json"
PHASE3P_PATH = _REPO / P3P_PRIMARY_PATH


class EvaluationSealError(RuntimeError):
    """p3f evaluation replicas 2/3 stay sealed."""


def refuse_p3f_evaluation(case_id: str) -> None:
    cid = str(case_id)
    if cid.startswith("p3f-") and ("-r2" in cid or "-r3" in cid):
        raise EvaluationSealError(f"p3f evaluation sealed: refused {cid}")


def derive_expected_sequence(annotation: Mapping[str, Any]) -> list[str]:
    if str(annotation.get("intended_dispersion")) != "high":
        return []
    sequence: list[str] = []
    if annotation.get("anomaly_unit_ids"):
        sequence.append("UNTANGLE")
    if annotation.get("duplicate_groups"):
        sequence.append("REDUCE_v2")
    if annotation.get("explicit_join_groups"):
        sequence.append("INTEGRATE")
    return sequence


def corpus_hashes() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(CORPUS_DIR.rglob("*")):
        if path.is_file():
            rel = path.relative_to(CORPUS_DIR).as_posix()
            hashes[rel] = sha256_text(path.read_text(encoding="utf-8"))
    return hashes


def locked_blobs_doc() -> dict[str, Any]:
    return {
        "schema": "bitebench-phase3q-locked-blobs/v0.1",
        "git_blob_sha": dict(LOCKED_BLOBS),
        "phase3p_primary_path": P3P_PRIMARY_PATH,
        "phase3p_primary_artifact": P3P_PRIMARY_BLOB,
        "phase3p_head_sha": P3P_HEAD_SHA,
        "phase3p_freeze_sha": P3P_FREEZE_SHA,
        "phase3o_o0_sha": O0_SHA,
        "phase3o_verdict": PHASE3O_VERDICT,
        "no_policy_change": True,
        "no_sensor_change": True,
        "no_operator_change": True,
        "no_safety_evaluator_change": True,
        "no_new_threshold": True,
        "no_predicate_retune": True,
        "on_failed": "do not retune predicates, sensors, or operators in this PR",
    }


def freeze_manifest() -> dict[str, Any]:
    hashes = corpus_hashes()
    anns = annotations_doc()["annotations"]
    derived = {case_id: derive_expected_sequence(row) for case_id, row in anns.items()}
    return {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "verdict": PROTOCOL_FROZEN,
        "paid_api": False,
        "offline": True,
        "synthetic": True,
        "research_conclusion": False,
        "premise": PREMISE,
        "phase3p_head_sha": P3P_HEAD_SHA,
        "phase3p_freeze_sha": P3P_FREEZE_SHA,
        "phase3p_primary_artifact": P3P_PRIMARY_BLOB,
        "phase3o_verdict": PHASE3O_VERDICT,
        "phase3o_o0_sha": O0_SHA,
        "phase3o_remains": PHASE3O_REMAINS,
        "phase3o_artifact_unchanged": True,
        "phase3p_development_repair_only": True,
        "corpus": CORPUS_ID,
        "n_canonical_cases": N_CANONICAL,
        "n_surfaces": N_SURFACES,
        "formats": list(FORMATS),
        "corpus_dir": "corpora/bite-xfer-2",
        "corpus_hashes": hashes,
        "unitization_contract": UNITIZATION_CONTRACT,
        "expected_route_derivation": DERIVATION_RULE,
        "operator_order": list(OPERATOR_ORDER),
        "derived_expected_sequences": derived,
        "safety_rule": list(SAFETY_KEYS),
        "token_reduction": "diagnostic_only",
        "no_winner_score": True,
        "cut_forbidden": True,
        "locked_blobs": dict(LOCKED_BLOBS),
        "no_xfer1_generator_import": True,
        "no_p3p_generator_import": True,
        "no_p3m_import": True,
        "p3f_evaluation_holdout_used": False,
        "calibration": False,
        "development_split": False,
        "evaluation_only": True,
        "one_shot": True,
        "no_new_threshold": True,
        "no_predicate_retune": True,
        "on_failed": "do not retune predicates, sensors, or operators in this PR",
        "failure_classes": list(FAILURE_CLASSES),
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": ["real-world corpus generalization", "BITE superiority"],
        "q1_verdicts": list(Q1_VERDICTS),
        "verdict_rule": {
            "PHASE3Q_XFER2_TRANSFER_CONFIRMED": (
                "112/112 expected routing; 28/28 four-rendering gate/predicate/sequence "
                "identity; 112/112 actionability; 112/112 composition safety; "
                "adversarial composition cases pass; frozen blobs/corpus unchanged; "
                "no gold leak; p3f unopened"
            ),
            "PHASE3Q_XFER2_TRANSFER_FAILED": (
                "one or more routing / actionability / interference / safety failures"
            ),
            "PHASE3Q_XFER2_TRANSFER_BLOCKED": (
                "protocol drift, corpus mutation, leak, or measurement cannot run"
            ),
        },
        "annotation_keys": list(ANNOTATION_KEYS),
        "paths": {
            "cases": str(CASES_PATH.relative_to(_REPO).as_posix()),
            "annotations": str(ANNOTATIONS_PATH.relative_to(_REPO).as_posix()),
            "manifest": str(MANIFEST_PATH.relative_to(_REPO).as_posix()),
            "locked_blobs": str(LOCKED_BLOBS_PATH.relative_to(_REPO).as_posix()),
        },
    }


def validate_phase3q_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("revision") != REVISION:
        errs.append("revision mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("protocol not frozen")
    if doc.get("premise") != PREMISE:
        errs.append("premise drifted")
    if doc.get("phase3o_verdict") != PHASE3O_VERDICT:
        errs.append("Phase 3O verdict rewritten")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("no_xfer1_generator_import") is not True:
        errs.append("must not import XFER-1 generator")
    if doc.get("no_p3p_generator_import") is not True:
        errs.append("must not import p3p generator")
    if doc.get("no_p3m_import") is not True:
        errs.append("must not import phase3m")
    if doc.get("n_surfaces") != N_SURFACES:
        errs.append("surface count drifted")
    if dict(doc.get("corpus_hashes") or {}) != corpus_hashes():
        errs.append("corpus hashes drifted")
    if dict(doc.get("locked_blobs") or {}) != LOCKED_BLOBS:
        errs.append("locked blobs drifted")
    if PHASE3O_PATH.is_file():
        phase3o = json.loads(PHASE3O_PATH.read_text(encoding="utf-8"))
        if phase3o.get("verdict") != PHASE3O_VERDICT:
            errs.append("Phase 3O artifact verdict rewritten")
    else:
        errs.append("Phase 3O artifact missing")
    if PHASE3P_PATH.is_file():
        phase3p = json.loads(PHASE3P_PATH.read_text(encoding="utf-8"))
        if phase3p.get("verdict") != PREMISE:
            errs.append("Phase 3P artifact verdict rewritten")
    else:
        errs.append("Phase 3P artifact missing")
    anns = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    for row in anns.get("annotations", {}).values():
        if "expected_sequence" in row:
            errs.append("expected_sequence stored in annotations")
        if set(row) != set(ANNOTATION_KEYS):
            errs.append("annotation keys drifted")
    derived = dict(doc.get("derived_expected_sequences") or {})
    for case_id, row in anns.get("annotations", {}).items():
        if derived.get(case_id) != derive_expected_sequence(row):
            errs.append(f"derivation drifted for {case_id}")
    return errs


def write_freeze() -> Path:
    write_corpus()
    LOCKED_BLOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCKED_BLOBS_PATH.write_text(
        json.dumps(locked_blobs_doc(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    FREEZE_PATH.write_text(
        json.dumps(freeze_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return FREEZE_PATH


if __name__ == "__main__":
    write_freeze()
