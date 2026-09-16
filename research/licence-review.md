# Licence review (BITE-07)

## Policy

- Do **not** download, bundle, or redistribute a real dataset until a human confirms licence + redistribution terms.
- Synthetic adapters use an explicit synthetic placeholder licence string and `local://synthetic` source.
- Ledger columns for real rows stay `TBD` with `human_approval=pending_human`.

## Checklist (per real dataset candidate)

1. Licence URI / SPDX id recorded
2. Redistribution allowed for research artifacts? (yes/no/TBD)
3. Commercial restriction? (TBD)
4. Share-alike obligations? (TBD)
5. Download source + version + checksum recorded
6. Human approval recorded before any fetch script is enabled

## Current status

| Domain category | Real dataset | Status |
| --- | --- | --- |
| observability_logs | TBD | blocked_pending_human |
| tabular_nested_machine_data | TBD | blocked_pending_human |
| repository_code | TBD | blocked_pending_human |
| long_technical_or_legal | TBD | blocked_pending_human |
| mixed_agent_tool_outputs | TBD | blocked_pending_human |
| synthetic-* (4 adapters) | synthetic | fixed (no network) |

No licence URLs for real corpora are asserted in this task.
