# Phase 1D confirmatory offline comparison

有料モデル精度は測っていない。BITE の優劣は主張しない。

- base main SHA: `0e50a2c54b2e56beaf749bc4e7ee28be444ca7bd`
- verdict: **PHASE1D_OFFLINE_NO_SIGNAL**
- paid_api: False
- frozen pair: `prose_narrative` vs `table_csv` (abs <= 3, rel <= 0.04, no padding)
- confirmatory rows: 96 (12 cases x 2 textures x 4 arms)

## Self-check

- negative controls ok: True (checked=12, violations=none)
- freeze manifest ok: True mismatches=none
- tokenizer remeasure ok: True

## Confirmatory lists (evaluation / holdout only)

平均値はこの一覧の代わりにならない。

### A. length_pi != rule_pi

なし

### A2. rule_pi が同一 facts で texture 間で違う判断

なし

### A3. profiler は texture で違うが sequence は同じ

- `{"facts_id": "syn-case-012", "morphology_delta": {"b": [0.35, 1.0]}, "sequence": ["CUT"]}`
- `{"facts_id": "syn-case-013", "morphology_delta": {"b": [0.35, 1.0], "l": [0.8571428571428571, 1.0], "u": [0.04285714285714287, 0.0]}, "sequence": ["CUT"]}`
- `{"facts_id": "syn-case-014", "morphology_delta": {"b": [0.35, 1.0], "l": [0.875, 1.0], "u": [0.0375, 0.0]}, "sequence": ["CUT"]}`
- `{"facts_id": "syn-case-015", "morphology_delta": {"b": [0.35, 1.0], "l": [0.875, 1.0], "u": [0.0375, 0.0]}, "sequence": ["CUT"]}`
- `{"facts_id": "syn-case-016", "morphology_delta": {"b": [0.35, 1.0], "l": [0.8571428571428571, 1.0], "u": [0.04285714285714287, 0.0]}, "sequence": ["CUT"]}`
- `{"facts_id": "syn-case-017", "morphology_delta": {"b": [0.35, 1.0]}, "sequence": ["CUT"]}`
- `{"facts_id": "syn-case-018", "morphology_delta": {"b": [0.35, 1.0]}, "sequence": ["CUT"]}`
- `{"facts_id": "syn-case-019", "morphology_delta": {"b": [0.35, 1.0], "l": [0.8571428571428571, 1.0], "u": [0.04285714285714287, 0.0]}, "sequence": ["CUT"]}`
- `{"facts_id": "syn-case-020", "morphology_delta": {"b": [0.35, 1.0], "l": [0.875, 1.0], "u": [0.0375, 0.0]}, "sequence": ["CUT"]}`
- `{"facts_id": "syn-case-021", "morphology_delta": {"b": [0.35, 1.0], "l": [0.875, 1.0], "u": [0.0375, 0.0]}, "sequence": ["CUT"]}`
- `{"facts_id": "syn-case-022", "morphology_delta": {"b": [0.35, 1.0], "l": [0.8571428571428571, 1.0], "u": [0.04285714285714287, 0.0]}, "sequence": ["CUT"]}`
- `{"facts_id": "syn-case-023", "morphology_delta": {"b": [0.35, 1.0]}, "sequence": ["CUT"]}`

### operator が実際に発火した (transformed / not no_op)

なし

### re-bite が実際に発火した

なし

### evidence recall が 1.0 未満

なし

### no-op だった case

- `syn-case-012:prose_narrative`
- `syn-case-012:table_csv`
- `syn-case-013:prose_narrative`
- `syn-case-013:table_csv`
- `syn-case-014:prose_narrative`
- `syn-case-014:table_csv`
- `syn-case-015:prose_narrative`
- `syn-case-015:table_csv`
- `syn-case-016:prose_narrative`
- `syn-case-016:table_csv`
- `syn-case-017:prose_narrative`
- `syn-case-017:table_csv`
- `syn-case-018:prose_narrative`
- `syn-case-018:table_csv`
- `syn-case-019:prose_narrative`
- `syn-case-019:table_csv`
- `syn-case-020:prose_narrative`
- `syn-case-020:table_csv`
- `syn-case-021:prose_narrative`
- `syn-case-021:table_csv`
- `syn-case-022:prose_narrative`
- `syn-case-022:table_csv`
- `syn-case-023:prose_narrative`
- `syn-case-023:table_csv`

