from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any

from .models import CanonicalCase, Fact, json_dumps_stable
from .renderers import (
    RENDERERS,
    TEXTURE_FAMILIES,
    RenderedSurface,
    render_event_logs,
    render_prose_narrative,
)

#: Bumped when renderer output changes — frozen fixtures must be regenerated.
GENERATOR_VERSION = "0.2.0-synthetic"

#: The renderer version stays at 0.2 because renderers are unchanged. This
#: revision identifies the expanded canonical-case pool and its fixed split.
CASE_POOL_REVISION = "phase1b-24case-v0.1"
CANONICAL_CASE_SEEDS: tuple[int, ...] = tuple(range(24))
CALIBRATION_SEEDS: tuple[int, ...] = tuple(range(12))
EVALUATION_SEEDS: tuple[int, ...] = tuple(range(12, 24))


def benchmark_split_for_seed(seed: int) -> str:
    """Return the locked Phase-1B split for a canonical seed."""
    if seed in CALIBRATION_SEEDS:
        return "calibration"
    if seed in EVALUATION_SEEDS:
        return "evaluation"
    return "unassigned"


def canonical_case_ids(split: str | None = None) -> tuple[str, ...]:
    """Return canonical case ids for the fixed 24-case Phase-1B pool."""
    if split is None:
        seeds = CANONICAL_CASE_SEEDS
    elif split == "calibration":
        seeds = CALIBRATION_SEEDS
    elif split == "evaluation":
        seeds = EVALUATION_SEEDS
    else:
        raise ValueError(f"unknown benchmark split: {split!r}")
    return tuple(f"syn-case-{seed:03d}" for seed in seeds)


def generate_canonical_pool(split: str | None = None) -> list[CanonicalCase]:
    """Generate the fixed Phase-1B pool without looking at evaluation results."""
    if split is None:
        seeds = CANONICAL_CASE_SEEDS
    elif split == "calibration":
        seeds = CALIBRATION_SEEDS
    elif split == "evaluation":
        seeds = EVALUATION_SEEDS
    else:
        raise ValueError(f"unknown benchmark split: {split!r}")
    return [make_synthetic_case(seed) for seed in seeds]


class CounterfactualIdentityError(ValueError):
    """Raised when a counterfactual pair does not hold its invariants."""


