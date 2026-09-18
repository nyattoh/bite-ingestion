"""Phase 1D frozen confirmatory offline comparison.

Records what the four existing arms do on the already-opened evaluation
cases. Does not change profiler features, thresholds, routing, operators,
split, or the Phase 1C token-match rule.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bite_bench.generator import (
    CASE_POOL_REVISION,
    EVALUATION_SEEDS,
    generate_texture_bundle,
)
from bite_bench.token_match import (
    TOKEN_MATCH_FREEZE_REVISION,
    TOKEN_MATCH_LEFT,
    TOKEN_MATCH_MAX_ABS_DELTA,
    TOKEN_MATCH_MAX_RELATIVE_DELTA,
    TOKEN_MATCH_RIGHT,
    relative_token_delta,
    token_length_match,
)
from bite_eval.arm_runtime import PHASE1_ARMS
from bite_eval.interface import extract_budget
from bite_eval.phase1_matrix import (
    FAIRNESS,
    OFFLINE_WRAPPER,
    OUTPUT_CONSTRAINT,
    ROW_KEYS,
    arm_rows_for_packet,
    negative_control_report,
    run_phase1_matrix,
    validate_matrix_doc,
)
from bite_ingestion.packet_contract import provenance_completeness, visible_evidence_from_units

SCHEMA_ID = "bite-phase1d-confirmatory-offline/v0.1"
BASE_MAIN_SHA = "0e50a2c54b2e56beaf749bc4e7ee28be444ca7bd"
FROZEN_TEXTURES: tuple[str, str] = (TOKEN_MATCH_LEFT, TOKEN_MATCH_RIGHT)

VERDICT_SIGNAL = "PHASE1D_OFFLINE_SIGNAL"
VERDICT_NO_SIGNAL = "PHASE1D_OFFLINE_NO_SIGNAL"
VERDICT_BLOCKED = "PHASE1D_BLOCKED"
VERDICTS = (VERDICT_SIGNAL, VERDICT_NO_SIGNAL, VERDICT_BLOCKED)

CASE_KIND_EVAL = "canonical_evaluation"
CASE_KIND_CALIB = "canonical_calibration"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def freeze_manifest_path() -> Path:
    return _repo_root() / "benchmarks" / "spec" / "phase1c-token-freeze.json"


def split_manifest_path() -> Path:
    return _repo_root() / "benchmarks" / "spec" / "phase1b-split-manifest.json"


def canonical_packet(bundle: Mapping[str, Any], texture: str) -> dict[str, Any]:
    """Eval packet for one frozen texture. Same facts/question/evidence as the bundle."""
    if texture not in bundle["textures"]:
        raise KeyError(texture)
    rec = bundle["textures"][texture]
    canonical = bundle["canonical"]
    units = [dict(u) for u in rec["units"]]
    case_id = str(canonical["case_id"])
    return {
        "instance_id": f"{case_id}:{texture}",
        "family": "canonical",
        "texture": texture,
        "facts_id": str(bundle["facts_id"]),
        "benchmark_split": str(bundle["benchmark_split"]),
        "domain": "synthetic",
        "source_uri": f"bitebench://{case_id}/{texture}",
        "document": rec["text"],
        "query": str(canonical["question"]),
        "gold_answer": str(canonical["answer"]),
        "units": units,
        "gold_evidence_ids": [str(x) for x in canonical["required_evidence_ids"]],
        "visible_evidence": visible_evidence_from_units(units),
        "recoverable_evidence_ids": [],
        "provenance_complete_rate": provenance_completeness(units),
        "synthetic": True,
        "paid_api": False,
    }


def case_identity(bundle: Mapping[str, Any]) -> dict[str, Any]:
    canonical = bundle["canonical"]
    return {
        "facts_id": str(bundle["facts_id"]),
        "case_id": str(canonical["case_id"]),
        "question": str(canonical["question"]),
        "answer": str(canonical["answer"]),
        "required_evidence_ids": [str(x) for x in canonical["required_evidence_ids"]],
        "facts": list(canonical["facts"]),
        "wrapper": OFFLINE_WRAPPER,
        "output_constraint": OUTPUT_CONSTRAINT,
        "benchmark_split": str(bundle["benchmark_split"]),
    }


def verify_freeze_manifest(path: Path | None = None) -> dict[str, Any]:
    """Check the committed freeze file against the locked constants. No tokenizer."""
    freeze_path = path or freeze_manifest_path()
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    split = json.loads(split_manifest_path().read_text(encoding="utf-8"))
    mismatches: list[str] = []
    rule = freeze.get("frozen_match_rule") or {}
    if rule.get("left") != TOKEN_MATCH_LEFT or rule.get("right") != TOKEN_MATCH_RIGHT:
        mismatches.append(f"frozen pair drifted: {rule.get('left')}/{rule.get('right')}")
    if int(rule.get("max_abs_delta", -1)) != TOKEN_MATCH_MAX_ABS_DELTA:
        mismatches.append(f"max_abs_delta drifted: {rule.get('max_abs_delta')}")
    if float(rule.get("max_relative_delta", -1)) != TOKEN_MATCH_MAX_RELATIVE_DELTA:
        mismatches.append(f"max_relative_delta drifted: {rule.get('max_relative_delta')}")
    if rule.get("no_padding") is not True:
        mismatches.append("no_padding is not true")
    if freeze.get("freeze_revision") != TOKEN_MATCH_FREEZE_REVISION:
        mismatches.append(f"freeze revision drifted: {freeze.get('freeze_revision')}")
    if freeze.get("case_pool_revision") != CASE_POOL_REVISION:
        mismatches.append(f"case pool revision drifted: {freeze.get('case_pool_revision')}")

    holdout = freeze.get("holdout") or {}
    results = list(holdout.get("results") or [])
    expected_ids = list(split.get("evaluation_case_ids") or [])
    got_ids = [str(r.get("case_id")) for r in results]
    if got_ids != expected_ids:
        mismatches.append(f"holdout case ids drifted: {got_ids} != {expected_ids}")
    matched = 0
    for row in results:
        left = int(row["left_tokens"])
        right = int(row["right_tokens"])
        abs_delta = abs(left - right)
        rel = relative_token_delta(left, right)
        ok = token_length_match(left, right)
        if abs_delta != int(row["abs_delta"]):
            mismatches.append(f"{row['case_id']}: stored abs_delta != |L-R|")
        if abs(rel - float(row["relative_delta"])) > 1e-12:
            mismatches.append(f"{row['case_id']}: stored relative_delta mismatch")
        if bool(row["length_matched"]) != ok:
            mismatches.append(f"{row['case_id']}: length_matched flag disagrees with rule")
        if not ok:
            mismatches.append(
                f"{row['case_id']}: holdout pair fails frozen rule "
                f"(abs={abs_delta}, rel={rel})"
            )
        else:
            matched += 1
    if matched != 12 or holdout.get("all_matched") is not True:
        mismatches.append(f"holdout all_matched/n_matched drifted: matched={matched}")
    return {
        "ok": not mismatches,
        "mismatches": mismatches,
        "n_holdout": len(results),
        "n_matched": matched,
        "freeze_revision": freeze.get("freeze_revision"),
        "pair": {"left": TOKEN_MATCH_LEFT, "right": TOKEN_MATCH_RIGHT},
        "rule": {
            "max_abs_delta": TOKEN_MATCH_MAX_ABS_DELTA,
            "max_relative_delta": TOKEN_MATCH_MAX_RELATIVE_DELTA,
            "no_padding": True,
        },
        "tokenizer_reference": freeze.get("tokenizer_reference"),
        "holdout_results": results,
    }


def compare_remeasure_to_freeze(
    freeze_holdout: Sequence[Mapping[str, Any]],
    remeasured_pairs: Sequence[Mapping[str, Any]],
) -> list[str]:
    """Exact token-count equality against the committed holdout table."""
    by_id = {str(row["case_id"]): row for row in remeasured_pairs}
    mismatches: list[str] = []
    for row in freeze_holdout:
        cid = str(row["case_id"])
        got = by_id.get(cid)
        if got is None:
            mismatches.append(f"{cid}: missing from remeasure")
            continue
        for key in ("left_tokens", "right_tokens", "abs_delta", "length_matched"):
            if got.get(key) != row.get(key):
                mismatches.append(f"{cid}: {key} freeze={row.get(key)} remeasure={got.get(key)}")
    extra = sorted(set(by_id) - {str(r["case_id"]) for r in freeze_holdout})
    for cid in extra:
        mismatches.append(f"{cid}: extra remeasure row")
    return mismatches


def run_negative_control_self_check() -> dict[str, Any]:
    """Prove the instrument still reports known failures. No confirmatory cases."""
    doc = run_phase1_matrix(n_per_family=1, artifact_path=None)
    report = negative_control_report(doc["rows"])
    matrix_errs = validate_matrix_doc(doc)
    return {
        "ok": not report["violations"] and not matrix_errs,
        "negative_control_report": report,
        "matrix_validation": matrix_errs,
        "n_matrix_rows": doc.get("n_rows"),
    }


def _annotate_vs_raw(rows: Sequence[Mapping[str, Any]]) -> None:
    by_case: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        by_case.setdefault(str(row["case_id"]), {})[str(row["method"])] = row
    for arms in by_case.values():
        raw = arms.get("raw_full")
        if raw is None:
            continue
        for row in arms.values():
            steps = row.get("rebite_steps") or []
            row["rebite_count"] = len(steps) if isinstance(steps, list) else 0
            recovered: list[str] = []
            if isinstance(steps, list):
                for step in steps:
                    if not isinstance(step, Mapping):
                        continue
                    recovered.extend(str(x) for x in (step.get("returned_evidence_ids") or []))
            row["rebite_evidence_ids"] = recovered
            row["r_entry_count"] = len(row.get("recoverable_evidence_ids") or [])
            row["payload_matches_raw"] = row.get("payload_sha256") == raw.get("payload_sha256")
            row["payload_chars_vs_raw"] = int(row.get("payload_chars") or 0) - int(
                raw.get("payload_chars") or 0
            )
            row["token_estimate_vs_raw"] = int(row.get("token_estimate") or 0) - int(
                raw.get("token_estimate") or 0
            )
            row["T_total_vs_raw"] = int(row.get("T_total") or 0) - int(raw.get("T_total") or 0)
            row["T_target_in_vs_raw"] = int(row.get("T_target_in") or 0) - int(
                raw.get("T_target_in") or 0
            )


def run_split_rows(split: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Four arms on the frozen texture pair. Calibration and evaluation stay separate."""
    if split == "evaluation":
        seeds = EVALUATION_SEEDS
        case_kind = CASE_KIND_EVAL
    elif split == "calibration":
        from bite_bench.generator import CALIBRATION_SEEDS

        seeds = CALIBRATION_SEEDS
        case_kind = CASE_KIND_CALIB
    else:
        raise ValueError(split)

    rows: list[dict[str, Any]] = []
    identities: list[dict[str, Any]] = []
    freeze = json.loads(freeze_manifest_path().read_text(encoding="utf-8"))
    token_block = freeze["holdout" if split == "evaluation" else "calibration"]
    token_table = token_block.get("results") or token_block.get("cases") or []
    token_rows = {str(r["case_id"]): r for r in token_table}
    for seed in seeds:
        bundle = generate_texture_bundle(seed=seed, length_match=False)
        identity = case_identity(bundle)
        token_row = token_rows[identity["case_id"]]
        identity["token_match"] = {
            "left": TOKEN_MATCH_LEFT,
            "right": TOKEN_MATCH_RIGHT,
            "left_tokens": token_row["left_tokens"],
            "right_tokens": token_row["right_tokens"],
            "abs_delta": token_row["abs_delta"],
            "relative_delta": token_row["relative_delta"],
            "length_matched": token_row["length_matched"],
            "no_padding": True,
        }
        identities.append(identity)
        for texture in FROZEN_TEXTURES:
            packet = canonical_packet(bundle, texture)
            budget = extract_budget(packet, None)
            arm_rows = arm_rows_for_packet(packet, case_kind=case_kind, family="canonical")
            for row in arm_rows:
                row["benchmark_split"] = split
                row["wrapper"] = OFFLINE_WRAPPER
                row["budget"] = {
                    k: budget[k] for k in ("char_len", "n_tokens") if k in budget
                }
            rows.extend(arm_rows)
    _annotate_vs_raw(rows)
    return rows, identities