### raw_full と payload 差がない case

- `syn-case-012:prose_narrative`
- `syn-case-012:table_csv`
- `syn-case-013:prose_narrative`
- `syn-case-013:table_csv`
- `syn-case-014:prose_narrative`
- `syn-case-014:table_csv`
- `syn-case-015:prose_narrative`
- `syn-case-015:table_csv`
- `syn-case-016:prose_narrative`
- `syn-case-016:table_csv`
- `syn-case-017:prose_narrative`
- `syn-case-017:table_csv`
- `syn-case-018:prose_narrative`
- `syn-case-018:table_csv`
- `syn-case-019:prose_narrative`
- `syn-case-019:table_csv`
- `syn-case-020:prose_narrative`
- `syn-case-020:table_csv`
- `syn-case-021:prose_narrative`
- `syn-case-021:table_csv`
- `syn-case-022:prose_narrative`
- `syn-case-022:table_csv`
- `syn-case-023:prose_narrative`
- `syn-case-023:table_csv`

## Confirmatory counts (descriptive means only)

- n_rows=96 n_failed=0 n_no_op=72 n_transformed=0 n_pass_through=24
- mean recall_vis=1.0 recall_rec=1.0 provenance=1.0
- mean T_total=24.0 mean payload_chars=94.33333333333333

## Development / calibration (not confirmatory)

- n_rows=96
- length_pi != rule_pi: 0
- operator fired: 0
- rebite fired: 0

## A-E (confirmatory, not a win/loss claim)

- A routing: length_pi != rule_pi = 0; rule_pi texture disagreement = 0
- A profiler: 12 facts_id had a morphology delta between prose and table with the same sequence
- B evidence loss: recall_lt_1 = 0
- C re-bite fired = 0
- D extra work: operator_fired = 0; no-op cases = 24
- E vs raw_full: payload-identical cases = 24 of 24 surfaces

## Per confirmatory row

