"""Phase 4E E0 full-key reference identity v2 protocol.

Freezes the repair contract, fresh p4e fixtures, intended edges, bridge
rule, and verdicts. Does not implement identity v2, sensor v4, or policy v5.
Does not rewrite Phase 4C/4D. Does not open p3f. Does not add baselines.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation

SCHEMA_ID = "bitebench-phase4e-full-key-reference-freeze/v0.1"
REVISION = "phase4e-full-key-reference-freeze-v0.1"
PROTOCOL_FROZEN = "PHASE4E_FULL_KEY_REFERENCE_PROTOCOL_FROZEN"
VERDICT_VALIDATED = "PHASE4E_FULL_KEY_REFERENCE_VALIDATED"
VERDICT_PARTIAL = "PHASE4E_FULL_KEY_REFERENCE_PARTIAL"
VERDICT_BLOCKED = "PHASE4E_FULL_KEY_REFERENCE_BLOCKED"
E1_VERDICTS = (VERDICT_VALIDATED, VERDICT_PARTIAL, VERDICT_BLOCKED)
PREMISE = "PHASE4D_MEASUREMENT_SEMANTICS_AUDITED"
PHASE4C_VERDICT = "PHASE4C_REAL_HOLDOUT_MEASURED"
PHASE3S_VERDICT = "PHASE3S_REFERENCE_SPECIFICITY_FAILED"
PHASE3Q_VERDICT = "PHASE3Q_XFER2_TRANSFER_FAILED"
PHASE3T_VERDICT = "PHASE3T_EXACT_REFERENCE_VALIDATED"
PHASE4D_HEAD = "8a585d2f0552541478bca5c691e4c051f5d626f3"
PHASE4C_RESULT_BLOB = "f344bde69d7f963bb78780e967bc59bf639d2942"
PHASE4C_REFERENCE_BLOB = "9d0fd974d72d923f97f7c9dc6f325d7ea1e8a032"
PHASE4C_PROVENANCE_BLOB = "b22d290d1d8f89276c923439b62f5ae1102a9fbb"
PHASE4D_ATOM_BLOB = "8092ad6a61c9407b892fcb42fec5dc89f6fe7348"
PHASE4D_RESULT_BLOB = "5a0060138866ed28fca9cb54b5916b03edebea5c"
GENERATION = "p4e"
FORMATS = ("key_value", "compact_json", "pretty_json", "reversed_order_json")
LOCKED_T_HIGH = 4.0
FULL_KEY_GRAMMAR = r"[A-Za-z_][A-Za-z0-9_]*(?:[.-][A-Za-z0-9_]+)*"
CLAIM_BOUNDARY = "development validation of full-key reference identity v2"
FAMILIES = (
    "simple_exact",
    "dotted_exact",
    "hyphenated_exact",
    "mixed_exact",
    "neg_prefix",
    "neg_suffix",
    "neg_substring",
    "neg_longer",
    "neg_hyphen_suffix",
    "hostname_version",
    "join_span",
    "actionability_control",
)
FAMILY_SLUG = {
    "simple_exact": "ex",
    "dotted_exact": "dot",
    "hyphenated_exact": "hyp",
    "mixed_exact": "mix",
    "neg_prefix": "npr",
    "neg_suffix": "nsf",
    "neg_substring": "nsb",
    "neg_longer": "nlg",
    "neg_hyphen_suffix": "nhs",
    "hostname_version": "hst",
    "join_span": "jsn",
    "actionability_control": "act",
}
FAMILY_DISTANCES = {
    "simple_exact": (1, 3, 4, 9),
    "dotted_exact": (1, 3, 4, 9),
    "hyphenated_exact": (1, 9),
    "mixed_exact": (1, 9),
    "neg_prefix": (3,),
    "neg_suffix": (3,),
    "neg_substring": (3,),
    "neg_longer": (3,),
    "neg_hyphen_suffix": (3,),
    "hostname_version": (3,),
    "join_span": (3,),
    "actionability_control": (3,),
}
POSITIVE = frozenset({"simple_exact", "dotted_exact", "hyphenated_exact", "mixed_exact"})
N_CANONICAL = sum(len(dists) for dists in FAMILY_DISTANCES.values())
N_SURFACES = N_CANONICAL * len(FORMATS)
LOCKED_BLOBS = {
    "src/bite_ingestion/profilers/reference_identity_v1.py": (
        "49dcd367eccdece7a1bd90df0a3f44f0c24ded65"
    ),
    "src/bite_ingestion/profilers/dependency_dispersion_v3.py": (
        "9ec1c46a68d685210898552c879098bf0416e56d"
    ),
    "src/bite_ingestion/policies/conditional_texture_policy_v4.py": (
        "04d46b15424ccbaf02694d7e7ae056b0b6715686"
    ),
    "src/bite_ingestion/policies/projected_actionability_plan_v1.py": (
        "af3737f078a6d91da38999885aea13860350526a"
    ),
    "src/bite_ingestion/operators/reduce_v2.py": "d4bafba7dfdd048a0ccad404a8f706202e2157b5",
    "src/bite_ingestion/operators/untangle.py": "2951b7542f96674930e750e438891ca772b46896",
    "src/bite_ingestion/operators/integrate.py": "68e34becd80e7e803f511ec57ea7a23c2aaa1240",
    "src/bite_eval/composition_safety_v2.py": "85560279375b30f737eb3825cce72373be70488e",
    "artifacts/phase4c/real-holdout.json": PHASE4C_RESULT_BLOB,
    "artifacts/phase4c/reference-coverage.json": PHASE4C_REFERENCE_BLOB,
    "artifacts/phase4c/full-source-provenance.json": PHASE4C_PROVENANCE_BLOB,
    "artifacts/phase4d/atom-aware-reference.json": PHASE4D_ATOM_BLOB,
    "artifacts/phase4d/measurement-semantics.json": PHASE4D_RESULT_BLOB,
}
FORBIDDEN_BODY = (
    "hadoop",
    "ratis",
    "koel",
    "laravel",
    "bookstack",
    "kafka",
    "tomcat",
    "polybar",
    "gogs",
    "tegra",
    "bitbake",
    "linkding",
    "log4j",
    "APP_NAME",
    "hadoop.log.dir",
    "ratis.root.logger",
    "service-endpoint",
    "rs1-",
    "p3f-",
    "p3t-",
    "REALSTRUCT-2",
    "confirmatory",
    "texture",
    "expected_sequence",
    "intended_reference",
)

_REPO = Path(__file__).resolve().parents[2]
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase4e-full-key-reference-freeze.json"
PHASE4C_PATH = _REPO / "artifacts" / "phase4c" / "real-holdout.json"
PHASE4D_PATH = _REPO / "artifacts" / "phase4d" / "measurement-semantics.json"
PHASE3T_PATH = _REPO / "artifacts" / "phase3t" / "exact-reference.json"
PHASE3S_PATH = _REPO / "artifacts" / "phase3s" / "reference-specificity.json"
PHASE3Q_PATH = _REPO / "artifacts" / "phase3q" / "xfer2-transfer.json"


def _stem(case_id: str) -> str:
    return case_id.replace("-", "_")


def _fill(cid: str, n: int) -> list[tuple[str, str]]:
    return [(f"note_cairn_{cid}_{i:02d}", f"scree_{cid}_{i:02d}") for i in range(n)]


def _hop(cid: str, distance: int, dest: str, src_value: str) -> list[tuple[str, str]]:
    n_between = max(int(distance) - 1, 0)
    return [
        (f"src_ridge_{cid}", src_value),
        *_fill(cid, n_between),
        (dest, f"weft_{cid}"),
    ]


def records_for(case_id: str) -> list[tuple[str, str]]:
    cid = _stem(case_id)
    family, dist = _parse_case(case_id)
    if family == "simple_exact":
        dest = f"cairn_mark_{cid}"
        return _hop(cid, dist, dest, dest)
    if family == "dotted_exact":
        dest = f"ridge.cairn.atlas_{cid}"
        return _hop(cid, dist, dest, f"${{{dest}}}")
    if family == "hyphenated_exact":
        dest = f"ware-kiln_{cid}"
        return _hop(cid, dist, dest, dest)
    if family == "mixed_exact":
        dest = f"ridge.mark-west_{cid}"
        return _hop(cid, dist, dest, f"${{{dest}}}")
    if family == "neg_prefix":
        return _hop(cid, dist, "ridge.cairn.atlas", "ridge.cairn")
    if family == "neg_suffix":
        return _hop(cid, dist, "ridge.cairn.atlas", "cairn.atlas")
    if family == "neg_substring":
        return _hop(cid, dist, "ridge.cairn.atlas", "cairn")
    if family == "neg_longer":
        return _hop(cid, dist, "volt.bus", "volt.bus.spare")
    if family == "neg_hyphen_suffix":
        return _hop(cid, dist, "ware-kiln", "kiln")
    if family == "hostname_version":
        return [
            (f"note_cairn_{cid}_00", "maps.atlas.net"),
            (f"note_cairn_{cid}_01", "rel.v2.4.1"),
            (f"note_cairn_{cid}_02", "scree.local"),
            (f"src_ridge_{cid}", "Build.1.0.0"),
        ]
    if family == "join_span":
        return [
            (f"mate_a_{cid}", f"bobbin_a_{cid} id=spool_{cid}"),
            (f"mate_b_{cid}", f"bobbin_b_{cid} key=spool_{cid}"),
            (f"spool_{cid}", f"kept_{cid}"),
            *_fill(cid, 1),
        ]
    if family == "actionability_control":
        pair = (f"copy_reed_{cid}", f"same_reed_{cid}_row")
        return [
            pair,
            pair,
            (f"alert_{cid}", "shuttle jam FATAL"),
            (f"mate_a_{cid}", f"bobbin_a_{cid} id=spool_{cid}"),
            (f"mate_b_{cid}", f"bobbin_b_{cid} id=spool_{cid}"),
            (f"src_ridge_{cid}", "maps.atlas.net"),
        ]
    raise KeyError(case_id)


def _parse_case(case_id: str) -> tuple[str, int]:
    slug = case_id.removeprefix("p4e-")
    fam_slug, dist_slug = slug.rsplit("-", 1)
    family = next(name for name, item in FAMILY_SLUG.items() if item == fam_slug)
    return family, int(dist_slug[1:])


def intended_reference_edges(case_id: str) -> list[list[int]]:
    family, dist = _parse_case(case_id)
    if family in POSITIVE:
        return [[0, int(dist)]]
    return []


def intended_mean(edges: list[list[int]]) -> float:
    if not edges:
        return 0.0
    return float(sum(abs(dst - src) for src, dst in edges) / len(edges))


def gate_expected(case_id: str) -> bool:
    edges = intended_reference_edges(case_id)
    mean = intended_mean(edges)
    return bool(edges) and mean >= LOCKED_T_HIGH


def is_bridge(case_id: str) -> bool:
    family, _dist = _parse_case(case_id)
    return family == "simple_exact"


def dest_index_for(case_id: str) -> int | None:
    family, dist = _parse_case(case_id)
    if family in POSITIVE:
        return int(dist)
    return None


def render_records(records: list[tuple[str, str]], fmt: str) -> str:
    if fmt == "key_value":
        return "\n".join(f"{key}={value}" for key, value in records) + "\n"
    if fmt == "reversed_order_json":
        objs = [{"v": value, "k": key} for key, value in records]
        return json.dumps(objs, separators=(",", ":"))
    objs = [{"k": key, "v": value} for key, value in records]
    if fmt == "pretty_json":
        return json.dumps(objs, indent=2)
    if fmt == "compact_json":
        return json.dumps(objs, separators=(",", ":"))
    raise ValueError(f"unknown format {fmt}")


def planned_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for family in FAMILIES:
        for dist in FAMILY_DISTANCES[family]:
            case_id = f"p4e-{FAMILY_SLUG[family]}-d{dist}"
            records = records_for(case_id)
            edges = intended_reference_edges(case_id)
            cases.append(
                {
                    "case_id": case_id,
                    "family": family,
                    "distance": dist,
                    "bridge": is_bridge(case_id),
                    "n_records": len(records),
                    "records": [[key, value] for key, value in records],
                    "intended_reference_edges": edges,
                    "intended_mean": intended_mean(edges),
                    "gate_expected": gate_expected(case_id),
                    "policy_sequence_expected": [],
                    "formats": list(FORMATS),
                }
            )
    return cases


def forbidden_hits(text: str) -> list[str]:
    return [token for token in FORBIDDEN_BODY if token in text]


def freeze_manifest() -> dict[str, Any]:
    cases = planned_cases()
    return {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "verdict": PROTOCOL_FROZEN,
        "paid_api": False,
        "offline": True,
        "synthetic": True,
        "research_conclusion": False,
        "premise": PREMISE,
        "phase4d_head_sha": PHASE4D_HEAD,
        "phase4c_verdict": PHASE4C_VERDICT,
        "phase4d_verdict": PREMISE,
        "phase3t_verdict": PHASE3T_VERDICT,
        "phase3s_verdict": PHASE3S_VERDICT,
        "phase3q_verdict": PHASE3Q_VERDICT,
        "generation": GENERATION,
        "copy_realstruct1_identifiers": False,
        "no_realstruct2": True,
        "no_baseline_added": True,
        "p3f_evaluation_holdout_used": False,
        "calibration": False,
        "no_threshold_grid": True,
        "no_planner_change": True,
        "no_operator_semantic_change": True,
        "repair_target": "preserve_exact_identity_for_dotted_and_hyphenated_full_keys",
        "full_key_grammar": FULL_KEY_GRAMMAR,
        "locked_t_high": LOCKED_T_HIGH,
        "locked_blobs": dict(LOCKED_BLOBS),
        "relation_contract": {
            "keep_reference_identity_v1": True,
            "target": "complete logical key when it matches full-key grammar",
            "source": "maximal full-key identifiers from masked value",
            "edge": "exact source full identity == exact target full identity",
            "no_component_identities": True,
            "no_case_folding": True,
            "no_prefix_suffix_substring_fuzzy": True,
            "dollar_brace_not_the_only_relation": True,
            "join_mask": "id=<token> and key=<token> in values",
            "chain_span": "evaluator-validated reachability replacement, not new semantics",
        },
        "families": list(FAMILIES),
        "formats": list(FORMATS),
        "n_canonical": N_CANONICAL,
        "n_surfaces": N_SURFACES,
        "planned_cases": cases,
        "bridge": {
            "family": "simple_exact",
            "requires_v3_v4_edge_set_n_and_mean_exact": True,
            "not_a_new_calibration": True,
            "candidate": LOCKED_T_HIGH,
            "identifiers_have_neither_dot_nor_hyphen": True,
        },
        "secondary_realstruct1": {
            "role": "development / retrospective diagnostic",
            "not_holdout": True,
            "not_confirmatory": True,
            "not_generalization": True,
            "not_primary_pass_criterion": True,
        },
        "primary_truth": "scorer-only intended_reference_edges; observed undirected set must match exactly",
        "no_mean_only_success": True,
        "e1_verdicts": list(E1_VERDICTS),
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "new holdout evidence",
            "real-world generalization",
            "BITE superiority",
            "confirmatory",
            "second holdout evaluation",
        ],
        "no_winner_score": True,
        "cut_forbidden": True,
    }


def validate_phase4e_freeze(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != SCHEMA_ID:
        errs.append("schema mismatch")
    if doc.get("verdict") != PROTOCOL_FROZEN:
        errs.append("protocol not frozen")
    if doc.get("premise") != PREMISE:
        errs.append("Phase 4D premise drifted")
    if doc.get("copy_realstruct1_identifiers") is not False:
        errs.append("must not copy REALSTRUCT-1 identifiers")
    if doc.get("no_realstruct2") is not True:
        errs.append("REALSTRUCT-2 must not be created")
    if doc.get("no_baseline_added") is not True:
        errs.append("baselines must not be added")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f evaluation must stay sealed")
    if doc.get("no_threshold_grid") is not True:
        errs.append("threshold grid forbidden")
    if doc.get("locked_t_high") != LOCKED_T_HIGH:
        errs.append("T_high drifted")
    if doc.get("n_canonical") != N_CANONICAL or N_CANONICAL < 20:
        errs.append("canonical count drifted")
    if doc.get("n_surfaces") != N_SURFACES or N_SURFACES < 80:
        errs.append("n_surfaces drifted")
    if len(doc.get("planned_cases") or []) != N_CANONICAL:
        errs.append("planned_cases count drifted")
    if json.loads(PHASE4C_PATH.read_text(encoding="utf-8")).get("verdict") != PHASE4C_VERDICT:
        errs.append("Phase 4C verdict rewritten")
    if json.loads(PHASE4D_PATH.read_text(encoding="utf-8")).get("verdict") != PREMISE:
        errs.append("Phase 4D verdict rewritten")
    if json.loads(PHASE3T_PATH.read_text(encoding="utf-8")).get("verdict") != PHASE3T_VERDICT:
        errs.append("Phase 3T verdict rewritten")
    if json.loads(PHASE3S_PATH.read_text(encoding="utf-8")).get("verdict") != PHASE3S_VERDICT:
        errs.append("Phase 3S verdict rewritten")
    if json.loads(PHASE3Q_PATH.read_text(encoding="utf-8")).get("verdict") != PHASE3Q_VERDICT:
        errs.append("Phase 3Q verdict rewritten")
    for spec in doc.get("planned_cases") or []:
        if not isinstance(spec, Mapping):
            errs.append("planned case not object")
            continue
        hits = forbidden_hits(json.dumps(spec.get("records") or []))
        if hits:
            errs.append(f"forbidden token in {spec.get('case_id')}: {hits}")
        if spec.get("family") == "simple_exact" and spec.get("bridge") is not True:
            errs.append(f"{spec.get('case_id')} must be bridge")
        if spec.get("family") == "simple_exact":
            blob = json.dumps(spec.get("records") or [])
            if "." in blob or "-" in blob:
                errs.append(f"{spec.get('case_id')} bridge records must lack . and -")
        if spec.get("family") in POSITIVE:
            if spec.get("intended_reference_edges") != [[0, spec.get("distance")]]:
                errs.append(f"{spec.get('case_id')} intended edge drifted")
            if spec.get("gate_expected") is not (int(spec.get("distance") or 0) >= 4):
                errs.append(f"{spec.get('case_id')} gate drifted")
        else:
            if spec.get("intended_reference_edges") != []:
                errs.append(f"{spec.get('case_id')} must have no intended edges")
            if spec.get("gate_expected") is not False:
                errs.append(f"{spec.get('case_id')} must not gate")
        if spec.get("policy_sequence_expected") != []:
            errs.append(f"{spec.get('case_id')} sequence must be []")
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
    print(freeze["verdict"], "n", freeze["n_canonical"], freeze["n_surfaces"])
    print("errors", validate_phase4e_freeze(freeze))
