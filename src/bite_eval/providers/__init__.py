"""Provider clients for billed target-model calls (BITE-15 / BITE-15b).

Keys are read from environment only. Never log or persist secret values.
"""

from __future__ import annotations

from bite_eval.providers.zai_client import (
    BILLED_USAGE_LABEL,
    ProviderTimeoutError,
    RateLimitError,
    ZaiClient,
    ZaiClientError,
    key_presence,
    parse_usage,
)

__all__ = [
    "BILLED_USAGE_LABEL",
    "ProviderTimeoutError",
    "RateLimitError",
    "ZaiClient",
    "ZaiClientError",
    "key_presence",
    "parse_usage",
]
