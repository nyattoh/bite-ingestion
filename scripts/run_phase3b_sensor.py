#!/usr/bin/env python3
"""Evaluate Phase 3B sensors on development fixtures. No paid API. No holdout."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bite_eval.phase3b_sensor import (
    build_phase3b_doc,
    render_phase3b_md,
    validate_phase3b_doc,
)


def main(argv: list[str] | None = None) -> int:
    del argv
    artifact = _ROOT / "artifacts" / "phase3b" / "sensor-evaluation.json"
    summary = artifact.with_name("sensor-evaluation.md")
    doc = build_phase3b_doc()
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary.write_text(render_phase3b_md(doc) + "\n", encoding="utf-8")
    errs = validate_phase3b_doc(doc)
    print(f"wrote {artifact} verdict={doc['verdict']}")
    print(f"wrote {summary}")
    if errs:
        print("FAIL validation:", file=sys.stderr)
        for err in errs:
            print(f"  {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
