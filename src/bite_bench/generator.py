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


class CounterfactualIdentityError(ValueError):
    """Raised when a counterfactual pair does not hold its invariants."""


def make_synthetic_case(seed: int = 0) -> CanonicalCase:
    """Deterministic synthetic case. No real dataset / licence claims.

    NOTE: only two canonical cases exist (``seed % 2``). Scaling the case pool
    is future work and is recorded as an open item in the handover.
    """
    variant = seed % 2
    if variant == 0:
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
            meta={"synthetic": True, "dataset": "TBD", "licence": "TBD"},
        )
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
        meta={"synthetic": True, "dataset": "TBD", "licence": "TBD"},
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
