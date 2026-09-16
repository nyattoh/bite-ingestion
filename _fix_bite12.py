from __future__ import annotations

import re
from pathlib import Path

ROOT = Path("src/bite_eval")


def main() -> None:
    iface = ROOT / "interface.py"
    t = iface.read_text(encoding="utf-8")
    if "_coerce_int" not in t:
        helper = '''

def _coerce_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _coerce_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default
'''
        if "__all__" in t:
            t = t.replace("__all__", helper + "\n__all__", 1)
            t = t.replace("__all__ = [", '__all__ = ["_coerce_int", "_coerce_float", ', 1)
        else:
            t = t + helper
        iface.write_text(t, encoding="utf-8", newline="\n")
        print("interface helper added")

    p = ROOT / "baselines" / "__init__.py"
    t = p.read_text(encoding="utf-8")
    t = t.replace("from collections.abc import Callable, Mapping", "from collections.abc import Callable")
    p.write_text(t, encoding="utf-8", newline="\n")

    p = ROOT / "baselines" / "adaptive_chunk_like.py"
    t = p.read_text(encoding="utf-8")
    t = t.replace("        sub = _HEADING.split(p)\n", "")
    if "from bite_eval.interface import" not in t:
        t = "from bite_eval.interface import _coerce_float, _coerce_int\n" + t
    elif "_coerce_int" not in t:
        t = t.replace(
            "from bite_eval.interface import",
            "from bite_eval.interface import _coerce_float, _coerce_int,",
        )
    t = re.sub(
        r"int\(budget\.get\(\"adaptive_max_chars\", self\.max_chars\)\)\s*(# type: ignore\[arg-type\])?",
        '_coerce_int(budget.get("adaptive_max_chars", self.max_chars), self.max_chars)',
        t,
    )
    t = re.sub(
        r"int\(budget\.get\(\"top_k\", self\.top_k\)\)\s*(# type: ignore\[arg-type\])?",
        '_coerce_int(budget.get("top_k", self.top_k), self.top_k)',
        t,
    )
    t = t.replace('int(c["start"])  # type: ignore[arg-type]', '_coerce_int(c.get("start"), 0)')
    t = t.replace('int(c["start"])', '_coerce_int(c.get("start"), 0)')
    t = t.replace('float(c["score"])', '_coerce_float(c.get("score"), 0.0)')
    p.write_text(t, encoding="utf-8", newline="\n")

    p = ROOT / "baselines" / "contextsniper_like.py"
    lines = p.read_text(encoding="utf-8").splitlines(True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        if (
            'if lead <= indent and not ln.lstrip().startswith("#"):' in lines[i]
            and i + 1 < len(lines)
            and "re.match" in lines[i + 1]
        ):
            indent = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
            out.append(
                f'{indent}if lead <= indent and not ln.lstrip().startswith("#") '
                f'and re.match(r"\\s*(async\\s+def|def|class)\\s+", ln):\n'
            )
            i += 2
            while i < len(lines) and (
                lines[i].startswith(indent + "    ") or lines[i].strip() == ""
            ):
                if lines[i].strip() == "":
                    out.append(lines[i])
                    i += 1
                    continue
                out.append(lines[i][4:])
                i += 1
                if "break" in out[-1]:
                    break
            continue
        out.append(lines[i])
        i += 1
    p.write_text("".join(out), encoding="utf-8", newline="\n")

    p = ROOT / "baselines" / "hyve_like.py"
    t = p.read_text(encoding="utf-8")
    t = t.replace(
        'if stripped.startswith("{") or stripped.startswith("["):',
        'if stripped.startswith(("{", "[")):',
    )
    p.write_text(t, encoding="utf-8", newline="\n")

    p = ROOT / "baselines" / "rule_pi_rebite.py"
    t = p.read_text(encoding="utf-8")
    t = t.replace("except Exception:  # pragma: no cover", "except ImportError:  # pragma: no cover")
    t = t.replace("        except Exception:\n            return None", "        except ImportError:\n            return None")
    if "def rebite(" in t:
        start = t.index("    def rebite(")
        rest = t[start:]
        end_rel = len(rest)
        for marker in ["\n\n\n", "\n\n__all__", "\n__all__"]:
            j = rest.find(marker, 20)
            if j != -1:
                end_rel = min(end_rel, j)
        # also stop before next top-level after class - look for \n\n at end of method via regex
        m = re.search(r"\n(?=\n__all__|\Z)", rest[20:])
        if m:
            end_rel = min(end_rel, 20 + m.start())
        # Prefer: find last line of method by scanning until dedent to 0 or class-end
        lines = rest.splitlines(True)
        end_i = 1
        while end_i < len(lines):
            L = lines[end_i]
            if L.startswith("    def ") and end_i > 0:
                break
            if L.startswith("__all__") or L.startswith("class "):
                break
            end_i += 1
        end_rel = sum(len(x) for x in lines[:end_i])
        new_rebite = '''    def rebite(
        self,
        packet: Mapping[str, object],
        request: Mapping[str, object] | None = None,
        **kwargs: object,
    ) -> Mapping[str, object]:
        """Optional re-bite hook. No-op stub if RecoverEngine / store missing."""
        eng_cls = self._recover_cls
        if eng_cls is None:
            return {
                "status": "ok",
                "rebite_enabled": True,
                "noop": True,
                "reason": "RecoverEngine not importable; empty re-bite hook stub",
                "request": dict(request or {}),
            }
        source_store = kwargs.get("source_store")
        state = kwargs.get("state")
        if source_store is None or state is None:
            return {
                "status": "ok",
                "rebite_enabled": True,
                "noop": True,
                "reason": "source_store/state not provided; empty re-bite hook stub",
                "request": dict(request or {}),
            }
        engine = eng_cls() if callable(eng_cls) else eng_cls
        recover = getattr(engine, "recover", None)
        if recover is None:
            return {
                "status": "failed",
                "rebite_enabled": True,
                "reason": "RecoverEngine has no recover()",
            }
        try:
            return recover(packet, request or {}, source_store, state)  # type: ignore[misc]
        except TypeError as exc:
            return {
                "status": "failed",
                "rebite_enabled": True,
                "reason": f"recover() signature mismatch: {exc}",
                "request": dict(request or {}),
            }

'''
        t = t[:start] + new_rebite + t[start + end_rel :]
    p.write_text(t, encoding="utf-8", newline="\n")

    p = ROOT / "baselines" / "universal_reduce.py"
    t = p.read_text(encoding="utf-8")
    t = t.replace("except Exception:", "except (ImportError, TypeError, ValueError, AttributeError):")
    t = t.replace(
        "apply_sequence(packet, (OperatorId.REDUCE,), context)",
        'apply_sequence((OperatorId.REDUCE,), packet, policy_name="universal_reduce", context=context)',
    )
    t = t.replace(
        "apply_sequence(packet, (OperatorId.REDUCE,)",
        "apply_sequence((OperatorId.REDUCE,), packet",
    )
    p.write_text(t, encoding="utf-8", newline="\n")

    p = ROOT / "baselines" / "raw_full.py"
    t = p.read_text(encoding="utf-8")
    if "_coerce_int" not in t:
        t = "from bite_eval.interface import _coerce_int\n" + t
    t = re.sub(
        r"limit = int\(max_chars\)\s*(# type: ignore\[arg-type\])?",
        "limit = _coerce_int(max_chars, 0)",
        t,
    )
    p.write_text(t, encoding="utf-8", newline="\n")

    p = ROOT / "baselines" / "fixed_chunk_topk.py"
    t = p.read_text(encoding="utf-8")
    if "_coerce_int" not in t:
        t = "from bite_eval.interface import _coerce_int\n" + t
    t = re.sub(
        r"int\(([^)]+)\)\s*# type: ignore\[arg-type\]",
        r"_coerce_int(\1, 0)",
        t,
    )
    t = t.replace('int(c["start"])', '_coerce_int(c.get("start"), 0)')
    p.write_text(t, encoding="utf-8", newline="\n")

    for name in ["rule_pi.py", "length_pi.py", "fixed_pi.py"]:
        p = ROOT / "baselines" / name
        t = p.read_text(encoding="utf-8")
        t = t.replace(
            "decision = policy.explain_propose(morphology, budget)  # type: ignore[attr-defined]",
            'explain = getattr(policy, "explain_propose", None)\n'
            "                decision = explain(morphology, budget) if callable(explain) else None",
        )
        t = t.replace(
            "decision = policy.explain_propose(morphology, budget)",
            'explain = getattr(policy, "explain_propose", None)\n'
            "                decision = explain(morphology, budget) if callable(explain) else None",
        )
        p.write_text(t, encoding="utf-8", newline="\n")
        print("patched", name)

    print("done")


if __name__ == "__main__":
    main()