def make_synthetic_case(seed: int = 0) -> CanonicalCase:
    """Build one deterministic synthetic canonical case.

    Seeds 0 and 1 preserve the v0.2 frozen cases byte-for-byte at the surface
    level. Seeds 2..23 expand the Phase-1B canonical pool. Seeds outside the
    locked 24-case pool remain deterministic but are marked unassigned and
    must not be used for confirmatory evaluation.
    """
    if seed < 0:
        raise ValueError("seed must be non-negative")

    split = benchmark_split_for_seed(seed)
    common_meta = {
        "synthetic": True,
        "dataset": "TBD",
        "licence": "TBD",
        "split": split,
        "case_pool_revision": CASE_POOL_REVISION,
    }
    facts: tuple[Fact, ...]
    required: tuple[str, ...]

    # Preserve the two v0.2 frozen identities exactly.
    if seed == 0:
        facts = (
            Fact("syn-e1", "service", "alpha"),
            Fact("syn-e2", "error_code", "E42"),
            Fact("syn-e3", "region", "lab-only"),
        )
        return CanonicalCase(
            case_id="syn-case-000",
            question="Which error_code did service alpha report?",
            answer="E42",
            required_evidence_ids=("syn-e1", "syn-e2"),
            facts=facts,
            task_family="texture_swap",
            meta=common_meta,
        )
    if seed == 1:
        facts = (
            Fact("syn-e1", "item", "widget"),
            Fact("syn-e2", "qty", "3"),
            Fact("syn-e3", "warehouse", "W1"),
        )
        return CanonicalCase(
            case_id="syn-case-001",
            question="What qty is recorded for item widget?",
            answer="3",
            required_evidence_ids=("syn-e1", "syn-e2"),
            facts=facts,
            task_family="texture_swap",
            meta=common_meta,
        )

    case_id = f"syn-case-{seed:03d}"
    ids = tuple(f"syn-{seed:03d}-e{i}" for i in range(1, 5))
    slot = seed % 6
    cycle = seed // 6

    if slot == 0:
        service = f"svc_{seed:03d}"
        answer = f"ERR_{400 + seed}"
        facts = (
            Fact(ids[0], "service", service),
            Fact(ids[1], "error_code", answer),
            Fact(ids[2], "region", f"zone_{cycle}_a"),
            Fact(ids[3], "severity", f"sev_{2 + cycle}"),
        )
        question = f"Which error_code did service {service} report?"
        required = (ids[0], ids[1])
    elif slot == 1:
        item = f"item_{seed:03d}"
        answer = f"QTY_{30 + seed}"
        facts = (
            Fact(ids[0], "item", item),
            Fact(ids[1], "qty", answer),
            Fact(ids[2], "warehouse", f"wh_{cycle}_b"),
            Fact(ids[3], "batch", f"batch_{700 + seed}"),
        )
        question = f"What qty is recorded for item {item}?"
        required = (ids[0], ids[1])
    elif slot == 2:
        app = f"app_{seed:03d}"
        env = f"env_{cycle}_stage"
        answer = f"VER_{2 + cycle}_{seed}"
        facts = (
            Fact(ids[0], "application", app),
            Fact(ids[1], "environment", env),
            Fact(ids[2], "version", answer),
            Fact(ids[3], "owner", f"team_{cycle}_c"),
        )
        question = f"What version is application {app} running in {env}?"
        required = (ids[0], ids[1], ids[2])
    elif slot == 3:
        sensor = f"sensor_{seed:03d}"
        room = f"room_{cycle}_d"
        answer = f"READ_{250 + seed}"
        facts = (
            Fact(ids[0], "sensor", sensor),
            Fact(ids[1], "location", room),
            Fact(ids[2], "reading", answer),
            Fact(ids[3], "unit", "unit_celsius"),
        )
        question = f"What reading is recorded for {sensor} in {room}?"
        required = (ids[0], ids[1], ids[2])
    elif slot == 4:
        order = f"order_{1000 + seed}"
        answer = f"STATUS_PACKED_{seed:03d}"
        facts = (
            Fact(ids[0], "order", order),
            Fact(ids[1], "status", answer),
            Fact(ids[2], "carrier", f"carrier_{cycle}_e"),
            Fact(ids[3], "priority", f"priority_{cycle}_normal"),
        )
        question = f"What status is recorded for order {order}?"
        required = (ids[0], ids[1])
    else:
        account = f"account_{seed:03d}"
        scope = f"scope_project_{cycle}_f"
        answer = f"ROLE_REVIEWER_{seed:03d}"
        facts = (
            Fact(ids[0], "account", account),
            Fact(ids[1], "scope", scope),
            Fact(ids[2], "role", answer),
            Fact(ids[3], "region", f"zone_{cycle}_f"),
        )
        question = f"What role does {account} have in {scope}?"
        required = (ids[0], ids[1], ids[2])

    return CanonicalCase(
        case_id=case_id,
        question=question,
        answer=answer,
        required_evidence_ids=required,
        facts=facts,
        task_family="texture_swap",
        meta=common_meta,
    )


def _surface_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pad_to_length(text: str, target: int) -> str:
    if len(text) >= target:
        return text
    pad = "\n# pad " + ("." * 16)
    out = text
    while len(out) < target:
        need = target - len(out)
        out += pad if need >= len(pad) else pad[:need]
    return out


def _surface_record(surface: RenderedSurface, *, version: str) -> dict[str, Any]:
    return {
        "renderer_id": f"{surface.family}@{version}",
        "text": surface.text,
        "surface_sha256": _surface_hash(surface.text),
        "char_len": len(surface.text),
        "units": [dict(u) for u in surface.units],
        "unit_ids": list(surface.unit_ids),
    }


def assert_counterfactual_identity(
    bundles: Sequence[dict[str, Any]],
) -> None:
    """Machine-check that bundles sharing a ``facts_id`` are true counterfactuals.

    Invariants: same answer, same question, same required-evidence identity,
    same canonical facts. Only the surface texture may differ.
    """
    by_facts: dict[str, list[dict[str, Any]]] = {}
    for bundle in bundles:
        facts_id = str(bundle.get("facts_id") or bundle["canonical"]["case_id"])
        by_facts.setdefault(facts_id, []).append(bundle)

    for facts_id, group in sorted(by_facts.items()):
        if len(group) < 2:
            continue
        ref = group[0]["canonical"]
        for other in group[1:]:
            cur = other["canonical"]
            for field in ("answer", "question", "required_evidence_ids", "facts"):
                if ref[field] != cur[field]:
                    raise CounterfactualIdentityError(
                        f"facts_id={facts_id!r}: {field} differs between "
                        f"{ref['case_id']!r} and {cur['case_id']!r}: "
                        f"{ref[field]!r} != {cur[field]!r}"
                    )


