"""Phase 4C C0 holdout first-open protocol.

Freezes eval-9 harness, reachability addendum, and ablation baselines
before any evaluation-document BITE or baseline run.
Does not open p3f. Does not retune frozen BITE components.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4b import (
    DEV_SOURCE_IDS,
    EVAL_SOURCE_IDS,
    LOCKED_BITE_BLOBS,
    LOCKED_PHASE4A_BLOBS,
    LOCKED_T_HIGH,
    OVERLAY_V2_BLOB,
    overlay_v2_sha256,
    raw_sha256_map,
)

SCHEMA_ID = "bitebench-phase4c-holdout-first-open-freeze/v0.1"
REVISION = "phase4c-holdout-first-open-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE4C_HOLDOUT_FIRST_OPEN_PROTOCOL_FROZEN"
VERDICT_MEASURED = "PHASE4C_REAL_HOLDOUT_MEASURED"
VERDICT_FAILED = "PHASE4C_REAL_HOLDOUT_FAILED"
VERDICT_BLOCKED = "PHASE4C_REAL_HOLDOUT_BLOCKED"
C1_VERDICTS = (VERDICT_MEASURED, VERDICT_FAILED, VERDICT_BLOCKED)
PREMISE = "PHASE4B_REAL_ADAPTER_READY"
PHASE3S_VERDICT = "PHASE3S_REFERENCE_SPECIFICITY_FAILED"
PHASE3Q_VERDICT = "PHASE3Q_XFER2_TRANSFER_FAILED"
PHASE3T_VERDICT = "PHASE3T_EXACT_REFERENCE_VALIDATED"
PHASE4A_VERDICT = "PHASE4A_REAL_CORPUS_FROZEN"
PHASE4B_HEAD = "8dd13d20cc06339ef07811d0d9438f0da8718106"
ADAPTER_BLOB = "2ef34b0486efb4badcdc29402ef5a9c4dc359565"
OVERLAY_V2_SHA256 = "dfcff8d9117918a56d77d31ee46c32c45b085f39b3337584abfc40fe03d0cab8"
PHASE4B_LOCK_BLOB = "9bb0f743f575ba298fdc63414032a2621c28aec2"
PHASE4B_EVAL_HARNESS_BLOB = "b48ad1f3ab98003f6cd4a1add39127f34a079f8f"
ADAPTER_PATH = "src/bite_ingestion/adapters/realstruct1_adapter_v1.py"
PHASE4B_LOCK_PATH = "artifacts/phase4b/evaluation-lock.json"
PHASE4B_EVAL_PATH = "src/bite_eval/phase4b_eval.py"
CLAIM_BOUNDARY = (
    "first-open measurement on 9 frozen REALSTRUCT-1 evaluation documents"
)
BASELINES = ("raw_full", "adapter_only")
REACHABILITY_CLAIM = (
    "semantics-preserving computational replacement for frozen _chain_span"
)

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase4c-holdout-first-open-freeze.json"
EQ_PATH = _REPO / "artifacts" / "phase4c" / "reachability-equivalence.json"
PHASE4B_RESULT = _REPO / "artifacts" / "phase4b" / "real-adapter.json"
PHASE4A_PATH = _REPO / "artifacts" / "phase4a" / "realstruct-1.json"
PHASE3T_PATH = _REPO / "artifacts" / "phase3t" / "exact-reference.json"
PHASE3S_PATH = _REPO / "artifacts" / "phase3s" / "reference-specificity.json"
PHASE3Q_PATH = _REPO / "artifacts" / "phase3q" / "xfer2-transfer.json"
SPLIT_PATH = _REPO / "corpora" / "realstruct-1" / "split.json"


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
        "phase4b_head_sha": PHASE4B_HEAD,
        "phase4a_verdict": PHASE4A_VERDICT,
        "phase3t_verdict": PHASE3T_VERDICT,
        "phase3s_verdict": PHASE3S_VERDICT,
        "phase3q_verdict": PHASE3Q_VERDICT,
        "p3f_evaluation_holdout_used": False,
        "no_xfer3": True,
        "no_eval_execution_in_c0": True,
        "no_source_rewrite": True,
        "no_retune_after_failure": True,
        "t_high_reference": LOCKED_T_HIGH,
        "dev_source_ids": list(DEV_SOURCE_IDS),
        "eval_source_ids": list(EVAL_SOURCE_IDS),
        "adapter_blob": ADAPTER_BLOB,
        "overlay_v2_blob": OVERLAY_V2_BLOB,
        "overlay_v2_sha256": OVERLAY_V2_SHA256,
        "phase4b_evaluation_lock_blob": PHASE4B_LOCK_BLOB,
        "phase4b_eval_harness_blob": PHASE4B_EVAL_HARNESS_BLOB,
        "locked_phase4a_blobs": dict(LOCKED_PHASE4A_BLOBS),
        "locked_bite_blobs": dict(LOCKED_BITE_BLOBS),
        "raw_sha256": raw_sha256_map(),
        "reachability_addendum": {
            "implementation": "evaluator-local chain_span_reachable",
            "claim": REACHABILITY_CLAIM,
            "not_claimed": [
                "original sensor source was changed",
                "runtime was completely unchanged",
            ],
            "exhaustive_n_max": 4,
            "dev3_feature_exact": [
                "n_reference_edges",
                "mean_reference_edge_distance",
                "gate",
            ],
        },
        "baselines": {
            "ids": list(BASELINES),
            "role": "ablation/reference for raw source → adapter projection → BITE transformation",
            "not_superiority_ranking": True,
            "no_length_budget_baseline": True,
            "no_winner_score": True,
            "raw_full": "identity reference: original source bytes",
            "adapter_only": (
                "same realstruct1_adapter_v1 routing plane; no policy/planner/operator"
            ),
        },
        "measurement_definitions": {
            "gold_reference_recall": "hits / gold directed ${NAME} pairs; NA if gold_n=0",
            "scoped_precision": (
                "TP/(TP+FP) over sensor edges whose source value contains literal "
                "${NAME} for the edge atom; unadjudicated extras excluded; NA if none"
            ),
            "unadjudicated_extra_edges": "sensor edges not in gold; not called false positives",
            "exact_duplicate_gold": "exact (assignment_key, assignment_value)",
        },
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "representative sample",
            "real-world generalization",
            "downstream answer-quality evidence",
            "BITE superiority",
        ],
        "c1_verdicts": list(C1_VERDICTS),
    }


def validate_phase4c_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("C0 protocol not frozen")
    if doc.get("premise") != PREMISE:
        errs.append("Phase 4B premise drifted")
    if doc.get("no_eval_execution_in_c0") is not True:
        errs.append("eval 9 must stay sealed in C0")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("no_xfer3") is not True:
        errs.append("XFER-3 must not be invented")
    if list(doc.get("eval_source_ids") or []) != list(EVAL_SOURCE_IDS):
        errs.append("eval split drifted")
    if list(doc.get("dev_source_ids") or []) != list(DEV_SOURCE_IDS):
        errs.append("dev split drifted")
    if doc.get("t_high_reference") != LOCKED_T_HIGH:
        errs.append("T_high drifted")
    if doc.get("adapter_blob") != ADAPTER_BLOB:
        errs.append("adapter blob drifted")
    if doc.get("overlay_v2_blob") != OVERLAY_V2_BLOB:
        errs.append("overlay v2 blob drifted")
    if doc.get("overlay_v2_sha256") != overlay_v2_sha256():
        errs.append("annotations-v2 hash drifted")
    if json.loads(PHASE4B_RESULT.read_text(encoding="utf-8")).get("verdict") != PREMISE:
        errs.append("Phase 4B verdict rewritten")
    if json.loads(PHASE4A_PATH.read_text(encoding="utf-8")).get("verdict") != PHASE4A_VERDICT:
        errs.append("Phase 4A verdict rewritten")
    split = json.loads(SPLIT_PATH.read_text(encoding="utf-8"))
    if list(split.get("evaluation") or []) != list(EVAL_SOURCE_IDS):
        errs.append("split.json evaluation drifted")
    if json.loads(PHASE3T_PATH.read_text(encoding="utf-8")).get("verdict") != PHASE3T_VERDICT:
        errs.append("Phase 3T verdict rewritten")
    if json.loads(PHASE3S_PATH.read_text(encoding="utf-8")).get("verdict") != PHASE3S_VERDICT:
        errs.append("Phase 3S verdict rewritten")
    if json.loads(PHASE3Q_PATH.read_text(encoding="utf-8")).get("verdict") != PHASE3Q_VERDICT:
        errs.append("Phase 3Q verdict rewritten")
    for path, expected in {
        ADAPTER_PATH: ADAPTER_BLOB,
        PHASE4B_LOCK_PATH: PHASE4B_LOCK_BLOB,
        PHASE4B_EVAL_PATH: PHASE4B_EVAL_HARNESS_BLOB,
        "corpora/realstruct-1/annotations-v2.json": OVERLAY_V2_BLOB,
        **LOCKED_BITE_BLOBS,
        **LOCKED_PHASE4A_BLOBS,
    }.items():
        if _git_blob(path) != expected:
            errs.append(f"locked blob drifted: {path}")
    try:
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
        errs.append("p3f seal did not fire")
    except EvaluationSealError:
        pass
    return errs


def write_equivalence() -> dict[str, Any]:
    from bite_eval.chain_span_reachable import (
        all_directed_graphs,
        chain_span_reachable,
        chain_span_simple_path,
    )

    rows = []
    mismatches = 0
    n_graphs = 0
    for n in range(5):
        n_n = 0
        for graph in all_directed_graphs(n):
            n_n += 1
            left = chain_span_simple_path(n, graph)
            right = chain_span_reachable(n, graph)
            if left != right:
                mismatches += 1
        n_graphs += n_n
        rows.append({"n": n, "n_graphs": n_n})
    doc = {
        "schema": "bite-phase4c-reachability-equivalence/v0.1",
        "revision": REVISION,
        "claim": REACHABILITY_CLAIM,
        "n_max": 4,
        "n_graphs": n_graphs,
        "n_mismatches": mismatches,
        "exact": mismatches == 0,
        "by_n": rows,
    }
    EQ_PATH.parent.mkdir(parents=True, exist_ok=True)
    EQ_PATH.write_bytes((json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return doc


def write_freeze() -> Path:
    FREEZE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FREEZE_PATH.write_bytes(
        (json.dumps(freeze_manifest(), indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    write_equivalence()
    return FREEZE_PATH


if __name__ == "__main__":
    write_freeze()
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    print(freeze["verdict"], "eq", json.loads(EQ_PATH.read_text(encoding="utf-8"))["exact"])
    print("errors", validate_phase4c_freeze(freeze))
