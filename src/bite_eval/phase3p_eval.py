"""Phase 3P development evaluation of record alignment v2.

Does not change v1 policy/operator/evaluator. Does not rewrite Phase 3O.
Does not open p3f. Does not retune thresholds. Reproduction surfaces are
secondary only.
"""

from __future__ import annotations

import json
import subprocess
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from bite_bench.phase3p import (
    CLAIM_BOUNDARY,
    FORBIDDEN_BODY,
    FORMATS,
    O0_SHA,
    P1_VERDICTS,
    PHASE3O_REMAINS,
    PHASE3O_VERDICT,
    PROTOCOL_FROZEN,
    REPRODUCTION_SURFACES,
    VERDICT_BLOCKED,
    VERDICT_PARTIAL,
    VERDICT_VALIDATED,
    development_surfaces,
    freeze_manifest,
    refuse_p3f_evaluation,
    validate_phase3p_freeze,
)
from bite_eval.composition_safety_v2 import composition_safety_v2
from bite_ingestion.adapters.bite_xfer1 import packet_from_document
from bite_ingestion.logical_record import identities_from_payload, identity_of_text
from bite_ingestion.operators.integrate import IntegrateOperator
from bite_ingestion.operators.reduce_v2 import LogicalReduceOperatorV2
from bite_ingestion.policies.conditional_texture_policy_v2 import (
    ConditionalTexturePolicyV2,
    PolicyLeakError,
    assert_policy_gold_isolated,
)
from bite_ingestion.profilers.structural_redundancy_v2 import measure as measure_v2

SCHEMA_ID = "bite-phase3p-record-alignment/v0.1"
ALIGN_SCHEMA_ID = "bite-phase3p-sensor-operator-alignment/v0.1"
SAFETY_SCHEMA_ID = "bite-phase3p-lineage-safety/v0.1"
REPRO_SCHEMA_ID = "bite-phase3p-xfer1-reproduction/v0.1"
PROTOCOL_COMMIT_SHA = "4756acbb09e3df59dbe4832e2888c35a9cd9c37b"
LOCKED_BLOBS_PATH = Path(__file__).resolve().parents[2] / "benchmarks" / "spec" / "phase3n-locked-blobs.json"
_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase3p-record-alignment-freeze.json"
PHASE3O_PATH = _REPO / "artifacts" / "phase3o" / "xfer1-transfer.json"
XFER1_DIR = _REPO / "corpora" / "bite-xfer-1" / "rendered"
ARTIFACT_DIR = _REPO / "artifacts" / "phase3p"
RESULT_PATH = ARTIFACT_DIR / "record-alignment.json"
RESULT_MD_PATH = ARTIFACT_DIR / "record-alignment.md"
ALIGN_PATH = ARTIFACT_DIR / "sensor-operator-alignment.json"
SAFETY_PATH = ARTIFACT_DIR / "lineage-safety.json"
REPRO_PATH = ARTIFACT_DIR / "xfer1-reproduction.json"

POLICY_CASES = {"p3p-rjoin", "p3p-uri", "p3p-tjoin"}
DERIVED_CASES = {"p3p-derj", "p3p-nroot"}
EXPECTED_POLICY = {
    "p3p-rjoin": ["REDUCE_v2", "INTEGRATE"],
    "p3p-uri": ["UNTANGLE", "REDUCE_v2", "INTEGRATE"],
    "p3p-tjoin": ["INTEGRATE"],
}


def _tau_sequence(packet: Mapping[str, Any]) -> list[str]:
    tau = packet.get("tau")
    if isinstance(tau, Mapping):
        return [str(item) for item in list(tau.get("sequence") or [])]
    return []


def _git_blob(path: str) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", f"HEAD:{path}"], cwd=_REPO, text=True
    ).strip()


