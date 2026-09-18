# Phase 2D confirmatory offline evaluation

有料モデル精度は測っていない。BITE の優劣は主張しない。
判定規則は Phase 2C v0.2 のみ。

- verdict: **PHASE2D_OFFLINE_NO_SIGNAL**
- freeze: `phase2c-dispersion-freeze-v0.2`
- n_signal / n_eligible: 0 / 48
- n_planned: 48 length_matched: 48
- n_excluded_length: 0
- n_consistency_issue: 0
- n_pairs_length_pi_neq_rule_pi (endpoint, not signal): 48
- confirmatory rows: 384 (max 384)
- paid_api: False
- evaluation_opened: True

## Self-check

- freeze v0.2 ok: True
- negative controls ok: True

## Breakdowns (n_signal / n_eligible)

**scale**

- large: 0/16 (planned 16)
- medium: 0/16 (planned 16)
- small: 0/16 (planned 16)

**dependency**

- chain3: 0/24 (planned 24)
- direct: 0/24 (planned 24)

**structure**

- flat: 0/24 (planned 24)
- nested: 0/24 (planned 24)

**redundancy**

- high: 0/24 (planned 24)
- low: 0/24 (planned 24)

## Recorded, not counted as dispersion signal

- raw payload hash differs: 48
- recall differs: 0
- provenance differs: 0
- T_total differs: 2
- length_pi != rule_pi pairs: 48

## Signal pairs

なし
