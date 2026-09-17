#!/usr/bin/env python3
"""Offline Phase-1 arm matrix (raw_full / length_pi / rule_pi / rule_pi_rebite).

Never calls paid APIs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bite_eval.phase1_matrix import run_phase1_matrix


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Phase-1 offline arm differentiation")
    ap.add_argument("--n-per-family", type=int, default=1)
    ap.add_argument(
        "--artifact",
        type=Path,
        default=_ROOT / "artifacts" / "phase1" / "arm_differentiation.json",
    )
    args = ap.parse_args(argv)
    doc = run_phase1_matrix(n_per_family=args.n_per_family, artifact_path=args.artifact)
    summary = doc["summary"]
    print(f"wrote {doc.get('artifact_path')} rows={doc['n_rows']}")
    print(f"summary md: {doc.get('summary_path')}")
    print(
        "n_total={n_total} n_measured={n_measured} n_excluded={n_excluded} "
        "n_failed={n_failed} n_no_op={n_no_op}".format(**summary)
    )
    print("rule_pi sequences:", summary["rule_pi_sequences"])
    print("length_pi != rule_pi:", summary["length_vs_rule_diff_families"])
    print(
        "n_pass_through={n_pass_through} n_transformed={n_transformed} "
        "raw_vs_candidate_diff_payload={raw_vs_candidate_diff_payload}".format(**summary)
    )
    # The markdown summary is written to disk, not echoed: it contains
    # non-ASCII characters that crash a cp932 console, and the crash used to
    # skip every self-check below.
    if summary["raw_vs_candidate_diff_payload"] <= 0:
        print("FAIL: every candidate payload matched raw_full", file=sys.stderr)
        return 1
    if not summary["length_vs_rule_diff_families"]:
        print("FAIL: length_pi and rule_pi never differed", file=sys.stderr)
        return 1
    if summary["rule_pi_distinct_sequences"] < 2:
        print("FAIL: rule_pi sequence did not vary across families", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
