"""Phase 4H REALSTRUCT-2 candidate pool (H1) and later corpus freeze.

H1 collects repository/path candidates without reading file contents.
Does not run comparison arms, tokenizers, BITE sensors, or policies.
Does not open p3f.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import quote

from bite_bench.phase4h import (
    CANDIDATE_POOL_PER_FAMILY,
    DISCOVERY_QUERIES,
    FAMILIES,
    G0_FREEZE_BLOB,
    PHASE4G_HEAD,
    PREMISE,
    freeze_manifest,
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


if __name__ == "__main__":
    pool = collect_pool()
    print("n_candidates", pool["n_candidates"])
    print("errors", validate_candidate_pool(pool))
