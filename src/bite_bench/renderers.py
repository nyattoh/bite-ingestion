"""Texture renderers for BITEBench.

Leakage rules (enforced by tests/test_texture_invariance.py):

- **No labelled answer.** No ``answer =``, ``# answer:``, ``gold_answer=``,
  ``"answer":`` or "Canonical answer label" field. The answer value may only
  occur inside a required-evidence fact, where the model has to find it.
- **No evidence ids.** ``fact_id`` values are evaluation metadata and never
  appear in the surface; units anchor by char span instead.
- **No required-evidence list.** The surface must not reveal which facts matter.
- **No question.** The question is supplied once by the target-model wrapper.
- **No route / oracle labels.**

Each renderer returns a :class:`RenderedSurface` carrying the text plus a unit
graph anchored to exact char spans, so evidence recall can be derived from the
payload rather than declared.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from bite_ingestion.packet_contract import make_unit

from .models import CanonicalCase, Fact

TEXTURE_FAMILIES: tuple[str, ...] = (
    "prose_narrative",
    "table_csv",
    "nested_json",
    "event_logs",
    "code_config",
    "mixed_payload",
)


@dataclass(frozen=True)
class RenderedSurface:
    """One rendered texture plus its span-anchored unit graph."""

    family: str
    text: str
    units: tuple[dict[str, Any], ...]

    @property
    def unit_ids(self) -> tuple[str, ...]:
        return tuple(str(u["unit_id"]) for u in self.units)


@dataclass(frozen=True)
class _Seg:
    """A document segment; ``fact_id`` marks it as an evidence unit."""

    text: str
    fact_id: str | None = None


def _assemble(
    family: str,
    pieces: Sequence[_Seg | str],
    *,
    source_uri: str,
    renderer_id: str,
) -> RenderedSurface:
    parts: list[str] = []
    units: list[dict[str, Any]] = []
    pos = 0
    filler_n = 0
    seen_facts: dict[str, int] = {}
    for piece in pieces:
        if isinstance(piece, str):
            parts.append(piece)
            pos += len(piece)
            continue
        start = pos
        end = start + len(piece.text)
        parts.append(piece.text)
        pos = end
        if piece.fact_id is None:
            unit_id = f"{family}-filler-{filler_n}"
            filler_n += 1
        else:
            # A fact may be rendered more than once (mixed_payload). The first
            # occurrence owns the canonical id; repeats get a suffixed id but
            # keep ``fact_id`` so evidence resolution still finds them.
            n = seen_facts.get(piece.fact_id, 0)
            seen_facts[piece.fact_id] = n + 1
            unit_id = piece.fact_id if n == 0 else f"{piece.fact_id}#{n}"
        unit = make_unit(
            unit_id=unit_id,
            text=piece.text,
            start=start,
            end=end,
            source_uri=source_uri,
            renderer_id=renderer_id,
        )
        unit["fact_id"] = piece.fact_id
        units.append(unit)
    return RenderedSurface(family=family, text="".join(parts), units=tuple(units))


def _uri(case: CanonicalCase, family: str) -> str:
    return f"bitebench://{case.case_id}/{family}"


def _fact_map(case: CanonicalCase) -> dict[str, Fact]:
    return {f.fact_id: f for f in case.facts}


def render_prose_narrative(
    case: CanonicalCase, *, dense: bool = True, version: str = "v0"
) -> RenderedSurface:
    family = "prose_narrative"
    pieces: list[_Seg | str] = []
    for i, f in enumerate(case.facts):
        if i:
            pieces.append("\n")
        if dense:
            pieces.append(_Seg(f"The {f.key} is {f.value}.", f.fact_id))
        else:
            pieces.append(
                _Seg(
                    f"According to the report, the field named {f.key} holds the value {f.value}.",
                    f.fact_id,
                )
            )
            pieces.append("\n")
            pieces.append(_Seg("(neutral filler line; not part of gold evidence)"))
    return _assemble(
        family, pieces, source_uri=_uri(case, family), renderer_id=f"{family}@{version}"
    )


def render_table_csv(case: CanonicalCase, *, version: str = "v0") -> RenderedSurface:
    family = "table_csv"
    pieces: list[_Seg | str] = [_Seg("key,value"), "\n"]
    for i, f in enumerate(case.facts):
        if i:
            pieces.append("\n")
        pieces.append(_Seg(f"{f.key},{f.value}", f.fact_id))
    pieces.append("\n")
    return _assemble(
        family, pieces, source_uri=_uri(case, family), renderer_id=f"{family}@{version}"
    )


def render_nested_json(case: CanonicalCase, *, version: str = "v0") -> RenderedSurface:
    family = "nested_json"
    pieces: list[_Seg | str] = ['{\n  "graph": {\n    "nodes": [\n']
    for i, f in enumerate(case.facts):
        if i:
            pieces.append(",\n")
        pieces.append(
            _Seg(f'      {{"attrs": {{"key": "{f.key}", "value": "{f.value}"}}}}', f.fact_id)
        )
    pieces.append("\n    ]\n  }\n}")
    return _assemble(
        family, pieces, source_uri=_uri(case, family), renderer_id=f"{family}@{version}"
    )


def render_event_logs(
    case: CanonicalCase, *, repetitive: bool = True, version: str = "v0"
) -> RenderedSurface:
    family = "event_logs"
    pieces: list[_Seg | str] = []
    for i, f in enumerate(case.facts):
        if i:
            pieces.append("\n")
        pieces.append(_Seg(f"INFO key={f.key} value={f.value}", f.fact_id))
        if repetitive:
            pieces.append("\n")
            pieces.append(_Seg("DEBUG heartbeat ok=1"))
            pieces.append("\n")
            pieces.append(_Seg("DEBUG heartbeat ok=1"))
    return _assemble(
        family, pieces, source_uri=_uri(case, family), renderer_id=f"{family}@{version}"
    )


def render_code_config(case: CanonicalCase, *, version: str = "v0") -> RenderedSurface:
    family = "code_config"
    pieces: list[_Seg | str] = [
        _Seg("# synthetic config; not a real service"),
        "\n",
        _Seg("records = {"),
        "\n",
    ]
    for f in case.facts:
        pieces.append(_Seg(f"    {f.key!r}: {f.value!r},", f.fact_id))
        pieces.append("\n")
    pieces.append(_Seg("}"))
    return _assemble(
        family, pieces, source_uri=_uri(case, family), renderer_id=f"{family}@{version}"
    )


def render_mixed_payload(case: CanonicalCase, *, version: str = "v0") -> RenderedSurface:
    """Concatenate three textures, re-anchoring spans in the joined text."""
    family = "mixed_payload"
    prose = render_prose_narrative(case, dense=True, version=version)
    table = render_table_csv(case, version=version)
    logs = render_event_logs(case, repetitive=False, version=version)

    pieces: list[_Seg | str] = []
    for label, surface in (
        ("\n--- PROSE ---\n", prose),
        ("\n--- TABLE ---\n", table),
        ("\n--- LOGS ---\n", logs),
    ):
        pieces.append(label)
        cursor = 0
        for unit in surface.units:
            span = unit["span"]
            if span["start"] > cursor:
                pieces.append(surface.text[cursor : span["start"]])
            # Only the first block keeps the canonical fact id; later repeats
            # get their own ids so unit_ids stay unique within the packet.
            pieces.append(_Seg(unit["text"], unit.get("fact_id")))
            cursor = span["end"]
        if cursor < len(surface.text):
            pieces.append(surface.text[cursor:])
    return _assemble(
        family, pieces, source_uri=_uri(case, family), renderer_id=f"{family}@{version}"
    )


RENDERERS: dict[str, Callable[[CanonicalCase], RenderedSurface]] = {
    "prose_narrative": lambda c: render_prose_narrative(c, dense=True),
    "table_csv": render_table_csv,
    "nested_json": render_nested_json,
    "event_logs": lambda c: render_event_logs(c, repetitive=True),
    "code_config": render_code_config,
    "mixed_payload": render_mixed_payload,
}

#: Substrings that would label the answer as the answer (oracle leakage).
FORBIDDEN_SURFACE_MARKERS: tuple[str, ...] = (
    "answer",
    "gold",
    "required_evidence",
    "route",
    "oracle",
    "question",
    "query",
)


__all__ = [
    "FORBIDDEN_SURFACE_MARKERS",
    "RENDERERS",
    "TEXTURE_FAMILIES",
    "RenderedSurface",
    "render_code_config",
    "render_event_logs",
    "render_mixed_payload",
    "render_nested_json",
    "render_prose_narrative",
    "render_table_csv",
]
