"""Local-only Gemini export reader (D-3=C).

Hard constraints:
- allow_network_fetch is always False
- does not register into EvalHarness / run_matrix
- does not upload, publish, or train
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ALLOW_NETWORK_FETCH = False
EVAL_PIPELINE_AUTO_INGEST = False
DEFAULT_RELATIVE = Path("data/local_only/gemini_export")


class LocalOnlyGeminiExport:
    """Frame for reading a local Gemini export file. Local disk only."""

    def __init__(self, repo_root: str | Path, filename: str | None = None) -> None:
        self.repo_root = Path(repo_root)
        self.directory = self.repo_root / DEFAULT_RELATIVE
        if filename is None:
            matches = sorted(self.directory.glob("*.json"))
            if not matches:
                raise FileNotFoundError(f"no local_only gemini json under {self.directory}")
            self.path = matches[0]
        else:
            self.path = self.directory / filename
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        self.allow_network_fetch = False
        self.eval_pipeline_auto_ingest = False
        self.local_only = True
        self.blocked_from_publish = True

    def read_raw(self) -> dict[str, Any]:
        """Load JSON from local disk only. Never fetches remotely."""
        if self.allow_network_fetch or ALLOW_NETWORK_FETCH:
            raise RuntimeError("network fetch is forbidden for this dataset")
        with self.path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise TypeError("expected top-level object")
        return data

    def meta_only(self) -> dict[str, Any]:
        """Return meta keys only; do not expand message bodies for reporting."""
        raw = self.read_raw()
        meta = raw.get("meta")
        out: dict[str, Any] = {
            "path": str(self.path),
            "allow_network_fetch": False,
            "eval_pipeline_auto_ingest": False,
            "local_only": True,
            "blocked_from_publish": True,
        }
        if isinstance(meta, dict):
            out["meta"] = meta
        messages = raw.get("messages")
        if isinstance(messages, list):
            out["message_count"] = len(messages)
        return out


__all__ = [
    "ALLOW_NETWORK_FETCH",
    "EVAL_PIPELINE_AUTO_INGEST",
    "LocalOnlyGeminiExport",
]
