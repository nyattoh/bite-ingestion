"""contextsniper_like — code evidence gate stub (def/class matching query tokens).

Applicable ONLY when domain=code; else status=not_applicable.
NO full ContextSniper reimplementation; fairness contrast stub only.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from bite_eval.interface import (
    empty_accounting,
    extract_domain,
    extract_query,
    extract_text,
    make_output,
)

APPLICABLE_DOMAINS = frozenset({"code", "code_config", "repository", "source_code"})

_BLOCK_START = re.compile(
    r"^(?P<indent>\s*)(?P<kind>def|class|async\s+def)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)


def _tokenize(q: str) -> set[str]:
    return {t for t in re.findall(r"[A-Za-z0-9_]+", q.lower()) if len(t) > 1}


def _extract_blocks(text: str) -> list[dict[str, object]]:
    lines = text.splitlines(keepends=True)
    # Find starts
    starts: list[tuple[int, str, str, int]] = []  # line_idx, kind, name, indent
    for i, line in enumerate(lines):
        m = re.match(
            r"^(?P<indent>\s*)(?P<kind>async\s+def|def|class)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)",
            line,
        )
        if m:
            starts.append((i, m.group("kind"), m.group("name"), len(m.group("indent"))))
    blocks: list[dict[str, object]] = []
    for j, (si, kind, name, indent) in enumerate(starts):
        end = len(lines)
        if j + 1 < len(starts):
            end = starts[j + 1][0]
        else:
            # extend until dedent to <= indent on non-empty line
            for k in range(si + 1, len(lines)):
                ln = lines[k]
                if not ln.strip():
                    continue
                lead = len(ln) - len(ln.lstrip(" \t"))
                if (
                    lead <= indent
                    and not ln.lstrip().startswith("#")
                    and re.match(r"\s*(async\s+def|def|class)\s+", ln)
                ):
                    end = k
                    break
        body = "".join(lines[si:end])
        blocks.append({"name": name, "kind": kind, "text": body, "start_line": si})
    return blocks


class ContextSniperLikeBaseline:
    """ContextSniper-*like* stub for code domain only — NO full reimplementation."""

    baseline_id: str = "contextsniper_like"

    fairness_note: str = (
        "stub-offline code evidence gate (keep def/class matching query tokens); "
        "domain=code only; NOT a ContextSniper reimplementation; trademark-safe -like"
    )

    def run(
        self,
        packet: Mapping[str, object],
        context: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        domain = extract_domain(packet, context)
        if domain not in APPLICABLE_DOMAINS:
            return make_output(
                baseline_id=self.baseline_id,
                status="not_applicable",
                visible_evidence="",
                accounting=empty_accounting(),
                baseline_trace={
                    "domain": domain or None,
                    "required_domain": "code",
                    "fairness_note": self.fairness_note,
                },
                reason=(
                    f"contextsniper_like not applicable for domain={domain!r}; "
                    "requires domain=code"
                ),
            )
        try:
            text = extract_text(packet)
            query = extract_query(packet, context)
            qtok = _tokenize(query)
            blocks = _extract_blocks(text)
            if not blocks:
                # fallback: keep lines with query tokens
                kept_lines = [
                    ln
                    for ln in text.splitlines()
                    if any(t in ln.lower() for t in qtok)
                ] if qtok else text.splitlines()[:40]
                visible = "\n".join(kept_lines)
                kind = "line_gate_fallback"
                kept_names: list[str] = []
            else:
                matched = []
                for b in blocks:
                    name = str(b["name"]).lower()
                    body_tok = _tokenize(str(b["text"]))
                    hit = (name in qtok) or bool(body_tok & qtok) or (not qtok)
                    if hit:
                        matched.append(b)
                if not matched and qtok:
                    # keep highest overlap
                    scored = sorted(
                        blocks,
                        key=lambda b: -len(_tokenize(str(b["text"])) & qtok),
                    )
                    matched = scored[:1]
                elif not matched:
                    matched = blocks[:3]
                visible = "\n\n".join(str(b["text"]).rstrip() for b in matched)
                kind = "def_class_gate"
                kept_names = [str(b["name"]) for b in matched]
            return make_output(
                baseline_id=self.baseline_id,
                status="ok",
                visible_evidence=visible,
                accounting=empty_accounting(),
                tau=[{"op": "CONTEXTSNIPER_LIKE", "kind": kind, "domain": domain}],
                baseline_trace={
                    "label": "contextsniper_like",
                    "domain": domain,
                    "kind": kind,
                    "kept_names": kept_names,
                    "n_blocks": len(blocks),
                    "fairness_note": self.fairness_note,
                    "NOT_reimplemented": "ContextSniper",
                },
            )
        except Exception as exc:  # noqa: BLE001
            return make_output(
                baseline_id=self.baseline_id,
                status="failed",
                visible_evidence="",
                accounting=empty_accounting(),
                reason=f"contextsniper_like failed: {exc}",
            )


__all__ = ["APPLICABLE_DOMAINS", "ContextSniperLikeBaseline"]
