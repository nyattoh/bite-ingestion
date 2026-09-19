#!/usr/bin/env python3
"""Phase 2B calibration-only prompt-length measurement.

Reuses the Phase 1C tokenizer and prompt contract. Never calls a paid LLM.
Evaluation/holdout is sealed: requesting it fails closed before generation.
"""

from __future__ import annotations

import argparse
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

from bite_bench.phase2a import generate_phase2a_bundle  # noqa: E402
from bite_bench.phase2b import (  # noqa: E402
    VERDICT_BLOCKED,
    build_matrix,
    calibration_cells,
    draft_spec,
    morphology_coverage,
    render_length_control_md,
    require_calibration,
    validate_phase2b_doc,
)


def _tokenizer_guard() -> dict[str, Any]:
    from measure_phase1c_token_lengths import (  # type: ignore[import-not-found]
        EXPECTED_TOKENIZER_JSON_SHA256,
        SYSTEM_PROMPT,
        TOKENIZER_LIBRARY,
        TOKENIZER_REPO,
        TOKENIZER_REVISION,
        USER_TEMPLATE,
        _load_tokenizer,
        _prompt_tokens,
    )

    try:
        import transformers
    except ImportError as exc:
        raise RuntimeError("transformers is required only for Phase 2B measurement") from exc
    version = getattr(transformers, "__version__", "unknown")
    if version != "4.54.0":
        raise RuntimeError(
            f"Phase 1C pin is transformers==4.54.0; this environment has {version}. "
            "Do not retune the tokenizer; install the pinned version."
        )
    tokenizer, sha = _load_tokenizer()
    if sha != EXPECTED_TOKENIZER_JSON_SHA256:
        raise RuntimeError(f"tokenizer.json hash mismatch: {sha}")
    return {
        "repo": TOKENIZER_REPO,
        "revision": TOKENIZER_REVISION,
        "transformers_version": version,
        "library": TOKENIZER_LIBRARY,
        "tokenizer_json_sha256": sha,
        "exact_hosted_model_equivalence_asserted": False,
        "relationship_to_provider_model": (
            "GLM-4.5 family reference tokenizer. Exact hosted "
            "glm-4.5-flash tokenizer equivalence is not asserted here."
        ),
        "prompt_contract": {
            "source": "scripts/measure_phase1c_token_lengths.py",
            "system": SYSTEM_PROMPT,
            "user_template": USER_TEMPLATE,
            "thinking": "disabled",
            "add_generation_prompt": True,
            "note": "same system + user wrapper + generation prompt as Phase 1C",
        },
        "_tokenizer": tokenizer,
        "_prompt_tokens": _prompt_tokens,
    }


def _count_calibration() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    guard = _tokenizer_guard()
    tokenizer = guard.pop("_tokenizer")
    prompt_tokens = guard.pop("_prompt_tokens")
    prompt_contract = guard.pop("prompt_contract")
    cases: list[dict[str, Any]] = []
    for cell in calibration_cells():
        bundle = generate_phase2a_bundle(cell)
        query = str(bundle["canonical"]["question"])
        surfaces: list[dict[str, Any]] = []
        for family, rec in sorted(bundle["surfaces"].items()):
            factors = rec["morphology_factors"]
            surfaces.append(
                {
                    "family": family,
                    "structure": factors["structure"],
                    "dispersion": factors["dispersion"],
                    "redundancy": factors["redundancy"],
                    "char_len": rec["char_len"],
                    "prompt_tokens": int(prompt_tokens(tokenizer, str(rec["text"]), query)),
                    "surface_sha256": rec["surface_sha256"],
                }
            )
        cases.append(
            {
                "case_id": cell.case_id,
                "scale": cell.scale,
                "dependency": cell.dependency,
                "replica": cell.replica,
                "split": cell.split,
                "surfaces": surfaces,
                "morphology_coverage": morphology_coverage(bundle),
            }
        )
    return cases, guard, prompt_contract


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Phase 2B calibration-only length control")
    ap.add_argument("--split", default="calibration")
    ap.add_argument(
        "--artifact-dir",
        type=Path,
        default=_ROOT / "artifacts" / "phase2b",
    )
    args = ap.parse_args(argv)

    artifact_dir: Path = args.artifact_dir
    json_path = artifact_dir / "calibration-token-matrix.json"
    md_path = artifact_dir / "calibration-length-control.md"
    draft_path = _ROOT / "benchmarks" / "spec" / "phase2b-length-control-draft.json"

    try:
        require_calibration(args.split)
    except ValueError as exc:
        print(f"PHASE2B_BLOCKED: {exc}", file=sys.stderr)
        return 2

    try:
        cases, tokenizer_reference, prompt_contract = _count_calibration()
        blocked: list[str] = []
    except Exception as exc:  # noqa: BLE001
        print(f"PHASE2B_BLOCKED: {exc}", file=sys.stderr)
        cases = []
        tokenizer_reference = {"error": str(exc)}
        prompt_contract = None
        blocked = [str(exc)]

    doc = build_matrix(
        counted_cases=cases,
        tokenizer_reference=tokenizer_reference,
        blocked_reasons=blocked,
        prompt_contract=prompt_contract,
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    md_path.write_text(render_length_control_md(doc), encoding="utf-8")
    draft_path.write_text(
        json.dumps(draft_spec(doc), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    errs = validate_phase2b_doc(doc)
    print(f"wrote {json_path} surfaces={doc.get('n_surfaces')}")
    print(f"wrote {md_path}")
    print(f"wrote {draft_path}")
    print(f"verdict={doc['verdict']}")
    if errs:
        print("FAIL validation:", file=sys.stderr)
        for err in errs:
            print(f"  {err}", file=sys.stderr)
        return 1
    return 0 if doc["verdict"] != VERDICT_BLOCKED else 2


if __name__ == "__main__":
    raise SystemExit(main())
