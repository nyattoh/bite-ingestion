"""Phase 3C development fixtures. Not Phase 2 evaluation.

Expectations are declared from the v0 sensor contract before measure() results
are treated as findings. Do not add stopwords after seeing these texts.
"""

from __future__ import annotations

import json
from typing import Any

from bite_eval.phase3b_fixtures import LINE_ONE, LINE_SRC, REF_A, REF_OUT

# Same absolute gap as Phase 3B one-hop medium: src at 0, dst at 4.
ABS_EDGE_DISTANCE = 4
ABS_BETWEEN = 3
ABS_TAILS = (("short", 4), ("medium", 20), ("long", 80))
REL_N_LINES = (12, 24, 48)
COST_LINE_COUNTS = (100, 500, 1000, 5000)

# Shared labels that are not closed stopwords. Do not add them to STOPWORDS.
SHARED_ENV = "env_prod_west"
SHARED_SVC = "svc_web_gate"
SHARED_OWNER = "owner_ada_k"
SHARED_CAT = "cat_billing_x"
SHARED_CASE = "case_helix_1"

DIAGNOSTIC_FEATURES = (
    "mean_edge_distance",
    "mean_edge_distance_norm",
    "median_edge_distance",
    "component_span",
    "chain_span",
)

# Contract implications of dependency_dispersion_v0. Not fitted post-hoc.
EXPECTED_ABS_RAW_EQUAL = True
EXPECTED_ABS_NORM_DECREASES = True
EXPECTED_REL_RAW_INCREASES = True
EXPECTED_REL_NORM_EQUAL = True
EXPECTED_REL_NORM = 1.0
EXPECTED_COOCCURRENCE_CREATES_EDGES = True
EXPECTED_SHARED_LABEL_POLLUTES_MEAN = True
EXPECTED_BLANK_INFLATES_RAW = True
EXPECTED_COMPACT_SINGLE_LINE_NO_CROSS_LINE_EDGE = True
EXPECTED_CANNOT_DISTINGUISH_REFERENCE_FROM_COOCCURRENCE = True
EXPECTED_FORMAT_STATUS = {
    "key_value": "supported",
    "oneline_json": "supported",
    "pretty_json": "unsupported",
    "compact_json_one_line": "unsupported",
    "csv": "unsupported",
    "yaml": "unsupported",
    "prose": "unsupported",
    "blank_lines": "supported",
    "wrapped_between": "supported",
    "wrapped_mid_identifier": "unsupported",
}

QUANTITY_MEANING = {
    "mean_edge_distance": "absolute_dependency_separation",
    "mean_edge_distance_norm": "relative_dependency_separation",
}


def _join(lines: list[str] | tuple[str, ...]) -> str:
    return "\n".join(lines)


def _pad(i: int) -> str:
    return f"pad_k{i}=pad_v{i}"


def _json_record(line: str) -> dict[str, str]:
    left, _, right = line.partition("=")
    return {"k": left, "v": right}


def _json_line(line: str) -> str:
    return json.dumps(_json_record(line), separators=(",", ":"))


def abs_scale_lines(tail: int) -> list[str]:
    between = [_pad(i) for i in range(ABS_BETWEEN)]
    extra = [_pad(ABS_BETWEEN + i) for i in range(tail)]
    return [LINE_SRC, *between, LINE_ONE, *extra]


def rel_scale_lines(n_lines: int) -> list[str]:
    if n_lines < 2:
        raise ValueError("n_lines")
    mid = [_pad(i) for i in range(n_lines - 2)]
    return [LINE_SRC, *mid, LINE_ONE]


def cost_lines(n_lines: int) -> list[str]:
    tail = n_lines - (2 + ABS_BETWEEN)
    if tail < 0:
        raise ValueError("n_lines")
    return abs_scale_lines(tail)


def kv_pair() -> str:
    return _join((LINE_SRC, LINE_ONE))


def oneline_json_pair() -> str:
    return _join((_json_line(LINE_SRC), _json_line(LINE_ONE)))


def pretty_json_doc() -> str:
    return json.dumps([_json_record(LINE_SRC), _json_record(LINE_ONE)], indent=2)


