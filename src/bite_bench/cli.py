from __future__ import annotations

import argparse
import json
from pathlib import Path

from .generator import bundle_fingerprint, generate_texture_bundle


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Generate synthetic BITEBench texture bundle")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    bundle = generate_texture_bundle(seed=args.seed)
    bundle["bundle_fingerprint"] = bundle_fingerprint(bundle)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
