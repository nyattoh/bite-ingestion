# Morphology feature contract (v0.1 transparent)

Vector: `[b, r, s, k, a, l, p, u]` each in `[0,1]` (higher = stronger property).

| Key | Meaning |
| --- | --- |
| b | boundary clarity |
| r | redundancy / compressibility |
| s | structural regularity |
| k | cross-unit coupling proxy |
| a | anomaly sparsity / entanglement proxy |
| l | evidence locality proxy (query-conditioned when `query` provided) |
| p | provenance sensitivity proxy |
| u | uncertainty about sufficient evidence |

## Rules

- Transparent / deterministic only in BITE-08 default profiler (no semantic LLM classifier).
- Do not read `answer` / `gold_route` / `route` as features.
- File type does not assign an operator route; it may only influence continuous structure proxies.
- Malformed / NUL inputs: fail closed + elevated `u` / `a`.
- Numeric thresholds for policy remain TBD (no invented kill numbers).
