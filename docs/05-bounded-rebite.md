# Bounded re-bite / Recover (Gate B pointer)

Condensed from BITE-03 §4. **Pivot-to-bench**; no Survive architecture claims; no invented
calibration numbers for \(J\) / \(B_r\) — use `TBD_CALIBRATE` placeholders only.

## Intent

When visible evidence \(E\) is insufficient, restore **only needed spans** via schema'd
requests against recovery index \(R\). Never resend whole raw corpora. Never open free-form
web search, crawlers, unlimited tool loops, or arbitrary shell/SQL.

**Terminology**: use `Recover` / `re-bite` / `bounded recovery`. Do **not** use Escalate.

## Allowed request types \(\mathcal{Q}_{req}\) (v0.1)

| request_type | Meaning | Required \(R\) keys | Notes |
|---|---|---|---|
| `fetch_unit` | Add full unit text to \(E\) | `unit_id` + locator | Base form |
| `fetch_span` | Add locator span only | `locator.span` | Partial recovery |
| `fetch_aggregate_members` | Add constituent units of an aggregate row | `aggregate_parent` | Post-REDUCE rare restore |
| `fetch_quarantine` | Restore from UNTANGLE quarantine by reason | `reason` + `unit_id` | Over-quarantine recovery |
| `fetch_by_version` | Same logical source at specified version | `version` | Freshness tasks |
| `clarify_sufficiency` | Meta only: which evidence *types* are missing (no body) | optional | Separates `model_indecision` from `missing_evidence` |

**Disallowed (v0.1)**: free-form web search; crawl outside \(R\); unlimited tool loops;
arbitrary shell/SQL; Escalate terminology / TierMem escalate path copy.

## Stop conditions

| Condition | Behaviour |
|---|---|
| Call ceiling | `state.calls < J` required to proceed. \(J\) = **TBD_CALIBRATE** (synthetic default `DEFAULT_J=3` for tests only; not empirical). |
| Token ceiling | Cumulative recovered token estimate ≤ \(B_r\). \(B_r\) = **TBD_CALIBRATE** (synthetic `DEFAULT_BR_TOKENS=512` for tests only). Estimate proxy = `ceil(len(chars)/4)` — **not** a tokenizer claim. |
| Empty match | Request matches zero \(R\) entries → `recover_miss` |
| Invalid type | Outside \(\mathcal{Q}_{req}\) → `invalid_request` |
| Stale / broken locator | Version mismatch with `stale=true` or broken pointer → `stale_or_broken_locator` |
| Safety | `withdrawn` / `forbidden` refused; `injection_suspect` may be policy-refused with audit |
| Sufficiency | Task-end / sufficiency signal (harness-defined; not invented here) |

## Failure behaviour

| Situation | Behaviour |
|---|---|
| `recover_miss` | \(E\) unchanged; `recovery_success=0`; task may continue on existing \(E\) |
| `budget_exhausted` | Further Recover refused; continue answering allowed |
| `invalid_request` | Refuse (retry-counting rule deferred to BITE-04; v0.1 still increments call count) |
| `stale_or_broken_locator` | Fail path; may later map to harness `constraint_fail` |
| Accounting | Every attempt increments call count; estimated recovered tokens go to `accounting.rebite_tokens` (part of \(T_{total}\)) |

Update rule (from BITE-02/03):

\[
E_{t+1} = E_t \cup \operatorname{Recover}(R, request_t),\quad t = 0,\ldots,J-1
\]

## Distinctions

- **`missing_evidence`**: \(R\) has a recoverable entry not yet in `visible_evidence`.
- **`model_indecision`**: model issues `clarify_sufficiency` without a body fetch — never treat
  recovery *loops* as success.
- Outside \(R\) (or handles → r_ids) → out of contract (`recover_miss` / refuse closed).

## Packet fields (BITE-09 bridge)

Working packet keeps: `visible_evidence`, `units`, `R.entries`, `recovery_handles`, `tau`,
plus recovery ledger `rebite` (steps) and `accounting.rebite_tokens`.

Successful body fetches append a `tau` step with `op=RECOVER` (and/or `rebite.steps`).

## Implementation map

| Module | Role |
|---|---|
| `recovery/types.py` | Request/response dataclasses; allowed enum |
| `recovery/guards.py` | Access control, withdrawn/forbidden, version freshness, injection refusal |
| `recovery/budget.py` | \(J\), \(B_r\) TBD placeholders |
| `recovery/audit.py` | Append-only audit (request + returned evidence IDs + outcomes) |
| `recovery/source_store.py` | In-memory synthetic SourceStore (no shell/SQL) |
| `recovery/dedupe.py` | Suppress identical successful re-fetches |
| `recovery/engine.py` | `RecoverEngine.recover(...)` |

## Near-neighbour one-liner

TierMem routes summary↔raw memory sufficiency; IterCOMP iterates retrieval compression.
This contract is **bounded recovery from ingestion-time \(R\)** only.
