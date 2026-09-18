#!/usr/bin/env python3
"""Measure BITEBench prompt lengths with a pinned GLM-4.5-family tokenizer.

This is a benchmark-construction utility, not a model-quality evaluation.
It deliberately defaults to the calibration split so the holdout is not
opened while length-matching rules are still being designed.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

from bite_bench.generator import (
    CALIBRATION_SEEDS,
    EVALUATION_SEEDS,
    CASE_POOL_REVISION,
    GENERATOR_VERSION,
    generate_texture_bundle,
)

TOKENIZER_REPO = "zai-org/GLM-4.5"
TOKENIZER_REVISION = "cbb2c7cfb52fa128a9660cb1a7a78e017899e115"
TOKENIZER_LIBRARY = "transformers==4.54.0"
TARGET_PROVIDER_MODEL = "glm-4.5-flash"

SYSTEM_PROMPT = "You are a careful extractive QA assistant. Reply with the answer only."
USER_TEMPLATE = (
    "Document:\n{payload}\n\n"
    "Question: {query}\n"
    "Answer with only the final value/string, no explanation."
)


def _seeds(split: str) -> tuple[int, ...]:
    if split == "calibration":
        return CALIBRATION_SEEDS
    if split == "evaluation":
        return EVALUATION_SEEDS
    if split == "all":
        return CALIBRATION_SEEDS + EVALUATION_SEEDS
    raise ValueError(split)


def _sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_tokenizer() -> tuple[Any, str]:
    try:
        from huggingface_hub import hf_hub_download
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise SystemExit(
            "This script requires transformers==4.54.0 and huggingface_hub. "
            "Install them only for the tokenizer-freeze step."
        ) from exc

    tokenizer_file = hf_hub_download(
        repo_id=TOKENIZER_REPO,
        filename="tokenizer.json",
        revision=TOKENIZER_REVISION,
    )
    tokenizer_sha256 = _sha256_file(tokenizer_file)
    tokenizer = AutoTokenizer.from_pretrained(
        TOKENIZER_REPO,
        revision=TOKENIZER_REVISION,
        trust_remote_code=False,
    )
    return tokenizer, tokenizer_sha256


def _prompt_tokens(tokenizer: Any, payload: str, query: str) -> int:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_TEMPLATE.format(payload=payload, query=query)},
    ]
    ids = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    return len(ids)


def build_report(split: str) -> dict[str, Any]:
    tokenizer, tokenizer_sha256 = _load_tokenizer()
    cases: list[dict[str, Any]] = []

    for seed in _seeds(split):
        bundle = generate_texture_bundle(seed=seed, length_match=False)
        query = str(bundle["canonical"]["question"])
        counts: dict[str, int] = {}
        for family, rec in sorted(bundle["textures"].items()):
            counts[family] = _prompt_tokens(tokenizer, str(rec["text"]), query)

        pairs: list[dict[str, Any]] = []
        for left, right in itertools.combinations(sorted(counts), 2):
            a, b = counts[left], counts[right]
            delta = abs(a - b)
            mean = (a + b) / 2.0
            pairs.append(
                {
                    "left": left,
                    "right": right,
                    "left_tokens": a,
                    "right_tokens": b,
                    "abs_delta": delta,
                    "relative_delta": 0.0 if mean == 0 else delta / mean,
                }
            )
        pairs.sort(key=lambda p: (p["abs_delta"], p["relative_delta"], p["left"], p["right"]))
        cases.append(
            {
                "seed": seed,
                "case_id": bundle["canonical"]["case_id"],
                "split": bundle["benchmark_split"],
                "surface_tokens": counts,
                "best_natural_pair": pairs[0],
                "all_pairs": pairs,
            }
        )

    pair_buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in cases:
        for pair in row["all_pairs"]:
            key = (str(pair["left"]), str(pair["right"]))
            pair_buckets.setdefault(key, []).append(pair)
    pair_summary: list[dict[str, Any]] = []
    for (left, right), vals in sorted(pair_buckets.items()):
        rel = [float(v["relative_delta"]) for v in vals]
        abs_d = [int(v["abs_delta"]) for v in vals]
        pair_summary.append(
            {
                "left": left,
                "right": right,
                "n": len(vals),
                "mean_relative_delta": sum(rel) / len(rel),
                "max_relative_delta": max(rel),
                "mean_abs_delta": sum(abs_d) / len(abs_d),
                "max_abs_delta": max(abs_d),
            }
        )
    pair_summary.sort(
        key=lambda p: (
            p["mean_relative_delta"],
            p["max_relative_delta"],
            p["left"],
            p["right"],
        )
    )

    return {
        "schema": "bitebench-token-length-calibration/v0.1",
        "purpose": "token-length construction only; not model-quality evaluation",
        "split": split,
        "case_pool_revision": CASE_POOL_REVISION,
        "generator_version": GENERATOR_VERSION,
        "target_provider_model": TARGET_PROVIDER_MODEL,
        "tokenizer_reference": {
            "repo": TOKENIZER_REPO,
            "revision": TOKENIZER_REVISION,
            "library": TOKENIZER_LIBRARY,
            "tokenizer_json_sha256": tokenizer_sha256,
            "relationship_to_provider_model": (
                "GLM-4.5 family reference tokenizer. Exact hosted "
                "glm-4.5-flash tokenizer equivalence is not asserted here."
            ),
        },
        "prompt_contract": {
            "system": SYSTEM_PROMPT,
            "user_template": USER_TEMPLATE,
            "thinking": "disabled",
            "add_generation_prompt": True,
        },
        "n_cases": len(cases),
        "pair_summary": pair_summary,
        "cases": cases,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--split",
        choices=("calibration", "evaluation", "all"),
        default="calibration",
        help="Defaults to calibration; do not open evaluation before matching rules are frozen.",
    )
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    report = build_report(args.split)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    compact = {
        "split": report["split"],
        "tokenizer_json_sha256": report["tokenizer_reference"]["tokenizer_json_sha256"],
        "best_pairs": [
            {
                "case_id": row["case_id"],
                **row["best_natural_pair"],
            }
            for row in report["cases"]
        ],
        "pair_summary": report["pair_summary"],
    }
    print("PHASE1C_TOKEN_REPORT_BEGIN")
    print(json.dumps(compact, sort_keys=True))
    print("PHASE1C_TOKEN_REPORT_END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
