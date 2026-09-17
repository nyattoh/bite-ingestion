"""Thin Z.ai OpenAI-compatible chat client (BITE-15 / BITE-15b).

- Reads API key ONLY from env ``ZAI_API_KEY`` (presence: PRESENT/ABSENT + optional length).
- Never prints, logs, or writes the key value.
- Returns assistant text + usage dict for billed T_total (DC-3 primary).
- Raises ``RateLimitError`` on HTTP 429 (no retry).
- Raises ``ProviderTimeoutError`` on read/connect timeout after finite retries.
- Redacts Authorization headers from any saved HTTP traces.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

BILLED_USAGE_LABEL = "provider_usage_billed"
DEFAULT_BASE_URL = "https://api.z.ai/api/paas/v4/"
# Documented cheap/flash model on Z.ai paas/v4 enum (docs.z.ai chat-completion).
DEFAULT_MODEL = "glm-4.5-flash"
ENV_KEY = "ZAI_API_KEY"
REDACTED = "***REDACTED***"

# Retry defaults (overridable via configs/pilot_bite15_billed.json)
DEFAULT_TIMEOUT_S = 120.0
DEFAULT_RETRY_MAX = 3  # retries after first attempt → 4 attempts total
DEFAULT_RETRY_BACKOFF_BASE_S = 2.0
DEFAULT_RETRY_BACKOFF_FACTOR = 2.0


class ZaiClientError(Exception):
    """Base error for Z.ai client failures (no secrets in message)."""


class RateLimitError(ZaiClientError):
    """HTTP 429 — caller should stop and write partial artifacts. Do not retry."""


class ProviderTimeoutError(ZaiClientError):
    """Read/connect timeout after exhausting finite retries (or single attempt)."""


def key_presence(*, report_length: bool = False) -> dict[str, Any]:
    """Return PRESENT/ABSENT status without exposing the key value.

    Optional ``length`` is the character length of the env value when present
    and ``report_length`` is True — never the value itself.
    """
    raw = os.environ.get(ENV_KEY)
    if raw is None or raw.strip() == "":
        out: dict[str, Any] = {"status": "ABSENT", "env": ENV_KEY}
        return out
    out = {"status": "PRESENT", "env": ENV_KEY}
    if report_length:
        out["length"] = len(raw)
    return out


def redact_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    """Copy headers with Authorization (and similar) redacted for traces."""
    if not headers:
        return {}
    safe: dict[str, str] = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk in {"authorization", "x-api-key", "api-key"}:
            safe[k] = REDACTED
        else:
            safe[k] = v
    return safe


def parse_usage(payload: Mapping[str, Any] | None) -> dict[str, int | None]:
    """Extract billed usage fields from an OpenAI-compatible response body.

    Maps: prompt_tokens, completion_tokens, total_tokens, cached_tokens.
    Missing keys become None. Values coerced to int when present.
    """
    usage = (payload or {}).get("usage") if payload else None
    if not isinstance(usage, Mapping):
        return {
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "cached_tokens": None,
        }

    def _as_int(key: str) -> int | None:
        val = usage.get(key)
        if val is None:
            # Some providers nest prompt_tokens_details.cached_tokens
            if key == "cached_tokens":
                details = usage.get("prompt_tokens_details")
                if isinstance(details, Mapping) and details.get("cached_tokens") is not None:
                    try:
                        return int(details["cached_tokens"])
                    except (TypeError, ValueError):
                        return None
            return None
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

    return {
        "prompt_tokens": _as_int("prompt_tokens"),
        "completion_tokens": _as_int("completion_tokens"),
        "total_tokens": _as_int("total_tokens"),
        "cached_tokens": _as_int("cached_tokens"),
    }


def _coerce_content_field(content: Any) -> str:
    """Normalize message.content which may be str or list-of-parts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for p in content:
            if isinstance(p, Mapping) and isinstance(p.get("text"), str):
                parts.append(p["text"])
            elif isinstance(p, str):
                parts.append(p)
        return "".join(parts)
    return ""


def _extract_text(payload: Mapping[str, Any]) -> str:
    """Extract assistant text from an OpenAI-compatible chat payload.

    Z.ai GLM thinking mode may leave ``content`` empty while spending
    completion tokens on ``reasoning_content``. Prefer ``content`` when
    non-empty; otherwise fall back to ``reasoning_content`` so pilots do
    not silently score empty answers after a billed call.
    """
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, Mapping):
        return ""
    msg = first.get("message")
    if isinstance(msg, Mapping):
        text = _coerce_content_field(msg.get("content")).strip()
        if text:
            return text
        reasoning = msg.get("reasoning_content")
        if isinstance(reasoning, str) and reasoning.strip():
            return reasoning.strip()
        return ""
    # Legacy text field
    legacy_text = first.get("text")
    return str(legacy_text) if legacy_text is not None else ""


def _is_timeout_exc(exc: BaseException) -> bool:
    """True for TimeoutError / socket.timeout / URLError wrapping a timeout."""
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, TimeoutError):
            return True
        if reason is not None and "timed out" in str(reason).lower():
            return True
        if "timed out" in str(exc).lower():
            return True
    return bool("timed out" in str(exc).lower() and type(exc).__name__ in {"timeout", "TimeoutError", "URLError"})


@dataclass
class ChatResult:
    text: str
    usage: dict[str, int | None]
    model: str
    estimate_source: str = BILLED_USAGE_LABEL
    raw_status: int = 200


