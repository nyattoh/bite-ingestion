"""Phase 4A REALSTRUCT-1 acquisition, split, and scorer-only annotation.

Does not import or run BITE sensors, policies, planners, or operators.
Does not open p3f. Does not execute baselines.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NamedTuple

from bite_bench.phase4a import (
    ALLOWED_SPDX,
    CLAIM_BOUNDARY,
    FAMILIES,
    LOCKED_BLOBS,
    MAX_BYTES,
    MAX_LINES,
    MIN_ASSIGNMENTS,
    N_DEV,
    N_DEV_PER_FAMILY,
    N_DOCUMENTS,
    N_ENRICHED_PER_FAMILY,
    N_EVAL,
    N_NATURAL_PER_FAMILY,
    PHASE3Q_VERDICT,
    PHASE3S_VERDICT,
    PHASE3T_VERDICT,
    PREMISE,
    STRATA,
    VERDICT_BLOCKED,
    VERDICT_FROZEN,
    VERDICT_PARTIAL,
    EvaluationSealError,
    freeze_manifest,
    refuse_p3f_evaluation,
    validate_phase4a_freeze,
)

SCHEMA_ID = "bite-phase4a-realstruct1/v0.1"
CORPUS_SCHEMA_ID = "bite-phase4a-realstruct1-corpus/v0.1"
LICENSE_SCHEMA_ID = "bite-phase4a-realstruct1-licenses/v0.1"
SPLIT_SCHEMA_ID = "bite-phase4a-realstruct1-split/v0.1"
ANNOTATION_SCHEMA_ID = "bite-phase4a-realstruct1-annotations/v0.1"
REVISION = "phase4a-realstruct1-v0.1"
PROTOCOL_COMMIT_SHA = "3e5d2d7c9cd0a07346e90401496df042aa956bf7"
A0_FREEZE_BLOB = "6e009fb6cf1cb239b8449e402301be15ffd7ed86"

ASSIGN_RE = re.compile(r"^\s*(?:export\s+)?([^#;=\s][^=]*?)\s*=\s*(.*)$")
COMMENT_RE = re.compile(r"^\s*(?:[#;]|//)")
SECTION_RE = re.compile(r"^\s*\[")
REF_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_.]*)\}")
SECRET_KEY_RE = re.compile(
    r"(password|secret|private.?key|api.?key|access.?key|token|credential)",
    re.IGNORECASE,
)
PEM_RE = re.compile(rb"BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY")
AKIA_RE = re.compile(rb"AKIA[0-9A-Z]{16}")
PLACEHOLDERS = {
    "",
    "null",
    "none",
    "changeme",
    "secret",
    "password",
    "xxx",
    "your-secret-here",
    "example",
    "todo",
    "replace_me",
    "false",
    "true",
    "database_user_password",
}

_REPO = Path(__file__).resolve().parents[2]
RAW_DIR = _REPO / "corpora" / "realstruct-1" / "raw"
CORPUS_DIR = _REPO / "corpora" / "realstruct-1"
ARTIFACT_DIR = _REPO / "artifacts" / "phase4a"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"
LICENSE_PATH = CORPUS_DIR / "licenses.json"
SPLIT_PATH = CORPUS_DIR / "split.json"
ANNOTATION_PATH = CORPUS_DIR / "annotations.json"
RESULT_PATH = ARTIFACT_DIR / "realstruct-1.json"
FREEZE_PATH = _REPO / "benchmarks" / "spec" / "phase4a-realstruct1-freeze.json"
PHASE4A_PY = Path(__file__).resolve()
FORBIDDEN_IMPORT_NEEDLES = (
    "bite_ingestion.policies",
    "bite_ingestion.profilers",
    "dependency_dispersion_v3",
    "conditional_texture_policy_v4",
)


class SourceSpec(NamedTuple):
    source_id: str
    owner: str
    repo: str
    commit_sha: str
    path: str
    family: str
    stratum: str
    spdx: str
    license_path: str
    license_note: str = ""


SOURCES: tuple[SourceSpec, ...] = (
    SourceSpec(
        "rs1-dotenv-laravel",
        "laravel",
        "laravel",
        "aa0cf127fc365a56ee016867144ddffabc2290ae",
        ".env.example",
        "dotenv-like",
        "explicit-reference-enriched",
        "MIT",
        "composer.json",
        "composer.json license field MIT; no LICENSE file in skeleton",
    ),
    SourceSpec(
        "rs1-dotenv-koel",
        "koel",
        "koel",
        "51698046353dfc7dd4ee466580f9120d5a1f6762",
        ".env.example",
        "dotenv-like",
        "explicit-reference-enriched",
        "MIT",
        "LICENSE.md",
    ),
    SourceSpec(
        "rs1-dotenv-bookstack",
        "BookStackApp",
        "BookStack",
        "cf133540b13073e18e08f10b65a2aff2be0f155e",
        ".env.example",
        "dotenv-like",
        "natural",
        "MIT",
        "LICENSE",
    ),
    SourceSpec(
        "rs1-dotenv-linkding",
        "sissbruecker",
        "linkding",
        "27b7303baf41bb28babc610ac8eaa486e1ddfab5",
        ".env.sample",
        "dotenv-like",
        "natural",
        "MIT",
        "LICENSE.txt",
    ),
    SourceSpec(
        "rs1-props-hadoop-log4j",
        "apache",
        "hadoop",
        "a3febb258a28c1023a09ba29bc41c1b98a2c2cc7",
        "hadoop-common-project/hadoop-common/src/main/conf/log4j.properties",
        "java_properties",
        "explicit-reference-enriched",
        "Apache-2.0",
        "LICENSE.txt",
    ),
    SourceSpec(
        "rs1-props-ratis-log4j",
        "apache",
        "ratis",
        "959ee33d8231deb798a876ecd9fa8f66b252cf71",
        "ratis-common/src/main/conf/log4j.properties",
        "java_properties",
        "explicit-reference-enriched",
        "Apache-2.0",
        "LICENSE",
    ),
    SourceSpec(
        "rs1-props-kafka-server",
        "apache",
        "kafka",
        "995cfcf99f7917403e030428c00b5c51808ddc61",
        "config/server.properties",
        "java_properties",
        "natural",
        "Apache-2.0",
        "LICENSE",
    ),
    SourceSpec(
        "rs1-props-tomcat-logging",
        "apache",
        "tomcat",
        "e7604b9f63c86a9e88bc569bd19d4f57739c6768",
        "conf/logging.properties",
        "java_properties",
        "natural",
        "Apache-2.0",
        "LICENSE",
    ),
    SourceSpec(
        "rs1-ini-gogs",
        "gogs",
        "gogs",
        "dbbd717e923694c36f41b0360515b4374bbe6ee0",
        "conf/app.ini",
        "ini_cfg",
        "natural",
        "MIT",
        "LICENSE",
    ),
    SourceSpec(
        "rs1-ini-polybar",
        "polybar",
        "polybar",
        "f99e0b1c7a5b094f5a04b14101899d0cb4ece69d",
        "doc/config.ini",
        "ini_cfg",
        "natural",
        "MIT",
        "LICENSE",
    ),
    SourceSpec(
        "rs1-ini-oe-bitbake",
        "openembedded",
        "openembedded-core",
        "4171f85bbc60cd8cbb95b768438b6b670cd276e0",
        "meta/conf/bitbake.conf",
        "ini_cfg",
        "explicit-reference-enriched",
        "MIT",
        "LICENSE.MIT",
        "OE LICENSE: all metadata MIT unless otherwise stated",
    ),
    SourceSpec(
        "rs1-ini-tegra-common",
        "OE4T",
        "meta-tegra",
        "8f741d06e6975ead6c710a8b5cb43ddd0be18ddb",
        "conf/machine/include/tegra-common.inc",
        "ini_cfg",
        "explicit-reference-enriched",
        "MIT",
        "LICENSE",
    ),
)

EXCLUSIONS: tuple[dict[str, str], ...] = (
    {
        "candidate": "Magisk settings.ini family",
        "reason": "GPL-3.0 not in allowed SPDX",
    },
    {
        "candidate": "immich .env",
        "reason": "AGPL-3.0 not in allowed SPDX",
    },
    {
        "candidate": "hoppscotch .env.example DATABASE_URL",
        "reason": "credential-like postgres:testpass value",
    },
    {
        "candidate": "apache/superset .env",
        "reason": "SUPERSET_SECRET_KEY=TEST_NON_DEV_SECRET live-secret-like",
    },
    {
        "candidate": "appwrite .env",
        "reason": "rootsecretpassword live-secret-like",
    },
    {
        "candidate": "netbox.env",
        "reason": "fewer than 10 first-= assignments",
    },
    {
        "candidate": "zookeeper zoo_sample.cfg",
        "reason": "fewer than 10 first-= assignments",
    },
    {
        "candidate": "tomcat catalina.properties",
        "reason": "fewer than 10 first-= assignments",
    },
    {
        "candidate": "pkg-config .pc.in templates",
        "reason": "Name:/Libs: colon keys are unsupported under first-= grammar",
    },
    {
        "candidate": "openssl.pc.in",
        "reason": "perl generator, not a runtime key=value config",
    },
    {
        "candidate": "gitea custom/conf/app.example.ini",
        "reason": "almost all comments; replaced by gogs conf/app.ini",
    },
    {
        "candidate": "openbmc phosphor-defaults.inc",
        "reason": "hashed password value plus license NOASSERTION",
    },
    {
        "candidate": "yoctoproject/poky",
        "reason": "pinned tree lacked usable distro conf paths",
    },
)


def _dump(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(doc), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_source(data: bytes) -> tuple[str, str]:
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return data.decode("latin-1"), "latin-1"


def _placeholder(value: str) -> bool:
    stripped = value.strip().strip("\"'").lower()
    return stripped in PLACEHOLDERS or stripped.startswith(
        ("change-me", "changeme", "your-", "${")
    )


def live_secret_hits(data: bytes, text: str) -> list[str]:
    hits: list[str] = []
    if PEM_RE.search(data):
        hits.append("pem_private_key")
    if AKIA_RE.search(data):
        hits.append("aws_access_key_id")
    for line in text.splitlines():
        match = ASSIGN_RE.match(line)
        if not match:
            continue
        key = match.group(1).strip()
        value = match.group(2).strip().strip("\"'")
        if not SECRET_KEY_RE.search(key):
            continue
        if _placeholder(value):
            continue
        if value.startswith("$6$") or (len(value) >= 12):
            hits.append(f"{key}={value[:24]}")
    return hits


def annotate_bytes(data: bytes) -> dict[str, Any]:
    text, encoding = decode_source(data)
    records: list[dict[str, Any]] = []
    key_lines: dict[str, list[int]] = defaultdict(list)
    edges: list[dict[str, Any]] = []
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
        value_off = match.start(2)
        for ref in REF_RE.finditer(value):
            name = ref.group(1)
            dest = key_lines.get(name) or []
            if not dest:
                continue
            edges.append(
                {
                    "name": name,
                    "source_line": line_no,
                    "source_span": [value_off + ref.start(), value_off + ref.end()],
                    "dest_lines": list(dest),
                }
            )
    duplicate_groups = [
        {"assignment_key": key, "lines": lines}
        for key, lines in sorted(key_lines.items())
        if len(lines) > 1
    ]
    n_assign = sum(1 for rec in records if rec["kind"] == "assignment")
    n_unsup = sum(1 for rec in records if rec["kind"] == "unsupported")
    return {
        "encoding": encoding,
        "records": records,
        "explicit_reference_edges": edges,
        "duplicate_groups": duplicate_groups,
        "n_assignments": n_assign,
        "n_unsupported": n_unsup,
        "n_explicit_reference_edges": len(edges),
        "n_lines": len(text.splitlines()),
    }


def raw_path(spec: SourceSpec) -> Path:
    return RAW_DIR / spec.source_id


def blob_url(spec: SourceSpec, path: str | None = None) -> str:
    rel = path if path is not None else spec.path
    return f"https://github.com/{spec.owner}/{spec.repo}/blob/{spec.commit_sha}/{rel}"


def repo_url(spec: SourceSpec) -> str:
    return f"https://github.com/{spec.owner}/{spec.repo}"


def load_raw(spec: SourceSpec) -> bytes:
    path = raw_path(spec)
    if not path.is_file():
        raise FileNotFoundError(f"missing raw bytes: {path}")
    return path.read_bytes()


def source_record(spec: SourceSpec) -> dict[str, Any]:
    data = load_raw(spec)
    ann = annotate_bytes(data)
    return {
        "source_id": spec.source_id,
        "repository_url": repo_url(spec),
        "commit_sha": spec.commit_sha,
        "path": spec.path,
        "source_url": blob_url(spec),
        "spdx": spec.spdx,
        "sha256": sha256_bytes(data),
        "byte_length": len(data),
        "line_count": ann["n_lines"],
        "family": spec.family,
        "stratum": spec.stratum,
        "n_assignments": ann["n_assignments"],
        "n_explicit_reference_edges": ann["n_explicit_reference_edges"],
        "encoding": ann["encoding"],
        "raw_file": f"corpora/realstruct-1/raw/{spec.source_id}",
    }


def split_records(records: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    by_family: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for rec in records:
        by_family[str(rec["family"])].append(rec)
    development: list[str] = []
    evaluation: list[str] = []
    for family in FAMILIES:
        ordered = sorted(by_family[family], key=lambda item: str(item["sha256"]))
        if not ordered:
            continue
        development.append(str(ordered[0]["source_id"]))
        evaluation.extend(str(item["source_id"]) for item in ordered[1:])
    return {"development": development, "evaluation": evaluation}


def corpus_manifest(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema": CORPUS_SCHEMA_ID,
        "revision": REVISION,
        "corpus_name": "REALSTRUCT-1",
        "protocol_commit_sha": PROTOCOL_COMMIT_SHA,
        "n_documents": len(records),
        "sources": list(records),
        "exclusions": list(EXCLUSIONS),
        "claim_boundary": CLAIM_BOUNDARY,
        "one_document_one_uri": True,
        "no_cross_document_join": True,
    }


def license_manifest(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_id = {spec.source_id: spec for spec in SOURCES}
    docs = []
    for rec in records:
        spec = by_id[str(rec["source_id"])]
        docs.append(
            {
                "source_id": spec.source_id,
                "spdx": spec.spdx,
                "redistributable": True,
                "license_url": blob_url(spec, spec.license_path),
                "license_note": spec.license_note,
                "repository_url": repo_url(spec),
                "commit_sha": spec.commit_sha,
            }
        )
    return {
        "schema": LICENSE_SCHEMA_ID,
        "revision": REVISION,
        "allowed_spdx": list(ALLOWED_SPDX),
        "documents": docs,
    }


def split_manifest(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    split = split_records(records)
    return {
        "schema": SPLIT_SCHEMA_ID,
        "revision": REVISION,
        "protocol_commit_sha": PROTOCOL_COMMIT_SHA,
        "order": "within family, lexicographic sha256 of exact raw bytes",
        "development_per_family": N_DEV_PER_FAMILY,
        "n_development": len(split["development"]),
        "n_evaluation": len(split["evaluation"]),
        "no_swap_after_split": True,
        "development": split["development"],
        "evaluation": split["evaluation"],
        "evaluation_may_not_be_measured_by_bite": True,
        "future_comparison_preregistration": {
            "same_bytes_for_bite_and_baseline": True,
            "no_baseline_in_phase4a": True,
            "no_baseline_tuning_on_evaluation": True,
        },
    }


def annotation_manifest(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_id = {spec.source_id: spec for spec in SOURCES}
    documents = []
    for rec in records:
        spec = by_id[str(rec["source_id"])]
        ann = annotate_bytes(load_raw(spec))
        documents.append({"source_id": spec.source_id, **ann})
    return {
        "schema": ANNOTATION_SCHEMA_ID,
        "revision": REVISION,
        "independent_of_bite_implementation": True,
        "raw_syntax_only": True,
        "explicit_reference_gold": "${NAME} only",
        "missing_annotation_is_not_non_reference": True,
        "forbidden_scorer_fields": [
            "expected BITE route",
            "expected operator sequence",
        ],
        "documents": documents,
    }


def result_manifest(
    records: Sequence[Mapping[str, Any]],
    split: Mapping[str, Any],
    errors: Sequence[str],
) -> dict[str, Any]:
    verdict = VERDICT_FROZEN if not errors else VERDICT_PARTIAL
    if any("blocked" in err for err in errors):
        verdict = VERDICT_BLOCKED
    return {
        "schema": SCHEMA_ID,
        "revision": REVISION,
        "protocol_commit_sha": PROTOCOL_COMMIT_SHA,
        "a0_freeze_blob": A0_FREEZE_BLOB,
        "verdict": verdict,
        "paid_api": False,
        "offline_core_tests": True,
        "research_conclusion": False,
        "premise": PREMISE,
        "phase3t_verdict": PHASE3T_VERDICT,
        "phase3s_verdict": PHASE3S_VERDICT,
        "phase3q_verdict": PHASE3Q_VERDICT,
        "p3f_evaluation_holdout_used": False,
        "no_xfer3": True,
        "no_bite_execution": True,
        "no_bite_policy_import": True,
        "no_bite_profiler_import": True,
        "no_baseline_execution": True,
        "claim_boundary": CLAIM_BOUNDARY,
        "not_claimed": [
            "representative sample",
            "real-world generalization",
            "BITE superiority",
        ],
        "n_documents": len(records),
        "n_development": split.get("n_development"),
        "n_evaluation": split.get("n_evaluation"),
        "locked_blobs": dict(LOCKED_BLOBS),
        "errors": list(errors),
        "synthetic_controls": {
            "phase3t_frozen_artifacts_secondary_only": True,
            "do_not_mix_real_and_synthetic_accuracy": True,
        },
    }


def _forbidden_imports(path: Path) -> list[str]:
    hits: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith(("import ", "from ")):
            continue
        for needle in FORBIDDEN_IMPORT_NEEDLES:
            if needle in stripped:
                hits.append(f"{path.name}:{needle}")
    return hits


def validate_phase4a_corpus(doc: Mapping[str, Any] | None = None) -> list[str]:
    errs: list[str] = []
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    if freeze != freeze_manifest():
        errs.append("A0 freeze drifted from freeze_manifest()")
    errs.extend(validate_phase4a_freeze(freeze))
    errs.extend(_forbidden_imports(PHASE4A_PY))
    errs.extend(_forbidden_imports(_REPO / "src" / "bite_bench" / "phase4a.py"))
    if len(SOURCES) != N_DOCUMENTS:
        errs.append("catalog size != 12")
    repos = [(spec.owner, spec.repo) for spec in SOURCES]
    if len(set(repos)) != len(repos):
        errs.append("one repository per document violated")
    records = [source_record(spec) for spec in SOURCES]
    by_family: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for rec in records:
        by_family[str(rec["family"])].append(rec)
        if rec["byte_length"] > MAX_BYTES or rec["line_count"] > MAX_LINES:
            errs.append(f"{rec['source_id']} exceeds size cap")
        if int(rec["n_assignments"]) < MIN_ASSIGNMENTS:
            errs.append(f"{rec['source_id']} has <{MIN_ASSIGNMENTS} assignments")
        if rec["spdx"] not in ALLOWED_SPDX:
            errs.append(f"{rec['source_id']} SPDX not allowed")
        spec = next(item for item in SOURCES if item.source_id == rec["source_id"])
        data = load_raw(spec)
        if sha256_bytes(data) != rec["sha256"]:
            errs.append(f"{rec['source_id']} hash mismatch")
        hits = live_secret_hits(data, decode_source(data)[0])
        if hits:
            errs.append(f"{rec['source_id']} secret-like: {hits[:3]}")
        if rec["stratum"] not in STRATA:
            errs.append(f"{rec['source_id']} bad stratum")
        if rec["stratum"] == "explicit-reference-enriched" and int(
            rec["n_explicit_reference_edges"]
        ) < 1:
            errs.append(f"{rec['source_id']} enriched without gold edges")
        if rec["family"] not in FAMILIES:
            errs.append(f"{rec['source_id']} bad family")
    for family in FAMILIES:
        rows = by_family[family]
        if len(rows) != 4:
            errs.append(f"{family} does not have 4 documents")
            continue
        n_nat = sum(1 for row in rows if row["stratum"] == "natural")
        n_enr = sum(1 for row in rows if row["stratum"] == "explicit-reference-enriched")
        if n_nat != N_NATURAL_PER_FAMILY or n_enr != N_ENRICHED_PER_FAMILY:
            errs.append(f"{family} stratum counts drifted")
    split = split_manifest(records)
    if len(split["development"]) != N_DEV or len(split["evaluation"]) != N_EVAL:
        errs.append("split counts drifted")
    if MANIFEST_PATH.is_file():
        committed = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        if committed != corpus_manifest(records):
            errs.append("corpus manifest drifted")
    if SPLIT_PATH.is_file():
        committed_split = json.loads(SPLIT_PATH.read_text(encoding="utf-8"))
        if committed_split != split:
            errs.append("split manifest drifted")
    if ANNOTATION_PATH.is_file():
        committed_ann = json.loads(ANNOTATION_PATH.read_text(encoding="utf-8"))
        generated_ann = annotation_manifest(records)
        if committed_ann != generated_ann:
            errs.append("annotation manifest drifted")
        blob = json.dumps(committed_ann)
        if '"non_reference"' in blob:
            errs.append("annotations must not encode missing as non_reference")
        for document in committed_ann.get("documents") or []:
            for edge in document.get("explicit_reference_edges") or []:
                name = str(edge.get("name") or "")
                if not name or ":-" in name:
                    errs.append(f"bad gold name {name!r}")
    if LICENSE_PATH.is_file():
        committed_lic = json.loads(LICENSE_PATH.read_text(encoding="utf-8"))
        if committed_lic != license_manifest(records):
            errs.append("license manifest drifted")
    if doc is not None:
        if doc.get("protocol_commit_sha") != PROTOCOL_COMMIT_SHA:
            errs.append("protocol_commit_sha drifted")
        if doc.get("p3f_evaluation_holdout_used") is not False:
            errs.append("p3f evaluation must stay sealed")
        if doc.get("no_bite_execution") is not True:
            errs.append("BITE execution leaked into 4A")
        if doc.get("verdict") == VERDICT_FROZEN and errs:
            errs.append("frozen verdict with validation errors")
        if doc.get("verdict") not in (VERDICT_FROZEN, VERDICT_PARTIAL, VERDICT_BLOCKED):
            errs.append("unknown 4A verdict")
    try:
        refuse_p3f_evaluation("p3f-medium-one_hop-r2")
        errs.append("p3f seal did not fire")
    except EvaluationSealError:
        pass
    return errs


def write_corpus() -> dict[str, Any]:
    records = [source_record(spec) for spec in SOURCES]
    split = split_manifest(records)
    _dump(MANIFEST_PATH, corpus_manifest(records))
    _dump(LICENSE_PATH, license_manifest(records))
    _dump(SPLIT_PATH, split)
    _dump(ANNOTATION_PATH, annotation_manifest(records))
    errors = validate_phase4a_corpus()
    result = result_manifest(records, split, errors)
    _dump(RESULT_PATH, result)
    return result


if __name__ == "__main__":
    payload = write_corpus()
    print(payload["verdict"], "errors", len(payload["errors"]))
    for item in payload["errors"]:
        print(" -", item)
