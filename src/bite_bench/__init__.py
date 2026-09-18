"""BITEBench: counterfactual texture generation (synthetic, Pivot-to-bench)."""

from .generator import (
    CALIBRATION_SEEDS,
    CANONICAL_CASE_SEEDS,
    CASE_POOL_REVISION,
    EVALUATION_SEEDS,
    TEXTURE_FAMILIES,
    benchmark_split_for_seed,
    canonical_case_ids,
    generate_canonical_pool,
    generate_texture_bundle,
)
from .models import CanonicalCase

__all__ = [
    "CALIBRATION_SEEDS",
    "CANONICAL_CASE_SEEDS",
    "CASE_POOL_REVISION",
    "EVALUATION_SEEDS",
    "TEXTURE_FAMILIES",
    "CanonicalCase",
    "benchmark_split_for_seed",
    "canonical_case_ids",
    "generate_canonical_pool",
    "generate_texture_bundle",
]
