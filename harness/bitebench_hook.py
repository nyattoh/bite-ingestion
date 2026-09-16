"""Eval/full-cost hook stub for BITEBench bundles (no paid API)."""

from __future__ import annotations

from typing import Any, Mapping


def token_meter_event_from_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    hook = bundle.get("harness_hooks", {}).get("token_meter_event_stub", {})
    return {
        "kind": hook.get("kind", "bitebench_render"),
        "case_id": hook.get("case_id"),
        "textures": list(hook.get("textures", [])),
        "full_cost_contract": bundle.get("harness_hooks", {}).get("full_cost_contract", "T_total"),
        "tokens": "TBD",
    }
