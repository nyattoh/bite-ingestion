#!/usr/bin/env python3
"""Phase 2D confirmatory offline evaluation. Never calls a paid LLM API."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
if str(_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "scripts"))

from bite_eval.phase2d_confirmatory import (
    build_phase2d_doc,
    render_phase2d_md,
    validate_phase2d_doc,
)


def _prompt_counter() -> tuple[Any, dict[str, Any]]:
    import transformers
    from measure_phase1c_token_lengths import (  # type: ignore[import-not-found]
        EXPECTED_TOKENIZER_JSON_SHA256,
        TOKENIZER_LIBRARY,
        TOKENIZER_REPO,
        TOKENIZER_REVISION,
        _load_tokenizer,
        _prompt_tokens,
    )

    version = getattr(transformers, "__version__", "unknown")
    if version != "4.54.0":
        raise RuntimeError(
            f"Phase 1C pin is transformers==4.54.0; this environment has {version}"
        )
    tokenizer, sha = _load_tokenizer()
    if sha != EXPECTED_TOKENIZER_JSON_SHA256:
        raise RuntimeError(f"tokenizer.json hash mismatch: {sha}")
    ref = {
        "repo": TOKENIZER_REPO,
        "revision": TOKENIZER_REVISION,
        "library": TOKENIZER_LIBRARY,
        "transformers_version": version,
        "tokenizer_json_sha256": sha,
        "exact_hosted_model_equivalence_asserted": False,
    }

    def count(text: str, query: str) -> int:
        return int(_prompt_tokens(tokenizer, text, query))

    return count, ref


def main(argv: list[str] | None = None) -> int:
    del argv
    artifact = _ROOT / "artifacts" / "phase2d" / "confirmatory-offline.json"
    summary = artifact.with_name("confirmatory-offline.md")
    try:
        prompt_tokens, tokenizer_reference = _prompt_counter()
    except Exception as exc:  # noqa: BLE001
        print(f"PHASE2D_BLOCKED: tokenizer: {exc}", file=sys.stderr)
        prompt_tokens = None
        tokenizer_reference = {"error": str(exc)}

    doc = build_phase2d_doc(
        prompt_tokens=prompt_tokens,
        tokenizer_reference=tokenizer_reference,
    )

    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    summary.write_text(render_phase2d_md(doc), encoding="utf-8")
    errs = validate_phase2d_doc(doc)
    print(f"wrote {artifact} rows={doc.get('n_rows')} verdict={doc['verdict']}")
    print(f"wrote {summary}")
    print(f"n_signal/n_eligible={doc.get('n_signal')}/{doc.get('n_eligible')}")
    if errs:
        print("FAIL validation:", file=sys.stderr)
        for err in errs:
            print(f"  {err}", file=sys.stderr)
        return 1
    return 0 if doc["verdict"] != "PHASE2D_BLOCKED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
