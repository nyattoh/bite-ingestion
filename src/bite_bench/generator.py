from __future__ import annotations

import hashlib
from typing import Any

from .models import CanonicalCase, Fact, json_dumps_stable
from .renderers import RENDERERS, TEXTURE_FAMILIES, render_event_logs, render_prose_narrative

GENERATOR_VERSION = "0.1.0-synthetic"


def make_synthetic_case(seed: int = 0) -> CanonicalCase:
    """Deterministic synthetic case. No real dataset / licence claims."""
    # seed only selects among a tiny fixed family to keep fixtures frozen.
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
        text = RENDERERS[family](case)
        surfaces[family] = {
            "renderer_id": f"{family}@{version}",
            "text": text,
            "surface_sha256": _surface_hash(text),
            "char_len": len(text),
        }

    # Length-matched pair: short-dense prose vs long-repetitive logs, then pad the shorter.
    dense = render_prose_narrative(case, dense=True)
    long_rep = render_event_logs(case, repetitive=True)
    target = max(len(dense), len(long_rep))
    if length_match:
        dense_m = _pad_to_length(dense, target)
        long_m = _pad_to_length(long_rep, target)
    else:
        dense_m, long_m = dense, long_rep

    pair = {
        "short_dense": {
            "renderer_id": f"prose_narrative_dense@{version}",
            "text": dense_m,
            "surface_sha256": _surface_hash(dense_m),
            "char_len": len(dense_m),
        },
        "long_repetitive": {
            "renderer_id": f"event_logs_repetitive@{version}",
            "text": long_m,
            "surface_sha256": _surface_hash(long_m),
            "char_len": len(long_m),
        },
        "length_matched": length_match and len(dense_m) == len(long_m),
    }

    # Explicit non-leakage: route labels are metadata only, never embedded as answers.
    return {
        "generator_version": version,
        "seed": seed,
        "identity_sha256": identity_hash,
        "canonical": case.identity_payload(),
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


def bundle_fingerprint(bundle: dict[str, Any]) -> str:
    # Fingerprint excludes surface texts' padding variance by using identity + family set.
    payload = {
        "generator_version": bundle["generator_version"],
        "seed": bundle["seed"],
        "identity_sha256": bundle["identity_sha256"],
        "families": sorted(bundle["textures"].keys()),
    }
    return hashlib.sha256(json_dumps_stable(payload).encode("utf-8")).hexdigest()
