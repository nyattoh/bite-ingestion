# Phase 3E dependency-dispersion v1 validation

Phase 3D freeze を未変更のまま検証。v0 未変更。routing 未接続。有料 API 未使用。

- verdict: **PHASE3E_V1_VALIDATED**
- sensor: `dependency_dispersion_v1` edge `value_to_key_or_record_id`
- fixtures matched: 21/21
- routing feature choice: not_decided

## Fixtures

- true_dep_near_kv: ok observed={'n_edges': 1.0, 'mean_edge_distance': 1.0, 'n_logical_units': 2.0} expect={'n_edges': 1.0, 'mean_edge_distance': 1.0, 'n_logical_units': 2}
- true_dep_medium_kv: ok observed={'n_edges': 1.0, 'mean_edge_distance': 4.0, 'n_logical_units': 5.0} expect={'n_edges': 1.0, 'mean_edge_distance': 4.0, 'n_logical_units': 5}
- true_dep_far_kv: ok observed={'n_edges': 1.0, 'mean_edge_distance': 9.0, 'n_logical_units': 10.0} expect={'n_edges': 1.0, 'mean_edge_distance': 9.0, 'n_logical_units': 10}
- true_dep_near_json_compact: ok observed={'n_edges': 1.0, 'mean_edge_distance': 1.0, 'n_logical_units': 2.0} expect={'n_edges': 1.0, 'mean_edge_distance': 1.0, 'n_logical_units': 2}
- true_dep_near_json_pretty: ok observed={'n_edges': 1.0, 'mean_edge_distance': 1.0, 'n_logical_units': 2.0} expect={'n_edges': 1.0, 'mean_edge_distance': 1.0, 'n_logical_units': 2}
- scale_short: ok observed={'n_edges': 1.0, 'mean_edge_distance': 4.0} expect={'n_edges': 1.0, 'mean_edge_distance': 4.0}
- scale_medium: ok observed={'n_edges': 1.0, 'mean_edge_distance': 4.0} expect={'n_edges': 1.0, 'mean_edge_distance': 4.0}
- scale_long: ok observed={'n_edges': 1.0, 'mean_edge_distance': 4.0} expect={'n_edges': 1.0, 'mean_edge_distance': 4.0}
- blank_line_kv: ok observed={'n_edges': 1.0, 'mean_edge_distance': 1.0, 'n_logical_units': 2.0} expect={'n_edges': 1.0, 'mean_edge_distance': 1.0, 'n_logical_units': 2}
- wrap_pretty_json: ok observed={'n_edges': 1.0, 'mean_edge_distance': 1.0, 'n_logical_units': 2.0} expect={'n_edges': 1.0, 'mean_edge_distance': 1.0, 'n_logical_units': 2}
- shared_env_only: ok observed={'n_edges': 0.0} expect={'n_edges': 0.0}
- shared_service_only: ok observed={'n_edges': 0.0} expect={'n_edges': 0.0}
- shared_owner_only: ok observed={'n_edges': 0.0} expect={'n_edges': 0.0}
- shared_label_only: ok observed={'n_edges': 0.0} expect={'n_edges': 0.0}
- multiple_unrelated_same_identifiers: ok observed={'n_edges': 0.0} expect={'n_edges': 0.0}
- true_edge_plus_cooccurrence_pollution: ok observed={'n_edges': 1.0, 'mean_edge_distance': 1.0} expect={'n_edges': 1.0, 'mean_edge_distance': 1.0}
- one_hop_kv: ok observed={'n_edges': 1.0, 'chain_span': 1.0} expect={'n_edges': 1.0, 'chain_span': 1.0}
- two_hop_kv: ok observed={'n_edges': 2.0, 'chain_span': 2.0, 'n_logical_units': 3.0} expect={'n_edges': 2.0, 'chain_span': 2.0, 'n_logical_units': 3}
- branch_kv: ok observed={'n_edges': 2.0, 'n_logical_units': 3.0, 'component_span': 2.0} expect={'n_edges': 2.0, 'n_logical_units': 3, 'component_span': 2.0}
- no_reference: ok observed={'n_edges': 0.0, 'mean_edge_distance': 0.0} expect={'n_edges': 0.0, 'mean_edge_distance': 0.0}
- malformed_nul: ok observed={'fail_closed': True, 'n_edges': 0.0} expect={'fail_closed': True, 'n_edges': 0.0}

## Relations

- near_lt_medium_lt_far: yes
- scale_abs_raw_equal: yes
- scale_norm_decreases: yes
- pretty_eq_compact_logical: yes
- blank_eq_near_logical: yes
- wrap_pretty_eq_compact: yes
- cooccurrence_zero_edges: yes
- pollution_matches_true_near: yes
- two_hop_chain_gt_one_hop: yes

## Cost (median of 5 after 1 warmup; not an SLO)

- n=100: median_s=0.0004820000031031668 min_s=0.00047639996046200395 max_s=0.0004835000145249069 n_edges=1.0 lookups=100.0
- n=500: median_s=0.00242239999352023 min_s=0.0023983000428415835 max_s=0.0036178999580442905 n_edges=1.0 lookups=500.0
- n=1000: median_s=0.005755899997893721 min_s=0.005329500010702759 max_s=0.006124100007582456 n_edges=1.0 lookups=1000.0
- n=5000: median_s=0.030527199967764318 min_s=0.029247899947222322 max_s=0.03211209998698905 n_edges=1.0 lookups=5000.0
- n=10000: median_s=0.06550709996372461 min_s=0.06264590000500903 max_s=0.06750020000617951 n_edges=1.0 lookups=10000.0

- ratios: {'t500_over_t100': 5.025726095279178, 't1000_over_t500': 2.3761146025802495, 't5000_over_t1000': 5.303636265212262, 't10000_over_t5000': 2.145860086509666}

## Checks

- sensor_is_v1: yes
- v0_unmodified: yes
- all_fixture_expects: yes
- all_relations: yes
- near_lt_medium_lt_far: yes
- malformed_fail_closed: yes
- per_value_full_document_scan_absent: yes
- routing_unconnected: yes
- holdout_unused: yes
- freeze_unmodified: yes
- gold_unused: yes

