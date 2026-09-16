# BITEBench generation (BITE-06)

## Goal

Counterfactual **same facts / different texture** surfaces for evaluation-first (Pivot-to-bench) work.

## Contract

- Canonical identity: `facts`, `question`, `answer`, `required_evidence_ids`
- Textures change **surface form only**
- Real dataset names / licences / human fact-identity locks remain `TBD` (BITE-07)
- No architecture-superiority claims

## Families

`prose_narrative`, `table_csv`, `nested_json`, `event_logs`, `code_config`, `mixed_payload`

## Reproduce

```bash
python -m bite_bench.cli --seed 0 --out benchmarks/frozen-v0.1/syn-case-000.json
```

Generator version is embedded in each bundle (`generator_version`).
