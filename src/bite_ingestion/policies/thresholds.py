"""TBD_CALIBRATE namespace — synthetic defaults for tests only.

These are NOT empirical scientific claims. Calibration is deferred
(BITE-04 / metric-contract). Do not report HIGH/LOW as measured.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TBDCalibrate:
    """Named placeholder thresholds (synthetic / tests only)."""

    HIGH: float = 0.66
    LOW: float = 0.34
    # Length-Π cutpoints (token counts); synthetic fixtures only.
    LENGTH_SHORT_MAX: int = 64
    LENGTH_MEDIUM_MAX: int = 256
    # Char-length fallbacks when n_tokens absent.
    CHAR_SHORT_MAX: int = 256
    CHAR_MEDIUM_MAX: int = 1024


# Module-level singleton used by policies; override in tests via ctor args.
TBD_CALIBRATE = TBDCalibrate()


__all__ = ["TBD_CALIBRATE", "TBDCalibrate"]
