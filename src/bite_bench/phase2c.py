"""Phase 2C dispersion confirmatory freeze.

Registers the primary confirmatory contrast before evaluation is opened.
Does not generate evaluation surfaces, count tokens, or run arms.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from bite_bench.phase2a import (
    PHASE2A_REVISION,
    SURFACE_REDUNDANCIES,
    SURFACE_STRUCTURES,
    design_cells,
)
from bite_bench.token_match import (
    TOKEN_MATCH_FREEZE_REVISION,
    TOKEN_MATCH_MAX_ABS_DELTA,
    TOKEN_MATCH_MAX_RELATIVE_DELTA,
)

SCHEMA_ID = "bitebench-phase2c-dispersion-freeze/v0.1"
PHASE2C_REVISION = "phase2c-dispersion-freeze-v0.1"
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


def freeze_manifest() -> dict[str, Any]:
    pairs = confirmatory_pairs()
    eval_cells = design_cells("evaluation")
    cal_cells = design_cells("calibration")
    return {
        "schema": SCHEMA_ID,
        "status": "FROZEN_PRE_HOLDOUT",
        "revision": PHASE2C_REVISION,
        "phase2a_revision": PHASE2A_REVISION,
        "phase2b_verdict": PHASE2B_VERDICT,
        "base_main_sha": BASE_MAIN_SHA,
        "offline": True,
        "paid_api": False,
        "research_conclusion": False,
        "evaluation_sealed": True,
        "arms_run": False,
        "primary_axis": PRIMARY_AXIS,
        "primary_levels": [LEFT_DISPERSION, RIGHT_DISPERSION],
        "n_planned_pairs": len(pairs),
        "case_ids": {
            "calibration": [c.case_id for c in cal_cells],
            "evaluation": [c.case_id for c in eval_cells],
        },
        "tokenizer_reference": dict(TOKENIZER_REFERENCE),
        "prompt_contract": {
            "source": "scripts/measure_phase1c_token_lengths.py",
            "system": SYSTEM_PROMPT,
            "user_template": USER_TEMPLATE,
            "thinking": "disabled",
            "add_generation_prompt": True,
        },
        "length_criterion": {
            "source": TOKEN_MATCH_FREEZE_REVISION,
            "max_abs_delta": TOKEN_MATCH_MAX_ABS_DELTA,
            "max_relative_delta": TOKEN_MATCH_MAX_RELATIVE_DELTA,
            "no_padding": True,
            "widened_after_phase2b": False,
            "calibration_observation": {
                "axis": PRIMARY_AXIS,
                "n_contrasts": 48,
                "n_matched": 48,
                "abs_delta": 0,
                "relative_delta": 0.0,
                "note": (
                    "Phase 2B calibration fact only. Evaluation token counts "
                    "are not measured or recorded in this freeze."
                ),
            },
        },
        "arms": list(PHASE2D_ARMS),
        "primary_question": {
            "ja": (
                "同じfacts・同じtoken長・同じsurface形式でも、required evidenceの"
                "dispersionだけが変わったとき、length_piとrule_piの"
                "routing/operator behaviorは異なるか？"
            ),
            "en": (
                "When facts, token length, and surface form are held fixed and "
                "only required-evidence dispersion changes, do length_pi and "
                "rule_pi differ in routing/operator behavior?"
            ),
        },
        "paid_model_accuracy_is_primary_endpoint": False,
        "primary_offline_endpoints": [
            "n_pairs_length_pi_neq_rule_pi",
            "n_pairs_rule_pi_sequence_differs_clustered_vs_dispersed",
            "n_pairs_operator_changed_payload",
            "visible_evidence_recall",
            "recoverable_evidence_recall",
            "provenance_completeness",
            "n_rebite_fires",
            "T_total",
            "payload_diff_vs_raw_full",
        ],
        "not_an_endpoint": ["BITE_wins", "morphology_superior", "Go"],
        "exclusion_rule": {
            "apply_in": "Phase 2D",
            "if_pair_fails_length_criterion": "exclude that pair from confirmatory analysis",
            "do_not": [
                "widen max_abs_delta",
                "widen max_relative_delta",
                "add padding",
                "rewrite surfaces",
                "retune routing thresholds to create a difference",
            ],
        },
        "phase2d_verdicts": {
            "PHASE2D_OFFLINE_SIGNAL": (
                "length-matched dispersion pairで、length_piでは説明できない"
                "routing/operator差が観測された。"
            ),
            "PHASE2D_OFFLINE_NO_SIGNAL": (
                "dispersionを変えても、length_piとrule_piの実質的差が観測されなかった。"
            ),
            "PHASE2D_BLOCKED": (
                "freeze条件、length criterion、instrumentationなどが破れて"
                "公平な評価ができない。"
            ),
        },
        "secondary_axes": {
            "structure": {
                "status": "secondary_length_confounded_stress_axis",
                "in_primary_confirmatory": False,
                "deleted": False,
                "phase2b_calibration_match_rate": 0.0,
                "new_matching_method_after_evaluation": False,
            },
            "redundancy": {
                "status": "secondary_length_confounded_stress_axis",
                "in_primary_confirmatory": False,
                "deleted": False,
                "phase2b_calibration_match_rate": 0.0,
                "new_matching_method_after_evaluation": False,
            },
        },
        "locks": {
            "no_profiler_in_phase2c": True,
            "no_routing_in_phase2c": True,
            "no_operator_in_phase2c": True,
            "no_evaluation_token_counts_in_phase2c": True,
            "no_threshold_retune_after_seeing_results": True,
            "no_criterion_widen_to_rescue_pairs": True,
            "evaluation_not_for_rule_tuning": True,
        },
        "confirmatory_pairs": pairs,
    }


def validate_freeze_doc(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append(f"bad schema id: {doc.get('schema')!r}")
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
    return errs


__all__ = [
    "PHASE2C_REVISION",
    "PHASE2D_ARMS",
    "PHASE2D_VERDICTS",
    "PRIMARY_AXIS",
    "SCHEMA_ID",
    "confirmatory_pairs",
    "freeze_manifest",
    "validate_freeze_doc",
]
