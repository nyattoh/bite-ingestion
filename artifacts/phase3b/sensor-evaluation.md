# Phase 3B dispersion sensor evaluation

development fixtures only。Phase 2 evaluation は未使用。routing 未接続。
deterministic_v0 は未変更。有料 API 未使用。

- verdict: **PHASE3B_SENSOR_READY**
- sensor: `dependency_dispersion_v0` primary `mean_edge_distance`
- expected order: ['near', 'medium', 'far']
- one-hop mean_edge_distance: [1.0, 4.0, 9.0]
- nested one-hop: [1.0, 4.0, 9.0]
- two-hop chain_span: [2.0, 6.0, 10.0]

## Checks

- one_hop_monotone: yes
- one_hop_edge_count_stable: yes
- v0_invariant: yes
- no_reference_zero: yes
- false_positive_zero: yes
- unrelated_perm_stable: yes
- duplicate_raw_stable: yes
- nested_monotone: yes
- two_hop_chain_monotone: yes
- malformed_fail_closed: yes
- deterministic: yes
- generic_query_idle: yes
- identifier_query_moves: yes

## Candidates

- reference-graph (primary): value-identifier reappears in another non-identical line
- query-identifier span (secondary): idle on generic questions; moves if the query carries a rare identifier
- v0 `l`: permutation-invariant on these fixtures