def compact_json_one_line() -> str:
    return json.dumps(
        [_json_record(LINE_SRC), _json_record(LINE_ONE)],
        separators=(",", ":"),
    )


def csv_doc() -> str:
    return _join((f"origin_bin,{REF_A}", f"bin_{REF_A},{REF_OUT}"))


def yaml_doc() -> str:
    return _join((f"origin_bin: {REF_A}", f"bin_{REF_A}: {REF_OUT}"))


def prose_doc() -> str:
    return _join(
        (
            f"See identifier {REF_A} in the origin bin.",
            f"The downstream bin_{REF_A} holds {REF_OUT}.",
        )
    )


def blank_lines_doc() -> str:
    return f"{LINE_SRC}\n\n{LINE_ONE}"


def wrapped_between_doc() -> str:
    return _join(
        (
            LINE_SRC,
            "wrap_noise_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa=wrap_val_bbbbbbbbbbbbbbbbbbbbbbbb",
            LINE_ONE,
        )
    )


def wrapped_mid_identifier_doc() -> str:
    return _join((f"origin_bin={REF_A[:6]}", REF_A[6:], LINE_ONE))


def shared_label_doc(atom: str) -> str:
    return _join((f"row_alpha={atom}", f"row_beta={atom}"))


def unrelated_same_identifier_doc() -> str:
    return _join((f"ticket_a={SHARED_CASE}", f"ticket_b={SHARED_CASE}"))


def pollution_doc() -> str:
    """True one-hop edge at distance 1, plus a far shared-label co-occurrence."""
    return _join(
        (
            LINE_SRC,
            LINE_ONE,
            f"label_a={SHARED_ENV}",
            _pad(0),
            _pad(1),
            _pad(2),
            _pad(3),
            _pad(4),
            f"label_b={SHARED_ENV}",
        )
    )


def format_docs() -> dict[str, str]:
    return {
        "key_value": kv_pair(),
        "oneline_json": oneline_json_pair(),
        "pretty_json": pretty_json_doc(),
        "compact_json_one_line": compact_json_one_line(),
        "csv": csv_doc(),
        "yaml": yaml_doc(),
        "prose": prose_doc(),
        "blank_lines": blank_lines_doc(),
        "wrapped_between": wrapped_between_doc(),
        "wrapped_mid_identifier": wrapped_mid_identifier_doc(),
    }


def false_positive_docs() -> dict[str, str]:
    return {
        "shared_env": shared_label_doc(SHARED_ENV),
        "shared_service": shared_label_doc(SHARED_SVC),
        "shared_owner": shared_label_doc(SHARED_OWNER),
        "shared_category": shared_label_doc(SHARED_CAT),
        "unrelated_records_same_identifier": unrelated_same_identifier_doc(),
        "true_edge_plus_shared_label": pollution_doc(),
    }


def predeclared_expectations() -> dict[str, Any]:
    return {
        "abs_edge_distance": ABS_EDGE_DISTANCE,
        "abs_raw_equal": EXPECTED_ABS_RAW_EQUAL,
        "abs_norm_decreases": EXPECTED_ABS_NORM_DECREASES,
        "rel_raw_increases": EXPECTED_REL_RAW_INCREASES,
        "rel_norm_equal": EXPECTED_REL_NORM_EQUAL,
        "rel_norm": EXPECTED_REL_NORM,
        "cooccurrence_creates_edges": EXPECTED_COOCCURRENCE_CREATES_EDGES,
        "shared_label_pollutes_mean": EXPECTED_SHARED_LABEL_POLLUTES_MEAN,
        "blank_inflates_raw": EXPECTED_BLANK_INFLATES_RAW,
        "compact_single_line_no_cross_line_edge": (
            EXPECTED_COMPACT_SINGLE_LINE_NO_CROSS_LINE_EDGE
        ),
        "cannot_distinguish_reference_from_cooccurrence": (
            EXPECTED_CANNOT_DISTINGUISH_REFERENCE_FROM_COOCCURRENCE
        ),
        "format_status": dict(EXPECTED_FORMAT_STATUS),
        "quantity_meaning": dict(QUANTITY_MEANING),
        "routing_feature_choice": "not_decided",
    }
