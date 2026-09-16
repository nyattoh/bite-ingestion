#!/usr/bin/env python3
"""BITE-14 offline synthetic pilot CLI.

Synthetic + offline ONLY. No Z.ai / paid API / keys.
T_total uses local_char4_proxy and is labeled as such.
Prefer decision=insufficient_offline over claiming Go on proxy evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from repo root or overlay without install
_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BITE-14 offline synthetic pilot")
    parser.add_argument(
        "--n-per-family",
        type=int,
        default=24,
        help="N_pilot target per synthetic family (lock default 24)",
    )
    parser.add_argument(
        "--families",
        nargs="*",
        default=None,
        help="Subset of synthetic family ids (default: all 8)",
    )
    parser.add_argument(
        "--methods",
        nargs="*",
        default=["raw_full", "synthetic_passthrough"],
        help="Offline method ids",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("artifacts/pilot/bite14_pilot_summary.json"),
        help="Summary JSON output path",
    )
    parser.add_argument(
        "--slim",
        action="store_true",
        help="Omit per-instance results from written JSON",
    )
    args = parser.parse_args(argv)

    from bite_eval.pilot.runner import run_pilot, write_summary

    summary = run_pilot(
        families=args.families,
        n_per_family=args.n_per_family,
        methods=tuple(args.methods),
        paid_api=False,
    )
    to_write = dict(summary)
    if args.slim:
        to_write.pop("results", None)
    path = write_summary(to_write, args.out)

    print(
        json.dumps(
            {
                "decision": summary["decision"],
                "decision_reason": summary["decision_reason"],
                "paid_api": summary["paid_api"],
                "estimate_source": summary["estimate_source"],
                "families_run": summary["families_run"],
                "constraints_ok_rate": summary["constraints_ok_rate"],
                "n_instance_rows": summary["n_instance_rows"],
                "out": str(path),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    # Exit 0 even on insufficient_offline — expected for offline proxy pilot
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
