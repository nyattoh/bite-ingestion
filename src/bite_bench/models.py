from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any


def json_dumps_stable(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class Fact:
    fact_id: str
    key: str
    value: str


@dataclass(frozen=True)
class CanonicalCase:
    """Same-facts core shared across textures. IDs are synthetic (no real dataset names)."""

    case_id: str
    question: str
    answer: str
    required_evidence_ids: tuple[str, ...]
    facts: tuple[Fact, ...]
    task_family: str = "texture_swap"
    meta: dict[str, Any] = field(default_factory=dict)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "question": self.question,
            "answer": self.answer,
            "required_evidence_ids": list(self.required_evidence_ids),
            "facts": [asdict(f) for f in self.facts],
            "task_family": self.task_family,
        }

    def identity_hash(self) -> str:
        blob = json_dumps_stable(self.identity_payload())
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()
