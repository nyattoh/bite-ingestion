"""Development fixtures for Phase 3B. Not Phase 2 evaluation.

Same line multiset; only order changes. Expected inequalities are declared
here before a sensor value is treated as a result.
"""

from __future__ import annotations

import json
from typing import Any

# Identifiers are synthetic and must not be Phase-2 key prefixes.
REF_A = "id_alpha_77"
REF_B = "id_bravo_88"
REF_OUT = "id_result_99"

LINE_SRC = f"origin_bin={REF_A}"
LINE_MID = f"bin_{REF_A}={REF_B}"
LINE_DST = f"bin_{REF_B}={REF_OUT}"
LINE_ONE = f"bin_{REF_A}={REF_OUT}"
NOISE = tuple(f"noise_k{i}=noise_v{i}" for i in range(8))

# Pre-registered order. Tests bind to this, not to a post-hoc number.
EXPECTED_DISTANCE_ORDER = ("near", "medium", "far")

FORBIDDEN_SENSOR_NEEDLES = (
    "required_evidence",
    "gold_answer",
    "gold_route",
    "is_required_evidence",
    "lookup_for_",
    "next_for_",
    "value_for_",
)


def _join(lines: tuple[str, ...] | list[str]) -> str:
    return "\n".join(lines)


def _nested_line(line: str) -> str:
    left, _, right = line.partition("=")
    return json.dumps({"k": left, "v": right}, separators=(",", ":"))


def one_hop_lines() -> tuple[str, ...]:
    return (LINE_SRC, LINE_ONE, *NOISE)


def two_hop_lines() -> tuple[str, ...]:
    return (LINE_SRC, LINE_MID, LINE_DST, *NOISE)


def layout_one_hop(kind: str) -> tuple[str, ...]:
    src, dst, *noise = one_hop_lines()
    if kind == "near":
        return (src, dst, *noise)
    if kind == "medium":
        return (src, noise[0], noise[1], noise[2], dst, *noise[3:])
    if kind == "far":
        return (src, *noise, dst)
    raise ValueError(kind)


def layout_two_hop(kind: str) -> tuple[str, ...]:
    src, mid, dst, *noise = two_hop_lines()
    if kind == "near":
        return (src, mid, dst, *noise)
    if kind == "medium":
        return (src, noise[0], noise[1], mid, noise[2], noise[3], dst, *noise[4:])
    if kind == "far":
        return (src, noise[0], noise[1], noise[2], noise[3], mid, noise[4], noise[5], noise[6], noise[7], dst)
    raise ValueError(kind)


def unrelated_noise_permutation() -> tuple[str, ...]:
    """Keep the reference pair adjacent; only shuffle unused noise lines."""
    src, dst, *noise = one_hop_lines()
    shuffled = (noise[7], noise[1], noise[4], noise[0], noise[6], noise[2], noise[5], noise[3])
    return (src, dst, *shuffled)


def duplicate_noise() -> tuple[str, ...]:
    src, dst, *noise = layout_one_hop("near")
    return (src, dst, *noise, *noise, *noise)


def no_reference_lines() -> tuple[str, ...]:
    return NOISE


def false_positive_lines() -> tuple[str, ...]:
    """Shared generic tokens only. Must not become a reference edge."""
    return (
        "alpha=value",
        "beta=value",
        "gamma=record",
        "delta=status",
        "epsilon=error",
        "zeta=true",
    )


def development_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for kind in EXPECTED_DISTANCE_ORDER:
        lines = layout_one_hop(kind)
        cases.append(
            {
                "case_id": f"one_hop_{kind}",
                "family": "one_hop",
                "kind": kind,
                "surface": "flat",
                "text": _join(lines),
                "query": "What result is stored?",
                "query_with_identifier": f"Where is {REF_A} used?",
            }
        )
        cases.append(
            {
                "case_id": f"one_hop_{kind}_nested",
                "family": "one_hop_nested",
                "kind": kind,
                "surface": "nested",
                "text": _join([_nested_line(x) for x in lines]),
                "query": "What result is stored?",
                "query_with_identifier": f"Where is {REF_A} used?",
            }
        )
        cases.append(
            {
                "case_id": f"two_hop_{kind}",
                "family": "two_hop",
                "kind": kind,
                "surface": "flat",
                "text": _join(layout_two_hop(kind)),
                "query": "What result is stored?",
                "query_with_identifier": f"Where is {REF_A} used?",
            }
        )
    cases.append(
        {
            "case_id": "unrelated_perm",
            "family": "robustness",
            "kind": "unrelated_perm",
            "surface": "flat",
            "text": _join(unrelated_noise_permutation()),
            "query": "What result is stored?",
            "query_with_identifier": f"Where is {REF_A} used?",
        }
    )
    cases.append(
        {
            "case_id": "duplicate_noise",
            "family": "robustness",
            "kind": "duplicate_noise",
            "surface": "flat",
            "text": _join(duplicate_noise()),
            "query": "What result is stored?",
            "query_with_identifier": f"Where is {REF_A} used?",
        }
    )
    cases.append(
        {
            "case_id": "no_reference",
            "family": "negative",
            "kind": "no_reference",
            "surface": "flat",
            "text": _join(no_reference_lines()),
            "query": "What result is stored?",
            "query_with_identifier": f"Where is {REF_A} used?",
        }
    )
    cases.append(
        {
            "case_id": "false_positive",
            "family": "negative",
            "kind": "false_positive",
            "surface": "flat",
            "text": _join(false_positive_lines()),
            "query": "What value is recorded?",
            "query_with_identifier": "What value is recorded?",
        }
    )
    return cases
