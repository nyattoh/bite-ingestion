"""Bounded Recover / re-bite (BITE-11).

Public API for schema'd recovery against index R — never whole-raw resend.
"""

from __future__ import annotations

from bite_ingestion.recovery.audit import AuditLog, AuditRecord
from bite_ingestion.recovery.budget import (
    DEFAULT_BR_TOKENS,
    DEFAULT_J,
    RecoverBudget,
    estimate_tokens,
)
from bite_ingestion.recovery.dedupe import DedupeIndex, fetch_key
from bite_ingestion.recovery.engine import RecoverEngine
from bite_ingestion.recovery.guards import GuardDecision, check_access, check_version_freshness
from bite_ingestion.recovery.source_store import SourceRecord, SourceStatus, SourceStore
from bite_ingestion.recovery.types import (
    ALLOWED_REQUEST_TYPES,
    OutcomeCode,
    RebiteRequest,
    RecoverResult,
    RecoverState,
    RequestType,
    SufficiencyKind,
)

__all__ = [
    "ALLOWED_REQUEST_TYPES",
    "DEFAULT_BR_TOKENS",
    "DEFAULT_J",
    "AuditLog",
    "AuditRecord",
    "DedupeIndex",
    "GuardDecision",
    "OutcomeCode",
    "RebiteRequest",
    "RecoverBudget",
    "RecoverEngine",
    "RecoverResult",
    "RecoverState",
    "RequestType",
    "SourceRecord",
    "SourceStatus",
    "SourceStore",
    "SufficiencyKind",
    "check_access",
    "check_version_freshness",
    "estimate_tokens",
    "fetch_key",
]
