# Phase 1 offline arm matrix (wiring check)

Not a research conclusion. Paid API: false.

- n_total=44 n_measured=44 n_excluded=0 n_failed=0 n_no_op=25
- no_op_rate=0.5681818181818182 failure_rate=0.0
- rule_pi sequences: [['CUT'], ['CUT', 'UNTANGLE']]
- length_pi ≠ rule_pi: ['adversarial_omission-000', 'malformed_mixed-000', 'sparse_anomaly-000']
- workload rows=32 negative-control rows=12 (means and arm differentiation above use WORKLOAD rows only)

## Negative controls (instrument check, must report failure)

- checked=12 violations=none

| family | method | recall_vis | recall_rec | provenance | T_rebite |
|---|---|---:|---:|---:|---:|
| neg_gold_quarantined | raw_full | 1.0 | 1.0 | 1.0 | 0 |
| neg_gold_quarantined | length_pi | 1.0 | 1.0 | 1.0 | 0 |
| neg_gold_quarantined | rule_pi | 0.5 | 1.0 | 1.0 | 0 |
| neg_gold_quarantined | rule_pi_rebite | 1.0 | 1.0 | 1.0 | 10 |
| neg_missing_provenance | raw_full | 1.0 | 1.0 | 0.5 | 0 |
| neg_missing_provenance | length_pi | 1.0 | 1.0 | 0.5 | 0 |
| neg_missing_provenance | rule_pi | 1.0 | 1.0 | 0.5 | 0 |
| neg_missing_provenance | rule_pi_rebite | 1.0 | 1.0 | 0.5 | 0 |
| neg_unrecoverable_gold | raw_full | 1.0 | 1.0 | 1.0 | 0 |
| neg_unrecoverable_gold | length_pi | 1.0 | 1.0 | 1.0 | 0 |
| neg_unrecoverable_gold | rule_pi | 0.5 | 1.0 | 1.0 | 0 |
| neg_unrecoverable_gold | rule_pi_rebite | 0.5 | 1.0 | 1.0 | 0 |

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
| neg_gold_quarantined-000 | raw_full | pass_through | `—` | `3b2d9b51fcc2306f` | 0 | 31 |
| neg_gold_quarantined-000 | length_pi | no_op | `CUT` | `3b2d9b51fcc2306f` | 0 | 31 |
| neg_gold_quarantined-000 | rule_pi | transformed | `CUT,UNTANGLE` | `c7790278ee35fc89` | 0 | 18 |
| neg_gold_quarantined-000 | rule_pi_rebite | transformed | `CUT,UNTANGLE` | `1acfdf290402f9fe` | 10 | 38 |
| neg_missing_provenance-000 | raw_full | pass_through | `—` | `126e7854e1f26049` | 0 | 22 |
| neg_missing_provenance-000 | length_pi | no_op | `CUT` | `126e7854e1f26049` | 0 | 22 |
| neg_missing_provenance-000 | rule_pi | no_op | `CUT` | `126e7854e1f26049` | 0 | 22 |
| neg_missing_provenance-000 | rule_pi_rebite | no_op | `CUT` | `126e7854e1f26049` | 0 | 22 |
| neg_unrecoverable_gold-000 | raw_full | pass_through | `—` | `5ef1e49cbbb1bda9` | 0 | 26 |
| neg_unrecoverable_gold-000 | length_pi | no_op | `CUT` | `5ef1e49cbbb1bda9` | 0 | 26 |
| neg_unrecoverable_gold-000 | rule_pi | transformed | `CUT,UNTANGLE` | `424295dab670d265` | 0 | 17 |
| neg_unrecoverable_gold-000 | rule_pi_rebite | transformed | `CUT,UNTANGLE` | `424295dab670d265` | 0 | 17 |
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
