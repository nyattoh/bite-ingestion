from __future__ import annotations

import json
from pathlib import Path

from bite_bench.generator import (
    GENERATOR_VERSION,
    TEXTURE_FAMILIES,
    bundle_fingerprint,
    generate_texture_bundle,
    make_synthetic_case,
)


def test_all_texture_families_emitted() -> None:
    bundle = generate_texture_bundle(seed=0)
    assert set(bundle["textures"]) == set(TEXTURE_FAMILIES)


def test_identity_invariant_across_textures() -> None:
    bundle = generate_texture_bundle(seed=0)
    ident = bundle["identity_sha256"]
    case = make_synthetic_case(0)
    assert ident == case.identity_hash()
    # surfaces must differ from each other (counterfactual textures)
    hashes = {t["surface_sha256"] for t in bundle["textures"].values()}
    assert len(hashes) == len(TEXTURE_FAMILIES)


def test_required_evidence_and_answer_stable() -> None:
    b0 = generate_texture_bundle(seed=0)
    b1 = generate_texture_bundle(seed=0)
    assert b0["canonical"]["answer"] == b1["canonical"]["answer"]
    assert b0["canonical"]["required_evidence_ids"] == b1["canonical"]["required_evidence_ids"]
    assert b0["identity_sha256"] == b1["identity_sha256"]
    assert bundle_fingerprint(b0) == bundle_fingerprint(b1)


def test_length_matched_contrast_pair() -> None:
    bundle = generate_texture_bundle(seed=0, length_match=True)
    pair = bundle["contrast_pair"]
    assert pair["length_matched"] is True
    assert pair["short_dense"]["char_len"] == pair["long_repetitive"]["char_len"]
    assert pair["short_dense"]["surface_sha256"] != pair["long_repetitive"]["surface_sha256"]


def test_route_label_not_in_surface_as_instruction() -> None:
    bundle = generate_texture_bundle(seed=0)
    banned = ["OPTIMAL_ROUTE=", "route_label="]
    for family, payload in bundle["textures"].items():
        text = payload["text"]
        for b in banned:
            assert b not in text, family


def test_frozen_fixture_if_present() -> None:
    path = Path("benchmarks/frozen-v0.1/syn-case-000.json")
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    live = generate_texture_bundle(seed=0)
    assert data["identity_sha256"] == live["identity_sha256"]
    assert data["generator_version"] == GENERATOR_VERSION
