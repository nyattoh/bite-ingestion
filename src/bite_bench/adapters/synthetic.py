from __future__ import annotations

import hashlib
from collections.abc import Iterator

from .base import AdapterManifest, WorkloadRecord


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _SyntheticBase:
    domain: str
    adapter_id: str
    sample_payload: str
    evidence_ids: tuple[str, ...]

    def __init__(self) -> None:
        payload = self.sample_payload
        self.manifest = AdapterManifest(
            adapter_id=self.adapter_id,
            domain=self.domain,
            dataset_name=f"synthetic-{self.domain}",
            licence="CC0-1.0-synthetic-placeholder",
            download_source="local://synthetic",
            version="0.1.0",
            checksum_sha256=_sha(payload),
            redistributable=True,
            pii_risk="none-synthetic",
            ground_truth_method="authored_synthetic_spans",
            human_approval="not_required_for_synthetic",
            notes="Synthetic only. Real dataset fields remain TBD.",
        )

    def allow_network_fetch(self) -> bool:
        return False

    def iter_records(self) -> Iterator[WorkloadRecord]:
        yield WorkloadRecord(
            unit_id=f"{self.adapter_id}-u0",
            media_type="text/plain",
            payload=self.sample_payload,
            evidence_ids=self.evidence_ids,
            meta={"synthetic": True, "real_dataset": "TBD"},
        )


class SyntheticLogsAdapter(_SyntheticBase):
    adapter_id = "synthetic_observability_logs"
    domain = "observability_logs"
    evidence_ids = ("syn-log-e1",)
    sample_payload = (
        "INFO service=alpha error_code=E42 region=lab-only\n"
        "DEBUG heartbeat service=alpha ok=1\n"
    )


class SyntheticStructuredAdapter(_SyntheticBase):
    adapter_id = "synthetic_structured_machine_data"
    domain = "tabular_nested_machine_data"
    evidence_ids = ("syn-tab-e1",)
    sample_payload = "fact_id,key,value\nsyn-e1,item,widget\nsyn-e2,qty,3\n"


class SyntheticCodeAdapter(_SyntheticBase):
    adapter_id = "synthetic_repository_code"
    domain = "repository_code"
    evidence_ids = ("syn-code-e1",)
    sample_payload = (
        "# synthetic module; not a real repository\n"
        "CONFIG = {'service': 'alpha', 'error_code': 'E42'}\n"
    )


class SyntheticMixedAdapter(_SyntheticBase):
    adapter_id = "synthetic_mixed_agent_tools"
    domain = "mixed_agent_tool_outputs"
    evidence_ids = ("syn-mix-e1",)
    sample_payload = (
        "TOOL tool=search status=ok\n"
        "OBS note=synthetic-only dataset=TBD\n"
        "RESULT answer_candidate=E42\n"
    )
