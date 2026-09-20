# Phase 3T exact reference identity v3

verdict: `PHASE3T_EXACT_REFERENCE_VALIDATED`
T0 SHA: `70a3f7792a5baee1382b890fb7021dc7fb234ce1`
ok: 128/128
T_high carry-forward: `True`
phase3s: `Phase3S remains FAILED`
phase3q: `Phase3Q remains FAILED`
p3f evaluation: sealed

## Checks

- edge_set_exact: `True`
- false_reference_edges_zero: `True`
- exact_reference_distances: `True`
- suffix_collision_no_edge: `True`
- true_plus_collision_true_only: `True`
- gate_expectation_exact: `True`
- cross_format_exact: `True`
- policy_consequence: `True`
- composition_safety: `True`
- t_high_carry_forward: `True`
- phase3s_failed_unchanged: `True`
- phase3q_failed_unchanged: `True`
- p3f_sealed: `True`
- frozen_unchanged: `True`
- reproduction_not_primary: `True`

## Families

- exact_reference_only: 16/16
- underscore_suffix_collision_only: 16/16
- exact_reference_plus_suffix_collision: 16/16
- suffix_collision_plus_actionability: 16/16
- prefix_only: 16/16
- suffix_text_only: 16/16
- substring_only: 16/16
- shared_generic_text: 16/16

routing / real-world generalization / BITE superiority ではない。
VALIDATED なら次は Phase 4 real-structured corpus。XFER-3 は作らない。
