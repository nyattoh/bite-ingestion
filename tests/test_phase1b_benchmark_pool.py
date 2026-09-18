from __future__ import annotations

import pytest

from bite_bench.generator import (
    CALIBRATION_SEEDS,
    CANONICAL_CASE_SEEDS,
    CASE_POOL_REVISION,
    EVALUATION_SEEDS,
    benchmark_split_for_seed,
    canonical_case_ids,
    generate_canonical_pool,
    generate_texture_bundle,
)


def test_phase1b_pool_has_24_unique_cases() -> None:
    pool = generate_canonical_pool()
    assert len(pool) == 24
    assert len({c.case_id for c in pool}) == 24
    assert tuple(c.case_id for c in pool) == canonical_case_ids()


def test_split_is_locked_and_disjoint() -> None:
    assert CALIBRATION_SEEDS == tuple(range(12))
    assert EVALUATION_SEEDS == tuple(range(12, 24))
    assert set(CALIBRATION_SEEDS).isdisjoint(EVALUATION_SEEDS)
    assert tuple(sorted(CALIBRATION_SEEDS + EVALUATION_SEEDS)) == CANONICAL_CASE_SEEDS


def test_each_split_has_12_cases() -> None:
    calibration = generate_canonical_pool("calibration")
    evaluation = generate_canonical_pool("evaluation")
    assert len(calibration) == 12
    assert len(evaluation) == 12
    assert all(c.meta["split"] == "calibration" for c in calibration)
    assert all(c.meta["split"] == "evaluation" for c in evaluation)


def test_evaluation_ids_are_fixed_and_not_calibration_ids() -> None:
    calibration_ids = set(canonical_case_ids("calibration"))
    evaluation_ids = set(canonical_case_ids("evaluation"))
    assert not (calibration_ids & evaluation_ids)
    assert evaluation_ids == {f"syn-case-{i:03d}" for i in range(12, 24)}


@pytest.mark.parametrize("seed", CANONICAL_CASE_SEEDS)
def test_every_case_has_stable_identity_and_six_textures(seed: int) -> None:
    a = generate_texture_bundle(seed=seed)
    b = generate_texture_bundle(seed=seed)
    assert a["identity_sha256"] == b["identity_sha256"]
    assert a["case_pool_revision"] == CASE_POOL_REVISION
    assert a["benchmark_split"] == benchmark_split_for_seed(seed)
    assert len(a["textures"]) == 6
    assert a["canonical"]["case_id"] == f"syn-case-{seed:03d}"


@pytest.mark.parametrize("seed", CANONICAL_CASE_SEEDS)
def test_answers_are_supported_by_required_evidence(seed: int) -> None:
    bundle = generate_texture_bundle(seed=seed)
    answer = str(bundle["canonical"]["answer"])
    required = set(bundle["canonical"]["required_evidence_ids"])
    facts = {
        str(f["fact_id"]): str(f["value"])
        for f in bundle["canonical"]["facts"]
    }
    assert required
    assert any(facts[eid] == answer for eid in required)


def test_unknown_split_fails_closed() -> None:
    with pytest.raises(ValueError):
        generate_canonical_pool("future")
    with pytest.raises(ValueError):
        canonical_case_ids("future")


def test_out_of_pool_seed_is_unassigned() -> None:
    bundle = generate_texture_bundle(seed=99)
    assert bundle["benchmark_split"] == "unassigned"
