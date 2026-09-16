# Operator catalogue (BITE-09)

Deterministic, provenance-preserving library. No in-operator model calls. Pivot-to-bench tone.

## API

```python
from bite_ingestion.operators import (
    OperatorId,
    get_operator,
    apply_operator,
    CutOperator,
    UntangleOperator,
    ReduceOperator,
    IntegrateOperator,
)

out = apply_operator(OperatorId.CUT, packet, context={"boundary": "paragraph"})
# or
out = CutOperator().apply(packet, context)
```

- `get_operator(op_id) -> Operator`
- `apply_operator(op_id, packet, context=None) -> Mapping`
- `mode` is always `deterministic`
- Same input ⇒ same output (stable sha256-prefix ids: `u_` / `r_` / `h_` / `loss_`)

## Unit synthesis

When `units` is missing/empty, units are synthesized from `visible_evidence[].text` with contiguous char spans over a virtual concatenation (newline between items). CUT then subdivides those spans.

## CUT

| Context key | Values | Default |
|---|---|---|
| `boundary` | `paragraph` \| `line` \| `record` | `paragraph` |
| `max_units` | int | omit = no budget truncate |

- Paragraph = blank-line split; line = newline; record = JSON array elements / NDJSON / CSV lines when clear, else lines.
- Budget truncate places remainder in \(R\) with reason `budget_truncated` + recovery handle — never silent drop.
- Packet extras: `cut.{boundary,max_units,n_produced,n_selected,n_omitted}`

## UNTANGLE

Quarantines into \(R\) (`reason=quarantined`, `recoverable=true`) with reason codes:

`malformed` | `anomaly_candidate` | `injection_suspect` | `dependency_cycle` | `dependency_edge`

- Residual + isolated cover the input unit set.
- Packet extras: `untangle.{isolated,residual_ids,reasons,dependency_edges}`
- Also mirrored under `tau.steps[].extra`.

## REDUCE

Paths (all on by default; toggle via context flags `dedupe`, `aggregate`, `canonicalise_whitespace`):

1. Whitespace canonicalise — original in \(R\); ledger kind `canonicalise_whitespace` (declared, recoverable).
2. Exact-text dedupe — ledger `dedupe_collapse`.
3. Aggregate identical `key=value` or CSV rows with `count=N` — ledger `aggregate_count`.

- Omit map: `reduce.omit_map` and `tau.extra["reduce.omit_map"]`.
- Does **not** overwrite source records with free-text semantic summaries.

## INTEGRATE

- Only `integrate_mode=deterministic_join` (default). Other modes → `op_status=failed`.
- Joins units sharing `id=` / `key=` fields, or dependency edges from context / prior `untangle`.
- Outputs `integrate.join_plan` (`[{join_key, unit_ids, method}]`) and `integrate.used_evidence_ids`.
- Visible items carry `unit_ids` provenance pointers to inputs.
- Nothing to join ⇒ pass-through, empty plan, `op_status=ok`.

## Loss ledger auditor

```python
from bite_ingestion.operators.loss_ledger import audit_undeclared_visible_loss, assert_no_undeclared_loss
```

Checker/tests use this to flag visible shrink without \(R\) / declared ledger coverage.

## Fixtures

Synthetic JSON under `output/operator-fixtures/`. No real datasets.
