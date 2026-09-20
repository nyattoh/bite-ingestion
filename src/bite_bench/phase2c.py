"""Phase 2C dispersion confirmatory freeze.

Registers the primary confirmatory contrast before evaluation is opened.
Does not generate evaluation surfaces, count tokens, or run arms.

v0.2 supersedes v0.1 verdict wording only. v0.1 remains on disk.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bite_bench.phase2a import (
    PHASE2A_REVISION,
    SURFACE_REDUNDANCIES,
    SURFACE_STRUCTURES,
    design_cells,
)
from bite_bench.token_match import (
    TOKEN_MATCH_MAX_ABS_DELTA,
    TOKEN_MATCH_MAX_RELATIVE_DELTA,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
V01_FREEZE_PATH = _REPO_ROOT / "benchmarks" / "spec" / "phase2c-dispersion-freeze.json"

SCHEMA_ID_V01 = "bitebench-phase2c-dispersion-freeze/v0.1"
SCHEMA_ID = "bitebench-phase2c-dispersion-freeze/v0.2"
PHASE2C_REVISION_V01 = "phase2c-dispersion-freeze-v0.1"
PHASE2C_REVISION = "phase2c-dispersion-freeze-v0.2"
BASE_MAIN_SHA = "dce759efbb94ae941a86c3358b1b717da3224c14"
PHASE2B_VERDICT = "PHASE2B_LENGTH_CONTROL_PARTIAL"
PRIMARY_AXIS = "dispersion"
LEFT_DISPERSION = "clustered"
RIGHT_DISPERSION = "dispersed"
PHASE2D_ARMS: tuple[str, ...] = ("raw_full", "length_pi", "rule_pi", "rule_pi_rebite")
PHASE2D_VERDICTS: tuple[str, ...] = (
    "PHASE2D_OFFLINE_SIGNAL",
    "PHASE2D_OFFLINE_NO_SIGNAL",
    "PHASE2D_BLOCKED",
)
VERDICT_SIGNAL = "PHASE2D_OFFLINE_SIGNAL"
VERDICT_NO_SIGNAL = "PHASE2D_OFFLINE_NO_SIGNAL"
VERDICT_BLOCKED = "PHASE2D_BLOCKED"

SYSTEM_PROMPT = "You are a careful extractive QA assistant. Reply with the answer only."
USER_TEMPLATE = (
    "Document:\n{payload}\n\n"
    "Question: {query}\n"
    "Answer with only the final value/string, no explanation."
)

TOKENIZER_REFERENCE: dict[str, Any] = {
    "repo": "zai-org/GLM-4.5",
    "revision": "cbb2c7cfb52fa128a9660cb1a7a78e017899e115",
    "transformers_version": "4.54.0",
    "tokenizer_json_sha256": (
        "9340665016419c825c4bdabbcc9acc43b7ca2c68ce142724afa829abb1be5efd"
    ),
    "exact_hosted_model_equivalence_asserted": False,
    "note": (
        "Pinned official GLM-4.5-family reference tokenizer. Exact hosted "
        "glm-4.5-flash tokenizer equivalence is not asserted here."
    ),
}

EVALUATION_RESULT_KEYS = frozenset(
    {
        "prompt_tokens",
        "left_tokens",
        "right_tokens",
        "abs_delta",
        "relative_delta",
        "operator_sequence",
        "T_total",
        "T_profiler",
        "T_router",
        "T_operator",
        "T_rebite",
        "payload_sha256",
        "route",
        "routing",
        "morphology",
    }
)

PHASE2D_VERDICT_V02: dict[str, Any] = {
    VERDICT_BLOCKED: {
        "when_any": [
            "negative control / instrumentation self-check failed",
            "frozen contract broken",
            "eligible pair count is 0",
            "fair confirmatory comparison cannot be formed",
        ]
    },
    VERDICT_SIGNAL: {
        "when": "n_eligible >= 1 and n_dispersion_specific_signal >= 1",
        "one_pair_is_still_signal": True,
        "no_strong_generalization": True,
    },
    VERDICT_NO_SIGNAL: {
        "when": "n_eligible >= 1 and n_dispersion_specific_signal == 0",
    },
}

ELIGIBLE_PAIR_V02: dict[str, Any] = {
    "must_all": [
        "satisfies Phase 1C length criterion",
        "instrumentation/self-check did not fail",
        "frozen canonical identity / wrapper / tokenizer contract hold",
    ],
    "if_length_criterion_fails": "exclude that pair; do not rescue",
}

DISPERSION_SPECIFIC_SIGNAL_V02: dict[str, Any] = {
    "applies_to": "eligible pairs",
    "first_check": (
        "length_pi clustered and dispersed have the same routing/operator behavior"
    ),
    "if_length_pi_differs_at_matched_length": (
        "not a BITE signal; record as instrumentation/policy consistency issue"
    ),
    "true_if_any": [
        "rule_pi operator sequence differs clustered vs dispersed",
        "rule_pi transformed/no-op status differs clustered vs dispersed",
        "rule_pi_rebite recovery-fire status differs clustered vs dispersed",
    ],
    "not_signal": [
        "raw payload hash difference (input order differs by design)",
        "evidence recall difference alone",
        "provenance difference alone",
        "T_total difference alone",
        "length_pi != rule_pi count alone",
    ],
    "record_always": [
        "visible_evidence_recall",
        "recoverable_evidence_recall",
        "provenance_completeness",
        "T_total",
    ],
}


def confirmatory_pairs() -> list[dict[str, Any]]:
    """Pre-register clustered vs dispersed pairs. IDs only; no surfaces."""
    rows: list[dict[str, Any]] = []
    for cell in design_cells("evaluation"):
        for structure in SURFACE_STRUCTURES:
            for redundancy in SURFACE_REDUNDANCIES:
                left_family = f"p2a_{structure}_{LEFT_DISPERSION}_{redundancy}"
                right_family = f"p2a_{structure}_{RIGHT_DISPERSION}_{redundancy}"
                rows.append(
                    {
                        "pair_id": (
                            f"{cell.case_id}::{structure}::{redundancy}::"
                            f"{LEFT_DISPERSION}-{RIGHT_DISPERSION}"
                        ),
                        "case_id": cell.case_id,
                        "split": "evaluation",
                        "replica": cell.replica,
                        "scale": cell.scale,
                        "dependency": cell.dependency,
                        "structure": structure,
                        "redundancy": redundancy,
                        "left": {
                            "dispersion": LEFT_DISPERSION,
                            "family": left_family,
                        },
                        "right": {
                            "dispersion": RIGHT_DISPERSION,
                            "family": right_family,
                        },
                        "held_fixed": [
                            "canonical_facts",
                            "question",
                            "answer",
                            "required_evidence",
                            "scale",
                            "dependency",
                            "structure",
                            "redundancy",
                            "prompt_wrapper",
                            "tokenizer_contract",
                        ],
                        "varies": PRIMARY_AXIS,
                    }
                )
    return rows


def load_v01_freeze() -> dict[str, Any]:
    if not V01_FREEZE_PATH.is_file():
        raise FileNotFoundError(f"v0.1 freeze missing: {V01_FREEZE_PATH}")
    return json.loads(V01_FREEZE_PATH.read_text(encoding="utf-8"))


def freeze_manifest() -> dict[str, Any]:
    """Active freeze is v0.2. Built from retained v0.1 plus verdict disambiguation."""
    doc = dict(load_v01_freeze())
    doc["schema"] = SCHEMA_ID
    doc["revision"] = PHASE2C_REVISION
    doc["supersedes"] = PHASE2C_REVISION_V01
    doc["supersession"] = {
        "previous": PHASE2C_REVISION_V01,
        "previous_path": "benchmarks/spec/phase2c-dispersion-freeze.json",
        "reason": "disambiguate Phase 2D verdicts before opening evaluation",
        "v0_1_deleted": False,
        "v0_1_overwritten": False,
    }
    doc["eligible_pair"] = dict(ELIGIBLE_PAIR_V02)
    doc["dispersion_specific_signal"] = dict(DISPERSION_SPECIFIC_SIGNAL_V02)
    doc["phase2d_verdicts"] = dict(PHASE2D_VERDICT_V02)
    doc["reporting"] = {
        "required_counts": ["n_signal", "n_eligible"],
        "required_breakdowns": ["scale", "dependency", "structure", "redundancy"],
        "one_pair_is_still_signal": True,
        "no_strong_generalization": True,
    }
    return doc


def classify_dispersion_pair(
    *,
    length_criterion_ok: bool,
    instrumentation_ok: bool,
    frozen_contract_ok: bool,
    length_pi_behavior_same: bool,
    rule_pi_sequence_differs: bool,
    rule_pi_noop_status_differs: bool,
    rule_pi_rebite_recovery_differs: bool,
    raw_payload_hash_differs: bool = False,
    recall_differs: bool = False,
    provenance_differs: bool = False,
    t_total_differs: bool = False,
    length_pi_neq_rule_pi: bool = False,
) -> dict[str, Any]:
    """Pre-declared pair classification. Does not inspect evaluation surfaces."""
    del raw_payload_hash_differs, recall_differs, provenance_differs
    del t_total_differs, length_pi_neq_rule_pi
    eligible = length_criterion_ok and instrumentation_ok and frozen_contract_ok
    if not eligible:
        return {
            "eligible": False,
            "dispersion_specific_signal": False,
            "classification": "ineligible",
        }
    if not length_pi_behavior_same:
        return {
            "eligible": True,
            "dispersion_specific_signal": False,
            "classification": "instrumentation_or_policy_consistency_issue",
        }
    signal = (
        rule_pi_sequence_differs
        or rule_pi_noop_status_differs
        or rule_pi_rebite_recovery_differs
    )
    return {
        "eligible": True,
        "dispersion_specific_signal": signal,
        "classification": "signal" if signal else "no_signal",
    }


def decide_phase2d_verdict(
    *,
    n_eligible: int,
    n_dispersion_specific_signal: int,
    blocked_reasons: Sequence[str] | None = None,
) -> str:
    if blocked_reasons:
        return VERDICT_BLOCKED
    if n_eligible < 1:
        return VERDICT_BLOCKED
    if n_dispersion_specific_signal >= 1:
        return VERDICT_SIGNAL
    return VERDICT_NO_SIGNAL


def _validate_shared(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("primary_axis") != PRIMARY_AXIS:
        errs.append("primary_axis must be dispersion")
    if doc.get("evaluation_sealed") is not True:
        errs.append("evaluation_sealed must be true")
    if doc.get("paid_api") is not False:
        errs.append("paid_api must be false")
    if doc.get("arms_run") is not False:
        errs.append("Phase 2C must not run arms")
    if list(doc.get("arms") or []) != list(PHASE2D_ARMS):
        errs.append("arms must be the four pre-registered Phase 2D arms")
    pairs = list(doc.get("confirmatory_pairs") or [])
    if len(pairs) != 48:
        errs.append(f"expected 48 confirmatory pairs, got {len(pairs)}")
    eval_ids = {c.case_id for c in design_cells("evaluation")}
    cal_ids = {c.case_id for c in design_cells("calibration")}
    listed_eval = set(doc.get("case_ids", {}).get("evaluation") or [])
    listed_cal = set(doc.get("case_ids", {}).get("calibration") or [])
    if listed_eval != eval_ids:
        errs.append("evaluation case ids must match Phase 2A")
    if listed_cal != cal_ids:
        errs.append("calibration case ids must match Phase 2A")
    for pair in pairs:
        if not isinstance(pair, Mapping):
            errs.append("pair is not an object")
            continue
        if pair.get("split") != "evaluation":
            errs.append(f"{pair.get('pair_id')}: split must be evaluation")
        if pair.get("case_id") not in eval_ids:
            errs.append(f"{pair.get('pair_id')}: case_id is not an evaluation cell")
        if pair.get("replica") not in {2, 3}:
            errs.append(f"{pair.get('pair_id')}: replica must be 2 or 3")
        if pair.get("varies") != PRIMARY_AXIS:
            errs.append(f"{pair.get('pair_id')}: varies must be dispersion")
        left_obj = pair.get("left")
        right_obj = pair.get("right")
        left: Mapping[str, Any] = left_obj if isinstance(left_obj, Mapping) else {}
        right: Mapping[str, Any] = right_obj if isinstance(right_obj, Mapping) else {}
        if left.get("dispersion") != LEFT_DISPERSION:
            errs.append(f"{pair.get('pair_id')}: left must be clustered")
        if right.get("dispersion") != RIGHT_DISPERSION:
            errs.append(f"{pair.get('pair_id')}: right must be dispersed")
        if pair.get("structure") is None or pair.get("redundancy") is None:
            errs.append(f"{pair.get('pair_id')}: structure/redundancy must be held fixed")
        overlap = EVALUATION_RESULT_KEYS.intersection(pair)
        if overlap:
            errs.append(f"{pair.get('pair_id')}: evaluation result keys present: {sorted(overlap)}")
    blob = json.dumps(pairs, sort_keys=True)
    for key in ("prompt_tokens", "operator_sequence", "T_total", "payload_sha256"):
        if key in blob:
            errs.append(f"evaluation result field leaked into pairs: {key}")
    criterion = dict(doc.get("length_criterion") or {})
    if criterion.get("max_abs_delta") != TOKEN_MATCH_MAX_ABS_DELTA:
        errs.append("length criterion abs delta was changed")
    if criterion.get("max_relative_delta") != TOKEN_MATCH_MAX_RELATIVE_DELTA:
        errs.append("length criterion relative delta was changed")
    if criterion.get("no_padding") is not True:
        errs.append("padding must remain forbidden")
    if criterion.get("widened_after_phase2b") is not False:
        errs.append("criterion must not be widened after Phase 2B")
    secondary = dict(doc.get("secondary_axes") or {})
    for axis in ("structure", "redundancy"):
        row = dict(secondary.get(axis) or {})
        if row.get("in_primary_confirmatory") is not False:
            errs.append(f"{axis} must be excluded from primary confirmatory")
        if row.get("deleted") is not False:
            errs.append(f"{axis} must not be deleted")
    verdicts = dict(doc.get("phase2d_verdicts") or {})
    if set(verdicts) != set(PHASE2D_VERDICTS):
        errs.append("Phase 2D verdict keys must be exactly the three freeze labels")
    if doc.get("phase2a_revision") != PHASE2A_REVISION:
        errs.append("phase2a_revision must stay frozen")
    return errs


def _validate_v02(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append(f"bad schema id: {doc.get('schema')!r}")
    if doc.get("revision") != PHASE2C_REVISION:
        errs.append(f"bad revision: {doc.get('revision')!r}")
    if doc.get("supersedes") != PHASE2C_REVISION_V01:
        errs.append("v0.2 must supersede v0.1")
    supersession = dict(doc.get("supersession") or {})
    if supersession.get("v0_1_deleted") is not False:
        errs.append("v0.1 must not be recorded as deleted")
    if supersession.get("v0_1_overwritten") is not False:
        errs.append("v0.1 must not be recorded as overwritten")
    if "eligible_pair" not in doc:
        errs.append("eligible_pair missing")
    signal = dict(doc.get("dispersion_specific_signal") or {})
    if "true_if_any" not in signal:
        errs.append("dispersion_specific_signal.true_if_any missing")
    not_signal = list(signal.get("not_signal") or [])
    if not any("payload hash" in str(x) for x in not_signal):
        errs.append("raw payload hash must be excluded from signal")
    if not any("length_pi != rule_pi" in str(x) for x in not_signal):
        errs.append("length_pi != rule_pi must not be the dispersion signal")
    reporting = dict(doc.get("reporting") or {})
    if "n_signal" not in list(reporting.get("required_counts") or []):
        errs.append("reporting must include n_signal")
    if "n_eligible" not in list(reporting.get("required_counts") or []):
        errs.append("reporting must include n_eligible")
    return errs


def validate_freeze_doc(doc: Mapping[str, Any]) -> list[str]:
    rev = doc.get("revision")
    errs = _validate_shared(doc)
    if rev == PHASE2C_REVISION_V01:
        if doc.get("schema") != SCHEMA_ID_V01:
            errs.append(f"v0.1 bad schema id: {doc.get('schema')!r}")
        return errs
    if rev == PHASE2C_REVISION:
        errs.extend(_validate_v02(doc))
        return errs
    errs.append(f"unknown freeze revision: {rev!r}")
    return errs


__all__ = [
    "PHASE2C_REVISION",
    "PHASE2C_REVISION_V01",
    "PHASE2D_ARMS",
    "PHASE2D_VERDICTS",
    "PRIMARY_AXIS",
    "SCHEMA_ID",
    "SCHEMA_ID_V01",
    "classify_dispersion_pair",
    "confirmatory_pairs",
    "decide_phase2d_verdict",
    "freeze_manifest",
    "load_v01_freeze",
    "validate_freeze_doc",
]
