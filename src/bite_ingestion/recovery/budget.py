"""Budget ceilings for bounded Recover.

J (max calls) and Br (token ceiling) are TBD_CALIBRATE placeholders.
Synthetic defaults exist for unit tests only — not empirical / not calibrated.
"""

from __future__ import annotations

from dataclasses import dataclass

# TBD_CALIBRATE — synthetic defaults for tests only; do NOT claim calibrated.
DEFAULT_J: int = 3
DEFAULT_BR_TOKENS: int = 512

_TBD_NOTE = (
    "TBD_CALIBRATE: DEFAULT_J / DEFAULT_BR_TOKENS are synthetic placeholders "
    "for tests only; not empirical; not a tokenizer claim."
)


def estimate_tokens(text: str) -> int:
    """Char/4 proxy token estimate (not a provider tokenizer claim).

    Empty text → 0. Non-empty → max(1, ceil(len/4)) via integer (len+3)//4.
    """
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


@dataclass(frozen=True)
class RecoverBudget:
    """Call and token ceilings for a recover session."""

    max_calls: int = DEFAULT_J  # TBD_CALIBRATE
    token_ceiling: int = DEFAULT_BR_TOKENS  # TBD_CALIBRATE
    label: str = "TBD_CALIBRATE"

    def calls_remaining(self, calls_used: int) -> int:
        return max(0, self.max_calls - calls_used)

    def tokens_remaining(self, tokens_used: int) -> int:
        return max(0, self.token_ceiling - tokens_used)

    def would_exceed_calls(self, calls_used: int) -> bool:
        """True when no further call is allowed (calls_used >= J)."""
        return calls_used >= self.max_calls

    def would_exceed_tokens(self, tokens_used: int, add: int) -> bool:
        return tokens_used + add > self.token_ceiling

    def as_dict(self) -> dict[str, object]:
        return {
            "max_calls": self.max_calls,
            "token_ceiling": self.token_ceiling,
            "label": self.label,
            "note": _TBD_NOTE,
        }
