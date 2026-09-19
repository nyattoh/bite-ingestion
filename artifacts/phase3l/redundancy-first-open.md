# Phase 3L structural redundancy first-open evaluation

verdict: `PHASE3L_REDUNDANCY_HOLDOUT_CONFIRMED`
protocol SHA: `d365d0b1bd4cb3dcdad617ed4e78df19fdf23ce6`
matched: 60/60
routing_connected: `false`
redundancy_threshold_set: `false`
rule_policy_changed: `false`
claim: `same frozen families / new replica values`

## Checks

- n_60: `True`
- frozen_expects: `True`
- format_invariance: `True`
- reorder_invariance: `True`
- negative_controls: `True`
- locked_blobs_unchanged: `True`

## Cross-format

| family | replica | ok |
|---|---|---|
| exact_dup_pairs | 2 | True |
| exact_dup_pairs | 3 | True |
| all_unique | 2 | True |
| all_unique | 3 | True |
| same_key_diff_value | 2 | True |
| same_key_diff_value | 3 | True |
| same_value_diff_key | 2 | True |
| same_value_diff_key | 3 | True |
| reordered_duplicates | 2 | True |
| reordered_duplicates | 3 | True |
| multiplicity_2 | 2 | True |
| multiplicity_2 | 3 | True |
| multiplicity_3 | 2 | True |
| multiplicity_3 | 3 | True |
| common_prefix | 2 | True |
| common_prefix | 3 | True |
| common_suffix | 2 | True |
| common_suffix | 3 | True |
| identifier_substring | 2 | True |
| identifier_substring | 3 | True |

BITE wins / Go ではない。unseen morphology 評価ではない。
