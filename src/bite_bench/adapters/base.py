from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class AdapterManifest:
    adapter_id: str
    domain: str
    dataset_name: str
    licence: str
    download_source: str
    version: str
    checksum_sha256: str
    redistributable: bool
    pii_risk: str
    ground_truth_method: str
    human_approval: str
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkloadRecord:
    unit_id: str
    media_type: str
    payload: str
    evidence_ids: tuple[str, ...] = ()
    meta: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class WorkloadAdapter(Protocol):
    """Provider-independent workload adapter. Network fetch is opt-in and blocked by default."""

    manifest: AdapterManifest

    def iter_records(self) -> Iterator[WorkloadRecord]:
        ...

    def allow_network_fetch(self) -> bool:
        """Real adapters must return False until human approval flips a config flag."""
        ...
