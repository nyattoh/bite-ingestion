"""Phase 3O BITE-XFER-1 transfer protocol (O0).

Freezes corpus, annotations, unitization, derivation, safety, and verdicts.
Does not run policy. Does not import phase3m. Does not open p3f evaluation.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bite_bench.xfer1_corpus import (
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

SCHEMA_ID = "bitebench-phase3o-xfer1-freeze/v0.1"
REVISION = "phase3o-xfer1-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE3O_XFER1_PROTOCOL_FROZEN"
VERDICT_CONFIRMED = "PHASE3O_XFER1_TRANSFER_CONFIRMED"
VERDICT_FAILED = "PHASE3O_XFER1_TRANSFER_FAILED"
VERDICT_BLOCKED = "PHASE3O_XFER1_TRANSFER_BLOCKED"
O1_VERDICTS = (VERDICT_CONFIRMED, VERDICT_FAILED, VERDICT_BLOCKED)
N3_SHA = "81dfcfc7f88f2f2b9df68e2b4d89a5556c9c089b"
OPERATOR_ORDER = ("UNTANGLE", "REDUCE", "INTEGRATE")
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
    "composition_safety",
    "other",
)
CLAIM_BOUNDARY = "independently-authored synthetic cross-corpus / cross-serialization transfer"
UNITIZATION_CONTRACT = (
    "KV: each source line exact char span. "
    "JSON: each top-level array object source-exact substring span. "
    "Do not replace with canonical text. Fail closed if spans cannot be made."
)
DERIVATION_RULE = (
    "If intended_dispersion==high, sequence is UNTANGLE? then REDUCE? then INTEGRATE? "
    "from has_quarantinable_anomaly / has_exact_duplicate / has_explicit_join_cluster. "
    "Otherwise []. CUT never. n_edges_zero and low/mid are []."
)

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase3o-xfer1-freeze.json"


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
    if annotation.get("has_quarantinable_anomaly"):
        sequence.append("UNTANGLE")
    if annotation.get("has_exact_duplicate"):
        sequence.append("REDUCE")
    if annotation.get("has_explicit_join_cluster"):
        sequence.append("INTEGRATE")
    return sequence


def corpus_hashes() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(CORPUS_DIR.rglob("*")):
        if path.is_file():
            rel = path.relative_to(CORPUS_DIR).as_posix()
            hashes[rel] = sha256_text(path.read_text(encoding="utf-8"))
    return hashes


def freeze_manifest() -> dict[str, Any]:
    hashes = corpus_hashes()
    anns = annotations_doc()["annotations"]
    derived = {
        case_id: derive_expected_sequence(row) for case_id, row in anns.items()
    }
    return {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "verdict": PROTOCOL_FROZEN,
        "paid_api": False,
        "offline": True,
        "synthetic": True,
        "research_conclusion": False,
        "premise": "PHASE3N_CONDITIONAL_ROUTING_HOLDOUT_CONFIRMED",
        "n3_commit_sha": N3_SHA,
        "corpus": CORPUS_ID,
        "n_canonical_cases": N_CANONICAL,
        "n_surfaces": N_SURFACES,
        "formats": list(FORMATS),
        "corpus_dir": "corpora/bite-xfer-1",
        "corpus_hashes": hashes,
        "unitization_contract": UNITIZATION_CONTRACT,
        "expected_route_derivation": DERIVATION_RULE,
        "operator_order": list(OPERATOR_ORDER),
        "derived_expected_sequences": derived,
        "safety_rule": list(SAFETY_KEYS),
        "token_reduction": "diagnostic_only",
        "no_winner_score": True,
        "cut_forbidden": True,
        "rule_policy_unchanged": True,
        "policy_unchanged": True,
        "sensor_unchanged": True,
        "operator_unchanged": True,
        "preflight_unchanged": True,
        "no_phase3m_import": True,
        "p3f_evaluation_holdout_used": False,
        "calibration": False,
        "on_failed": "do not retune predicates, sensors, or operators in this PR",
        "failure_classes": list(FAILURE_CLASSES),
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": ["real-world corpus generalization", "BITE superiority"],
        "o1_verdicts": list(O1_VERDICTS),
        "verdict_rule": {
            "PHASE3O_XFER1_TRANSFER_CONFIRMED": (
                "104/104 expected routing; 104/104 safety; 4-format sequence identity; "
                "actionability realized; frozen corpus/code unchanged; no gold leak; "
                "p3f unopened"
            ),
            "PHASE3O_XFER1_TRANSFER_FAILED": (
                "one or more gate / predicate / sequence / actionability / safety mismatches"
            ),
            "PHASE3O_XFER1_TRANSFER_BLOCKED": (
                "protocol drift, corpus mutation, leak, or measurement cannot run"
            ),
        },
        "annotation_keys": [
            "required_evidence_ids",
            "intended_dispersion",
            "has_exact_duplicate",
            "has_quarantinable_anomaly",
            "has_explicit_join_cluster",
        ],
        "paths": {
            "cases": str(CASES_PATH.relative_to(_REPO).as_posix()),
            "annotations": str(ANNOTATIONS_PATH.relative_to(_REPO).as_posix()),
            "manifest": str(MANIFEST_PATH.relative_to(_REPO).as_posix()),
        },
    }


def validate_phase3o_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("revision") != REVISION:
        errs.append("revision mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("protocol not frozen")
    if doc.get("premise") != "PHASE3N_CONDITIONAL_ROUTING_HOLDOUT_CONFIRMED":
        errs.append("premise drifted")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("no_phase3m_import") is not True:
        errs.append("must not import phase3m")
    if doc.get("n_surfaces") != N_SURFACES:
        errs.append("surface count drifted")
    if dict(doc.get("corpus_hashes") or {}) != corpus_hashes():
        errs.append("corpus hashes drifted")
    anns = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    for row in anns.get("annotations", {}).values():
        if "expected_sequence" in row:
            errs.append("expected_sequence stored in annotations")
    derived = dict(doc.get("derived_expected_sequences") or {})
    for case_id, row in anns.get("annotations", {}).items():
        if derived.get(case_id) != derive_expected_sequence(row):
            errs.append(f"derivation drifted for {case_id}")
    return errs


def write_freeze() -> Path:
    write_corpus()
    FREEZE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FREEZE_PATH.write_text(
        json.dumps(freeze_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return FREEZE_PATH


if __name__ == "__main__":
    write_freeze()
