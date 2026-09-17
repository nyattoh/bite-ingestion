from __future__ import annotations

import json
import math
import re
import time
import tracemalloc
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

FEATURE_KEYS = ("b", "r", "s", "k", "a", "l", "p", "u")


def _clamp01(x: float) -> float:
    if math.isnan(x):
        return 0.0
    return max(0.0, min(1.0, float(x)))


@dataclass
class ProfileReport:
    features: dict[str, float]
    evidence: dict[str, str]
    uncertain: bool
    fail_closed: bool
    cpu_ms: float
    peak_memory_kb: float
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class DeterministicMorphologyProfiler:
    """Transparent, non-LLM morphology profiler.

    Does not consult ground-truth routes or target answers.
    File type alone does not force a route; features remain continuous.
    """

    name = "deterministic_v0"

    def profile(self, source_unit: Mapping[str, object]) -> Mapping[str, float]:
        return self.profile_report(source_unit).features

    def profile_report(self, source_unit: Mapping[str, object]) -> ProfileReport:
        t0 = time.perf_counter()
        tracemalloc.start()
        try:
            return self._profile_impl(source_unit, t0)
        finally:
            tracemalloc.stop()

    def _profile_impl(self, source_unit: Mapping[str, object], t0: float) -> ProfileReport:
        evidence: dict[str, str] = {}
        notes: list[str] = []
        fail_closed = False
        uncertain = False

        if not isinstance(source_unit, Mapping):
            fail_closed = True
            uncertain = True
            feats = {k: 0.0 for k in FEATURE_KEYS}
            feats["u"] = 1.0
            evidence["error"] = "source_unit_not_mapping"
            cpu_ms = (time.perf_counter() - t0) * 1000.0
            _, peak = tracemalloc.get_traced_memory()
            return ProfileReport(feats, evidence, True, True, cpu_ms, peak / 1024.0, notes)

        payload = source_unit.get("payload", source_unit.get("text", ""))
        query = source_unit.get("query") or source_unit.get("q") or ""
        if payload is None:
            payload = ""
        if not isinstance(payload, str):
            try:
                payload = json.dumps(payload, ensure_ascii=False)
                notes.append("non_str_payload_json_serialized")
            except (TypeError, ValueError, OverflowError):
                payload = str(payload)
                notes.append("non_str_payload_str_fallback")
                uncertain = True

        if "\x00" in payload:
            fail_closed = True
            uncertain = True
            evidence["nul_byte"] = "present"
            notes.append("fail_closed_nul")

        text = payload
        n = max(len(text), 1)
        lines = text.splitlines() or [""]
        line_count = len(lines)

        # b: boundary clarity — newline density + schema separators
        newline_density = (line_count - 1) / n
        sep_hits = len(re.findall(r"[,|;{}()=]", text)) / n
        b = _clamp01(0.35 * min(1.0, newline_density * 40.0) + 0.65 * min(1.0, sep_hits * 20.0))
        evidence["b"] = f"newline_density={newline_density:.4f};sep_hits_norm={sep_hits:.4f}"

        # r: redundancy — duplicate line ratio
        stripped = [ln.strip() for ln in lines if ln.strip()]
        if stripped:
            uniq = len(set(stripped))
            dup_ratio = 1.0 - (uniq / len(stripped))
        else:
            dup_ratio = 0.0
        r = _clamp01(dup_ratio)
        evidence["r"] = f"dup_line_ratio={dup_ratio:.4f};lines={len(stripped)}"

        # s: structural regularity — JSON/CSV/code heuristics (not a route decision)
        s_score = 0.0
        json_ok = False
        try:
            json.loads(text)
            json_ok = True
            s_score += 0.7
        except (json.JSONDecodeError, TypeError, ValueError):
            notes.append("json_parse_failed")
        csvish = sum(1 for ln in stripped if ln.count(",") >= 2)
        if stripped and csvish / len(stripped) >= 0.5:
            s_score += 0.5
        if re.search(r"\b(def|class|import|function|const|let)\b", text):
            s_score += 0.3
        if re.search(r"^\s*#|^\s*//|=\s*\{", text, re.MULTILINE):
            s_score += 0.2
        s = _clamp01(s_score)
        evidence["s"] = f"json_ok={json_ok};csvish_lines={csvish};s_raw={s_score:.3f}"

        # k: coupling proxy — id-like tokens / imports / references
        refs = re.findall(r"\b(import|from|ref|id|unit|syn-[a-z0-9-]+)\b", text, re.IGNORECASE)
        k = _clamp01(min(1.0, len(refs) / max(8.0, line_count)))
        evidence["k"] = f"ref_like_tokens={len(refs)}"

        # a: anomaly / entanglement proxy
        anom = 0.0
        if fail_closed:
            anom += 0.8
        anom += 0.2 * min(
            1.0,
            len(re.findall(r"traceback|exception|malformed|parse.?error", text, re.IGNORECASE))
            / 3.0,
        )
        if not stripped:
            anom += 0.4
            uncertain = True
        # Broken JSON-like payload is an anomaly (not a family/oracle label).
        lead = text.lstrip()
        jsonish = lead.startswith("{") or (lead.startswith("[") and (":" in text or '"' in text))
        if jsonish:
            try:
                json.loads(text)
            except (json.JSONDecodeError, TypeError, ValueError):
                anom += 0.8
                notes.append("malformed_json")
        a = _clamp01(anom)
        evidence["a"] = f"anom_raw={anom:.3f}"

        # l: locality proxy — if query present, concentration of query tokens; else mid prior
        if isinstance(query, str) and query.strip():
            q_tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9_]+", query) if len(t) > 1]
            if q_tokens and stripped:
                hits = []
                for ln in stripped:
                    low = ln.lower()
                    hits.append(sum(1 for t in q_tokens if t in low))
                total = sum(hits) or 1
                top = sorted(hits, reverse=True)[: max(1, min(3, len(hits)))]
                l = _clamp01(sum(top) / total)
                evidence["l"] = f"query_tokens={len(q_tokens)};top_mass={sum(top) / total:.3f}"
            else:
                l = 0.5
                uncertain = True
                evidence["l"] = "query_present_but_no_overlap_stats"
        else:
            l = 0.5
            evidence["l"] = "no_query_prior_0.5"

        # p: provenance sensitivity proxy — paths, versions, line numbers
        prov_hits = len(
            re.findall(
                r"(line\s*\d+|v?\d+\.\d+\.\d+|/[A-Za-z0-9_.-]+|unit_id|version=)",
                text,
                re.IGNORECASE,
            )
        )
        p = _clamp01(min(1.0, prov_hits / 6.0))
        evidence["p"] = f"prov_hits={prov_hits}"

        # u: uncertainty — high when anomalous / empty / weak locality without structure
        u = _clamp01(
            0.5 * a
            + 0.3 * (1.0 - l)
            + (0.4 if uncertain or fail_closed else 0.0)
            + (0.2 if n < 8 else 0.0)
        )
        if uncertain or fail_closed:
            u = max(u, 0.6)
        evidence["u"] = f"uncertain={uncertain};fail_closed={fail_closed}"

        features = {
            "b": b,
            "r": r,
            "s": s,
            "k": k,
            "a": a,
            "l": l,
            "p": p,
            "u": u,
        }
        # Never use answer/target fields even if present
        if "answer" in source_unit or "gold_route" in source_unit or "route" in source_unit:
            notes.append("ignored_answer_or_route_fields")

        cpu_ms = (time.perf_counter() - t0) * 1000.0
        _, peak = tracemalloc.get_traced_memory()
        return ProfileReport(
            features=features,
            evidence=evidence,
            uncertain=uncertain or fail_closed,
            fail_closed=fail_closed,
            cpu_ms=cpu_ms,
            peak_memory_kb=peak / 1024.0,
            notes=notes,
        )
