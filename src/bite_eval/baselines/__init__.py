"""Fair baseline adapter registry (BITE-12)."""

from __future__ import annotations

from collections.abc import Callable

from bite_eval.baselines.adaptive_chunk_like import AdaptiveChunkLikeBaseline
from bite_eval.baselines.contextsniper_like import ContextSniperLikeBaseline
from bite_eval.baselines.fixed_chunk_topk import FixedChunkTopkBaseline
from bite_eval.baselines.fixed_pi import FixedPiBaseline
from bite_eval.baselines.hyve_like import HyveLikeBaseline
from bite_eval.baselines.length_pi import LengthPiBaseline
from bite_eval.baselines.oracle_pi import OraclePiBaseline
from bite_eval.baselines.query_aware_compress_like import QueryAwareCompressLikeBaseline
from bite_eval.baselines.raw_full import RawFullBaseline
from bite_eval.baselines.rule_pi import RulePiBaseline
from bite_eval.baselines.rule_pi_rebite import RulePiRebiteBaseline
from bite_eval.baselines.universal_reduce import UniversalReduceBaseline

# Required ids (BITE-04 §4 items 1–10) + fixed_pi
REQUIRED_BASELINE_IDS: tuple[str, ...] = (
    "raw_full",
    "length_pi",
    "fixed_chunk_topk",
    "adaptive_chunk_like",
    "universal_reduce",
    "query_aware_compress_like",
    "hyve_like",
    "contextsniper_like",
    "rule_pi",
    "rule_pi_rebite",
    "oracle_pi",
    "fixed_pi",
)

BASELINE_IDS = REQUIRED_BASELINE_IDS

_FACTORIES: dict[str, Callable[[], object]] = {
    "raw_full": RawFullBaseline,
    "length_pi": LengthPiBaseline,
    "fixed_chunk_topk": FixedChunkTopkBaseline,
    "adaptive_chunk_like": AdaptiveChunkLikeBaseline,
    "universal_reduce": UniversalReduceBaseline,
    "query_aware_compress_like": QueryAwareCompressLikeBaseline,
    "hyve_like": HyveLikeBaseline,
    "contextsniper_like": ContextSniperLikeBaseline,
    "rule_pi": RulePiBaseline,
    "rule_pi_rebite": RulePiRebiteBaseline,
    "oracle_pi": OraclePiBaseline,
    "fixed_pi": FixedPiBaseline,
}


def get_baseline(baseline_id: str, **kwargs: object) -> object:
    """Instantiate a baseline adapter by id."""
    bid = str(baseline_id).strip()
    if bid not in _FACTORIES:
        raise KeyError(f"unknown baseline_id={bid!r}; known={list(_FACTORIES)}")
    factory = _FACTORIES[bid]
    try:
        return factory(**kwargs)  # type: ignore[arg-type,call-arg]
    except TypeError:
        # Factories that reject unexpected kwargs (no-arg adapters)
        if kwargs:
            return factory()  # type: ignore[call-arg]
        raise


def list_baselines() -> list[str]:
    return list(REQUIRED_BASELINE_IDS)


__all__ = [
    "BASELINE_IDS",
    "REQUIRED_BASELINE_IDS",
    "AdaptiveChunkLikeBaseline",
    "ContextSniperLikeBaseline",
    "FixedChunkTopkBaseline",
    "FixedPiBaseline",
    "HyveLikeBaseline",
    "LengthPiBaseline",
    "OraclePiBaseline",
    "QueryAwareCompressLikeBaseline",
    "RawFullBaseline",
    "RulePiBaseline",
    "RulePiRebiteBaseline",
    "UniversalReduceBaseline",
    "get_baseline",
    "list_baselines",
]
