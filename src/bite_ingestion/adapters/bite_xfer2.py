"""Source-exact unitizer for BITE-XFER-2 renderings.

Reuses the XFER-1 span splitter. Does not import XFER-1/p3p/p3m generators.
Fail closed if spans cannot be recovered from the source document.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bite_ingestion.adapters.bite_xfer1 import UnitizerError
from bite_ingestion.adapters.bite_xfer1 import unitize as unitize_xfer1
from bite_ingestion.packet_contract import visible_evidence_from_units

__all__ = ["UnitizerError", "assert_no_annotation_leak", "packet_from_document", "unitize"]


def unitize(
    document: str,
    *,
    case_id: str,
    fmt: str,
    source_uri: str | None = None,
) -> list[dict[str, Any]]:
    return unitize_xfer1(
        document,
        case_id=case_id,
        fmt=fmt,
        source_uri=source_uri,
        renderer_id="bite-xfer-2",
    )


def packet_from_document(
    document: str,
    *,
    case_id: str,
    fmt: str,
) -> dict[str, Any]:
    units = unitize(document, case_id=case_id, fmt=fmt)
    return {
        "packet_id": f"{case_id}-{fmt}",
        "document": document,
        "units": units,
        "visible_evidence": visible_evidence_from_units(units),
        "source_uri": f"bitebench://{case_id}",
    }


def assert_no_annotation_leak(packet: Mapping[str, Any]) -> None:
    forbidden = {
        "texture",
        "expected_sequence",
        "required_evidence_ids",
        "intended_dispersion",
        "duplicate_groups",
        "anomaly_unit_ids",
        "explicit_join_groups",
        "has_exact_duplicate",
        "has_quarantinable_anomaly",
        "has_explicit_join_cluster",
        "gold_unit_ids",
        "operator",
        "route",
        "answer",
    }
    found = sorted(key for key in packet if str(key) in forbidden)
    if found:
        raise UnitizerError(f"annotation leak into packet: {found}")
