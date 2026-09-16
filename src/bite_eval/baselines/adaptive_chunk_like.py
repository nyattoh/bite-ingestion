"""adaptive_chunk_like — simple offline adaptive-ish chunker stub.

NOT a port of Adaptive Chunking paper code. Boundary heuristics only
(blank lines / headings / braces). Labelled -like for fairness contrast.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from bite_eval.interface import (
    _coerce_float,
    _coerce_int,
    empty_accounting,
    extract_budget,
    extract_query,
    extract_text,
    make_output,
)

DEFAULT_MAX_CHARS = 200  # TBD_CALIBRATE
DEFAULT_TOP_K = 3  # TBD_CALIBRATE

_HEADING = re.compile(r"^(#{1,6}\s|\s*[A-Z][A-Za-z0-9 _-]{2,40}:\s*$)", re.MULTILINE)


def _boundary_split(text: str) -> list[str]:
    """Heuristic boundaries: blank lines, markdown headings, brace blocks."""
    if not text:
        return [""]
    # Prefer double-newline paragraphs
    parts = re.split(r"\n\s*\n+", text)
    refined: list[str] = []
    for p in parts:
        p = p.strip("\n")
        if not p.strip():
            continue
        # Further split on heading-like lines
        # split keeps delimiters oddly; simpler: split lines and regroup
        lines = p.split("\n")
        buf: list[str] = []
        for line in lines:
            if _HEADING.match(line) and buf or line.strip() in {"{", "}", "---", "==="} and buf:
                refined.append("\n".join(buf))
                buf = [line]
            else:
                buf.append(line)
        if buf:
            refined.append("\n".join(buf))
    return refined or [text]


def _pack(segments: list[str], max_chars: int) -> list[dict[str, object]]:
    chunks: list[dict[str, object]] = []
    buf = ""
    start = 0
    pos = 0
    idx = 0
    for seg in segments:
        if buf and len(buf) + 1 + len(seg) > max_chars:
            chunks.append(
                {"chunk_id": f"a{idx}", "start": start, "end": start + len(buf), "text": buf}
            )
            idx += 1
            pos = start + len(buf)
            buf = seg
            start = pos
        else:
            if not buf:
                start = pos
                buf = seg
            else:
                buf = buf + "\n" + seg
        pos = start + len(buf)
    if buf or not chunks:
        chunks.append(
            {"chunk_id": f"a{idx}", "start": start, "end": start + len(buf), "text": buf}
        )
    return chunks


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[A-Za-z0-9_]+", text.lower()) if t}


class AdaptiveChunkLikeBaseline:
    """Offline adaptive-*like* stub — NOT Adaptive Chunking paper reimplementation."""

    baseline_id: str = "adaptive_chunk_like"

    fairness_note: str = (
        "stub-offline; boundary heuristics only; NOT a port of Adaptive Chunking; "
        "fairness contrast only"
    )

    def __init__(self, *, max_chars: int = DEFAULT_MAX_CHARS, top_k: int = DEFAULT_TOP_K) -> None:
        self.max_chars = max_chars
        self.top_k = top_k

    def run(
        self,
        packet: Mapping[str, object],
        context: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        try:
            text = extract_text(packet)
            query = extract_query(packet, context)
            budget = extract_budget(packet, context)
            max_chars = _coerce_int(budget.get("adaptive_max_chars", self.max_chars), self.max_chars)
            top_k = _coerce_int(budget.get("top_k", self.top_k), self.top_k)

            segments = _boundary_split(text)
            chunks = _pack(segments, max_chars)
            qtok = _tokenize(query)
            scored = []
            for c in chunks:
                ct = _tokenize(str(c["text"]))
                score = (len(ct & qtok) / float(len(qtok))) if qtok else 0.0
                scored.append({**c, "score": score})
            scored.sort(key=lambda c: (-_coerce_float(c.get("score"), 0.0), _coerce_int(c.get("start"), 0)))
            selected = sorted(scored[: max(1, top_k)], key=lambda c: _coerce_int(c.get("start"), 0))
            visible = "\n\n".join(str(c["text"]) for c in selected)
            return make_output(
                baseline_id=self.baseline_id,
                status="ok",
                visible_evidence=visible,
                accounting=empty_accounting(),
                tau=[{"op": "ADAPTIVE_CHUNK_LIKE", "n_segments": len(segments)}],
                baseline_trace={
                    "label": "adaptive_chunk_like",
                    "fairness_note": self.fairness_note,
                    "max_chars": max_chars,
                    "n_chunks": len(chunks),
                    "selected_ids": [c["chunk_id"] for c in selected],
                    "NOT_reimplemented": "Adaptive Chunking paper code",
                    "cutpoints": "TBD_CALIBRATE",
                },
            )
        except Exception as exc:  # noqa: BLE001
            return make_output(
                baseline_id=self.baseline_id,
                status="failed",
                visible_evidence="",
                accounting=empty_accounting(),
                reason=f"adaptive_chunk_like failed: {exc}",
            )


__all__ = ["AdaptiveChunkLikeBaseline"]
