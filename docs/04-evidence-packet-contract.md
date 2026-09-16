# Evidence packet contract (Gate A pointer)

Condensed from BITE-03 §3. Pivot-to-bench; no Survive claims; no invented eval numbers.

## Conceptual fields

| Symbol | Name | Role |
|---|---|---|
| \(E\) | visible evidence | What the target model actually sees (`visible_evidence` in scaffold schema) |
| \(R\) | recovery index | Pointers to omitted / quarantined / unselected source (`R.entries`) |
| \(\tau\) | operator trace | Applied op sequence + per-step refs (`tau`) |
| provenance | lineage | `unit_id`, source URI/path, span, renderer_id, `op_last_touch` |
| coverage | split recall | Visible vs recoverable must **not** be collapsed to one score at eval time |
| version/freshness | staleness | Do not present old versions as new |

## Working packet (BITE-09 bridge)

Scaffold `evidence_packet.schema.json` is intentionally thin. Operators accept/produce an
**extended working packet** (`Mapping[str, object]`) that remains backward-compatible with
required scaffold keys when present:

- Required-when-present: `packet_id`, `visible_evidence`, `provenance`, `op_last_touch`
- Extended (maintained by operators): `units`, `R`, `tau`, `recovery_handles`,
  `irreversible_loss_ledger`, `op_status`, plus op-specific blobs
- Recovery (BITE-11): `rebite` ledger, `accounting.rebite_tokens`

## Leak / policy rules

1. Oracle \(\mathbf{m}\) / gold coverage must not enter transparent routing features.
2. `coverage.eval_*` (if present) is harness-only — never operator decision input.
3. Recover outside \(R\) is out of contract (separate baseline).
4. No silent data loss: text leaving visible surface must appear in \(R\) (recoverable)
   and/or declared `irreversible_loss_ledger`.

## Bounded Recover (pointer)

Request types and stop conditions: `docs/05-bounded-rebite.md` / BITE-03 §4.
Implementation: `src/bite_ingestion/recovery/`.
