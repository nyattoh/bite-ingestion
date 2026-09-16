from __future__ import annotations

from .base import WorkloadAdapter
from .synthetic import (
    SyntheticCodeAdapter,
    SyntheticLogsAdapter,
    SyntheticMixedAdapter,
    SyntheticStructuredAdapter,
)

_REGISTRY: dict[str, type] = {
    SyntheticLogsAdapter.adapter_id: SyntheticLogsAdapter,
    SyntheticStructuredAdapter.adapter_id: SyntheticStructuredAdapter,
    SyntheticCodeAdapter.adapter_id: SyntheticCodeAdapter,
    SyntheticMixedAdapter.adapter_id: SyntheticMixedAdapter,
}


def available_adapters() -> list[str]:
    return sorted(_REGISTRY)


def get_adapter(adapter_id: str) -> WorkloadAdapter:
    try:
        cls = _REGISTRY[adapter_id]
    except KeyError as exc:
        raise KeyError(f"Unknown adapter_id={adapter_id!r}; real adapters require human approval") from exc
    return cls()


def assert_no_network_adapters_enabled() -> None:
    for adapter_id in available_adapters():
        adapter = get_adapter(adapter_id)
        if adapter.allow_network_fetch():
            raise RuntimeError(f"Network fetch unexpectedly enabled: {adapter_id}")
