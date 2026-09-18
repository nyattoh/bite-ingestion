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
from .phase2a import (
    PHASE2A_REVISION,
    Phase2ACell,
    Phase2ASurfaceProfile,
    design_cells as phase2a_design_cells,
    design_manifest as phase2a_design_manifest,
    generate_phase2a_bundle,
    surface_profiles as phase2a_surface_profiles,
)

__all__ = [
    "CALIBRATION_SEEDS",
    "CANONICAL_CASE_SEEDS",
    "CASE_POOL_REVISION",
    "EVALUATION_SEEDS",
    "PHASE2A_REVISION",
    "TEXTURE_FAMILIES",
    "CanonicalCase",
    "Phase2ACell",
    "Phase2ASurfaceProfile",
    "benchmark_split_for_seed",
    "canonical_case_ids",
    "generate_canonical_pool",
    "generate_phase2a_bundle",
    "generate_texture_bundle",
    "phase2a_design_cells",
    "phase2a_design_manifest",
    "phase2a_surface_profiles",
]