def _seq(row: Mapping[str, Any]) -> list[str]:
    return [str(x) for x in (row.get("operator_sequence") or [])]


def collect_lists(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Per-case lists. Averages are not a substitute for these."""
    by_case: dict[str, dict[str, Mapping[str, Any]]] = {}
    for row in rows:
        by_case.setdefault(str(row["case_id"]), {})[str(row["method"])] = row

    length_ne_rule: list[dict[str, Any]] = []
    operator_fired: list[dict[str, Any]] = []
    rebite_fired: list[dict[str, Any]] = []
    recall_lt_1: list[dict[str, Any]] = []
    no_op_cases: list[str] = []
    no_diff_vs_raw: list[str] = []
    rule_texture_disagreement: list[dict[str, Any]] = []
    profiler_differed_sequence_same: list[dict[str, Any]] = []

    for cid, arms in sorted(by_case.items()):
        lp, rp = arms.get("length_pi"), arms.get("rule_pi")
        raw = arms.get("raw_full")
        if lp and rp and (_seq(lp) != _seq(rp) or lp.get("payload_sha256") != rp.get("payload_sha256")):
            length_ne_rule.append(
                {
                    "case_id": cid,
                    "facts_id": lp.get("facts_id"),
                    "texture": lp.get("texture"),
                    "length_pi_sequence": _seq(lp),
                    "rule_pi_sequence": _seq(rp),
                    "payload_differs": lp.get("payload_sha256") != rp.get("payload_sha256"),
                    "length_pi_status": lp.get("status"),
                    "rule_pi_status": rp.get("status"),
                    "length_pi_recall_vis": lp.get("evidence_recall_visible"),
                    "rule_pi_recall_vis": rp.get("evidence_recall_visible"),
                }
            )
        candidate_no_op = True
        candidate_same_raw = True
        for method, row in arms.items():
            if row.get("status") == "transformed" or (
                method != "raw_full" and not row.get("no_op")
            ):
                operator_fired.append(
                    {
                        "case_id": cid,
                        "method": method,
                        "sequence": _seq(row),
                        "status": row.get("status"),
                        "r_entry_count": row.get("r_entry_count"),
                    }
                )
            if int(row.get("T_rebite") or 0) > 0 or int(row.get("rebite_count") or 0) > 0:
                rebite_fired.append(
                    {
                        "case_id": cid,
                        "method": method,
                        "T_rebite": row.get("T_rebite"),
                        "rebite_count": row.get("rebite_count"),
                        "rebite_evidence_ids": row.get("rebite_evidence_ids"),
                    }
                )
            vis = row.get("evidence_recall_visible")
            rec = row.get("evidence_recall_recoverable")
            if (isinstance(vis, (int, float)) and vis < 1.0) or (
                isinstance(rec, (int, float)) and rec < 1.0
            ):
                recall_lt_1.append(
                    {
                        "case_id": cid,
                        "method": method,
                        "evidence_recall_visible": vis,
                        "evidence_recall_recoverable": rec,
                        "sequence": _seq(row),
                    }
                )
            if method != "raw_full" and not row.get("no_op"):
                candidate_no_op = False
            if method != "raw_full" and not row.get("payload_matches_raw"):
                candidate_same_raw = False
        if candidate_no_op and raw is not None:
            no_op_cases.append(cid)
        if candidate_same_raw and raw is not None:
            no_diff_vs_raw.append(cid)

    by_facts: dict[str, dict[str, Mapping[str, Any]]] = {}
    for cid, arms in by_case.items():
        rp = arms.get("rule_pi")
        if rp is None:
            continue
        by_facts.setdefault(str(rp.get("facts_id")), {})[str(rp.get("texture"))] = rp
    for facts_id, textures in sorted(by_facts.items()):
        left = textures.get(TOKEN_MATCH_LEFT)
        right = textures.get(TOKEN_MATCH_RIGHT)
        if left is None or right is None:
            continue
        if _seq(left) != _seq(right) or left.get("status") != right.get("status"):
            rule_texture_disagreement.append(
                {
                    "facts_id": facts_id,
                    "prose_sequence": _seq(left),
                    "table_sequence": _seq(right),
                    "prose_status": left.get("status"),
                    "table_status": right.get("status"),
                    "prose_recall_vis": left.get("evidence_recall_visible"),
                    "table_recall_vis": right.get("evidence_recall_visible"),
                }
            )
        left_m = dict(left.get("morphology") or {})
        right_m = dict(right.get("morphology") or {})
        morph_keys = sorted(set(left_m) | set(right_m))
        morph_delta = {
            k: [left_m.get(k), right_m.get(k)]
            for k in morph_keys
            if left_m.get(k) != right_m.get(k)
        }
        if morph_delta and _seq(left) == _seq(right):
            profiler_differed_sequence_same.append(
                {
                    "facts_id": facts_id,
                    "sequence": _seq(left),
                    "morphology_delta": morph_delta,
                }
            )

    return {
        "length_pi_ne_rule_pi": length_ne_rule,
        "operator_fired": operator_fired,
        "rebite_fired": rebite_fired,
        "recall_lt_1": recall_lt_1,
        "no_op_cases": no_op_cases,
        "no_diff_vs_raw": no_diff_vs_raw,
        "rule_pi_texture_disagreement": rule_texture_disagreement,
        "profiler_differed_sequence_same": profiler_differed_sequence_same,
    }


def decide_verdict(lists: Mapping[str, Any]) -> str:
    """Offline observation only. Not a Go/Stop and not a paid-model claim."""
    if lists.get("length_pi_ne_rule_pi") or lists.get("rule_pi_texture_disagreement"):
        return VERDICT_SIGNAL
    return VERDICT_NO_SIGNAL


def _mean(vals: Sequence[float]) -> float | None:
    return sum(vals) / len(vals) if vals else None


def split_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    def nums(key: str) -> list[float]:
        return [float(r[key]) for r in rows if isinstance(r.get(key), (int, float))]

    return {
        "n_rows": n,
        "n_failed": sum(1 for r in rows if r.get("failed") or r.get("status") == "failed"),
        "n_no_op": sum(1 for r in rows if r.get("no_op") or r.get("status") == "no_op"),
        "n_pass_through": sum(1 for r in rows if r.get("status") == "pass_through"),
        "n_transformed": sum(1 for r in rows if r.get("status") == "transformed"),
        "mean_evidence_recall_visible": _mean(nums("evidence_recall_visible")),
        "mean_evidence_recall_recoverable": _mean(nums("evidence_recall_recoverable")),
        "mean_provenance": _mean(nums("provenance")),
        "mean_T_total": _mean(nums("T_total")),
        "mean_payload_chars": _mean(nums("payload_chars")),
        "note": "means are descriptive only; lists in `comparisons` are the result",
    }


def build_phase1d_doc(
    *,
    tokenizer_remeasure: Mapping[str, Any] | None = None,
    require_tokenizer_remeasure: bool = False,
    include_calibration: bool = True,
) -> dict[str, Any]:
    freeze_check = verify_freeze_manifest()
    neg = run_negative_control_self_check()
    blocked_reasons: list[str] = []
    if not freeze_check["ok"]:
        blocked_reasons.append("token freeze manifest does not match the locked rule or holdout table")
        blocked_reasons.extend(freeze_check["mismatches"])
    if not neg["ok"]:
        blocked_reasons.append("negative controls no longer report the required failures")
        blocked_reasons.extend(str(v) for v in neg["negative_control_report"].get("violations") or [])
        blocked_reasons.extend(str(v) for v in neg.get("matrix_validation") or [])
    if require_tokenizer_remeasure:
        if not tokenizer_remeasure:
            blocked_reasons.append("tokenizer remeasure missing")
        elif not tokenizer_remeasure.get("ok"):
            blocked_reasons.append("tokenizer remeasure does not match freeze holdout")
            blocked_reasons.extend(str(v) for v in tokenizer_remeasure.get("mismatches") or [])
            if tokenizer_remeasure.get("error"):
                blocked_reasons.append(str(tokenizer_remeasure["error"]))

    eval_rows: list[dict[str, Any]] = []
    eval_identities: list[dict[str, Any]] = []
    calib_rows: list[dict[str, Any]] = []
    calib_identities: list[dict[str, Any]] = []
    if not blocked_reasons:
        eval_rows, eval_identities = run_split_rows("evaluation")
        if any(r.get("failed") or r.get("status") == "failed" for r in eval_rows):
            blocked_reasons.append("a confirmatory arm failed; comparison is not fair")
        if include_calibration:
            calib_rows, calib_identities = run_split_rows("calibration")

    lists = collect_lists(eval_rows) if eval_rows else collect_lists([])
    if blocked_reasons:
        verdict = VERDICT_BLOCKED
    else:
        verdict = decide_verdict(lists)

    doc: dict[str, Any] = {
        "schema": SCHEMA_ID,
        "offline": True,
        "paid_api": False,
        "synthetic": True,
        "research_conclusion": False,
        "purpose": (
            "frozen confirmatory offline comparison of four arms; "
            "not a paid-model result and not an architecture-superiority claim"
        ),
        "base_main_sha": BASE_MAIN_SHA,
        "case_pool_revision": CASE_POOL_REVISION,
        "token_match_freeze_revision": TOKEN_MATCH_FREEZE_REVISION,
        "arms": list(PHASE1_ARMS),
        "frozen_textures": list(FROZEN_TEXTURES),
        "fairness": FAIRNESS,
        "shared_across_arms": [
            "facts",
            "question",
            "answer",
            "required_evidence",
            "wrapper",
            "budget",
        ],
        "token_freeze_verification": {
            **{k: freeze_check[k] for k in ("ok", "mismatches", "n_holdout", "n_matched", "rule", "pair")},
            "tokenizer_remeasure": dict(tokenizer_remeasure) if tokenizer_remeasure else None,
            "require_tokenizer_remeasure": require_tokenizer_remeasure,
        },
        "negative_control_self_check": {
            "ok": neg["ok"],
            "n_matrix_rows": neg.get("n_matrix_rows"),
            "matrix_validation": neg.get("matrix_validation"),
            "negative_control_report": neg["negative_control_report"],
        },
        "blocked_reasons": blocked_reasons,
        "verdict": verdict,
        "confirmatory": {
            "split": "evaluation",
            "role": "confirmatory",
            "n_canonical_cases": 12,
            "n_textures": 2,
            "n_arms": 4,
            "n_rows": len(eval_rows),
            "identities": eval_identities,
            "summary": split_summary(eval_rows),
            "comparisons": lists,
            "rows": eval_rows,
        },
        "development": {
            "split": "calibration",
            "role": "development / descriptive; not mixed into confirmatory",
            "n_rows": len(calib_rows),
            "identities": calib_identities,
            "summary": split_summary(calib_rows),
            "comparisons": collect_lists(calib_rows) if calib_rows else collect_lists([]),
            "rows": calib_rows,
        },
    }
    return doc


def render_confirmatory_md(doc: Mapping[str, Any]) -> str:
    conf = dict(doc.get("confirmatory") or {})
    lists = dict(conf.get("comparisons") or {})
    neg = dict(doc.get("negative_control_self_check") or {})
    ncr = dict(neg.get("negative_control_report") or {})
    freeze = dict(doc.get("token_freeze_verification") or {})
    rem = freeze.get("tokenizer_remeasure") if isinstance(freeze.get("tokenizer_remeasure"), Mapping) else {}
    devel = dict(doc.get("development") or {})
    lines = [
        "# Phase 1D confirmatory offline comparison",
        "",
        "有料モデル精度は測っていない。BITE の優劣は主張しない。",
        "",
        f"- base main SHA: `{doc.get('base_main_sha')}`",
        f"- verdict: **{doc.get('verdict')}**",
        f"- paid_api: {doc.get('paid_api')}",
        (
            f"- frozen pair: `{TOKEN_MATCH_LEFT}` vs `{TOKEN_MATCH_RIGHT}` "
            f"(abs <= {TOKEN_MATCH_MAX_ABS_DELTA}, rel <= {TOKEN_MATCH_MAX_RELATIVE_DELTA}, no padding)"
        ),
        (
            f"- confirmatory rows: {conf.get('n_rows')} "
            f"(12 cases x 2 textures x 4 arms)"
        ),
        "",
        "## Self-check",
        "",
        (
            f"- negative controls ok: {neg.get('ok')} "
            f"(checked={ncr.get('n_checked')}, violations={ncr.get('violations') or 'none'})"
        ),
        f"- freeze manifest ok: {freeze.get('ok')} mismatches={freeze.get('mismatches') or 'none'}",
        f"- tokenizer remeasure ok: {rem.get('ok') if rem else 'not recorded'}",
        "",
    ]
    blocked = list(doc.get("blocked_reasons") or [])
    if blocked:
        lines += ["## BLOCKED reasons", ""]
        for reason in blocked:
            lines.append(f"- {reason}")
        lines.append("")

    def _dump(title: str, items: object) -> None:
        lines.append(f"### {title}")
        lines.append("")
        if not items:
            lines.append("なし")
            lines.append("")
            return
        if isinstance(items, list) and items and isinstance(items[0], str):
            for x in items:
                lines.append(f"- `{x}`")
            lines.append("")
            return
        if isinstance(items, list):
            for item in items:
                lines.append(f"- `{json.dumps(item, ensure_ascii=False, sort_keys=True)}`")
            lines.append("")

    lines += [
        "## Confirmatory lists (evaluation / holdout only)",
        "",
        "平均値はこの一覧の代わりにならない。",
        "",
    ]
    _dump("A. length_pi != rule_pi", lists.get("length_pi_ne_rule_pi"))
    _dump("A2. rule_pi が同一 facts で texture 間で違う判断", lists.get("rule_pi_texture_disagreement"))
    _dump(
        "A3. profiler は texture で違うが sequence は同じ",
        lists.get("profiler_differed_sequence_same"),
    )
    _dump("operator が実際に発火した (transformed / not no_op)", lists.get("operator_fired"))
    _dump("re-bite が実際に発火した", lists.get("rebite_fired"))
    _dump("evidence recall が 1.0 未満", lists.get("recall_lt_1"))
    _dump("no-op だった case", lists.get("no_op_cases"))
    _dump("raw_full と payload 差がない case", lists.get("no_diff_vs_raw"))

    s = dict(conf.get("summary") or {})
    lines += [
        "## Confirmatory counts (descriptive means only)",
        "",
        (
            f"- n_rows={s.get('n_rows')} n_failed={s.get('n_failed')} "
            f"n_no_op={s.get('n_no_op')} n_transformed={s.get('n_transformed')} "
            f"n_pass_through={s.get('n_pass_through')}"
        ),
        (
            f"- mean recall_vis={s.get('mean_evidence_recall_visible')} "
            f"recall_rec={s.get('mean_evidence_recall_recoverable')} "
            f"provenance={s.get('mean_provenance')}"
        ),
        f"- mean T_total={s.get('mean_T_total')} mean payload_chars={s.get('mean_payload_chars')}",
        "",
        "## Development / calibration (not confirmatory)",
        "",
        f"- n_rows={devel.get('n_rows')}",
        f"- length_pi != rule_pi: {len((devel.get('comparisons') or {}).get('length_pi_ne_rule_pi') or [])}",
        f"- operator fired: {len((devel.get('comparisons') or {}).get('operator_fired') or [])}",
        f"- rebite fired: {len((devel.get('comparisons') or {}).get('rebite_fired') or [])}",
        "",
        "## A-E (confirmatory, not a win/loss claim)",
        "",
        (
            f"- A routing: length_pi != rule_pi = {len(lists.get('length_pi_ne_rule_pi') or [])}; "
            f"rule_pi texture disagreement = {len(lists.get('rule_pi_texture_disagreement') or [])}"
        ),
        (
            "- A profiler: "
            f"{len(lists.get('profiler_differed_sequence_same') or [])} facts_id "
            "had a morphology delta between prose and table with the same sequence"
        ),
        f"- B evidence loss: recall_lt_1 = {len(lists.get('recall_lt_1') or [])}",
        f"- C re-bite fired = {len(lists.get('rebite_fired') or [])}",
        (
            f"- D extra work: operator_fired = {len(lists.get('operator_fired') or [])}; "
            f"no-op cases = {len(lists.get('no_op_cases') or [])}"
        ),
        (
            f"- E vs raw_full: payload-identical cases = {len(lists.get('no_diff_vs_raw') or [])} "
            f"of {len(lists.get('no_op_cases') or []) or 24} surfaces"
        ),
        "",
        "## Per confirmatory row",
        "",
        (
            "| case_id | method | status | sequence | recall_vis | recall_rec | prov | "
            "T_rebite | T_total | vs_raw_chars | no_op |"
        ),
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    by_case: dict[str, dict[str, Mapping[str, Any]]] = {}
    for row in conf.get("rows") or []:
        if isinstance(row, Mapping):
            by_case.setdefault(str(row.get("case_id")), {})[str(row.get("method"))] = row
    for cid in sorted(by_case):
        for method in PHASE1_ARMS:
            row = by_case[cid].get(method)
            if not isinstance(row, Mapping):
                continue
            seq = ",".join(_seq(row)) or "-"
            lines.append(
                f"| `{cid}` | {method} | {row.get('status')} | `{seq}` | "
                f"{row.get('evidence_recall_visible')} | {row.get('evidence_recall_recoverable')} | "
                f"{row.get('provenance')} | {row.get('T_rebite')} | {row.get('T_total')} | "
                f"{row.get('payload_chars_vs_raw')} | {row.get('no_op')} |"
            )
    lines.append("")
    return "\n".join(lines)


def validate_confirmatory_doc(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("paid_api") is not False:
        errs.append("paid_api must be false")
    if doc.get("schema") != SCHEMA_ID:
        errs.append(f"bad schema id: {doc.get('schema')!r}")
    verdict = doc.get("verdict")
    if verdict not in VERDICTS:
        errs.append(f"verdict must be one of {VERDICTS}, got {verdict!r}")
    if doc.get("research_conclusion") is not False:
        errs.append("research_conclusion must be false")
    freeze = doc.get("token_freeze_verification")
    if not isinstance(freeze, Mapping):
        errs.append("missing token_freeze_verification")
    neg = doc.get("negative_control_self_check")
    if not isinstance(neg, Mapping):
        errs.append("missing negative_control_self_check")

    conf = doc.get("confirmatory")
    if not isinstance(conf, Mapping):
        return errs + ["missing confirmatory"]
    if conf.get("split") != "evaluation":
        errs.append("confirmatory.split must be evaluation")
    rows = conf.get("rows")
    if not isinstance(rows, list):
        return errs + ["confirmatory.rows must be a list"]

    devel = doc.get("development")
    if not isinstance(devel, Mapping):
        errs.append("missing development split (must exist even if empty)")
    else:
        if devel.get("split") != "calibration":
            errs.append("development.split must be calibration")
        for row in devel.get("rows") or []:
            if isinstance(row, Mapping) and row.get("benchmark_split") == "evaluation":
                errs.append("evaluation row leaked into development")

    if verdict != VERDICT_BLOCKED:
        if len(rows) != 12 * 2 * 4:
            errs.append(f"confirmatory must have 96 rows, got {len(rows)}")
        ncr = (neg or {}).get("negative_control_report") if isinstance(neg, Mapping) else None
        if isinstance(ncr, Mapping) and ncr.get("violations"):
            errs.append("negative control violations present but verdict is not BLOCKED")
        if isinstance(freeze, Mapping) and freeze.get("ok") is not True:
            errs.append("freeze verification not ok but verdict is not BLOCKED")

    seen_eval_ids: set[str] = set()
    for i, row in enumerate(rows):
        if not isinstance(row, Mapping):
            errs.append(f"row {i} not an object")
            continue
        for k in ROW_KEYS:
            if k not in row:
                errs.append(f"row {i} missing {k}")
        if row.get("case_kind") != CASE_KIND_EVAL:
            errs.append(f"row {i} case_kind is not canonical_evaluation")
        if row.get("benchmark_split") != "evaluation":
            errs.append(f"row {i} is not evaluation")
        if row.get("texture") not in FROZEN_TEXTURES:
            errs.append(f"row {i} texture {row.get('texture')!r} is not the frozen pair")
        seen_eval_ids.add(str(row.get("facts_id")))
        buckets = [
            int(row.get(k) or 0)
            for k in (
                "T_profiler",
                "T_router",
                "T_operator",
                "T_target_in",
                "T_target_out",
                "T_rebite",
            )
        ]
        if int(row.get("T_total") or 0) != sum(buckets):
            errs.append(f"row {i} T_total != bucket sum")
        ids = list(row.get("ledger_call_ids") or [])
        if len(ids) != len(set(ids)):
            errs.append(f"row {i} duplicate call_id")

    if verdict != VERDICT_BLOCKED and seen_eval_ids:
        expected = {f"syn-case-{i:03d}" for i in range(12, 24)}
        if seen_eval_ids != expected:
            errs.append(f"confirmatory facts_id set drifted: {sorted(seen_eval_ids)}")

    for name in (
        "length_pi_ne_rule_pi",
        "operator_fired",
        "rebite_fired",
        "recall_lt_1",
        "no_op_cases",
        "no_diff_vs_raw",
        "profiler_differed_sequence_same",
    ):
        comparisons = conf.get("comparisons")
        if not isinstance(comparisons, Mapping) or name not in comparisons:
            errs.append(f"comparisons missing {name}")
    return errs


__all__ = [
    "BASE_MAIN_SHA",
    "CASE_KIND_CALIB",
    "CASE_KIND_EVAL",
    "FROZEN_TEXTURES",
    "SCHEMA_ID",
    "VERDICTS",
    "VERDICT_BLOCKED",
    "VERDICT_NO_SIGNAL",
    "VERDICT_SIGNAL",
    "build_phase1d_doc",
    "canonical_packet",
    "collect_lists",
    "compare_remeasure_to_freeze",
    "decide_verdict",
    "render_confirmatory_md",
    "run_negative_control_self_check",
    "run_split_rows",
    "validate_confirmatory_doc",
    "verify_freeze_manifest",
]
