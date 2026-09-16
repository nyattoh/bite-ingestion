"""Dataset / workload adapters (BITE-07). Real downloads are gated on human approval."""

from .base import AdapterManifest, WorkloadAdapter, WorkloadRecord
from .registry import available_adapters, get_adapter
from .synthetic import (
    SyntheticCodeAdapter,
    SyntheticLogsAdapter,
    SyntheticMixedAdapter,
    SyntheticStructuredAdapter,
)

__all__ = [
    "AdapterManifest",
    "SyntheticCodeAdapter",
    "SyntheticLogsAdapter",
    "SyntheticMixedAdapter",
    "SyntheticStructuredAdapter",
    "WorkloadAdapter",
    "WorkloadRecord",
    "available_adapters",
    "get_adapter",
]