def assert_no_surface_leakage(bundle: dict[str, Any]) -> None:
    """Fail closed when a surface carries oracle-only information.

    The answer *value* may occur inside a required-evidence unit (that is the
    task). It may not occur anywhere else, and it may never be labelled.
    """
    canonical = bundle["canonical"]
    answer = str(canonical["answer"])
    question = str(canonical["question"])
    required = [str(x) for x in canonical["required_evidence_ids"]]

    for family, payload in bundle["textures"].items():
        text = str(payload["text"])
        if question in text:
            raise CounterfactualIdentityError(f"{family}: question leaked into the surface")
        for eid in required:
            if eid in text:
                raise CounterfactualIdentityError(
                    f"{family}: required evidence id {eid!r} leaked into the surface"
                )
        # Every occurrence of the answer must sit inside an evidence unit span.
        # Match on fact_id so repeated renderings (mixed_payload) also count.
        evidence_spans = [
            (int(u["span"]["start"]), int(u["span"]["end"]))
            for u in payload["units"]
            if str(u.get("fact_id") or u["unit_id"]) in required
        ]
        idx = text.find(answer)
        while idx != -1:
            end = idx + len(answer)
            if not any(start <= idx and end <= stop for start, stop in evidence_spans):
                raise CounterfactualIdentityError(
                    f"{family}: answer {answer!r} occurs at char {idx} outside "
                    "any required-evidence unit"
                )
            idx = text.find(answer, idx + 1)


def generate_texture_bundle(
    *,
    case: CanonicalCase | None = None,
    seed: int = 0,
    version: str = GENERATOR_VERSION,
    length_match: bool = True,
) -> dict[str, Any]:
    """Render all texture families for one canonical case (same F/q/y/Ev)."""
    if case is None:
        case = make_synthetic_case(seed)
    identity_hash = case.identity_hash()
    surfaces: dict[str, dict[str, Any]] = {}
    for family in TEXTURE_FAMILIES:
        surfaces[family] = _surface_record(RENDERERS[family](case), version=version)

    # Contrast pair: short-dense prose vs long-repetitive logs.
    dense = render_prose_narrative(case, dense=True, version=version)
    long_rep = render_event_logs(case, repetitive=True, version=version)
    dense_text = dense.text
    long_text = long_rep.text
    target = max(len(dense_text), len(long_text))
    if length_match:
        dense_text = _pad_to_length(dense_text, target)
        long_text = _pad_to_length(long_text, target)
    char_len_matched = len(dense_text) == len(long_text)

    pair = {
        "short_dense": {
            "renderer_id": f"prose_narrative_dense@{version}",
            "text": dense_text,
            "surface_sha256": _surface_hash(dense_text),
            "char_len": len(dense_text),
            "units": [dict(u) for u in dense.units],
        },
        "long_repetitive": {
            "renderer_id": f"event_logs_repetitive@{version}",
            "text": long_text,
            "surface_sha256": _surface_hash(long_text),
            "char_len": len(long_text),
            "units": [dict(u) for u in long_rep.units],
        },
        # char length is NOT token length. Until a tokeniser-based matcher
        # exists, this pair must not enter a token-matched analysis.
        "length_matched": False,
        "length_match_basis": "char_only_not_token",
        "char_len_matched": char_len_matched,
        "padding_applied": bool(length_match),
        "padding_note": (
            "padding inserts '# pad' comment lines, which shift the structural "
            "morphology feature; treat padded pairs as diagnostic only"
        ),
    }

    bundle = {
        "generator_version": version,
        "case_pool_revision": CASE_POOL_REVISION,
        "benchmark_split": str(case.meta.get("split", "unassigned")),
        "seed": seed,
        "identity_sha256": identity_hash,
        "canonical": case.identity_payload(),
        "facts_id": case.case_id,
        "textures": surfaces,
        "contrast_pair": pair,
        "harness_hooks": {
            "full_cost_contract": "T_total",
            "token_meter_event_stub": {
                "kind": "bitebench_render",
                "case_id": case.case_id,
                "textures": list(TEXTURE_FAMILIES),
            },
        },
        "notes": {
            "pivot": "Pivot-to-bench",
            "real_dataset": "TBD",
            "fact_identity_human_lock": "TBD",
        },
    }
    # Fail closed rather than emit a leaking benchmark.
    assert_no_surface_leakage(bundle)
    return bundle


def bundle_fingerprint(bundle: dict[str, Any]) -> str:
    """Fingerprint identity **and** rendered surfaces.

    Surface hashes are included so that changing a renderer changes the
    fingerprint — otherwise a benchmark version could silently drift.
    """
    payload = {
        "generator_version": bundle["generator_version"],
        "seed": bundle["seed"],
        "identity_sha256": bundle["identity_sha256"],
        "families": sorted(bundle["textures"].keys()),
        "surface_sha256": {
            family: bundle["textures"][family]["surface_sha256"]
            for family in sorted(bundle["textures"])
        },
    }
    return hashlib.sha256(json_dumps_stable(payload).encode("utf-8")).hexdigest()
