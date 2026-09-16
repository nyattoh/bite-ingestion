#!/usr/bin/env python3
"""Offline smoke matrix over synthetic fixtures / baseline ids (BITE-13).

Never calls paid APIs. No Go/Pivot/Stop judgments.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from repo root or dist root
_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bite_eval.harness import EvalHarness  # noqa: E402


DEFAULT_BASELINES = (
    "raw_full",
    "length_pi",
    "fixed_chunk_topk",
    "universal_reduce",
    "rule_pi",
    "rule_pi_rebite",
    "synthetic_passthrough",
)


def _load_fixtures(path: Path) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    if path.is_file():
        out.append((path.stem, json.loads(path.read_text(encoding="utf-8"))))
        return out
    if path.is_dir():
        for p in sorted(path.glob("*.json")):
            out.append((p.stem, json.loads(p.read_text(encoding="utf-8"))))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="BITE-13 offline smoke matrix")
    ap.add_argument(
        "--fixtures",
        type=Path,
        default=_ROOT / "output" / "eval-fixtures",
        help="Synthetic fixture file or directory",
    )
    ap.add_argument(
        "--methods",
        nargs="*",
        default=None,
        help="method/baseline ids (default: small offline set)",
    )
    ap.add_argument(
        "--artifact-root",
        type=Path,
        default=_ROOT,
        help="Root for artifacts/runs/",
    )
    ap.add_argument(
        "--no-persist",
        action="store_true",
        help="Do not write artifact manifests",
    )
    args = ap.parse_args(argv)

    fixtures = _load_fixtures(args.fixtures)
    if not fixtures:
        # Built-in minimal synthetic packet
        fixtures = [
            (
                "builtin_smoke",
                {
                    "document": "Synthetic smoke packet. Fact: ALPHA=42.",
                    "query": "What is ALPHA?",
                    "domain": "prose",
                },
            )
        ]

    methods = list(args.methods) if args.methods else list(DEFAULT_BASELINES)
    harness = EvalHarness(
        artifact_root=args.artifact_root,
        persist=not args.no_persist,
    )

    results: list[dict] = []
    for fix_name, packet in fixtures:
        for mid in methods:
            ctx = {
                "domain": packet.get("domain"),
                "fixture": fix_name,
                "cache_policy": "TBD",
            }
            manifest = harness.run_smoke(mid, packet, ctx)
            results.append(
                {
                    "fixture": fix_name,
                    "method_id": mid,
                    "status": manifest.get("status"),
                    "T_total": manifest.get("T_total"),
                    "run_id": manifest.get("run_id"),
                    "resumed": manifest.get("resumed"),
                    "reason": manifest.get("reason"),
                }
            )
            print(
                f"[smoke] fixture={fix_name} method={mid} "
                f"status={manifest.get('status')} T_total={manifest.get('T_total')} "
                f"run_id={manifest.get('run_id')} resumed={manifest.get('resumed')}"
            )

    summary = {
        "n": len(results),
        "n_failed": sum(1 for r in results if r["status"] not in {"ok", "not_applicable"}),
        "results": results,
        "note": "Smoke only; thresholds TBD; no Go/Pivot/Stop",
    }
    out_path = Path(args.artifact_root) / "artifacts" / "smoke_matrix_summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")
    # Failures retained; exit 0 for smoke unless catastrophic
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