def _units(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = packet.get("units") or []
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return [dict(unit) for unit in raw if isinstance(unit, Mapping)]
    return []


def _packet(surface: Mapping[str, Any]) -> dict[str, Any]:
    refuse_p3f_evaluation(str(surface["case_id"]))
    packet = packet_from_document(
        str(surface["document"]),
        case_id=str(surface["case_id"]),
        fmt=str(surface["format"]),
    )
    assert_policy_gold_isolated(packet)
    return packet


def _as_derived(packet: dict[str, Any]) -> dict[str, Any]:
    out = dict(packet)
    derived: list[dict[str, Any]] = []
    for index, unit in enumerate(_units(packet)):
        row = dict(unit)
        src = str(unit["unit_id"])
        row["unit_id"] = f"{src}-der"
        row["parent_unit_id"] = src
        row["derived_from"] = src
        derived.append(row)
    out["units"] = derived
    out["lineage_units"] = _units(packet)
    return out


def _logical_mult(packet: Mapping[str, Any]) -> dict[tuple[str, str], int]:
    counts: Counter[tuple[str, str]] = Counter()
    for unit in _units(packet):
        try:
            ident = identity_of_text(str(unit.get("text", "")))
        except Exception:  # noqa: BLE001
            ident = None
        if ident is not None:
            counts[ident] += 1
    return dict(counts)


def _alignment_row(surface: Mapping[str, Any]) -> dict[str, Any]:
    packet = _packet(surface)
    report = measure_v2({"payload": packet["document"], "text": packet["document"]})
    ratio = float(report.features["duplicate_unit_ratio"])
    sensor_dup = (not report.fail_closed) and ratio > 0.0
    after = dict(LogicalReduceOperatorV2().apply(packet))
    before_mult = _logical_mult(packet)
    after_mult = _logical_mult(after)
    reduce_blob = after.get("reduce")
    omit = {}
    if isinstance(reduce_blob, Mapping):
        omit = dict(reduce_blob.get("omit_map") or {})
    reduced_idents = set()
    before_by_id = {str(u["unit_id"]): u for u in _units(packet)}
    for omitted in omit:
        try:
            ident = identity_of_text(str(before_by_id[omitted].get("text", "")))
        except Exception:  # noqa: BLE001
            ident = None
        if ident is not None:
            reduced_idents.add(ident)
    sensor_idents, _fail, _notes = identities_from_payload(str(packet["document"]))
    sensor_dup_idents = {ident for ident, n in Counter(sensor_idents).items() if n >= 2}
    expect = bool(surface["expect_duplicate"])
    after_ok = all(n <= 1 for n in after_mult.values()) if expect else after_mult == before_mult
    bidi_fwd = (not expect) or after_ok
    bidi_rev = reduced_idents <= sensor_dup_idents
    if expect:
        bidi = sensor_dup and bidi_fwd and bidi_rev and bool(reduced_idents)
    else:
        bidi = (not sensor_dup) and not omit
    return {
        "surface_id": surface["surface_id"],
        "case_id": surface["case_id"],
        "format": surface["format"],
        "role": surface["role"],
        "expect_duplicate": expect,
        "sensor_duplicate": sensor_dup,
        "duplicate_unit_ratio": ratio,
        "fail_closed": report.fail_closed,
        "max_multiplicity_after": max(after_mult.values()) if after_mult else 0,
        "n_omitted": len(omit),
        "biconditional": bidi,
        "ok": bidi and after_ok and not report.fail_closed,
    }


def _safety_row(surface: Mapping[str, Any], policy: ConditionalTexturePolicyV2) -> dict[str, Any]:
    packet = _packet(surface)
    cid = str(surface["case_id"])
    gold = [str(unit["unit_id"]) for unit in _units(packet)]
    if cid in DERIVED_CASES:
        working = _as_derived(packet)
        after = dict(IntegrateOperator().apply(working))
        sequence = ["INTEGRATE"]
        before = working
    else:
        before = packet
        after = policy.apply(packet)
        sequence = _tau_sequence(after)
    safety = composition_safety_v2(before, after, gold_ids=gold, sequence=sequence)
    expect = EXPECTED_POLICY.get(cid)
    sequence_ok = True if expect is None else sequence == expect
    return {
        "surface_id": surface["surface_id"],
        "case_id": cid,
        "format": surface["format"],
        "role": surface["role"],
        "sequence": sequence,
        "sequence_ok": sequence_ok,
        "safety": safety,
        "safety_ok": safety["ok"],
        "ok": sequence_ok and safety["ok"],
    }


def _invariance(align_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in align_rows:
        by_case[str(row["case_id"])].append(row)
    out = []
    for cid, group in sorted(by_case.items()):
        fmts = {str(row["format"]) for row in group}
        if fmts != set(FORMATS):
            continue
        ratios = {row["format"]: row["duplicate_unit_ratio"] for row in group}
        after = {row["format"]: row["max_multiplicity_after"] for row in group}
        ok = len(set(ratios.values())) == 1 and len(set(after.values())) == 1
        out.append({"case_id": cid, "ratios": ratios, "after": after, "ok": ok})
    return {"n_ok": sum(1 for row in out if row["ok"]), "n_cases": len(out), "rows": out}


def _reproduction() -> dict[str, Any]:
    phase3o = json.loads(PHASE3O_PATH.read_text(encoding="utf-8"))
    rows = []
    for row in phase3o.get("rows") or []:
        sid = str(row.get("surface_id"))
        if sid in REPRODUCTION_SURFACES:
            rows.append(
                {
                    "surface_id": sid,
                    "failure_classes": row.get("failure_classes"),
                    "ok": row.get("ok"),
                    "primary": False,
                }
            )
    return {
        "schema": REPRO_SCHEMA_ID,
        "phase3o_verdict": phase3o.get("verdict"),
        "phase3o_remains": PHASE3O_REMAINS,
        "n_surfaces": len(rows),
        "primary": False,
        "rows": rows,
    }


def _v2_regression() -> list[dict[str, Any]]:
    policy = ConditionalTexturePolicyV2()
    out: list[dict[str, Any]] = []
    for surface_id in REPRODUCTION_SURFACES:
        cid, fmt = surface_id.rsplit("-", 1)
        if fmt == "mixed_order_json":
            name = f"{cid}.mixed_order_json.json"
        elif fmt == "pretty_json":
            name = f"{cid}.pretty_json.json"
        else:
            continue
        body = (XFER1_DIR / name).read_text(encoding="utf-8")
        packet = packet_from_document(body, case_id=cid, fmt=fmt)
        after = policy.apply(packet)
        sequence = _tau_sequence(after)
        gold = [str(unit["unit_id"]) for unit in _units(packet)]
        safety = composition_safety_v2(packet, after, gold_ids=gold, sequence=sequence)
        after_mult = _logical_mult(after)
        out.append(
            {
                "surface_id": surface_id,
                "sequence": sequence,
                "safety_ok": safety["ok"],
                "max_multiplicity_after": max(after_mult.values()) if after_mult else 0,
                "primary": False,
            }
        )
    return out


def _premise_errors() -> list[str]:
    errs = validate_phase3p_freeze(json.loads(FREEZE_PATH.read_text(encoding="utf-8")))
    if json.loads(FREEZE_PATH.read_text(encoding="utf-8")) != freeze_manifest():
        errs.append("committed freeze drifted")
    if freeze_manifest().get("verdict") != PROTOCOL_FROZEN:
        errs.append("P0 freeze drifted")
    locked = json.loads(LOCKED_BLOBS_PATH.read_text(encoding="utf-8")).get("git_blob_sha") or {}
    for path, expected in locked.items():
        try:
            if _git_blob(str(path)) != expected:
                errs.append(f"v1 blob drifted: {path}")
        except Exception as exc:  # noqa: BLE001
            errs.append(f"blob check failed {path}: {exc}")
    if json.loads(PHASE3O_PATH.read_text(encoding="utf-8")).get("verdict") != PHASE3O_VERDICT:
        errs.append("Phase 3O verdict rewritten")
    return errs


def run_evaluation() -> dict[str, Any]:
    blocked = _premise_errors()
    align_rows: list[dict[str, Any]] = []
    safety_rows: list[dict[str, Any]] = []
    policy = ConditionalTexturePolicyV2()
    try:
        for surface in development_surfaces():
            refuse_p3f_evaluation(str(surface["case_id"]))
            if any(token in str(surface["document"]) for token in FORBIDDEN_BODY):
                blocked.append(f"gold leak in {surface['surface_id']}")
                continue
            align_rows.append(_alignment_row(surface))
            if surface["case_id"] in POLICY_CASES or surface["case_id"] in DERIVED_CASES:
                safety_rows.append(_safety_row(surface, policy))
    except (PolicyLeakError, Exception) as exc:  # noqa: BLE001
        blocked.append(str(exc))
    invariance = _invariance(align_rows)
    repro = _reproduction()
    regression = _v2_regression()
    blob = json.dumps({"align": align_rows, "safety": safety_rows}, sort_keys=True)
    if "p3f-" in blob:
        blocked.append("p3f identifier leaked")
    align_ok = bool(align_rows) and all(row["ok"] for row in align_rows)
    safety_ok = bool(safety_rows) and all(row["ok"] for row in safety_rows)
    inv_ok = bool(invariance["rows"]) and all(row["ok"] for row in invariance["rows"])
    negatives = [row for row in align_rows if not row["expect_duplicate"]]
    neg_ok = bool(negatives) and all(row["ok"] for row in negatives)
    checks = {
        "sensor_operator_biconditional": align_ok,
        "four_rendering_invariance": inv_ok,
        "lineage_aware_safety": safety_ok,
        "negative_controls": neg_ok,
        "v1_unchanged": not any("blob drifted" in item for item in blocked),
        "phase3o_failed_unchanged": not any("verdict rewritten" in item for item in blocked),
        "p3f_sealed": not any("p3f" in item.lower() for item in blocked),
        "reproduction_not_primary": repro.get("primary") is False,
    }
    if blocked:
        verdict = VERDICT_BLOCKED
    elif all(checks.values()):
        verdict = VERDICT_VALIDATED
    elif any(
        checks[key]
        for key in (
            "sensor_operator_biconditional",
            "four_rendering_invariance",
            "lineage_aware_safety",
            "negative_controls",
        )
    ):
        verdict = VERDICT_PARTIAL
    else:
        verdict = VERDICT_BLOCKED
        blocked.append("no invariant passed")
    if verdict not in P1_VERDICTS:
        verdict = VERDICT_BLOCKED
        blocked.append("verdict not in frozen set")
    return {
        "schema": SCHEMA_ID,
        "revision": "phase3p-record-alignment-v0.1",
        "protocol_revision": "phase3p-record-alignment-freeze-v0.1",
        "protocol_commit_sha": PROTOCOL_COMMIT_SHA,
        "phase3o_o0_sha": O0_SHA,
        "verdict": verdict,
        "blocked_reasons": blocked,
        "paid_api": False,
        "offline": True,
        "synthetic": True,
        "research_conclusion": False,
        "p3f_evaluation_holdout_used": False,
        "calibration": False,
        "no_new_threshold": True,
        "phase3o_verdict_unchanged": True,
        "phase3o_remains": PHASE3O_REMAINS,
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "Phase3O TRANSFER_CONFIRMED",
            "real-world corpus generalization",
            "BITE superiority",
        ],
        "rule_policy_changed": False,
        "v1_policy_changed": False,
        "v1_reduce_changed": False,
        "v1_sensor_changed": False,
        "v1_safety_changed": False,
        "token_reduction": "diagnostic_only",
        "no_winner_score": True,
        "n_align": len(align_rows),
        "n_align_ok": sum(1 for row in align_rows if row["ok"]),
        "n_safety": len(safety_rows),
        "n_safety_ok": sum(1 for row in safety_rows if row["ok"]),
        "checks": checks,
        "rows": align_rows,
        "sensor_operator_alignment": {
            "schema": ALIGN_SCHEMA_ID,
            "n_ok": sum(1 for row in align_rows if row["ok"]),
            "invariance": invariance,
            "rows": align_rows,
        },
        "lineage_safety": {
            "schema": SAFETY_SCHEMA_ID,
            "n_ok": sum(1 for row in safety_rows if row["ok"]),
            "rows": safety_rows,
        },
        "xfer1_reproduction": {**repro, "v2_regression_secondary": regression},
        "formats": list(FORMATS),
    }


def validate_phase3p_result(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("protocol_commit_sha") != PROTOCOL_COMMIT_SHA:
        errs.append("protocol commit SHA mismatch")
    if doc.get("verdict") not in P1_VERDICTS:
        errs.append("verdict not in frozen set")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation opened")
    if doc.get("phase3o_verdict_unchanged") is not True:
        errs.append("Phase 3O marked changed")
    if doc.get("no_new_threshold") is not True:
        errs.append("new threshold")
    blob = json.dumps(doc, sort_keys=True)
    if "p3f-" in blob:
        errs.append("p3f identifier leaked")
    repro = doc.get("xfer1_reproduction") or {}
    if repro.get("primary") is True:
        errs.append("reproduction counted as primary")
    return errs


def render_md(doc: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 3P logical record alignment v2",
        "",
        f"verdict: `{doc.get('verdict')}`",
        f"P0 SHA: `{doc.get('protocol_commit_sha')}`",
        f"align: {doc.get('n_align_ok')}/{doc.get('n_align')}",
        f"safety: {doc.get('n_safety_ok')}/{doc.get('n_safety')}",
        f"phase3o: `{doc.get('phase3o_remains')}`",
        "p3f evaluation: sealed",
        "",
        "## Checks",
        "",
    ]
    for key, ok in dict(doc.get("checks") or {}).items():
        lines.append(f"- {key}: `{ok}`")
    lines.extend(["", "BITE wins / Go ではない。Phase 3O は FAILED のまま。", ""])
    reasons = list(doc.get("blocked_reasons") or [])
    if reasons:
        lines.append("blocked:")
        lines.extend(f"- {reason}" for reason in reasons)
        lines.append("")
    return "\n".join(lines)


def write_artifacts(doc: Mapping[str, Any] | None = None) -> tuple[Path, ...]:
    if doc is None:
        doc = run_evaluation()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    RESULT_MD_PATH.write_text(render_md(doc), encoding="utf-8")
    ALIGN_PATH.write_text(
        json.dumps(doc["sensor_operator_alignment"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    SAFETY_PATH.write_text(
        json.dumps(doc["lineage_safety"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    REPRO_PATH.write_text(
        json.dumps(doc["xfer1_reproduction"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return RESULT_PATH, ALIGN_PATH, SAFETY_PATH, REPRO_PATH


if __name__ == "__main__":
    write_artifacts()
