"""Write SHA256 checksums for managed seeds/artifacts (offline)."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    lines: list[str] = []
    for rel in ("seeds", "artifacts"):
        base = ROOT / rel
        if not base.exists():
            continue
        for path in sorted(p for p in base.rglob("*") if p.is_file() and p.name != ".gitkeep"):
            lines.append(f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}")
    out = ROOT / "artifacts" / "SHA256SUMS.txt"
    text = "\n".join(lines)
    if lines:
        text += "\n"
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out} ({len(lines)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
