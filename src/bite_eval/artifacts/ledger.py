"""ArtifactLedger — write/resume run manifests under artifacts/runs/<run_id>/."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Patterns that look like secrets — never write these into artifacts
# Match credential-like *keys* only — do NOT match token_totals / token_buckets.
_SECRET_KEY_RE = re.compile(
    r"(?i)^(.*_)?(api[_-]?key|secret|password|passwd|access[_-]?token|auth[_-]?token|"
    r"api[_-]?token|refresh[_-]?token|authorization|bearer|private[_-]?key|aws_secret|"
    r"openai_api_key)$"
)
_SECRET_VALUE_RE = re.compile(
    r"(?i)\b(sk-[a-zA-Z0-9]{10,}|Bearer\s+[A-Za-z0-9\-._~+/]+=*|AKIA[0-9A-Z]{16})\b"
)


def sha256_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def redact_secrets(obj: Any, *, hash_prompts: bool = True) -> Any:
    """Deep-copy-ish redact: strip secret-looking keys; hash raw prompt fields."""
    if isinstance(obj, Mapping):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            key = str(k)
            if _SECRET_KEY_RE.search(key):
                out[key] = "[REDACTED]"
                continue
            if hash_prompts and key.lower() in {
                "prompt",
                "raw_prompt",
                "raw_response",
                "response_text",
                "system_prompt",
                "messages",
            }:
                serialized = v if isinstance(v, str) else json.dumps(v, sort_keys=True, default=str)
                out[f"{key}_sha256"] = sha256_hex(serialized)
                out[key] = "[REDACTED_HASHED]"
                continue
            out[key] = redact_secrets(v, hash_prompts=hash_prompts)
        return out
    if isinstance(obj, list):
        return [redact_secrets(x, hash_prompts=hash_prompts) for x in obj]
    if isinstance(obj, str) and _SECRET_VALUE_RE.search(obj):
        return "[REDACTED_VALUE]"
    return obj


_VOLATILE_KEYS = frozenset(
    {
        "run_id",
        "created_at",
        "updated_at",
        "artifact_path",
        "resumed",
        "error_trace",
        # wall / cpu clocks must not break resume-by-content
        "cpu_ms",
        "wall_ms",
        "latency",
    }
)


def _strip_volatile(obj: Any) -> Any:
    if isinstance(obj, Mapping):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if str(k) in _VOLATILE_KEYS:
                continue
            out[str(k)] = _strip_volatile(v)
        return out
    if isinstance(obj, list):
        return [_strip_volatile(x) for x in obj]
    return obj


def content_digest(payload: Mapping[str, object]) -> str:
    """Stable content hash for idempotent resume (excludes clocks / run_id)."""
    # Prefer explicit fingerprint when harness supplies one
    if payload.get("input_fingerprint"):
        return sha256_hex(str(payload["input_fingerprint"]))
    slim = _strip_volatile(dict(payload))
    if isinstance(slim, dict):
        slim.pop("content_digest", None)
    blob = json.dumps(slim, sort_keys=True, ensure_ascii=False, default=str)
    return sha256_hex(blob)


class ArtifactLedger:
    """Persist run manifests; resume by content hash without duplicate run_ids."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.runs_dir = self.root / "artifacts" / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.runs_dir / "_index.json"
        self._index = self._load_index()

    def _load_index(self) -> dict[str, Any]:
        if self._index_path.is_file():
            try:
                return json.loads(self._index_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return {"by_digest": {}, "by_run_id": {}}
        return {"by_digest": {}, "by_run_id": {}}

    def _save_index(self) -> None:
        self._index_path.write_text(
            json.dumps(self._index, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def write_run(
        self,
        manifest: Mapping[str, object],
        *,
        hash_prompts: bool = True,
        force_new: bool = False,
    ) -> dict[str, object]:
        """Write (or resume) a run manifest. Idempotent by content digest.

        Failed runs are retained (status=failed stays in manifest).
        Secrets and raw prompts are redacted/hashed.
        """
        cleaned = redact_secrets(dict(manifest), hash_prompts=hash_prompts)
        if not isinstance(cleaned, dict):
            raise TypeError("manifest must be a mapping")

        digest = content_digest(cleaned)
        cleaned["content_digest"] = digest

        if not force_new and digest in self._index.get("by_digest", {}):
            existing_id = self._index["by_digest"][digest]
            existing_path = self.runs_dir / existing_id / "manifest.json"
            if existing_path.is_file():
                prev = json.loads(existing_path.read_text(encoding="utf-8"))
                prev["resumed"] = True
                prev["updated_at"] = _now_iso()
                existing_path.write_text(
                    json.dumps(prev, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                return prev

        run_id = str(cleaned.get("run_id") or f"run_{digest[:16]}")
        # Avoid colliding run_id with different content
        if run_id in self._index.get("by_run_id", {}):
            prior_digest = self._index["by_run_id"][run_id]
            if prior_digest != digest:
                run_id = f"{run_id}_{digest[:8]}"
                cleaned["run_id"] = run_id

        cleaned.setdefault("run_id", run_id)
        cleaned.setdefault("created_at", _now_iso())
        cleaned["updated_at"] = cleaned["created_at"]
        cleaned["resumed"] = False
        cleaned["artifact_path"] = f"artifacts/runs/{run_id}/manifest.json"

        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / "manifest.json"
        path.write_text(
            json.dumps(cleaned, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        self._index.setdefault("by_digest", {})[digest] = run_id
        self._index.setdefault("by_run_id", {})[run_id] = digest
        self._save_index()
        return cleaned

    def get_run(self, run_id: str) -> dict[str, object] | None:
        path = self.runs_dir / run_id / "manifest.json"
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_runs(self) -> list[str]:
        return sorted(
            p.name
            for p in self.runs_dir.iterdir()
            if p.is_dir() and (p / "manifest.json").is_file()
        )

    def find_by_digest(self, digest: str) -> str | None:
        return self._index.get("by_digest", {}).get(digest)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


__all__ = ["ArtifactLedger", "content_digest", "redact_secrets", "sha256_hex"]
