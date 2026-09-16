"""query_aware_compress_like — irreversible truncate/summarize stub (offline).

Keeps query-overlapping sentences only. Declares irreversible loss.
NOT a LongLLMLingua / CompAct reimplementation.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from bite_eval.interface import (
    _coerce_int,
    empty_accounting,
    extract_budget,
    extract_query,
    extract_text,
    make_output,
)

DEFAULT_MAX_SENTENCES = 5  # TBD_CALIBRATE


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[A-Za-z0-9_]+", text.lower()) if len(t) > 1}


class QueryAwareCompressLikeBaseline:
    """Irreversible query-overlap keep stub — NOT LongLLMLingua."""

    baseline_id: str = "query_aware_compress_like"

    fairness_note: str = (
        "stub-offline irreversible truncate; keep query-overlapping sentences; "
        "NOT LongLLMLingua / CompAct reimplementation; declares irreversible loss"
    )

    def __init__(self, *, max_sentences: int = DEFAULT_MAX_SENTENCES) -> None:
        self.max_sentences = max_sentences

    def run(
        self,
        packet: Mapping[str, object],
        context: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        try:
            text = extract_text(packet)
            query = extract_query(packet, context)
            budget = extract_budget(packet, context)
            max_s = _coerce_int(budget.get("max_sentences", self.max_sentences), self.max_sentences)
            sents = _sentences(text)
            qtok = _tokenize(query)
            ranked: list[tuple[float, int, str]] = []
            for i, s in enumerate(sents):
                st = _tokenize(s)
                score = (len(st & qtok) / float(len(qtok))) if qtok else 0.0
                ranked.append((score, i, s))
            ranked.sort(key=lambda x: (-x[0], x[1]))
            kept = ranked[: max(1, max_s)] if ranked else []
            # Restore original order among kept
            kept_sorted = sorted(kept, key=lambda x: x[1])
            visible = " ".join(s for _, _, s in kept_sorted)
            dropped = max(0, len(sents) - len(kept_sorted))
            # Rough compressor token proxy: chars of dropped / 4 (deterministic offline = still 0 LLM)
            # Contract: pure deterministic offline → compressor tokens 0; note loss in trace
            return make_output(
                baseline_id=self.baseline_id,
                status="ok",
                visible_evidence=visible,
                accounting=empty_accounting(
                    router=0,
                    compressor=0,
                    extra={
                        "irreversible_loss": True,
                        "sentences_in": len(sents),
                        "sentences_kept": len(kept_sorted),
                        "sentences_dropped": dropped,
                    },
                ),
                tau=[
                    {
                        "op": "QUERY_AWARE_COMPRESS_LIKE",
                        "irreversible": True,
                        "kept": len(kept_sorted),
                        "dropped": dropped,
                    }
                ],
                baseline_trace={
                    "label": "query_aware_compress_like",
                    "fairness_note": self.fairness_note,
                    "irreversible_loss": True,
                    "NOT_reimplemented": "LongLLMLingua / CompAct",
                    "max_sentences": max_s,
                    "cutpoints": "TBD_CALIBRATE",
                },
            )
        except Exception as exc:  # noqa: BLE001
            return make_output(
                baseline_id=self.baseline_id,
                status="failed",
                visible_evidence="",
                accounting=empty_accounting(),
                reason=f"query_aware_compress_like failed: {exc}",
            )


__all__ = ["QueryAwareCompressLikeBaseline"]