class ZaiClient:
    """Minimal chat-completions client for billed pilot target calls."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        retry_max: int = DEFAULT_RETRY_MAX,
        retry_backoff_base_s: float = DEFAULT_RETRY_BACKOFF_BASE_S,
        retry_backoff_factor: float = DEFAULT_RETRY_BACKOFF_FACTOR,
        api_key: str | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        # Prefer explicit api_key only for tests; production reads env.
        # Never store or log beyond this instance attribute for request use.
        if api_key is not None:
            key = api_key
        else:
            key = os.environ.get(ENV_KEY) or ""
        if not key.strip():
            raise ZaiClientError(
                f"KEY_ABSENT: env {ENV_KEY} missing or empty"
            )
        self._api_key = key
        self.base_url = base_url.rstrip("/") + "/"
        self.model = model
        self.timeout_s = float(timeout_s)
        self.retry_max = int(retry_max)
        self.retry_backoff_base_s = float(retry_backoff_base_s)
        self.retry_backoff_factor = float(retry_backoff_factor)
        self._sleep = sleep_fn or time.sleep

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 256,
        http_trace: list[dict[str, Any]] | None = None,
        retry_max: int | None = None,
    ) -> ChatResult:
        """POST /chat/completions; return text + billed usage.

        Timeouts: finite exponential backoff retries
        (``retry_max`` retries → ``retry_max + 1`` attempts). HTTP 429 is
        never retried. If ``http_trace`` is provided, append a redacted
        request/response summary (Authorization redacted; no key material).
        """
        attempts_max = 1 + (self.retry_max if retry_max is None else int(retry_max))
        last_timeout: BaseException | None = None
        for attempt in range(attempts_max):
            try:
                return self._chat_completion_once(
                    messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    http_trace=http_trace,
                )
            except RateLimitError:
                raise
            except ProviderTimeoutError as exc:
                last_timeout = exc
                if attempt + 1 >= attempts_max:
                    raise
                delay = self.retry_backoff_base_s * (
                    self.retry_backoff_factor ** attempt
                )
                self._sleep(delay)
        # Unreachable, but keep mypy/runtime safe
        raise ProviderTimeoutError(
            f"provider read timed out after {attempts_max} attempts"
        ) from last_timeout

    def _chat_completion_once(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 256,
        http_trace: list[dict[str, Any]] | None = None,
    ) -> ChatResult:
        use_model = model or self.model
        url = self.base_url + "chat/completions"
        # Z.ai GLM: default thinking can fill reasoning_content and leave
        # content empty under small max_tokens — disable for pilot target calls.
        body = {
            "model": use_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "thinking": {"type": "disabled"},
        }
        data = json.dumps(body).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept-Language": "en-US,en",
        }
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                status = getattr(resp, "status", 200) or 200
                raw = resp.read().decode("utf-8")
                payload = json.loads(raw) if raw else {}
        except RateLimitError:
            raise
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            err_body = ""
            try:
                err_body = exc.read().decode("utf-8", errors="replace")[:500]
            except Exception:  # noqa: BLE001
                err_body = ""
            if http_trace is not None:
                http_trace.append(
                    {
                        "url": url,
                        "method": "POST",
                        "status": status,
                        "request_headers": redact_headers(headers),
                        "error_body_prefix": err_body,
                    }
                )
            if status == 429:
                raise RateLimitError("HTTP 429 rate limit from provider") from None
            raise ZaiClientError(f"HTTP {status} from provider") from None
        except Exception as exc:  # noqa: BLE001 — classify timeout vs network
            if _is_timeout_exc(exc):
                if http_trace is not None:
                    http_trace.append(
                        {
                            "url": url,
                            "method": "POST",
                            "status": None,
                            "request_headers": redact_headers(headers),
                            "error_type": "TimeoutError",
                        }
                    )
                raise ProviderTimeoutError(
                    "provider read timed out"
                ) from None
            if isinstance(exc, urllib.error.URLError):
                raise ZaiClientError(
                    f"network error contacting provider: {type(exc.reason).__name__ if exc.reason else type(exc).__name__}"
                ) from None
            raise ZaiClientError(
                f"network error contacting provider: {type(exc).__name__}"
            ) from None

        if not isinstance(payload, dict):
            raise ZaiClientError("invalid JSON response from provider")

        if http_trace is not None:
            http_trace.append(
                {
                    "url": url,
                    "method": "POST",
                    "status": status,
                    "request_headers": redact_headers(headers),
                    "usage": parse_usage(payload),
                    "model": use_model,
                }
            )

        usage = parse_usage(payload)
        text = _extract_text(payload)
        return ChatResult(
            text=text,
            usage=usage,
            model=use_model,
            estimate_source=BILLED_USAGE_LABEL,
            raw_status=int(status),
        )


__all__ = [
    "BILLED_USAGE_LABEL",
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "DEFAULT_RETRY_BACKOFF_BASE_S",
    "DEFAULT_RETRY_BACKOFF_FACTOR",
    "DEFAULT_RETRY_MAX",
    "DEFAULT_TIMEOUT_S",
    "ENV_KEY",
    "ChatResult",
    "ProviderTimeoutError",
    "RateLimitError",
    "ZaiClient",
    "ZaiClientError",
    "key_presence",
    "parse_usage",
    "redact_headers",
]
