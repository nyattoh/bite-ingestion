from __future__ import annotations

import json
from pathlib import Path

import pytest

from bite_bench.generator import (
    GENERATOR_VERSION,
    CounterfactualIdentityError,
    assert_counterfactual_identity,
    assert_no_surface_leakage,
    bundle_fingerprint,
    generate_texture_bundle,
    make_synthetic_case,
)
from bite_bench.renderers import RENDERERS, TEXTURE_FAMILIES
from bite_ingestion.packet_contract import (
    assert_evidence_ids_resolve,
    validate_units,
)

SEEDS = (0, 1, 2, 3, 4, 5)


def test_all_texture_families_emitted() -> None:
    bundle = generate_texture_bundle(seed=0)
    assert set(bundle["textures"]) == set(TEXTURE_FAMILIES)


def test_identity_invariant_across_textures() -> None:
    case = make_synthetic_case(0)
    bundle = generate_texture_bundle(case=case)
    ident = bundle["identity_sha256"]
    assert ident == case.identity_hash()
    hashes = {v["surface_sha256"] for v in bundle["textures"].values()}
    assert len(hashes) == len(TEXTURE_FAMILIES)


def test_required_evidence_and_answer_stable() -> None:
    b0 = generate_texture_bundle(seed=0)
    b1 = generate_texture_bundle(seed=0)
    assert b0["canonical"]["answer"] == b1["canonical"]["answer"]
    assert b0["canonical"]["required_evidence_ids"] == b1["canonical"]["required_evidence_ids"]
    assert b0["identity_sha256"] == b1["identity_sha256"]
    assert bundle_fingerprint(b0) == bundle_fingerprint(b1)


# ---------------------------------------------------------------------------
# Gold leakage — all renderers, multiple seeds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("family", TEXTURE_FAMILIES)
def test_no_gold_leakage_in_surface(seed: int, family: str) -> None:
    """The surface must not carry question, evidence ids or a labelled answer.

    The answer *value* may appear inside a required-evidence unit — that is the
    task. It may not appear anywhere else, which is what
    ``assert_no_surface_leakage`` enforces.
    """
    case = make_synthetic_case(seed)
    bundle = generate_texture_bundle(seed=seed)
    text = bundle["textures"][family]["text"]

    assert case.question not in text, f"{family}: question leaked"
    for eid in case.required_evidence_ids:
        assert eid not in text, f"{family}: evidence id {eid} leaked"
    for fact in case.facts:
        assert fact.fact_id not in text, f"{family}: fact id {fact.fact_id} leaked"

    # No answer-labelling field of any shape.
    lowered = text.lower()
    for marker in (
        "answer",
        "gold_answer",
        "canonical answer",
        "required_evidence",
        "optimal_route",
        "route_label",
        "oracle",
    ):
        assert marker not in lowered, f"{family}: oracle marker {marker!r} present"


@pytest.mark.parametrize("seed", SEEDS)
def test_answer_only_inside_required_evidence_spans(seed: int) -> None:
    bundle = generate_texture_bundle(seed=seed)
    # Raises CounterfactualIdentityError on any out-of-evidence occurrence.
    assert_no_surface_leakage(bundle)


def test_leak_guard_actually_fires() -> None:
    """The guard must reject a surface that labels the answer."""
    bundle = generate_texture_bundle(seed=0)
    answer = bundle["canonical"]["answer"]
    bundle["textures"]["prose_narrative"]["text"] += f"\nanswer = {answer}"
    with pytest.raises(CounterfactualIdentityError):
        assert_no_surface_leakage(bundle)


def test_leak_guard_rejects_question_in_surface() -> None:
    bundle = generate_texture_bundle(seed=0)
    bundle["textures"]["table_csv"]["text"] += "\n" + bundle["canonical"]["question"]
    with pytest.raises(CounterfactualIdentityError):
        assert_no_surface_leakage(bundle)


# ---------------------------------------------------------------------------
# Units / spans
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("family", TEXTURE_FAMILIES)
def test_surface_units_resolve_to_spans(seed: int, family: str) -> None:
    case = make_synthetic_case(seed)
    rec = generate_texture_bundle(seed=seed)["textures"][family]
    validate_units(rec["units"], document=rec["text"])
    assert_evidence_ids_resolve(list(case.required_evidence_ids), rec["units"])


