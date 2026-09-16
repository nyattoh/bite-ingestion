# Recovery security (BITE-11)

Pivot-to-bench notes for bounded Recover. No Survive claims.

## Threat model (synthetic / eval)

1. **Recovery bypass** — request a `unit_id` / locator not present in \(R\) (or not reachable via
   `recovery_handles` → `r_ids`). **Fail closed** → `recover_miss` / out of contract.
2. **Withdrawn / forbidden sources** — SourceStore status `withdrawn` or `forbidden` must never
   return body text into `visible_evidence`. Outcome: refuse with audit.
3. **Injection-suspect restore** — UNTANGLE may quarantine `injection_suspect`. Re-bite of such
   units is **policy-refused** by default (`refused_injection_suspect`) with audit; never silent.
4. **Stale version presentation** — if request version mismatches store version and locator/store
   marks `stale=true` (or explicit mismatch under freshness check) → `stale_or_broken_locator`.
5. **Budget abuse** — unbounded loops; enforced by \(J\) and \(B_r\) (TBD_CALIBRATE placeholders).
6. **Prompt / request injection into store** — free-form shell/SQL/web disallowed; only schema'd
   request types in \(\mathcal{Q}_{req}\).
7. **Duplicate inflation** — identical successful fetch for same unit/span suppressed
   (`suppressed_repeat`); does not re-add duplicate evidence.

## Access control rules (v0.1)

| Check | On failure |
|---|---|
| `request_type ∈ Q_req` | `invalid_request` |
| Target resolvable in `R.entries` (direct unit_id / r_id / handle→r_ids / aggregate_parent / quarantine reason) | `recover_miss` |
| Source status not `withdrawn` | `refused_withdrawn` |
| Source status not `forbidden` | `refused_forbidden` |
| Source status not `injection_suspect` (default policy) | `refused_injection_suspect` |
| Version freshness OK | `stale_or_broken_locator` |
| `state.calls < J` and tokens ≤ \(B_r\) | `budget_exhausted` |

## Audit requirements

Every attempt (success or fail) appends an audit row:

- request fingerprint (`request_type`, target ids, span, version)
- outcome code
- returned evidence IDs (empty on refuse/miss)
- estimated tokens added this call
- timestamp optional (deterministic tests may omit wall clock; use monotonic step index)

Audit log is **append-only** within a `RecoverState`.

## Token proxy disclaimer

`estimate_tokens(text) = max(1, (len(text) + 3) // 4)` when text non-empty (0 if empty).
This is a **char/4 proxy for tests**, not a provider tokenizer claim. Values feed
`accounting.rebite_tokens` and are noted as belonging in \(T_{total}\).

## Disallowed capabilities

- Free-form web search / crawlers
- Arbitrary shell or SQL execution from Recover
- Unlimited tool loops
- Escalate terminology / paths
- Downloading real external datasets from this module

## Clarify vs fetch

`clarify_sufficiency` returns **meta only** (e.g. missing evidence type tags derived from \(R\)
reasons not yet visible). It must not copy source bodies into \(E\). Use this to avoid
conflating `model_indecision` with `missing_evidence`.
