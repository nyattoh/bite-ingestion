"""Phase 4H2 extension pool (H4) and augmented corpus freeze (H5).

Does not rewrite Phase 4H H0/H1/H2 artifacts. Does not infer licenses.
Does not run comparison arms or tokenizers. Does not open p3f.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4h import DISCOVERY_QUERIES, FAMILIES, N_PRIMARY, N_PRIMARY_PER_FAMILY
from bite_bench.phase4h2 import (
    CLAIM_BOUNDARY,
    EXTENSION_POOL_PER_FAMILY,
    H0_COMMIT_SHA,
    H0_FREEZE_BLOB,
    H1_COMMIT_SHA,
    H1_POOL_BLOB,
    H2_COMMIT_SHA,
    H2_RESULT_BLOB,
    LOCKED_BLOBS,
    PREMISE,
    REMAINING_PRIMARY,
    VERDICT_BLOCKED,
    VERDICT_FROZEN,
    VERDICT_PARTIAL,
    WAVE1_PRIMARY_IDS,
    freeze_manifest,
    validate_phase4h2_freeze,
)
from bite_bench.realstruct2 import (
    POOL_PATH,
    RAW_DIR,
    _content_reject,
    _dump,
    _repo_meta,
    _search_page,
    _source_id,
    annotate_source,
    fetch_raw,
    metadata_reject,
    selection_key,
    sha256_bytes,
)

H3_COMMIT_SHA = "3441f3524891fc772ce8751f75b22d32755d58da"
H3_FREEZE_BLOB = "b3823492dc987b0c2489fa8785cd0b8d813f4b53"
EXT_POOL_SCHEMA = "bite-phase4h2-extension-pool/v0.1"
EXT_RESULT_SCHEMA = "bite-phase4h2-realstruct2-augmented/v0.1"
REVISION = "phase4h2-realstruct2-v0.1"

_REPO = Path(__file__).resolve().parents[2]
EXT_POOL_PATH = _REPO / "artifacts" / "phase4h2" / "extension-pool.json"
RESULT_PATH = _REPO / "artifacts" / "phase4h2" / "realstruct-2-augmented.json"
AUG_MANIFEST = _REPO / "corpora" / "realstruct-2" / "augmented-manifest.json"
AUG_LICENSE = _REPO / "corpora" / "realstruct-2" / "augmented-licenses.json"
AUG_ANNOTATION = _REPO / "corpora" / "realstruct-2" / "augmented-annotations.json"
EXT_REJECTION = _REPO / "corpora" / "realstruct-2" / "extension-rejections.json"
WAVE_PROVENANCE = _REPO / "corpora" / "realstruct-2" / "wave-provenance.json"
WAVE1_PRIMARY = _REPO / "corpora" / "realstruct-2" / "primary.json"
WAVE1_MANIFEST = _REPO / "corpora" / "realstruct-2" / "manifest.json"
WAVE1_LICENSE = _REPO / "corpora" / "realstruct-2" / "licenses.json"
WAVE1_ANNOTATION = _REPO / "corpora" / "realstruct-2" / "annotations.json"
HIST_RESULT = _REPO / "artifacts" / "phase4h" / "realstruct-2.json"


def _h1_keys() -> set[tuple[str, str]]:
    pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))
    keys: set[tuple[str, str]] = set()
    for rows in (pool.get("families") or {}).values():
        for row in rows:
            keys.add((str(row["repository_full_name"]), str(row["path"])))
    return keys


def collect_extension_family(
    family: str,
    exclude: set[tuple[str, str]],
    cache: dict[str, dict[str, Any] | None],
) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set(exclude)
    rows: list[dict[str, Any]] = []
    for query in DISCOVERY_QUERIES[family]:
        page = 1
        while len(rows) < EXTENSION_POOL_PER_FAMILY and page <= 10:
            try:
                payload = _search_page(query, page)
            except RuntimeError:
                break
            time.sleep(2.2)
            items = list(payload.get("items") or [])
            if not items:
                break
            for item in items:
                if len(rows) >= EXTENSION_POOL_PER_FAMILY:
                    break
                repo_obj = item.get("repository") or {}
                full_name = str(repo_obj.get("full_name") or "")
                path = str(item.get("path") or "")
                if not full_name or not path:
                    continue
                key = (full_name, path)
                if key in seen:
                    continue
                seen.add(key)
                meta = _repo_meta(full_name, cache)
                if meta is None:
                    continue
                commit = str(meta["head_commit_sha"])
                rows.append(
                    {
                        "family": family,
                        "query": query,
                        "collection_index": len(rows),
                        "repository_full_name": meta["repository_full_name"],
                        "repository_id": meta["repository_id"],
                        "path": path,
                        "default_branch": meta["default_branch"],
                        "head_commit_sha": commit,
                        "license_spdx": meta["license_spdx"],
                        "archived": meta["archived"],
                        "fork": meta["fork"],
                        "html_url": meta["html_url"],
                        "selection_key": selection_key(
                            meta["repository_full_name"], commit, path
                        ),
                    }
                )
            if len(items) < 100:
                break
            page += 1
    return rows


def collect_extension_pool() -> dict[str, Any]:
    exclude = _h1_keys()
    cache: dict[str, dict[str, Any] | None] = {}
    families: dict[str, list[dict[str, Any]]] = {}
    for family in FAMILIES:
        families[family] = collect_extension_family(family, exclude, cache)
    doc = {
        "schema": EXT_POOL_SCHEMA,
        "revision": REVISION,
        "verdict": "PHASE4H2_EXTENSION_POOL_FROZEN",
        "premise": PREMISE,
        "h3_commit_sha": H3_COMMIT_SHA,
        "h3_freeze_blob": H3_FREEZE_BLOB,
        "h1_pool_blob": H1_POOL_BLOB,
        "p3f_evaluation_holdout_used": False,
        "file_contents_opened": False,
        "no_arm_execution": True,
        "no_tokenizer_execution": True,
        "exclude_h1_repo_path": True,
        "n_h1_excluded": len(exclude),
        "extension_pool_per_family": EXTENSION_POOL_PER_FAMILY,
        "n_candidates": {family: len(rows) for family, rows in families.items()},
        "families": families,
        "discovery_queries": {
            family: list(queries) for family, queries in DISCOVERY_QUERIES.items()
        },
    }
    _dump(EXT_POOL_PATH, doc)
    return doc


def validate_extension_pool(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != EXT_POOL_SCHEMA:
        errs.append("extension pool schema mismatch")
    if doc.get("file_contents_opened") is not False:
        errs.append("extension contents opened at H4")
    if doc.get("h1_pool_blob") != H1_POOL_BLOB:
        errs.append("H1 pool blob drifted")
    h1 = _h1_keys()
    families = doc.get("families") or {}
    if set(families) != set(FAMILIES):
        errs.append("extension families drifted")
    for family in FAMILIES:
        rows = list(families.get(family) or [])
        if len(rows) > EXTENSION_POOL_PER_FAMILY:
            errs.append(f"{family} extension exceeds {EXTENSION_POOL_PER_FAMILY}")
        seen: set[tuple[str, str]] = set()
        for row in rows:
            key = (str(row.get("repository_full_name")), str(row.get("path")))
            if key in h1:
                errs.append(f"H1 candidate leaked into extension: {key}")
            if key in seen:
                errs.append(f"duplicate extension repo/path {key}")
            seen.add(key)
            if "raw" in row or "text" in row or "content" in row:
                errs.append("H4 pool contains file contents")
            expected = selection_key(
                str(row["repository_full_name"]),
                str(row["head_commit_sha"]),
                str(row["path"]),
            )
            if row.get("selection_key") != expected:
                errs.append("selection_key mismatch")
    hist = json.loads(HIST_RESULT.read_text(encoding="utf-8"))
    if hist.get("verdict") != PREMISE or hist.get("n_primary") != 10:
        errs.append("historical Phase 4H result rewritten")
    return errs


def freeze_augmented() -> dict[str, Any]:
    pool = json.loads(EXT_POOL_PATH.read_text(encoding="utf-8"))
    pool_errs = validate_extension_pool(pool)
    if pool_errs:
        raise RuntimeError(f"H4 pool invalid: {pool_errs}")
    wave1 = json.loads(WAVE1_PRIMARY.read_text(encoding="utf-8"))
    wave1_manifest = json.loads(WAVE1_MANIFEST.read_text(encoding="utf-8"))
    wave1_ann = json.loads(WAVE1_ANNOTATION.read_text(encoding="utf-8"))
    wave1_lic = json.loads(WAVE1_LICENSE.read_text(encoding="utf-8"))
    wave1_by_id = {row["source_id"]: row for row in wave1["sources"]}
    if tuple(wave1["source_ids"]) != WAVE1_PRIMARY_IDS:
        raise RuntimeError("wave1 primary IDs drifted")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rejections: list[dict[str, str]] = []
    wave2: list[dict[str, Any]] = []
    wave2_ann: list[dict[str, Any]] = []
    used_ids = set(WAVE1_PRIMARY_IDS)
    sha_seen = {str(row["sha256"]) for row in wave1_manifest["sources"]}
    all_repos = {
        str(row["repository_url"]).removeprefix("https://github.com/")
        for row in wave1["sources"]
    }
    n_primary = {
        family: sum(1 for row in wave1["sources"] if row["family"] == family)
        for family in FAMILIES
    }
    n_secondary = {family: 0 for family in FAMILIES}
    for family in FAMILIES:
        rows = sorted(
            pool["families"][family],
            key=lambda item: str(item["selection_key"]),
        )
        for row in rows:
            full = str(row["repository_full_name"])
            path = str(row["path"])
            commit = str(row["head_commit_sha"])
            loc = f"{full}:{path}"
            meta = metadata_reject(row)
            if meta:
                rejections.append({"family": family, "candidate": loc, "reason": meta})
                continue
            if (
                n_primary[family] >= N_PRIMARY_PER_FAMILY
                and n_secondary[family] >= 2
            ):
                rejections.append({"family": family, "candidate": loc, "reason": "quotas filled"})
                continue
            try:
                data = fetch_raw(full, commit, path)
            except FileNotFoundError as exc:
                rejections.append(
                    {"family": family, "candidate": loc, "reason": f"missing at HEAD: {exc}"}
                )
                continue
            content = _content_reject(data, sha_seen)
            if content:
                rejections.append({"family": family, "candidate": loc, "reason": content})
                continue
            ann = annotate_source(data)
            primary_open = n_primary[family] < N_PRIMARY_PER_FAMILY
            secondary_open = (
                not primary_open
                and n_secondary[family] < 2
                and int(ann["n_explicit_reference_edges"]) > 0
            )
            if primary_open:
                if full in all_repos:
                    rejections.append(
                        {
                            "family": family,
                            "candidate": loc,
                            "reason": "repository overlap with another primary document",
                        }
                    )
                    continue
                stratum = "primary"
            elif secondary_open:
                if full in all_repos:
                    rejections.append(
                        {"family": family, "candidate": loc, "reason": "repository already used"}
                    )
                    continue
                stratum = "secondary_reference_enriched"
            else:
                rejections.append({"family": family, "candidate": loc, "reason": "quotas filled"})
                continue
            source_id = _source_id(family, full, used_ids)
            raw_rel = f"corpora/realstruct-2/raw/{source_id}"
            (_REPO / raw_rel).write_bytes(data)
            sha_seen.add(sha256_bytes(data))
            all_repos.add(full)
            if stratum == "primary":
                n_primary[family] += 1
            else:
                n_secondary[family] += 1
            rec = {
                "source_id": source_id,
                "family": family,
                "stratum": stratum,
                "wave": 2,
                "repository_url": str(row["html_url"]),
                "repository_id": row["repository_id"],
                "commit_sha": commit,
                "path": path,
                "source_url": f"https://github.com/{full}/blob/{commit}/{path}",
                "raw_url": f"https://raw.githubusercontent.com/{full}/{commit}/{path}",
                "license": row["license_spdx"],
                "spdx": row["license_spdx"],
                "sha256": sha256_bytes(data),
                "byte_length": len(data),
                "line_count": ann["n_lines"],
                "n_assignments": ann["n_assignments"],
                "n_explicit_reference_edges": ann["n_explicit_reference_edges"],
                "encoding": "utf-8",
                "raw_file": raw_rel,
                "selection_key": row["selection_key"],
            }
            wave2.append(rec)
            wave2_ann.append({"source_id": source_id, "stratum": stratum, "wave": 2, **ann})
            time.sleep(0.15)
    freeze_errs = validate_phase4h2_freeze(freeze_manifest())
    try:
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
        freeze_errs.append("p3f seal did not fire")
    except EvaluationSealError:
        pass
    wave1_sources = [{**wave1_by_id[sid], "wave": 1} for sid in WAVE1_PRIMARY_IDS]
    accepted = wave1_sources + wave2
    primary = [row for row in accepted if row["stratum"] == "primary"]
    secondary = [row for row in accepted if row["stratum"] != "primary"]
    errors: list[str] = list(freeze_errs)
    if len(primary) != N_PRIMARY:
        errors.append(f"primary count {len(primary)} != {N_PRIMARY}")
    for family in FAMILIES:
        got = sum(1 for row in primary if row["family"] == family)
        if got != N_PRIMARY_PER_FAMILY:
            errors.append(f"{family} primary {got} != {N_PRIMARY_PER_FAMILY}")
        remaining = REMAINING_PRIMARY[family]
        wave2_primary = sum(
            1 for row in wave2 if row["family"] == family and row["stratum"] == "primary"
        )
        if wave2_primary > remaining:
            errors.append(f"{family} wave2 replaced wave1 quota")
    if [row["source_id"] for row in wave1_sources] != list(WAVE1_PRIMARY_IDS):
        errors.append("wave1 primary IDs rewritten")
    verdict = VERDICT_FROZEN if not errors else VERDICT_PARTIAL
    if any("blocked" in err for err in errors):
        verdict = VERDICT_BLOCKED
    pool_blob = subprocess.check_output(
        ["git", "hash-object", str(EXT_POOL_PATH)], cwd=_REPO, text=True
    ).strip()
    ann_docs = []
    hist_ann = {doc["source_id"]: doc for doc in wave1_ann["documents"]}
    for row in accepted:
        if row.get("wave") == 1:
            ann_docs.append({**hist_ann[row["source_id"]], "wave": 1})
        else:
            match = next(item for item in wave2_ann if item["source_id"] == row["source_id"])
            ann_docs.append(match)
    corpus = {
        "schema": "bite-phase4h2-augmented-corpus/v0.1",
        "revision": REVISION,
        "corpus_name": "REALSTRUCT-2",
        "acquisition_design": (
            "two-wave prospective acquisition; wave 2 added after quota shortfall, "
            "before any comparison-arm or tokenizer execution"
        ),
        "protocol_commit_sha": H3_COMMIT_SHA,
        "h0_commit_sha": H0_COMMIT_SHA,
        "h1_commit_sha": H1_COMMIT_SHA,
        "h2_commit_sha": H2_COMMIT_SHA,
        "n_documents": len(accepted),
        "n_primary": len(primary),
        "n_secondary": len(secondary),
        "sources": accepted,
        "claim_boundary": CLAIM_BOUNDARY,
        "secondary_never_pooled_with_primary": True,
    }
    licenses = {
        "schema": "bite-phase4h2-augmented-licenses/v0.1",
        "revision": REVISION,
        "allowed_spdx": ["MIT", "Apache-2.0"],
        "documents": list(wave1_lic["documents"])
        + [
            {
                "source_id": row["source_id"],
                "spdx": row["spdx"],
                "redistributable": True,
                "license_url": row["repository_url"],
                "license_note": "GitHub license API SPDX recorded at H4",
                "repository_url": row["repository_url"],
                "commit_sha": row["commit_sha"],
                "wave": 2,
            }
            for row in wave2
        ],
    }
    annotation_doc = {
        "schema": "bite-phase4h2-augmented-annotations/v0.1",
        "revision": REVISION,
        "independent_of_bite_implementation": True,
        "raw_syntax_only": True,
        "two_pass_whole_document_key_index": True,
        "explicit_reference_gold": "${NAME} only",
        "gold_identity": "(source_line, NAME, dest_line)",
        "exact_duplicate_identity": "(key, value)",
        "missing_annotation_is_not_non_reference": True,
        "forbidden_scorer_fields": [
            "expected route",
            "expected operator sequence",
            "expected BITE edge",
            "expected arm winner",
        ],
        "documents": ann_docs,
    }
    rejection_doc = {
        "schema": "bite-phase4h2-extension-rejections/v0.1",
        "revision": REVISION,
        "h3_commit_sha": H3_COMMIT_SHA,
        "n_rejections": len(rejections),
        "do_not_reconsider_h1_rejections": True,
        "rejections": rejections,
    }
    provenance = {
        "schema": "bite-phase4h2-wave-provenance/v0.1",
        "revision": REVISION,
        "acquisition_design": corpus["acquisition_design"],
        "wave1_source_ids": list(WAVE1_PRIMARY_IDS),
        "wave2_source_ids": [row["source_id"] for row in wave2],
        "final_primary_source_ids": [row["source_id"] for row in primary],
        "final_secondary_source_ids": [row["source_id"] for row in secondary],
        "extension_pool_path": "artifacts/phase4h2/extension-pool.json",
        "h1_pool_unchanged": True,
    }
    result = {
        "schema": EXT_RESULT_SCHEMA,
        "revision": REVISION,
        "protocol_commit_sha": H3_COMMIT_SHA,
        "h3_freeze_blob": H3_FREEZE_BLOB,
        "h1_pool_blob": H1_POOL_BLOB,
        "h2_result_blob": H2_RESULT_BLOB,
        "h2_commit_sha": H2_COMMIT_SHA,
        "extension_pool_hash": pool_blob,
        "verdict": verdict,
        "paid_api": False,
        "offline_core_tests": True,
        "research_conclusion": False,
        "premise": PREMISE,
        "p3f_evaluation_holdout_used": False,
        "no_xfer3": True,
        "no_arm_execution": True,
        "no_tokenizer_execution": True,
        "no_bite_execution": True,
        "no_phase4h_rewrite": True,
        "no_license_inference": True,
        "acquisition_design": corpus["acquisition_design"],
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "comparison evidence",
            "confirmatory result",
            "generalization",
            "BITE superiority",
        ],
        "n_wave1_primary": 10,
        "n_primary": len(primary),
        "n_secondary": len(secondary),
        "n_documents": len(accepted),
        "locked_blobs": dict(LOCKED_BLOBS),
        "errors": errors,
    }
    _dump(AUG_MANIFEST, corpus)
    _dump(AUG_LICENSE, licenses)
    _dump(AUG_ANNOTATION, annotation_doc)
    _dump(EXT_REJECTION, rejection_doc)
    _dump(WAVE_PROVENANCE, provenance)
    _dump(RESULT_PATH, result)
    return result


def validate_augmented(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != EXT_RESULT_SCHEMA:
        errs.append("augmented schema mismatch")
    if doc.get("verdict") not in (VERDICT_FROZEN, VERDICT_PARTIAL, VERDICT_BLOCKED):
        errs.append("unknown verdict")
    if doc.get("no_arm_execution") is not True or doc.get("no_tokenizer_execution") is not True:
        errs.append("arm/tokenizer leaked")
    if doc.get("no_license_inference") is not True:
        errs.append("license inference leaked")
    if doc.get("h2_result_blob") != H2_RESULT_BLOB:
        errs.append("H2 result blob drifted")
    if doc.get("h1_pool_blob") != H1_POOL_BLOB:
        errs.append("H1 pool blob drifted")
    hist = json.loads(HIST_RESULT.read_text(encoding="utf-8"))
    if hist.get("n_primary") != 10 or hist.get("verdict") != PREMISE:
        errs.append("historical Phase 4H result rewritten")
    if json.loads(POOL_PATH.read_text(encoding="utf-8")).get("file_contents_opened") is not False:
        errs.append("H1 pool rewritten")
    if WAVE_PROVENANCE.is_file():
        prov = json.loads(WAVE_PROVENANCE.read_text(encoding="utf-8"))
        if list(prov.get("wave1_source_ids") or []) != list(WAVE1_PRIMARY_IDS):
            errs.append("wave1 IDs rewritten")
    if doc.get("verdict") == VERDICT_FROZEN and (
        doc.get("n_primary") != N_PRIMARY or doc.get("errors")
    ):
        errs.append("FROZEN requires 18 primary and empty errors")
    if doc.get("verdict") == VERDICT_PARTIAL and not doc.get("errors"):
        errs.append("PARTIAL must record the shortfall")
    for path, expected in {
        "artifacts/phase4h/realstruct-2.json": H2_RESULT_BLOB,
        "artifacts/phase4h/candidate-pool.json": H1_POOL_BLOB,
        "benchmarks/spec/phase4h-realstruct2-freeze.json": H0_FREEZE_BLOB,
    }.items():
        got = subprocess.check_output(["git", "hash-object", path], cwd=_REPO, text=True).strip()
        if got != expected:
            errs.append(f"historical blob drifted: {path}")
    return errs


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "freeze"
    if cmd == "collect":
        pool = collect_extension_pool()
        print("n_candidates", pool["n_candidates"])
        print("errors", validate_extension_pool(pool))
    else:
        result = freeze_augmented()
        print(result["verdict"], "primary", result["n_primary"], "secondary", result["n_secondary"])
        print("errors", result["errors"])