| case_id | method | status | sequence | recall_vis | recall_rec | prov | T_rebite | T_total | vs_raw_chars | no_op |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|
| `syn-case-012:prose_narrative` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 25 | 0 | False |
| `syn-case-012:prose_narrative` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 25 | 0 | True |
| `syn-case-012:prose_narrative` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 25 | 0 | True |
| `syn-case-012:prose_narrative` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 25 | 0 | True |
| `syn-case-012:table_csv` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 19 | 0 | False |
| `syn-case-012:table_csv` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 19 | 0 | True |
| `syn-case-012:table_csv` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 19 | 0 | True |
| `syn-case-012:table_csv` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 19 | 0 | True |
| `syn-case-013:prose_narrative` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 23 | 0 | False |
| `syn-case-013:prose_narrative` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 23 | 0 | True |
| `syn-case-013:prose_narrative` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 23 | 0 | True |
| `syn-case-013:prose_narrative` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 23 | 0 | True |
| `syn-case-013:table_csv` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 17 | 0 | False |
| `syn-case-013:table_csv` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 17 | 0 | True |
| `syn-case-013:table_csv` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 17 | 0 | True |
| `syn-case-013:table_csv` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 17 | 0 | True |
| `syn-case-014:prose_narrative` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 27 | 0 | False |
| `syn-case-014:prose_narrative` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 27 | 0 | True |
| `syn-case-014:prose_narrative` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 27 | 0 | True |
| `syn-case-014:prose_narrative` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 27 | 0 | True |
| `syn-case-014:table_csv` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 22 | 0 | False |
| `syn-case-014:table_csv` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 22 | 0 | True |
| `syn-case-014:table_csv` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 22 | 0 | True |
| `syn-case-014:table_csv` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 22 | 0 | True |
| `syn-case-015:prose_narrative` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 26 | 0 | False |
| `syn-case-015:prose_narrative` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 26 | 0 | True |
| `syn-case-015:prose_narrative` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 26 | 0 | True |
| `syn-case-015:prose_narrative` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 26 | 0 | True |
| `syn-case-015:table_csv` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 21 | 0 | False |
| `syn-case-015:table_csv` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 21 | 0 | True |
| `syn-case-015:table_csv` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 21 | 0 | True |
| `syn-case-015:table_csv` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 21 | 0 | True |
| `syn-case-016:prose_narrative` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 30 | 0 | False |
| `syn-case-016:prose_narrative` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 30 | 0 | True |
| `syn-case-016:prose_narrative` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 30 | 0 | True |
| `syn-case-016:prose_narrative` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 30 | 0 | True |
| `syn-case-016:table_csv` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 25 | 0 | False |
| `syn-case-016:table_csv` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 25 | 0 | True |
| `syn-case-016:table_csv` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 25 | 0 | True |
| `syn-case-016:table_csv` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 25 | 0 | True |
| `syn-case-017:prose_narrative` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 29 | 0 | False |
| `syn-case-017:prose_narrative` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 29 | 0 | True |
| `syn-case-017:prose_narrative` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 29 | 0 | True |
| `syn-case-017:prose_narrative` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 29 | 0 | True |
| `syn-case-017:table_csv` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 24 | 0 | False |
| `syn-case-017:table_csv` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 24 | 0 | True |
| `syn-case-017:table_csv` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 24 | 0 | True |
| `syn-case-017:table_csv` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 24 | 0 | True |
| `syn-case-018:prose_narrative` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 25 | 0 | False |
| `syn-case-018:prose_narrative` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 25 | 0 | True |
| `syn-case-018:prose_narrative` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 25 | 0 | True |
| `syn-case-018:prose_narrative` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 25 | 0 | True |
| `syn-case-018:table_csv` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 19 | 0 | False |
| `syn-case-018:table_csv` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 19 | 0 | True |
| `syn-case-018:table_csv` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 19 | 0 | True |
| `syn-case-018:table_csv` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 19 | 0 | True |
| `syn-case-019:prose_narrative` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 23 | 0 | False |
| `syn-case-019:prose_narrative` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 23 | 0 | True |
| `syn-case-019:prose_narrative` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 23 | 0 | True |
| `syn-case-019:prose_narrative` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 23 | 0 | True |
| `syn-case-019:table_csv` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 17 | 0 | False |
| `syn-case-019:table_csv` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 17 | 0 | True |
| `syn-case-019:table_csv` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 17 | 0 | True |
| `syn-case-019:table_csv` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 17 | 0 | True |
| `syn-case-020:prose_narrative` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 27 | 0 | False |
| `syn-case-020:prose_narrative` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 27 | 0 | True |
| `syn-case-020:prose_narrative` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 27 | 0 | True |
| `syn-case-020:prose_narrative` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 27 | 0 | True |
| `syn-case-020:table_csv` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 22 | 0 | False |
| `syn-case-020:table_csv` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 22 | 0 | True |
| `syn-case-020:table_csv` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 22 | 0 | True |
| `syn-case-020:table_csv` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 22 | 0 | True |
| `syn-case-021:prose_narrative` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 26 | 0 | False |
| `syn-case-021:prose_narrative` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 26 | 0 | True |
| `syn-case-021:prose_narrative` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 26 | 0 | True |
| `syn-case-021:prose_narrative` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 26 | 0 | True |
| `syn-case-021:table_csv` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 21 | 0 | False |
| `syn-case-021:table_csv` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 21 | 0 | True |
| `syn-case-021:table_csv` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 21 | 0 | True |
| `syn-case-021:table_csv` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 21 | 0 | True |
| `syn-case-022:prose_narrative` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 30 | 0 | False |
| `syn-case-022:prose_narrative` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 30 | 0 | True |
| `syn-case-022:prose_narrative` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 30 | 0 | True |
| `syn-case-022:prose_narrative` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 30 | 0 | True |
| `syn-case-022:table_csv` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 25 | 0 | False |
| `syn-case-022:table_csv` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 25 | 0 | True |
| `syn-case-022:table_csv` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 25 | 0 | True |
| `syn-case-022:table_csv` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 25 | 0 | True |
| `syn-case-023:prose_narrative` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 29 | 0 | False |
| `syn-case-023:prose_narrative` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 29 | 0 | True |
| `syn-case-023:prose_narrative` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 29 | 0 | True |
| `syn-case-023:prose_narrative` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 29 | 0 | True |
| `syn-case-023:table_csv` | raw_full | pass_through | `-` | 1.0 | 1.0 | 1.0 | 0 | 24 | 0 | False |
| `syn-case-023:table_csv` | length_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 24 | 0 | True |
| `syn-case-023:table_csv` | rule_pi | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 24 | 0 | True |
| `syn-case-023:table_csv` | rule_pi_rebite | no_op | `CUT` | 1.0 | 1.0 | 1.0 | 0 | 24 | 0 | True |
