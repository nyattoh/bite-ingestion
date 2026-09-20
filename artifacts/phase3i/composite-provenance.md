# Phase 3I composite provenance

verdict: `PHASE3I_COMPOSITE_PROVENANCE_VALIDATED`
protocol SHA: `e6bc818ec37c2b31f33a800b4e724b10acbfb887`
Phase 3H verdict unchanged: `PHASE3H_CONDITIONAL_MAP_REQUIRED`
routing implemented: `false`

| case | ok | completeness | lineage recall | join |
|---|---|---|---|---|
| p3i-same-uri-2way | True | 1.0 | 1.0 | True |
| p3i-three-way | True | 1.0 | 1.0 | True |
| p3i-mixed-uri | True | 1.0 | 1.0 | True |
| p3i-passthrough | True | 1.0 | 1.0 | False |
| p3i-dep-edge | True | 1.0 | 1.0 | True |
| p3i-explicit-key | True | 1.0 | 1.0 | True |

malformed fail-closed:

- `p3i-malformed-joined-from-only` fail_closed=True
- `p3i-malformed-fake-span` fail_closed=True

BITE wins / Go ではない。
