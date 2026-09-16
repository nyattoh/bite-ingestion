# Error atlas — BITE-15b billed pilot **v2** (pivot)

Source: `artifacts/pilot/bite15b_billed_summary_v2.json` @ `967ec0b`.

## Transport / protocol

| Class | Count |
| --- | ---: |
| empty `answer_text` | **0 / 384** |
| row `error` | 0 |
| rate_limit | 0 |
| T_completion | min 2 / max 5 / mean ≈ 2.86 |

v1 empty×64 confounder is **cleared** on v2.

## Constraint failures (v2)

| Failure string | Count |
| --- | ---: |
| `Q < Q_baseline - delta` | 46 |
| constraints_ok | 338 |

Almost all failures sit in **`dependency_chain`**（2/48 ok ≈ 0.0417）. Other 7 families are **1.0**.

## Pattern notes

1. **Gate C = pivot**: C1 false（compressed not cheaper on mean T）, C3 false（net savings ≤ 0）, C2 true only as placeholder equality of constraint rates.
2. **No token win from compressed_passthrough**: every paired `dT_raw_minus_comp = -2` in recompute（comp slightly higher T）.
3. **Quality generally holds** except dependency_chain — treat that family as the primary error locus for follow-up, **not** as a reason to flip Go.
4. **Do not** hide the 46 Q failures behind the 0.88 aggregate ok rate alone.

## Exploratory (not primary)

High ok rates on 7/8 families are descriptive only. No post-hoc promotion to confirmatory win.

## Missing data

- checkpoint JSONL not in git
- no `output/main/failures.jsonl` yet — this atlas is pilot-scoped
