"""Phase 4H REALSTRUCT-2 candidate pool (H1) and later corpus freeze.

H1 collects repository/path candidates without reading file contents.
Does not run comparison arms, tokenizers, BITE sensors, or policies.
Does not open p3f.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import quote

from bite_bench.phase4a import EvaluationSealError, refuse_p3f_evaluation
from bite_bench.phase4h import (
    ALLOWED_SPDX,
    CANDIDATE_POOL_PER_FAMILY,
    CLAIM_BOUNDARY,
    DISCOVERY_QUERIES,
    FAMILIES,
    G0_FREEZE_BLOB,
    LOCKED_BLOBS,
    MAX_BYTES,
    MIN_ASSIGNMENTS,
    N_PRIMARY,
    N_PRIMARY_PER_FAMILY,
    N_SECONDARY_PER_FAMILY,
    PHASE3Q_VERDICT,
    PHASE3S_VERDICT,
    PHASE3T_VERDICT,
    PHASE4C_VERDICT,
    PHASE4D_VERDICT,
    PHASE4E_VERDICT,
    PHASE4F_VERDICT,
    PHASE4G_HEAD,
    PREMISE,
    RS1_REPOS,
    TEST_PATH_MARKERS,
    VERDICT_BLOCKED,
    VERDICT_FROZEN,
    VERDICT_PARTIAL,
    freeze_manifest,
    validate_phase4h_freeze,
)
from bite_bench.realstruct1 import (
    ASSIGN_RE,
    COMMENT_RE,
    REF_RE,
    SECTION_RE,
    live_secret_hits,
)

H0_COMMIT_SHA = "29dd6c91d02edcca6b486e74bac9bdf50259b149"
H0_FREEZE_BLOB = "4c48c198456babe2f5d0e652aefe831f8dacd3bc"
POOL_SCHEMA_ID = "bite-phase4h-candidate-pool/v0.1"
POOL_REVISION = "phase4h-realstruct2-v0.1"

_REPO = Path(__file__).resolve().parents[2]
POOL_PATH = _REPO / "artifacts" / "phase4h" / "candidate-pool.json"
CORPUS_POOL_PATH = _REPO / "corpora" / "realstruct-2" / "candidate-pool.json"


def _dump(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(dict(doc), indent=2, sort_keys=True) + "\n").encode("utf-8"))


def selection_key(full_name: str, commit_sha: str, path: str) -> str:
    payload = f"{full_name}@{commit_sha}:{path}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _gh_api(path: str, retries: int = 6) -> Any:
    delay = 2.0
    for attempt in range(retries):
        proc = subprocess.run(
            ["gh", "api", "-H", "Accept: application/vnd.github+json", path],
            cwd=_REPO,
            capture_output=True,
            check=False,
        )
        stdout = (proc.stdout or b"").decode("utf-8", errors="replace")
        stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
        if proc.returncode == 0:
            return json.loads(stdout)
        err = (stderr + stdout).strip()
        if attempt + 1 == retries:
            raise RuntimeError(f"gh api {path} failed: {err[:400]}")
        time.sleep(delay)
        delay = min(delay * 2, 30.0)
    raise RuntimeError(f"gh api {path} failed")


def _search_page(query: str, page: int) -> dict[str, Any]:
    q = quote(query, safe=".:")
    return _gh_api(f"/search/code?q={q}&per_page=100&page={page}")


def _repo_meta(full_name: str, cache: dict[str, dict[str, Any] | None]) -> dict[str, Any] | None:
    if full_name in cache:
        return cache[full_name]
    try:
        repo = _gh_api(f"/repos/{full_name}")
        branch = str(repo.get("default_branch") or "")
        head = _gh_api(f"/repos/{full_name}/commits/{quote(branch, safe='')}")
        license_obj = repo.get("license") or {}
        row = {
            "repository_full_name": str(repo.get("full_name") or full_name),
            "repository_id": repo.get("id"),
            "html_url": repo.get("html_url"),
            "default_branch": branch,
            "head_commit_sha": head.get("sha"),
            "license_spdx": (license_obj or {}).get("spdx_id"),
            "archived": bool(repo.get("archived")),
            "fork": bool(repo.get("fork")),
        }
        if not row["head_commit_sha"] or not row["default_branch"]:
            cache[full_name] = None
            return None
        cache[full_name] = row
        return row
    except (RuntimeError, TypeError, ValueError, json.JSONDecodeError):
        cache[full_name] = None
        return None


def collect_family(family: str, cache: dict[str, dict[str, Any] | None]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    rows: list[dict[str, Any]] = []
    for query in DISCOVERY_QUERIES[family]:
        page = 1
        while len(rows) < CANDIDATE_POOL_PER_FAMILY:
            payload = _search_page(query, page)
            time.sleep(2.2)
            items = list(payload.get("items") or [])
            if not items:
                break
            for item in items:
                if len(rows) >= CANDIDATE_POOL_PER_FAMILY:
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
                        "selection_key": selection_key(meta["repository_full_name"], commit, path),
                    }
                )
            if len(items) < 100:
                break
            page += 1
            if page > 10:
                break
    return rows


def collect_pool() -> dict[str, Any]:
    cache: dict[str, dict[str, Any] | None] = {}
    families: dict[str, list[dict[str, Any]]] = {}
    for family in FAMILIES:
        families[family] = collect_family(family, cache)
    doc = {
        "schema": POOL_SCHEMA_ID,
        "revision": POOL_REVISION,
        "verdict": "PHASE4H_CANDIDATE_POOL_FROZEN",
        "premise": PREMISE,
        "h0_commit_sha": H0_COMMIT_SHA,
        "h0_freeze_blob": H0_FREEZE_BLOB,
        "phase4g_head_sha": PHASE4G_HEAD,
        "g0_freeze_blob": G0_FREEZE_BLOB,
        "p3f_evaluation_holdout_used": False,
        "file_contents_opened": False,
        "no_arm_execution": True,
        "no_tokenizer_execution": True,
        "ignore_code_search_snippets": True,
        "candidate_pool_per_family": CANDIDATE_POOL_PER_FAMILY,
        "n_candidates": {family: len(rows) for family, rows in families.items()},
        "families": families,
        "discovery_queries": {
            family: list(queries) for family, queries in DISCOVERY_QUERIES.items()
        },
        "protocol_queries": freeze_manifest()["discovery"]["queries"],
    }
    _dump(POOL_PATH, doc)
    _dump(CORPUS_POOL_PATH, doc)
    return doc


def validate_candidate_pool(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != POOL_SCHEMA_ID:
        errs.append("pool schema mismatch")
    if doc.get("verdict") != "PHASE4H_CANDIDATE_POOL_FROZEN":
        errs.append("pool not frozen")
    if doc.get("file_contents_opened") is not False:
        errs.append("file contents must stay unopened at H1")
    if doc.get("h0_commit_sha") != H0_COMMIT_SHA:
        errs.append("H0 commit drifted")
    families = doc.get("families") or {}
    if set(families) != set(FAMILIES):
        errs.append("pool families drifted")
    for family in FAMILIES:
        rows = list(families.get(family) or [])
        if len(rows) > CANDIDATE_POOL_PER_FAMILY:
            errs.append(f"{family} pool exceeds {CANDIDATE_POOL_PER_FAMILY}")
        seen: set[tuple[str, str]] = set()
        for row in rows:
            key = (str(row.get("repository_full_name")), str(row.get("path")))
            if key in seen:
                errs.append(f"duplicate repo/path in {family}: {key}")
            seen.add(key)
            for field in (
                "repository_id",
                "default_branch",
                "head_commit_sha",
                "selection_key",
            ):
                if not row.get(field) and row.get(field) != 0:
                    errs.append(f"{family} missing {field}")
            if "raw" in row or "text" in row or "content" in row:
                errs.append("H1 pool contains file contents")
            expected = selection_key(
                str(row["repository_full_name"]),
                str(row["head_commit_sha"]),
                str(row["path"]),
            )
            if row.get("selection_key") != expected:
                errs.append("selection_key mismatch")
    return errs


H1_COMMIT_SHA = "b50e36d2916ff8de7eaae37055fef6bf114d2008"
H1_POOL_BLOB = "7f45295f0ffe2880516f9f8ccbfa2c20b942a002"
RESULT_SCHEMA_ID = "bite-phase4h-realstruct2/v0.1"
CORPUS_SCHEMA_ID = "bite-phase4h-realstruct2-corpus/v0.1"
LICENSE_SCHEMA_ID = "bite-phase4h-realstruct2-licenses/v0.1"
ANNOTATION_SCHEMA_ID = "bite-phase4h-realstruct2-annotations/v0.1"
REJECTION_SCHEMA_ID = "bite-phase4h-realstruct2-rejections/v0.1"
FAMILY_SHORT = {"dotenv-like": "dotenv", "properties": "props", "ini_cfg": "ini"}
CORPUS_DIR = _REPO / "corpora" / "realstruct-2"
RAW_DIR = CORPUS_DIR / "raw"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"
PRIMARY_PATH = CORPUS_DIR / "primary.json"
SECONDARY_PATH = CORPUS_DIR / "secondary.json"
LICENSE_PATH = CORPUS_DIR / "licenses.json"
ANNOTATION_PATH = CORPUS_DIR / "annotations.json"
REJECTION_PATH = CORPUS_DIR / "rejections.json"
RESULT_PATH = _REPO / "artifacts" / "phase4h" / "realstruct-2.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def annotate_source(data: bytes) -> dict[str, Any]:
    text = data.decode("utf-8")
    records: list[dict[str, Any]] = []
    assignments: list[tuple[int, str, str, re.Match[str]]] = []
    key_lines: dict[str, list[int]] = defaultdict(list)
    key_values: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for line_no, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            records.append({"kind": "unsupported", "line": line_no, "reason": "blank"})
            continue
        if COMMENT_RE.match(line):
            records.append({"kind": "unsupported", "line": line_no, "reason": "comment"})
            continue
        if SECTION_RE.match(line):
            records.append({"kind": "unsupported", "line": line_no, "reason": "section"})
            continue
        match = ASSIGN_RE.match(line)
        if not match:
            records.append({"kind": "unsupported", "line": line_no, "reason": "other"})
            continue
        key = match.group(1).strip()
        value = match.group(2)
        records.append(
            {
                "kind": "assignment",
                "line": line_no,
                "assignment_key": key,
                "assignment_value": value,
            }
        )
        key_lines[key].append(line_no)
        key_values[key][value].append(line_no)
        assignments.append((line_no, key, value, match))
    edges: list[dict[str, Any]] = []
    for line_no, _key, value, match in assignments:
        value_off = match.start(2)
        for ref in REF_RE.finditer(value):
            name = ref.group(1)
            for dest_line in key_lines.get(name) or []:
                edges.append(
                    {
                        "name": name,
                        "source_line": line_no,
                        "dest_line": dest_line,
                        "gold_identity": [line_no, name, dest_line],
                        "source_span": [value_off + ref.start(), value_off + ref.end()],
                    }
                )
    exact_dups = [
        {"assignment_key": key, "assignment_value": value, "lines": lines}
        for key, values in sorted(key_values.items())
        for value, lines in sorted(values.items())
        if len(lines) > 1
    ]
    repeated_diff = [
        {"assignment_key": key, "n_values": len(values)}
        for key, values in sorted(key_values.items())
        if len(values) > 1
    ]
    n_assign = sum(1 for rec in records if rec["kind"] == "assignment")
    return {
        "encoding": "utf-8",
        "records": records,
        "explicit_reference_edges": edges,
        "exact_duplicate_groups": exact_dups,
        "repeated_key_different_value": repeated_diff,
        "n_assignments": n_assign,
        "n_unsupported": sum(1 for rec in records if rec["kind"] == "unsupported"),
        "n_explicit_reference_edges": len(edges),
        "n_lines": len(text.splitlines()),
    }


def _norm_path(path: str) -> str:
    return "/" + path.replace("\\", "/").lstrip("/").lower()


def metadata_reject(row: Mapping[str, Any]) -> str | None:
    if row.get("archived"):
        return "archived"
    if row.get("fork"):
        return "fork"
    spdx = row.get("license_spdx")
    if spdx not in ALLOWED_SPDX:
        return f"license {spdx!r} not MIT or Apache-2.0"
    full = str(row.get("repository_full_name") or "")
    if full in RS1_REPOS:
        return "used in REALSTRUCT-1"
    npath = _norm_path(str(row.get("path") or ""))
    for marker in TEST_PATH_MARKERS:
        if marker in npath:
            return "generated benchmark/test fixture path"
    lowered = full.lower()
    if lowered == "nyattoh/bite-ingestion" or "bite-ingestion" in npath:
        return "BITE-specific artificial input"
    return None


def fetch_raw(full_name: str, commit: str, path: str) -> bytes:
    api = f"/repos/{full_name}/contents/{quote(path, safe='/')}?ref={commit}"
    proc = subprocess.run(
        ["gh", "api", "-H", "Accept: application/vnd.github.raw", api],
        cwd=_REPO,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or b"").decode("utf-8", errors="replace")[:200]
        raise FileNotFoundError(err or "missing blob")
    data = proc.stdout or b""
    stripped = data.lstrip()
    if stripped.startswith(b"{") and b'"message"' in stripped[:240]:
        raise FileNotFoundError(stripped[:200].decode("utf-8", errors="replace"))
    return data


def _source_id(family: str, full_name: str, used: set[str]) -> str:
    slug = full_name.replace("/", "-").lower()
    base = f"rs2-{FAMILY_SHORT[family]}-{slug}"
    source_id = base
    n = 2
    while source_id in used:
        source_id = f"{base}-{n}"
        n += 1
    used.add(source_id)
    return source_id


def _content_reject(data: bytes, sha_seen: set[str]) -> str | None:
    if b"\x00" in data:
        return "NUL bytes"
    if len(data) > MAX_BYTES:
        return f"byte length {len(data)} > {MAX_BYTES}"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "not UTF-8 / ASCII compatible"
    digest = sha256_bytes(data)
    if digest in sha_seen:
        return "duplicate raw SHA256"
    secrets = live_secret_hits(data, text)
    if secrets:
        return "live credentials / private keys / obvious real secrets"
    ann = annotate_source(data)
    if int(ann["n_assignments"]) < MIN_ASSIGNMENTS:
        return f"fewer than {MIN_ASSIGNMENTS} assignment records"
    return None


def freeze_corpus() -> dict[str, Any]:
    pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))
    pool_errs = validate_candidate_pool(pool)
    if pool_errs:
        raise RuntimeError(f"H1 pool invalid: {pool_errs}")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rejections: list[dict[str, str]] = []
    accepted: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    sha_seen: set[str] = set()
    primary_repos: set[str] = set()
    all_repos: set[str] = set()
    n_primary = {family: 0 for family in FAMILIES}
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
                and n_secondary[family] >= N_SECONDARY_PER_FAMILY
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
            digest = sha256_bytes(data)
            primary_open = n_primary[family] < N_PRIMARY_PER_FAMILY
            secondary_open = (
                not primary_open
                and n_secondary[family] < N_SECONDARY_PER_FAMILY
                and int(ann["n_explicit_reference_edges"]) > 0
            )
            if primary_open:
                if full in primary_repos:
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
                        {
                            "family": family,
                            "candidate": loc,
                            "reason": "repository already used",
                        }
                    )
                    continue
                stratum = "secondary_reference_enriched"
            else:
                rejections.append(
                    {"family": family, "candidate": loc, "reason": "quotas filled"}
                )
                continue
            source_id = _source_id(family, full, used_ids)
            raw_rel = f"corpora/realstruct-2/raw/{source_id}"
            ( _REPO / raw_rel).write_bytes(data)
            sha_seen.add(digest)
            all_repos.add(full)
            if stratum == "primary":
                primary_repos.add(full)
                n_primary[family] += 1
            else:
                n_secondary[family] += 1
            rec = {
                "source_id": source_id,
                "family": family,
                "stratum": stratum,
                "repository_url": str(row["html_url"]),
                "repository_id": row["repository_id"],
                "commit_sha": commit,
                "path": path,
                "source_url": f"https://github.com/{full}/blob/{commit}/{path}",
                "raw_url": (
                    f"https://raw.githubusercontent.com/{full}/{commit}/{path}"
                ),
                "license": row["license_spdx"],
                "spdx": row["license_spdx"],
                "sha256": digest,
                "byte_length": len(data),
                "line_count": ann["n_lines"],
                "n_assignments": ann["n_assignments"],
                "n_explicit_reference_edges": ann["n_explicit_reference_edges"],
                "encoding": "utf-8",
                "raw_file": raw_rel,
                "selection_key": row["selection_key"],
            }
            accepted.append(rec)
            annotations.append(
                {
                    "source_id": source_id,
                    "stratum": stratum,
                    **ann,
                }
            )
            time.sleep(0.15)
    freeze_errs = validate_phase4h_freeze(freeze_manifest())
    try:
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
        freeze_errs.append("p3f seal did not fire")
    except EvaluationSealError:
        pass
    primary = [row for row in accepted if row["stratum"] == "primary"]
    secondary = [row for row in accepted if row["stratum"] != "primary"]
    errors: list[str] = list(freeze_errs)
    if len(primary) != N_PRIMARY:
        errors.append(f"primary count {len(primary)} != {N_PRIMARY}")
    for family in FAMILIES:
        got = sum(1 for row in primary if row["family"] == family)
        if got != N_PRIMARY_PER_FAMILY:
            errors.append(f"{family} primary {got} != {N_PRIMARY_PER_FAMILY}")
    verdict = VERDICT_FROZEN if not errors else VERDICT_PARTIAL
    if any("blocked" in err for err in errors):
        verdict = VERDICT_BLOCKED
    corpus = {
        "schema": CORPUS_SCHEMA_ID,
        "revision": POOL_REVISION,
        "corpus_name": "REALSTRUCT-2",
        "protocol_commit_sha": H0_COMMIT_SHA,
        "h1_commit_sha": H1_COMMIT_SHA,
        "n_documents": len(accepted),
        "n_primary": len(primary),
        "n_secondary": len(secondary),
        "sources": accepted,
        "claim_boundary": CLAIM_BOUNDARY,
        "one_document_one_uri": True,
        "no_cross_document_join": True,
        "secondary_never_pooled_with_primary": True,
    }
    licenses = {
        "schema": LICENSE_SCHEMA_ID,
        "revision": POOL_REVISION,
        "allowed_spdx": list(ALLOWED_SPDX),
        "documents": [
            {
                "source_id": row["source_id"],
                "spdx": row["spdx"],
                "redistributable": True,
                "license_url": row["repository_url"],
                "license_note": "GitHub license API SPDX recorded at H1",
                "repository_url": row["repository_url"],
                "commit_sha": row["commit_sha"],
            }
            for row in accepted
        ],
    }
    annotation_doc = {
        "schema": ANNOTATION_SCHEMA_ID,
        "revision": POOL_REVISION,
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
        "documents": annotations,
    }
    rejection_doc = {
        "schema": REJECTION_SCHEMA_ID,
        "revision": POOL_REVISION,
        "h1_commit_sha": H1_COMMIT_SHA,
        "n_rejections": len(rejections),
        "rejections": rejections,
    }
    primary_doc = {
        "schema": "bite-phase4h-realstruct2-primary/v0.1",
        "revision": POOL_REVISION,
        "n_primary": len(primary),
        "source_ids": [row["source_id"] for row in primary],
        "sources": primary,
    }
    secondary_doc = {
        "schema": "bite-phase4h-realstruct2-secondary/v0.1",
        "revision": POOL_REVISION,
        "label": "mechanism-enriched diagnostic",
        "never_pooled_with_primary": True,
        "not_representative_evidence": True,
        "n_secondary": len(secondary),
        "source_ids": [row["source_id"] for row in secondary],
        "sources": secondary,
    }
    result = {
        "schema": RESULT_SCHEMA_ID,
        "revision": POOL_REVISION,
        "protocol_commit_sha": H0_COMMIT_SHA,
        "h0_freeze_blob": H0_FREEZE_BLOB,
        "h1_commit_sha": H1_COMMIT_SHA,
        "h1_pool_blob": H1_POOL_BLOB,
        "verdict": verdict,
        "paid_api": False,
        "offline_core_tests": True,
        "research_conclusion": False,
        "premise": PREMISE,
        "phase4g_verdict": PREMISE,
        "phase4f_verdict": PHASE4F_VERDICT,
        "phase4e_verdict": PHASE4E_VERDICT,
        "phase4c_verdict": PHASE4C_VERDICT,
        "phase4d_verdict": PHASE4D_VERDICT,
        "phase3t_verdict": PHASE3T_VERDICT,
        "phase3s_verdict": PHASE3S_VERDICT,
        "phase3q_verdict": PHASE3Q_VERDICT,
        "p3f_evaluation_holdout_used": False,
        "no_xfer3": True,
        "no_bite_execution": True,
        "no_tokenizer_execution": True,
        "no_arm_execution": True,
        "no_phase4f_rewrite": True,
        "no_phase4g_rewrite": True,
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "BITE evidence",
            "baseline evidence",
            "comparison result",
            "generalization",
            "superiority",
        ],
        "n_primary": len(primary),
        "n_secondary": len(secondary),
        "n_documents": len(accepted),
        "locked_blobs": dict(LOCKED_BLOBS),
        "errors": errors,
    }
    _dump(MANIFEST_PATH, corpus)
    _dump(PRIMARY_PATH, primary_doc)
    _dump(SECONDARY_PATH, secondary_doc)
    _dump(LICENSE_PATH, licenses)
    _dump(ANNOTATION_PATH, annotation_doc)
    _dump(REJECTION_PATH, rejection_doc)
    _dump(RESULT_PATH, result)
    return result


def validate_phase4h_corpus(doc: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if doc.get("schema") != RESULT_SCHEMA_ID:
        errs.append("result schema mismatch")
    if doc.get("verdict") not in (VERDICT_FROZEN, VERDICT_PARTIAL, VERDICT_BLOCKED):
        errs.append("unknown verdict")
    if doc.get("no_arm_execution") is not True or doc.get("no_tokenizer_execution") is not True:
        errs.append("arm/tokenizer execution leaked")
    if doc.get("p3f_evaluation_holdout_used") is not False:
        errs.append("p3f opened")
    if doc.get("h0_freeze_blob") != H0_FREEZE_BLOB:
        errs.append("H0 freeze blob drifted")
    if doc.get("h1_pool_blob") != H1_POOL_BLOB:
        errs.append("H1 pool blob drifted")
    if json.loads(POOL_PATH.read_text(encoding="utf-8")).get("file_contents_opened") is not False:
        errs.append("H1 pool rewritten with contents")
    if doc.get("verdict") == VERDICT_FROZEN:
        if doc.get("n_primary") != N_PRIMARY:
            errs.append("FROZEN requires 18 primary")
        if doc.get("errors"):
            errs.append("FROZEN must have empty errors")
    if doc.get("verdict") == VERDICT_PARTIAL and not doc.get("errors"):
        errs.append("PARTIAL must record the shortfall")
    if MANIFEST_PATH.is_file():
        corpus = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        ids = [row["source_id"] for row in corpus.get("sources") or []]
        if len(ids) != len(set(ids)):
            errs.append("duplicate source_id")
        primary_ids = {
            row["source_id"]
            for row in corpus.get("sources") or []
            if row.get("stratum") == "primary"
        }
        secondary_ids = {
            row["source_id"]
            for row in corpus.get("sources") or []
            if row.get("stratum") != "primary"
        }
        if primary_ids & secondary_ids:
            errs.append("secondary pooled with primary")
        for row in corpus.get("sources") or []:
            raw = _REPO / str(row["raw_file"])
            if not raw.is_file():
                errs.append(f"missing raw {row['source_id']}")
                continue
            data = raw.read_bytes()
            if sha256_bytes(data) != row.get("sha256"):
                errs.append(f"raw sha256 mismatch {row['source_id']}")
            if b"\x00" in data:
                errs.append(f"NUL in {row['source_id']}")
    for path, expected in LOCKED_BLOBS.items():
        got = subprocess.check_output(["git", "hash-object", path], cwd=_REPO, text=True).strip()
        if got != expected:
            errs.append(f"locked blob drifted: {path}")
    return errs


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "freeze"
    if cmd == "collect":
        pool = collect_pool()
        print("n_candidates", pool["n_candidates"])
        print("errors", validate_candidate_pool(pool))
    else:
        result = freeze_corpus()
        print(result["verdict"], "primary", result["n_primary"], "secondary", result["n_secondary"])
        print("errors", result["errors"])