@pytest.mark.parametrize("family", TEXTURE_FAMILIES)
def test_every_unit_text_occurs_in_surface(family: str) -> None:
    rec = generate_texture_bundle(seed=0)["textures"][family]
    for unit in rec["units"]:
        assert unit["text"] in rec["text"]


def test_renderers_return_span_anchored_surfaces() -> None:
    case = make_synthetic_case(0)
    for family, render in RENDERERS.items():
        surface = render(case)
        assert surface.family == family
        assert surface.units, f"{family}: no units"
        validate_units(list(surface.units), document=surface.text)


# ---------------------------------------------------------------------------
# Counterfactual pair identity
# ---------------------------------------------------------------------------


def test_counterfactual_identity_holds_for_same_facts_id() -> None:
    bundles = [generate_texture_bundle(seed=s) for s in SEEDS]
    assert_counterfactual_identity(bundles)


def test_counterfactual_identity_detects_mismatch() -> None:
    a = generate_texture_bundle(seed=0)
    b = generate_texture_bundle(seed=0)
    b["canonical"]["answer"] = "DIFFERENT"
    with pytest.raises(CounterfactualIdentityError):
        assert_counterfactual_identity([a, b])


def test_counterfactual_identity_detects_question_mismatch() -> None:
    a = generate_texture_bundle(seed=0)
    b = generate_texture_bundle(seed=0)
    b["canonical"]["question"] = "something else?"
    with pytest.raises(CounterfactualIdentityError):
        assert_counterfactual_identity([a, b])


def test_counterfactual_identity_detects_required_evidence_mismatch() -> None:
    a = generate_texture_bundle(seed=0)
    b = generate_texture_bundle(seed=0)
    b["canonical"]["required_evidence_ids"] = ["syn-e3"]
    with pytest.raises(CounterfactualIdentityError):
        assert_counterfactual_identity([a, b])


# ---------------------------------------------------------------------------
# Length matching honesty
# ---------------------------------------------------------------------------


def test_contrast_pair_is_not_claimed_token_matched() -> None:
    """char length is not token length — the pair must say so.

    Supersedes the earlier assertion ``pair["length_matched"] is True``, which
    labelled a char-padded pair as length matched and would have let it enter a
    token-matched analysis.
    """
    pair = generate_texture_bundle(seed=0)["contrast_pair"]
    assert pair["length_matched"] is False
    assert pair["length_match_basis"] == "char_only_not_token"
    assert pair["char_len_matched"] is True
    assert pair["short_dense"]["char_len"] == pair["long_repetitive"]["char_len"]
    assert pair["short_dense"]["surface_sha256"] != pair["long_repetitive"]["surface_sha256"]


def test_unpadded_pair_reports_char_mismatch() -> None:
    pair = generate_texture_bundle(seed=0, length_match=False)["contrast_pair"]
    assert pair["length_matched"] is False
    assert pair["padding_applied"] is False
    assert pair["char_len_matched"] is False


# ---------------------------------------------------------------------------
# Benchmark versioning
# ---------------------------------------------------------------------------


def test_fingerprint_changes_when_a_renderer_changes() -> None:
    """A renderer edit must move the fingerprint, or versions drift silently."""
    bundle = generate_texture_bundle(seed=0)
    before = bundle_fingerprint(bundle)
    mutated = json.loads(json.dumps(bundle))
    mutated["textures"]["event_logs"]["surface_sha256"] = "0" * 64
    assert bundle_fingerprint(mutated) != before


def test_frozen_fixture_matches_current_generator() -> None:
    path = Path("benchmarks/frozen-v0.2/syn-case-000.json")
    assert path.is_file(), "frozen v0.2 fixture must be regenerated with the renderers"
    data = json.loads(path.read_text(encoding="utf-8"))
    live = generate_texture_bundle(seed=0)
    assert data["identity_sha256"] == live["identity_sha256"]
    assert data["generator_version"] == GENERATOR_VERSION
    assert data["bundle_fingerprint"] == bundle_fingerprint(live)


def test_superseded_v01_fixtures_are_not_current() -> None:
    """frozen-v0.1 leaked gold; it must not match the current generator."""
    path = Path("benchmarks/frozen-v0.1/syn-case-000.json")
    if not path.is_file():
        pytest.skip("v0.1 fixtures removed")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["generator_version"] != GENERATOR_VERSION
