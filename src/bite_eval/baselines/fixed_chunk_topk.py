"""fixed_chunk_topk — fixed-size char chunk + top-k lexical overlap (offline).

Cutpoints are TBD_CALIBRATE placeholders — not empirical paper numbers.
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

# TBD synthetic defaults (not calibrated)
DEFAULT_CHUNK_CHARS = 128  # TBD_CALIBRATE
DEFAULT_OVERLAP = 16  # TBD_CALIBRATE
DEFAULT_TOP_K = 3  # TBD_CALIBRATE


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[A-Za-z0-9_]+", text.lower()) if t}


def _chunk(text: str, size: int, overlap: int) -> list[dict[str, object]]:
    if size <= 0:
        size = DEFAULT_CHUNK_CHARS
    overlap = max(0, min(overlap, size - 1)) if size > 1 else 0
    chunks: list[dict[str, object]] = []
    i = 0
    n = len(text)
    idx = 0
    if n == 0:
        return [{"chunk_id": "c0", "start": 0, "end": 0, "text": ""}]
    while i < n:
        end = min(i + size, n)
        chunks.append(
            {
                "chunk_id": f"c{idx}",
                "start": i,
                "end": end,
                "text": text[i:end],
            }
        )
        idx += 1
        if end >= n:
            break
        i = end - overlap
        if i <= chunks[-1]["start"]:  # type: ignore[operator]
            i = end
    return chunks


def _score(chunk_text: str, query_tokens: set[str]) -> float:
    if not query_tokens:
        return 0.0
    ct = _tokenize(chunk_text)
    if not ct:
        return 0.0
    return len(ct & query_tokens) / float(len(query_tokens))


class FixedChunkTopkBaseline:
    baseline_id: str = "fixed_chunk_topk"

    def __init__(
        self,
        *,
        chunk_chars: int = DEFAULT_CHUNK_CHARS,
        overlap: int = DEFAULT_OVERLAP,
        top_k: int = DEFAULT_TOP_K,
    ) -> None:
        self.chunk_chars = chunk_chars
        self.overlap = overlap
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
            size = _coerce_int(budget.get("chunk_chars", self.chunk_chars), self.chunk_chars)
            overlap = _coerce_int(budget.get("chunk_overlap", self.overlap), self.overlap)
            top_k = _coerce_int(budget.get("top_k", self.top_k), self.top_k)

            chunks = _chunk(text, size, overlap)
            qtok = _tokenize(query)
            scored = [
                {**c, "score": _score(str(c["text"]), qtok)}
                for c in chunks
            ]
            scored.sort(key=lambda c: (-_coerce_float(c.get("score"), 0.0), _coerce_int(c.get("start"), 0)))
            selected = scored[: max(1, top_k)]
            # Stable order by original position for visible evidence
            selected_sorted = sorted(selected, key=lambda c: _coerce_int(c.get("start"), 0))
            visible = "\n".join(str(c["text"]) for c in selected_sorted)
            return make_output(
                baseline_id=self.baseline_id,
                status="ok",
                visible_evidence=visible,
                accounting=empty_accounting(router=0, compressor=0),
                tau=[{"op": "FIXED_CHUNK_TOPK", "n_chunks": len(chunks), "top_k": top_k}],
                baseline_trace={
                    "chunk_chars": size,
                    "overlap": overlap,
                    "top_k": top_k,
                    "n_chunks": len(chunks),
                    "selected_ids": [c["chunk_id"] for c in selected_sorted],
                    "scores": {c["chunk_id"]: c["score"] for c in selected_sorted},
                    "cutpoints": "TBD_CALIBRATE",
                    "method": "char-chunk + lexical-overlap (offline heuristic)",
                },
            )
        except Exception as exc:  # noqa: BLE001
            return make_output(
                baseline_id=self.baseline_id,
                status="failed",
                visible_evidence="",
                accounting=empty_accounting(),
                reason=f"fixed_chunk_topk failed: {exc}",
            )


__all__ = ["DEFAULT_CHUNK_CHARS", "DEFAULT_TOP_K", "FixedChunkTopkBaseline"]
