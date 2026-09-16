# Policy decision table (rule-Π) — BITE-10

**Status**: Pivot-to-bench. Transparent routing only.  
**Thresholds**: `TBD_CALIBRATE` synthetic placeholders (`HIGH=0.66`, `LOW=0.34`) — **not** empirical; do not report as calibrated science.  
**Grammar**: normal-form only `CUT? → UNTANGLE? → REDUCE? → INTEGRATE?` (each ≤1; length ≥1).

Condition names: `rule-Π`, `oracle-Π`, `fixed-Π`, `length-Π`.

## rule-Π rows

| rule_id | feature | comparison | effect |
| --- | --- | --- | --- |
| CUT-IN | `b`, `pre_segmented` | `b < HIGH` **OR** `pre_segmented=False` | include CUT |
| CUT-OMIT | `b`, `pre_segmented` | `b ≥ HIGH` **AND** `pre_segmented=True` | omit CUT |
| UNTANGLE-IN | `a`, `malformed` | `a ≥ HIGH` **OR** `malformed=True` | include UNTANGLE |
| UNTANGLE-OMIT | `a`, `malformed` | `a < HIGH` **AND** `malformed=False` | omit UNTANGLE |
| REDUCE-IN | `r` | `r ≥ HIGH` | include REDUCE |
| REDUCE-OMIT | `r` | `r < HIGH` | omit REDUCE |
| INTEGRATE-IN-QC | `k`, `l` | `query_conditioned` **AND** `k ≥ HIGH` **AND** `l ≤ LOW` | include INTEGRATE |
| INTEGRATE-OMIT-QC | `k`, `l` | `query_conditioned` **AND** NOT (`k ≥ HIGH` ∧ `l ≤ LOW`) | omit INTEGRATE |
| INTEGRATE-IN-NOQC | `k` | NOT `query_conditioned` **AND** `k ≥ HIGH` | include INTEGRATE |
| INTEGRATE-OMIT-NOQC | `k` | NOT `query_conditioned` **AND** `k < HIGH` | omit INTEGRATE |
| QC-OFF | `l`, `u` | `query_conditioned=False` | zero-out `l`,`u` for routing (still accepted in input) |
| EMPTY-FALLBACK | all omit | no op included | fallback: **CUT** default; **REDUCE** if `pre_segmented` and `n_tokens > LENGTH_SHORT_MAX` |
| BUDGET-MAX-OPS | `budget.max_ops` | `len(seq) > max_ops` | drop later ops first (INTEGRATE→REDUCE→UNTANGLE); keep ≥1 |
| BUDGET-TOKEN | `budget.token_budget` | `token_budget < LENGTH_SHORT_MAX` | keep first op only |

Aligned with BITE-02 §3.2 omit rules (direction only).

## length-Π (morphology ignored)

| band | length source | TBD cutpoint | sequence |
| --- | --- | --- | --- |
| short | `n_tokens` ≤ 64 (or `char_len` ≤ 256) | TBD | `(CUT,)` |
| medium | else ≤ 256 tokens (or ≤ 1024 chars) | TBD | `(CUT, REDUCE)` |
| long | above medium | TBD | `(CUT, REDUCE, INTEGRATE)` |

## fixed-Π

| rule_id | feature | comparison | effect |
| --- | --- | --- | --- |
| FIXED | none | constant | always configurable sequence (default `(CUT, REDUCE)`) |

## oracle-Π (eval-only)

| rule_id | feature | comparison | effect |
| --- | --- | --- | --- |
| ORACLE-LOOKUP | `task_id` | `route_table[task_id]` | gold sequence; requires `allow_eval_use=True` |

Leak contract: transparent `rule-Π` rejects morphology/budget keys matching `oracle_*`, `gold_*`, `eval_*`, and exact keys such as `gold_route`, `eval_visible_recall`.

## Empty / budget fallback documentation

1. If every include-rule omits → propose `(CUT)` unless `pre_segmented=True` and length suggests compression → `(REDUCE)`.
2. If `max_ops` truncates → keep earliest ops in normal order.
3. Sequences always validated as normal-form; loops/oscillation never emitted.
