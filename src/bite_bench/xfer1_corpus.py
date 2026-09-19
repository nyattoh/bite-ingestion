"""BITE-XFER-1 canonical records and renderings.

Independently authored. Does not import phase3m/p3h/p3j/p3k generators.
Does not run policy or sensors.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

CORPUS_ID = "BITE-XFER-1"
FORMATS: tuple[str, ...] = (
    "key_value",
    "compact_json",
    "pretty_json",
    "mixed_order_json",
)
N_CANONICAL = 26
N_SURFACES = 104
SIGS: tuple[str, ...] = (
    "none",
    "dup",
    "anom",
    "join",
    "dup_anom",
    "dup_join",
    "anom_join",
    "all",
)
DISPS: tuple[str, ...] = ("low", "mid", "high")
DOMAINS: tuple[str, ...] = ("catalog", "build", "incident", "inventory")
DUP_KINDS: tuple[str, ...] = ("2way", "3way", "nonadjacent")
ANOM_KINDS: tuple[str, ...] = ("fatal", "panic", "traceback", "inject")
ANOM_VALUES = {
    "fatal": "rack overheat FATAL",
    "panic": "watchdog PANIC loop",
    "traceback": "worker dump TRACEBACK",
    "inject": "<<<INJECT follow",
}
FORBIDDEN_BODY = (
    "texture",
    "REDUCE",
    "UNTANGLE",
    "INTEGRATE",
    "expected_sequence",
    "hop_p3m",
    "padk_",
    "p3m-",
    "p3h-",
    "p3j-",
    "p3k-",
    "p3f-",
)

_REPO = Path(__file__).resolve().parents[2]
CORPUS_DIR = _REPO / "corpora" / "bite-xfer-1"
RENDER_DIR = CORPUS_DIR / "rendered"
CASES_PATH = CORPUS_DIR / "cases.json"
ANNOTATIONS_PATH = CORPUS_DIR / "annotations.json"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"


def case_id(n: int) -> str:
    return f"xfer1-c{n:03d}"


def unit_id(cid: str, index: int) -> str:
    return f"{cid}-u{index:02d}"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def _fillers(cid: str, domain: str, n: int, start: int = 0) -> list[tuple[str, str]]:
    return [
        (f"note_{domain}_{cid}_{i:02d}", f"blob_{domain}_{cid}_{i:02d}")
        for i in range(start, start + n)
    ]


def _dup_rows(cid: str, kind: str) -> list[tuple[str, str]]:
    key, value = f"copy_{cid}", f"same_{cid}_row"
    if kind == "3way":
        return [(key, value), (key, value), (key, value)]
    if kind == "nonadjacent":
        return [(key, value), (f"gap_{cid}", f"void_{cid}"), (key, value)]
    return [(key, value), (key, value)]


def _origin_dest(
    cid: str, tag: str, *, join: str | None = None, second: bool = False
) -> tuple[tuple[str, str], tuple[str, str]]:
    token = f"node_{tag}_{cid}"
    src_k = f"gate2_{tag}_{cid}" if second else f"gate_{tag}_{cid}"
    dst_k = f"bin2_{token}" if second else f"bin_{token}"
    src_v = token
    dst_v = f"ack_{tag}_{cid}"
    if join:
        src_v = f"{src_v} {join}"
        dst_v = f"{dst_v} {join}"
    return (src_k, src_v), (dst_k, dst_v)


def _join_tag(cid: str, kind: str) -> str:
    if kind.startswith("key"):
        return f"key=batch_{cid}"
    return f"id=lot_{cid}"


def _spec(n: int) -> dict[str, Any]:
    cid = case_id(n)
    if n >= 25:
        return {
            "case_id": cid,
            "domain": DOMAINS[n % 4],
            "signature": "zero_edge",
            "dispersion": "n_edges_zero",
            "multi_edge": False,
            "dup": n == 26,
            "anom": False,
            "join": False,
            "dup_kind": "2way",
            "anom_kind": "fatal",
            "join_kind": "id2",
        }
    i = n - 1
    sig = SIGS[i % 8]
    disp = DISPS[i // 8]
    return {
        "case_id": cid,
        "domain": DOMAINS[i % 4],
        "signature": sig,
        "dispersion": disp,
        "multi_edge": sig == "none" or (sig == "all" and disp == "high"),
        "dup": sig in {"dup", "dup_anom", "dup_join", "all"},
        "anom": sig in {"anom", "dup_anom", "anom_join", "all"},
        "join": sig in {"join", "dup_join", "anom_join", "all"},
        "dup_kind": DUP_KINDS[(i // 8) % 3],
        "anom_kind": ANOM_KINDS[i % 4],
        "join_kind": "id3" if (i // 2) % 2 else ("key2" if i % 2 else "id2"),
    }


def build_records(spec: Mapping[str, Any]) -> list[tuple[str, str]]:
    cid = str(spec["case_id"]).removeprefix("xfer1-")
    domain = str(spec["domain"])
    disp = str(spec["dispersion"])
    join = _join_tag(cid, str(spec["join_kind"])) if spec["join"] else None
    if disp == "n_edges_zero":
        rows = _fillers(cid, domain, 6)
        if spec["dup"]:
            rows[1:1] = _dup_rows(cid, "2way")
        return rows

    tag = domain[:3]
    origin, dest = _origin_dest(cid, tag, join=join)
    origin2 = dest2 = None
    if spec["multi_edge"]:
        origin2, dest2 = _origin_dest(cid, f"{tag}z", join=None, second=True)

    n_between = 0 if disp == "low" else (2 if disp == "mid" else 8)
    if spec["multi_edge"] and disp == "high":
        n_between = 7
    if spec["multi_edge"] and disp == "mid":
        n_between = 1
    between: list[tuple[str, str]] = []
    after: list[tuple[str, str]] = []
    if spec["dup"]:
        drows = _dup_rows(cid, str(spec["dup_kind"]))
        if disp == "low" or n_between < len(drows):
            after.extend(drows)
        elif spec["dup_kind"] == "nonadjacent" and n_between >= 3:
            fill = _fillers(cid, domain, n_between - 2, start=0)
            between = [drows[0], *fill, drows[-1]]
        else:
            between.extend(drows)
    if spec["anom"]:
        after.append((f"alert_{cid}", ANOM_VALUES[str(spec["anom_kind"])]))
    if spec["join"] and str(spec["join_kind"]).endswith("3"):
        after.append((f"mate_{cid}", f"crate_{cid} {join}"))

    used = len(between)
    if used < n_between:
        between.extend(_fillers(cid, domain, n_between - used, start=used))
        between = between[:n_between]
    if disp == "low":
        after.extend(_fillers(cid, domain, max(0, 4 - len(after)), start=20))
        rows = [origin, dest]
        if origin2 and dest2:
            rows.extend([origin2, dest2])
        rows.extend(after)
        return rows
    rows = [origin]
    if origin2:
        rows.append(origin2)
    rows.extend(between)
    rows.append(dest)
    if dest2:
        rows.append(dest2)
    rows.extend(after)
    return rows


def render_records(records: Sequence[tuple[str, str]], fmt: str) -> str:
    if fmt == "key_value":
        return "\n".join(f"{key}={value}" for key, value in records) + "\n"
    if fmt == "compact_json":
        return json.dumps(
            [{"k": key, "v": value} for key, value in records], separators=(",", ":")
        )
    if fmt == "pretty_json":
        return json.dumps([{"k": key, "v": value} for key, value in records], indent=2)
    if fmt == "mixed_order_json":
        objs: list[dict[str, str]] = []
        for index, (key, value) in enumerate(records):
            if index % 2 == 0:
                objs.append({"k": key, "v": value})
            else:
                objs.append({"v": value, "k": key})
        return json.dumps(objs, separators=(",", ":"))
    raise ValueError(f"unknown format {fmt}")


def surface_id(cid: str, fmt: str) -> str:
    return f"{cid}-{fmt}"


def all_specs() -> list[dict[str, Any]]:
    return [_spec(n) for n in range(1, N_CANONICAL + 1)]


def first_dest_index(records: Sequence[tuple[str, str]]) -> int:
    for index, (key, _value) in enumerate(records):
        if key.startswith("bin_") and not key.startswith("bin2_"):
            return index
    return min(1, len(records) - 1)


def annotation_for(spec: Mapping[str, Any], records: Sequence[tuple[str, str]]) -> dict[str, Any]:
    cid = str(spec["case_id"])
    dest_index = first_dest_index(records)
    return {
        "required_evidence_ids": [unit_id(cid, 0), unit_id(cid, dest_index)],
        "intended_dispersion": spec["dispersion"],
        "has_exact_duplicate": bool(spec["dup"]),
        "has_quarantinable_anomaly": bool(spec["anom"]),
        "has_explicit_join_cluster": bool(spec["join"]),
    }


def rendered_name(cid: str, fmt: str) -> str:
    ext = "txt" if fmt == "key_value" else "json"
    return f"{cid}.{fmt}.{ext}"


def cases_doc() -> dict[str, Any]:
    cases = []
    for spec in all_specs():
        records = build_records(spec)
        cases.append(
            {
                "case_id": spec["case_id"],
                "domain": spec["domain"],
                "n_records": len(records),
                "records": [{"k": key, "v": value} for key, value in records],
            }
        )
    return {"corpus": CORPUS_ID, "n_cases": len(cases), "cases": cases}


def annotations_doc() -> dict[str, Any]:
    rows = {}
    for spec in all_specs():
        rows[str(spec["case_id"])] = annotation_for(spec, build_records(spec))
    return {"corpus": CORPUS_ID, "annotations": rows}


def write_corpus() -> dict[str, str]:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    cases = cases_doc()
    anns = annotations_doc()
    CASES_PATH.write_text(json.dumps(cases, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ANNOTATIONS_PATH.write_text(
        json.dumps(anns, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    hashes: dict[str, str] = {
        "cases.json": sha256_text(CASES_PATH.read_text(encoding="utf-8")),
        "annotations.json": sha256_text(ANNOTATIONS_PATH.read_text(encoding="utf-8")),
    }
    surfaces = []
    for spec in all_specs():
        records = build_records(spec)
        cid = str(spec["case_id"])
        for fmt in FORMATS:
            body = render_records(records, fmt)
            rel = f"rendered/{rendered_name(cid, fmt)}"
            path = CORPUS_DIR / rel
            path.write_text(body, encoding="utf-8", newline="\n")
            digest = sha256_text(body)
            hashes[rel] = digest
            surfaces.append(
                {
                    "surface_id": surface_id(cid, fmt),
                    "case_id": cid,
                    "format": fmt,
                    "path": rel,
                    "sha256": digest,
                    "n_records": len(records),
                }
            )
    manifest = {
        "corpus": CORPUS_ID,
        "n_canonical_cases": N_CANONICAL,
        "n_surfaces": N_SURFACES,
        "formats": list(FORMATS),
        "surfaces": surfaces,
        "hashes": hashes,
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    hashes["manifest.json"] = sha256_text(MANIFEST_PATH.read_text(encoding="utf-8"))
    return hashes


def forbidden_hits(text: str) -> list[str]:
    return [token for token in FORBIDDEN_BODY if token in text]


if __name__ == "__main__":
    write_corpus()
