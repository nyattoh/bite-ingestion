# Phase 1 offline arm matrix (wiring check)

Not a research conclusion. Paid API: false.

- n_total=32 n_measured=32 n_excluded=0 n_failed=0 n_no_op=20
- no_op_rate=0.625 failure_rate=0.0
- rule_pi sequences: [['CUT'], ['CUT', 'UNTANGLE']]
- length_pi ≠ rule_pi: ['adversarial_omission-000', 'malformed_mixed-000', 'sparse_anomaly-000']

| case_id | method | status | sequence | payload_sha256 | T_rebite | T_total |
|---|---|---|---|---|---:|---:|
| adversarial_omission-000 | raw_full | pass_through | `—` | `bbe4fcc2bc48db0b` | 0 | 85 |
| adversarial_omission-000 | length_pi | transformed | `CUT,REDUCE` | `5370f213e8d3f333` | 0 | 48 |
| adversarial_omission-000 | rule_pi | no_op | `CUT` | `bbe4fcc2bc48db0b` | 0 | 85 |
| adversarial_omission-000 | rule_pi_rebite | no_op | `CUT` | `bbe4fcc2bc48db0b` | 0 | 85 |
| clean_local-000 | raw_full | pass_through | `—` | `22756a47e32cf697` | 0 | 23 |
| clean_local-000 | length_pi | no_op | `CUT` | `22756a47e32cf697` | 0 | 23 |
| clean_local-000 | rule_pi | no_op | `CUT` | `22756a47e32cf697` | 0 | 23 |
| clean_local-000 | rule_pi_rebite | no_op | `CUT` | `22756a47e32cf697` | 0 | 23 |
| dense_cross_reference-000 | raw_full | pass_through | `—` | `29cd373c65ca8016` | 0 | 15 |
| dense_cross_reference-000 | length_pi | no_op | `CUT` | `29cd373c65ca8016` | 0 | 15 |
| dense_cross_reference-000 | rule_pi | no_op | `CUT` | `29cd373c65ca8016` | 0 | 15 |
| dense_cross_reference-000 | rule_pi_rebite | no_op | `CUT` | `29cd373c65ca8016` | 0 | 15 |
| dependency_chain-000 | raw_full | pass_through | `—` | `1b6fa2f17451af1d` | 0 | 17 |
| dependency_chain-000 | length_pi | no_op | `CUT` | `1b6fa2f17451af1d` | 0 | 17 |
| dependency_chain-000 | rule_pi | no_op | `CUT` | `1b6fa2f17451af1d` | 0 | 17 |
| dependency_chain-000 | rule_pi_rebite | no_op | `CUT` | `1b6fa2f17451af1d` | 0 | 17 |
| malformed_mixed-000 | raw_full | pass_through | `—` | `02dfca2d582f19c1` | 0 | 20 |
| malformed_mixed-000 | length_pi | no_op | `CUT` | `02dfca2d582f19c1` | 0 | 20 |
| malformed_mixed-000 | rule_pi | transformed | `CUT,UNTANGLE` | `219bae5ad47449b9` | 0 | 12 |
| malformed_mixed-000 | rule_pi_rebite | transformed | `CUT,UNTANGLE` | `219bae5ad47449b9` | 0 | 12 |
| repeated_records-000 | raw_full | pass_through | `—` | `c276d44b4244ce15` | 0 | 70 |
| repeated_records-000 | length_pi | no_op | `CUT,REDUCE` | `c276d44b4244ce15` | 0 | 70 |
| repeated_records-000 | rule_pi | no_op | `CUT` | `c276d44b4244ce15` | 0 | 70 |
| repeated_records-000 | rule_pi_rebite | no_op | `CUT` | `c276d44b4244ce15` | 0 | 70 |
| sparse_anomaly-000 | raw_full | pass_through | `—` | `72563067ee622e61` | 0 | 100 |
| sparse_anomaly-000 | length_pi | transformed | `CUT,REDUCE` | `2e68f398c70b01ca` | 0 | 54 |
| sparse_anomaly-000 | rule_pi | no_op | `CUT` | `72563067ee622e61` | 0 | 100 |
| sparse_anomaly-000 | rule_pi_rebite | no_op | `CUT` | `72563067ee622e61` | 0 | 100 |
| texture_swap-000 | raw_full | pass_through | `—` | `8fb94cd2099df2d9` | 0 | 6 |
| texture_swap-000 | length_pi | no_op | `CUT` | `8fb94cd2099df2d9` | 0 | 6 |
| texture_swap-000 | rule_pi | no_op | `CUT` | `8fb94cd2099df2d9` | 0 | 6 |
| texture_swap-000 | rule_pi_rebite | no_op | `CUT` | `8fb94cd2099df2d9` | 0 | 6 |
