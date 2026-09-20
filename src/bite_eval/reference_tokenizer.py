"""Pinned GLM-4.5-family payload tokenizer (Phase 4F).

Primary cost unit is reference-tokenizer payload tokens.
Does not use local_char4_proxy. Does not claim hosted glm-4.5-flash
byte-identical equivalence.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Protocol

from bite_bench.phase4f import (
    TOKENIZER_JSON_SHA256,
    TOKENIZER_LIBRARY,
    TOKENIZER_REPO,
    TOKENIZER_REVISION,
)

TOKENIZER_FILENAME = "tokenizer.json"


class PayloadTokenizer(Protocol):
    def payload_tokens(self, text: str) -> int: ...

    def prefix_char_end(self, text: str, budget: int) -> int: ...


class TokenizerError(RuntimeError):
    """Raised when the pinned tokenizer cannot be loaded or hashed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tokenizer_json_path() -> Path:
    env = os.environ.get("BITE_TOKENIZER_JSON")
    if env:
        path = Path(env)
        if not path.is_file():
            raise TokenizerError(f"BITE_TOKENIZER_JSON not a file: {path}")
        return path
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise TokenizerError(
            "tokenizer.json missing; install huggingface_hub or set BITE_TOKENIZER_JSON"
        ) from exc
    downloaded = hf_hub_download(
        repo_id=TOKENIZER_REPO,
        filename=TOKENIZER_FILENAME,
        revision=TOKENIZER_REVISION,
    )
    return Path(downloaded)


class ReferenceTokenizer:
    """Encode payload text with the hashed tokenizer.json file."""

    def __init__(self, tokenizer: Any, *, tokenizer_json_sha256: str) -> None:
        self._tok = tokenizer
        self.tokenizer_json_sha256 = tokenizer_json_sha256

    def _encode(self, text: str) -> tuple[list[int], list[tuple[int, int]]]:
        try:
            encoded = self._tok.encode(text, add_special_tokens=False)
        except TypeError:
            encoded = self._tok.encode(text)
        ids = list(encoded.ids)
        offsets = [(int(start), int(end)) for start, end in encoded.offsets]
        payload: list[tuple[int, tuple[int, int]]] = []
        for token_id, span in zip(ids, offsets, strict=False):
            start, end = span
            if end <= start:
                continue
            payload.append((token_id, (start, end)))
        return [item[0] for item in payload], [item[1] for item in payload]

    def payload_tokens(self, text: str) -> int:
        if not text:
            return 0
        ids, _offsets = self._encode(text)
        return len(ids)

    def prefix_char_end(self, text: str, budget: int) -> int:
        if not text or budget <= 0:
            return 0
        _ids, offsets = self._encode(text)
        if len(offsets) <= budget:
            return len(text)
        return offsets[budget - 1][1]


def load_reference_tokenizer() -> ReferenceTokenizer:
    path = tokenizer_json_path()
    digest = sha256_file(path)
    if digest != TOKENIZER_JSON_SHA256:
        raise TokenizerError(f"tokenizer.json hash changed: {digest} != {TOKENIZER_JSON_SHA256}")
    try:
        from tokenizers import Tokenizer
    except ImportError as exc:
        raise TokenizerError("python tokenizers package required") from exc
    tokenizer = Tokenizer.from_file(str(path))
    return ReferenceTokenizer(tokenizer, tokenizer_json_sha256=digest)


def tokenizer_lock_record(loaded: ReferenceTokenizer | None, error: str | None) -> dict[str, Any]:
    return {
        "repo": TOKENIZER_REPO,
        "revision": TOKENIZER_REVISION,
        "library": TOKENIZER_LIBRARY,
        "tokenizer_json_sha256": TOKENIZER_JSON_SHA256,
        "observed_sha256": None if loaded is None else loaded.tokenizer_json_sha256,
        "hash_verified": loaded is not None and loaded.tokenizer_json_sha256 == TOKENIZER_JSON_SHA256,
        "primary_cost_unit": "reference-tokenizer payload tokens",
        "forbidden_cost_metric": "local_char4_proxy",
        "hosted_glm_45_flash_byte_identical": False,
        "error": error,
    }
