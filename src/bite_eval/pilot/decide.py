"""Gate C decision labels from D-2 lock v0.1 confirmatory C1–C3.

Lock symbols referenced (d2-threshold-lock-2026-09-16.md §3):
  delta, rho_visible, rho_recoverable, eta, confirmatory set C1/C2/C3,
  primary T_total = billed/provider when available.

Honest offline rule: if paid_api is false OR T_total estimate is local_char4_proxy,
C1–C3 cannot be evaluated with billed tokens → insufficient_offline
(prefer that over claiming Go on proxy/smoke evidence).

BITE-15 billed path: estimate_source=provider_usage_billed allows go/pivot/stop.
With minimal sample (n << N_pilot), prefer pivot — go only when confirmatory
C1–C3 + N_pilot are met (documented); minimal set must NOT claim Go.
"""

from __future__ import annotations

from typing import Literal

DecisionLabel = Literal["go", "pivot", "stop", "insufficient_offline"]

LOCAL_PROXY = "local_char4_proxy"
BILLED_PROVIDER = "provider_usage_billed"
# Legacy alias accepted as billed (BITE-14 tests used "provider_usage")
_BILLED_ALIASES = frozenset({BILLED_PROVIDER, "provider_usage"})


def _is_billed_source(source: str) -> bool:
    return source in _BILLED_ALIASES


def decide_gate_c(
    *,
    paid_api: bool,
    t_total_estimate_source: str,
    constraints_ok_rate: float,
    systematic_constraint_fail: bool,
    # Confirmatory C1–C3 (lock §3). None = not evaluable offline.
    c1_t_total_improves_vs_raw_and_best_single: bool | None,
    c2_morphology_beats_length_only: bool | None,
    c3_net_savings_positive: bool | None,
    pivot_scope_trigger: bool = False,
    # BITE-15 extensions
    sample_meets_n_pilot: bool = True,
    rate_limit_partial: bool = False,
    has_billed_usage: bool | None = None,
) -> DecisionLabel:
    """Return go | pivot | stop | insufficient_offline.

    Predicates (lock §3 confirmatory + bite-04 §7 spirit + BITE-15 billed):

    - **insufficient_offline** if ``paid_api`` is False OR
      ``t_total_estimate_source == local_char4_proxy`` (cannot honestly
      assess C1/C3 T_total improvement with billed tokens), OR if billed
      path claims no usable provider usage (``has_billed_usage is False``),
      OR if any of C1–C3 is None (not evaluable) *and* not a rate-limit
      partial. Prefer this over Go on proxy/smoke.

    - **stop** if constraints fail systematically
      (``systematic_constraint_fail``), OR if all of C1–C3 are evaluable
      and False (negative confirmatory result under billed accounting).

    - **pivot** if ``rate_limit_partial`` mid-run; OR ``pivot_scope_trigger``;
      OR billed path with partial confirmatory support; OR billed path
      where C1∧C2∧C3 hold but ``sample_meets_n_pilot`` is False
      (minimal 2×3 set → need full N_pilot billed before Go).

    - **go** only if paid_api, billed T_total (``provider_usage_billed``),
      ``sample_meets_n_pilot``, constraints broadly hold, and C1 and C2
      and C3 are all True. Minimal billed pilots must not reach this
      branch (``sample_meets_n_pilot=False`` → pivot instead).
    """
    is_proxy = t_total_estimate_source == LOCAL_PROXY
    is_billed = _is_billed_source(t_total_estimate_source)
    proxy_or_unpaid = (not paid_api) or is_proxy

    if has_billed_usage is None:
        billed_ok = is_billed and paid_api
    else:
        billed_ok = bool(has_billed_usage)

    c_unevaluable = (
        c1_t_total_improves_vs_raw_and_best_single is None
        or c2_morphology_beats_length_only is None
        or c3_net_savings_positive is None
    )

    if systematic_constraint_fail:
        return "stop"

    # Rate-limit mid-run: save partial; prefer pivot (not Go).
    if rate_limit_partial:
        return "pivot"

    if is_billed and has_billed_usage is False:
        return "insufficient_offline"

    if proxy_or_unpaid or not is_billed:
        return "insufficient_offline"

    if not billed_ok:
        return "insufficient_offline"

    if c_unevaluable:
        return "insufficient_offline"

    # --- Billed path only below ---
    c1 = bool(c1_t_total_improves_vs_raw_and_best_single)
    c2 = bool(c2_morphology_beats_length_only)
    c3 = bool(c3_net_savings_positive)

    if not (c1 or c2 or c3):
        return "stop"

    if c1 and c2 and c3 and constraints_ok_rate >= 1.0 - 1e-9:
        if not sample_meets_n_pilot:
            return "pivot"
        if pivot_scope_trigger:
            return "pivot"
        return "go"

    if pivot_scope_trigger or not (c1 and c2 and c3):
        return "pivot"

    if not sample_meets_n_pilot:
        return "pivot"

    return "insufficient_offline"
