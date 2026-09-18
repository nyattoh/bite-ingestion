#!/usr/bin/env python3
"""Phase 1D confirmatory offline comparison. Never calls a paid LLM API."""

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

from bite_eval.phase1d_confirmatory import (
    VERDICT_BLOCKED,
    build_phase1d_doc,
    compare_remeasure_to_freeze,
    render_confirmatory_md,
    validate_confirmatory_doc,
    verify_freeze_manifest,
)


def _remeasure_holdout() -> dict[str, Any]:
    """Re-count frozen-pair tokens with the pinned GLM tokenizer. No billed LLM."""
    try:
        from measure_phase1c_token_lengths import (  # type: ignore[import-not-found]
            EXPECTED_TOKENIZER_JSON_SHA256,
            TOKENIZER_REVISION,
            build_report,
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"cannot import tokenizer measurement: {exc}"}
    try:
        import transformers

        report = build_report("evaluation")
        transformers_version = getattr(transformers, "__version__", "unknown")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"holdout remeasure failed: {exc}"}
    freeze = verify_freeze_manifest()
    pairs = [{"case_id": row["case_id"], **row["frozen_pair"]} for row in report["cases"]]
    mismatches = compare_remeasure_to_freeze(freeze["holdout_results"], pairs)
    sha = report["tokenizer_reference"]["tokenizer_json_sha256"]
    if sha != EXPECTED_TOKENIZER_JSON_SHA256:
        mismatches.append(f"tokenizer.json sha drifted: {sha}")
    return {
        "ok": not mismatches,
        "mismatches": mismatches,
        "tokenizer_json_sha256": sha,
        "tokenizer_revision": TOKENIZER_REVISION,
        "transformers_version": transformers_version,
        "expected_transformers_version": "4.54.0",
        "n_cases": len(pairs),
        "pairs": pairs,
    }


def main(argv: list[str] | None = None) -> int:
    del argv
    artifact = _ROOT / "artifacts" / "phase1d" / "confirmatory-offline.json"
    summary = artifact.with_name("confirmatory-offline.md")
    freeze = verify_freeze_manifest()
    if not freeze["ok"]:
        print("PHASE1D_BLOCKED: freeze manifest check failed", file=sys.stderr)
        for m in freeze["mismatches"]:
            print(f"  {m}", file=sys.stderr)
        rem = {"ok": False, "error": "skipped because freeze manifest failed"}
        require = True
    else:
        rem = _remeasure_holdout()
        require = True
        if not rem["ok"]:
            print("PHASE1D_BLOCKED: tokenizer remeasure failed", file=sys.stderr)
            for m in rem.get("mismatches") or []:
                print(f"  {m}", file=sys.stderr)
            if rem.get("error"):
                print(f"  {rem['error']}", file=sys.stderr)

    doc = build_phase1d_doc(
        tokenizer_remeasure=rem,
        require_tokenizer_remeasure=require,
        include_calibration=True,
    )
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    summary.write_text(render_confirmatory_md(doc), encoding="utf-8")
    errs = validate_confirmatory_doc(doc)
    print(f"wrote {artifact} rows={doc['confirmatory']['n_rows']}")
    print(f"wrote {summary}")
    print(f"verdict={doc['verdict']}")
    if doc["blocked_reasons"]:
        print("blocked_reasons:")
        for r in doc["blocked_reasons"]:
            print(f"  {r}")
    if errs:
        print("FAIL validation:", file=sys.stderr)
        for e in errs:
            print(f"  {e}", file=sys.stderr)
        return 1
    return 0 if doc["verdict"] != VERDICT_BLOCKED else 2


if __name__ == "__main__":
    raise SystemExit(main())
