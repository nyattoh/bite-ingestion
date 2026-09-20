"""BITE-XFER-2 canonical records and renderings.

Independently authored. Does not import XFER-1 / p3p / p3m generators.
Does not run policy or sensors. Dependency layout is structural.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

CORPUS_ID = "BITE-XFER-2"
FORMATS: tuple[str, ...] = (
    "key_value",
    "compact_json",
    "pretty_json",
    "reversed_order_json",
)
N_BASE = 24
N_ADVERSARIAL = 4
N_CANONICAL = N_BASE + N_ADVERSARIAL
N_SURFACES = N_CANONICAL * len(FORMATS)
SIGS: tuple[str, ...] = (
    "none",
    "duplicate",
    "anomaly",
    "explicit_join",
    "duplicate+anomaly",
    "duplicate+join",
    "anomaly+join",
    "duplicate+anomaly+join",
)
DISPS: tuple[str, ...] = ("low", "mid", "high")
DOMAINS: tuple[str, ...] = ("astro", "museum", "scheduler", "firmware")
DUP_KINDS: tuple[str, ...] = ("2way", "3way", "nonadjacent")
ANOM_KINDS: tuple[str, ...] = ("fatal", "panic", "traceback", "inject")
ANOM_VALUES = {
    "fatal": "CCD readout FATAL",
    "panic": "mount drive PANIC stall",
    "traceback": "ingest dump TRACEBACK",
    "inject": "<<<INJECT device map",
}
HOP = {
    "astro": ("src_scope", "star_lock", "src2_scope", "moon_lock"),
    "museum": ("src_accn", "vitrine_lock", "src2_accn", "shelf_lock"),
    "scheduler": ("src_queue", "cron_lock", "src2_queue", "tick_lock"),
    "firmware": ("src_flash", "chip_lock", "src2_flash", "rom_lock"),
}
ADVERSARIAL: tuple[str, ...] = (
    "two_dup_disjoint_join",
    "one_dup_two_joins",
    "dup_overlaps_join",
    "anomaly_in_join",
)
FORBIDDEN_BODY = (
    "texture",
    "REDUCE",
    "UNTANGLE",
    "INTEGRATE",
    "expected_sequence",
    "xfer1-",
    "p3p-",
    "p3m-",
    "p3h-",
    "p3j-",
    "p3k-",
    "p3f-",
    "hop_p3m",
    "padk_",
    "BITE-XFER",
    "bite-xfer",
)

_REPO = Path(__file__).resolve().parents[2]
CORPUS_DIR = _REPO / "corpora" / "bite-xfer-2"
RENDER_DIR = CORPUS_DIR / "rendered"
CASES_PATH = CORPUS_DIR / "cases.json"
ANNOTATIONS_PATH = CORPUS_DIR / "annotations.json"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"


def case_id(n: int) -> str:
    return f"xfer2-q{n:03d}"


def short_of(cid: str) -> str:
    return cid.removeprefix("xfer2-")


def unit_id(cid: str, index: int) -> str:
    return f"{cid}-u{index:02d}"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def _hop(short: str, domain: str, *, second: bool = False) -> tuple[tuple[str, str], tuple[str, str]]:
    src_pfx, lock, src2, lock2 = HOP[domain]
    if second:
        src_pfx, lock = src2, lock2
    return (f"{src_pfx}_{short}", f"{lock}_{short}"), (
        f"dst_{lock}_{short}",
        f"ack_{lock}_{short}",
    )


def _fillers(short: str, domain: str, n: int, start: int = 0) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for i in range(start, start + n):
        key = f"note_{domain}_{short}_{i:02d}"
        extras = (
            f"blob_{domain}_{short}_{i:02d}",
            f"blob_{domain}_{short}_{i:02d} 観測",
            f"naïve blob_{domain}_{short}_{i:02d}",
            f"blob_{domain}_{short}_{i:02d} shift = 1",
            f'blob_{domain}_{short}_{i:02d} said "ok"',
            f"α blob_{domain}_{short}_{i:02d}",
            f"NGC 1300 blob_{domain}_{short}_{i:02d}",
        )
        rows.append((key, extras[i % 7]))
    return rows


def _dup_rows(short: str, kind: str, tag: str) -> list[tuple[str, str]]:
    key, value = f"copy_{tag}_{short}", f"same_{tag}_{short}_row"
    if kind == "3way":
        return [(key, value), (key, value), (key, value)]
    if kind == "nonadjacent":
        return [(key, value), (f"gap_{tag}_{short}", f"void_{tag}_{short}"), (key, value)]
    return [(key, value), (key, value)]


def _join_token(short: str, kind: str, *, alt: bool = False) -> str:
    if kind.startswith("key"):
        stem = f"accn_{short}" if not alt else f"folio_{short}"
        return f"key={stem}"
    stem = f"plate_{short}" if not alt else f"job_{short}"
    return f"id={stem}"


def _join_rows(short: str, kind: str, *, alt: bool = False) -> list[tuple[str, str]]:
    token = _join_token(short, kind, alt=alt)
    prefix = "alt" if alt else "mate"
    count = 3 if kind.endswith("3") else 2
    return [
        (f"{prefix}_{chr(97 + i)}_{short}", f"crate_{chr(97 + i)}_{short} {token}")
        for i in range(count)
    ]


def _spec(n: int) -> dict[str, Any]:
    cid = case_id(n)
    if n > N_BASE:
        role = ADVERSARIAL[n - N_BASE - 1]
        return {
            "case_id": cid,
            "domain": DOMAINS[(n - 1) % 4],
            "signature": role,
            "dispersion": "high",
            "multi_edge": role == "two_dup_disjoint_join",
            "dup": role != "anomaly_in_join",
            "anom": role == "anomaly_in_join",
            "join": True,
            "dup_kind": "2way",
            "anom_kind": "fatal",
            "join_kind": "id2",
            "adversarial": True,
            "role": role,
        }
    i = n - 1
    sig = SIGS[i % 8]
    disp = DISPS[i // 8]
    return {
        "case_id": cid,
        "domain": DOMAINS[i % 4],
        "signature": sig,
        "dispersion": disp,
        "multi_edge": sig == "none" or (sig == "duplicate+anomaly+join" and disp == "high"),
        "dup": "duplicate" in sig,
        "anom": "anomaly" in sig,
        "join": "join" in sig,
        "dup_kind": DUP_KINDS[(i // 8) % 3],
        "anom_kind": ANOM_KINDS[i % 4],
        "join_kind": "id3" if (i // 2) % 2 else ("key2" if i % 2 else "id2"),
        "adversarial": False,
        "role": sig,
    }


def _n_between(disp: str, multi_edge: bool) -> int:
    if disp == "low":
        return 0
    if disp == "mid":
        return 1 if multi_edge else 2
    return 8


def _dup_indices(start: int, kind: str) -> list[int]:
    if kind == "3way":
        return [start, start + 1, start + 2]
    if kind == "nonadjacent":
        return [start, start + 2]
    return [start, start + 1]


def build_case(spec: Mapping[str, Any]) -> tuple[list[tuple[str, str]], dict[str, Any]]:
    cid = str(spec["case_id"])
    short = short_of(cid)
    domain = str(spec["domain"])
    disp = str(spec["dispersion"])
    multi = bool(spec["multi_edge"])
    origin, dest = _hop(short, domain)
    origin2 = dest2 = None
    if multi:
        origin2, dest2 = _hop(short, domain, second=True)
    n_between = _n_between(disp, multi)
    between = _fillers(short, domain, n_between, start=0)
    after: list[tuple[str, str]] = []
    dup_groups: list[list[int]] = []
    anom_indices: list[int] = []
    join_groups: list[list[int]] = []

    def _after_base() -> int:
        hop = 4 if multi else 2
        return hop + n_between

    role = str(spec["role"])
    if spec.get("adversarial"):
        if role == "two_dup_disjoint_join":
            g1 = _dup_rows(short, "2way", "alpha")
            g2 = _dup_rows(short, "nonadjacent", "beta")
            jrows = _join_rows(short, "id2")
            after.extend(g1)
            after.extend(g2)
            after.extend(jrows)
            base = _after_base()
            dup_groups.append([base, base + 1])
            dup_groups.append([base + 2, base + 4])
            join_groups.append([base + 5, base + 6])
        elif role == "one_dup_two_joins":
            drows = _dup_rows(short, "2way", "solo")
            j1 = _join_rows(short, "id2")
            j2 = _join_rows(short, "key3", alt=True)
            after.extend(drows)
            after.extend(j1)
            after.extend(j2)
            base = _after_base()
            dup_groups.append([base, base + 1])
            join_groups.append([base + 2, base + 3])
            join_groups.append([base + 4, base + 5, base + 6])
        elif role == "dup_overlaps_join":
            token = _join_token(short, "id2")
            pair = (f"copy_ov_{short}", f"{token} same_{short}_row")
            after.extend([pair, pair])
            base = _after_base()
            dup_groups.append([base, base + 1])
            join_groups.append([base, base + 1])
        else:
            token = _join_token(short, "id2")
            after.append((f"alert_{short}", f"{token} {ANOM_VALUES['fatal']}"))
            after.append((f"mate_a_{short}", f"crate_a_{short} {token}"))
            base = _after_base()
            anom_indices.append(base)
            join_groups.append([base, base + 1])
        if disp == "low":
            after.extend(_fillers(short, domain, max(0, 4 - len(after)), start=20))
        rows: list[tuple[str, str]] = [origin]
        if origin2:
            rows.append(origin2)
        rows.extend(between)
        rows.append(dest)
        if dest2:
            rows.append(dest2)
        rows.extend(after)
        dest_index = 1 + (1 if origin2 else 0) + n_between
        meta = {
            "origin_index": 0,
            "dest_index": dest_index,
            "dup_groups": dup_groups,
            "anom_indices": anom_indices,
            "join_groups": join_groups,
        }
        return rows, meta

    if spec["dup"]:
        drows = _dup_rows(short, str(spec["dup_kind"]), "main")
        after.extend(drows)
        dup_groups.append(_dup_indices(_after_base(), str(spec["dup_kind"])))
    if spec["anom"]:
        after.append((f"alert_{short}", ANOM_VALUES[str(spec["anom_kind"])]))
        anom_indices.append(_after_base() + len(after) - 1)
    if spec["join"]:
        jrows = _join_rows(short, str(spec["join_kind"]))
        start = _after_base() + len(after)
        after.extend(jrows)
        join_groups.append(list(range(start, start + len(jrows))))
    if disp == "low":
        after.extend(_fillers(short, domain, max(0, 4 - len(after)), start=20))

    rows = [origin]
    if origin2:
        rows.append(origin2)
    rows.extend(between)
    rows.append(dest)
    if dest2:
        rows.append(dest2)
    rows.extend(after)
    dest_index = 1 + (1 if origin2 else 0) + n_between
    meta = {
        "origin_index": 0,
        "dest_index": dest_index,
        "dup_groups": dup_groups,
        "anom_indices": anom_indices,
        "join_groups": join_groups,
    }
    return rows, meta


def render_records(records: Sequence[tuple[str, str]], fmt: str) -> str:
    if fmt == "key_value":
        return "\n".join(f"{key}={value}" for key, value in records) + "\n"
    objs: list[dict[str, str]]
    if fmt == "reversed_order_json":
        objs = [{"v": value, "k": key} for key, value in records]
        return json.dumps(objs, separators=(",", ":"), ensure_ascii=False)
    objs = [{"k": key, "v": value} for key, value in records]
    if fmt == "compact_json":
        return json.dumps(objs, separators=(",", ":"), ensure_ascii=False)
    if fmt == "pretty_json":
        return json.dumps(objs, indent=2, ensure_ascii=False)
    raise ValueError(f"unknown format {fmt}")


def surface_id(cid: str, fmt: str) -> str:
    return f"{cid}-{fmt}"


def all_specs() -> list[dict[str, Any]]:
    return [_spec(n) for n in range(1, N_CANONICAL + 1)]


def annotation_for(
    spec: Mapping[str, Any], meta: Mapping[str, Any]
) -> dict[str, Any]:
    cid = str(spec["case_id"])
    return {
        "required_evidence_ids": [
            unit_id(cid, int(meta["origin_index"])),
            unit_id(cid, int(meta["dest_index"])),
        ],
        "intended_dispersion": spec["dispersion"],
        "duplicate_groups": [
            [unit_id(cid, i) for i in group] for group in meta["dup_groups"]
        ],
        "anomaly_unit_ids": [unit_id(cid, i) for i in meta["anom_indices"]],
        "explicit_join_groups": [
            [unit_id(cid, i) for i in group] for group in meta["join_groups"]
        ],
    }


def rendered_name(cid: str, fmt: str) -> str:
    ext = "txt" if fmt == "key_value" else "json"
    return f"{cid}.{fmt}.{ext}"


def cases_doc() -> dict[str, Any]:
    cases = []
    for spec in all_specs():
        records, _meta = build_case(spec)
        cases.append(
            {
                "case_id": spec["case_id"],
                "domain": spec["domain"],
                "signature": spec["signature"],
                "n_records": len(records),
                "records": [{"k": key, "v": value} for key, value in records],
            }
        )
    return {"corpus": CORPUS_ID, "n_cases": len(cases), "cases": cases}


def annotations_doc() -> dict[str, Any]:
    rows = {}
    for spec in all_specs():
        _records, meta = build_case(spec)
        rows[str(spec["case_id"])] = annotation_for(spec, meta)
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
        records, _meta = build_case(spec)
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
