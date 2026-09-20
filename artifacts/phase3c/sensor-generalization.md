# Phase 3C dependency-dispersion sensor generalization

development fixtures only。Phase 2 evaluation は未使用。routing 未接続。
dependency_dispersion_v0 は未変更。有料 API 未使用。

- verdict: **PHASE3C_SENSOR_SCOPED**
- sensor: `dependency_dispersion_v0` primary `mean_edge_distance`
- routing feature choice: not_decided

## Quantity meaning

- `mean_edge_distance`: absolute dependency separation (line-index gap)
- `mean_edge_distance_norm`: relative dependency separation (gap / (n_lines-1))
- routing にどちらを使うかは未決定

## Scale

- abs_short: n_lines=9 raw=4.0 norm=0.5
- abs_medium: n_lines=25 raw=4.0 norm=0.16666666666666666
- abs_long: n_lines=85 raw=4.0 norm=0.047619047619047616

- rel_12: n_lines=12 raw=11.0 norm=1.0
- rel_24: n_lines=24 raw=23.0 norm=1.0
- rel_48: n_lines=48 raw=47.0 norm=1.0

## Formats

- key_value: predeclared=supported observed=supported n_edges=1.0 raw=1.0
- oneline_json: predeclared=supported observed=supported n_edges=1.0 raw=1.0
- pretty_json: predeclared=unsupported observed=unsupported n_edges=0.0 raw=0.0
- compact_json_one_line: predeclared=unsupported observed=unsupported n_edges=0.0 raw=0.0
- csv: predeclared=unsupported observed=unsupported n_edges=0.0 raw=0.0
- yaml: predeclared=unsupported observed=unsupported n_edges=0.0 raw=0.0
- prose: predeclared=unsupported observed=unsupported n_edges=0.0 raw=0.0
- blank_lines: predeclared=supported observed=supported n_edges=1.0 raw=2.0
- wrapped_between: predeclared=supported observed=supported n_edges=1.0 raw=2.0
- wrapped_mid_identifier: predeclared=unsupported observed=unsupported n_edges=0.0 raw=0.0

## False-positive co-occurrence

- shared_env: n_edges=1.0 raw=1.0
- shared_service: n_edges=1.0 raw=1.0
- shared_owner: n_edges=1.0 raw=1.0
- shared_category: n_edges=1.0 raw=1.0
- unrelated_records_same_identifier: n_edges=1.0 raw=1.0
- true_edge_plus_shared_label: n_edges=2.0 raw=3.5

## Cost

- n=100: wall_time_s=0.011458499997388572 n_edges=1.0 n_lines=100
- n=500: wall_time_s=0.24310620001051575 n_edges=1.0 n_lines=500
- n=1000: wall_time_s=0.9179841000004672 n_edges=1.0 n_lines=1000
- n=5000: wall_time_s=41.4752368000336 n_edges=1.0 n_lines=5000

- t5000/t1000=45.180779057080066 (linear=5, quadratic=25; not an SLO)

## Checks

- abs_raw_equal: yes
- abs_norm_decreases: yes
- rel_raw_increases: yes
- rel_norm_equal: yes
- kv_supported: yes
- oneline_json_supported: yes
- pretty_json_unsupported: yes
- csv_unsupported: yes
- yaml_unsupported: yes
- prose_unsupported: yes
- compact_single_line_no_cross_line_edge: yes
- blank_inflates_raw: yes
- cooccurrence_creates_edges: yes
- shared_label_pollutes_mean: yes
- cannot_distinguish_reference_from_cooccurrence: yes
- format_status_matches_predeclaration: yes
- sensor_unrevised: yes
- holdout_unused: yes
- routing_unconnected: yes

## Limits

- raw mean_edge_distance is absolute line-index separation
- mean_edge_distance_norm is that quantity divided by (n_lines-1)
- pretty JSON / CSV / YAML / prose are outside the v0 extractor
- blank lines and wrapping change line-index distances
- shared env/service/owner/label identifiers become edges
- reference vs mere co-occurrence is not distinguished

