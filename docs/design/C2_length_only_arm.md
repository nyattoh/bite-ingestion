# C2 length-only arm 設計メモ

**Date**: 2026-09-16  
**Status**: Design only — implementation deferred  
**Context**: BITE-16 v2 pivot (`c1=False c2=True c3=False`)

## 1. Problem

v2 pivot で C2 が `True` だが、現在の C2 placeholder は **形態素vs長さの真の勝利ではない**（BITE-16.md § Do-not）。

長さの影響を制御せずに morphology-conditioned policy を評価しても、差分が長さ由来か形態素由来か分離できない。

## 2. Goal

**length-only arm** を追加し、長さ制御を実施する：

- 形態素を無視し、token count / char length のみで operator sequence を決定
- 既存 morphology-conditioned policy との paired 比較を可能にする
- 長さが同一のペアで形態素の効果を isolate する

## 3. Proposed Interface

### 3.1 Existing Infrastructure (reuse)

| Component | Path | Role |
| --- | --- | --- |
| `LengthOnlyPolicy` | `src/bite_ingestion/policies/length_policy.py` | 決定論的 length-Π |
| `LengthPiBaseline` | `src/bite_eval/baselines/length_pi.py` | eval wrapper |
| Config | `configs/policies/length_pi.json` | bands: short/medium/long |
| Fixtures | `output/policy-fixtures/length_matched_pair_*.json` | matched pair examples |

### 3.2 Integration Points

```
Input:
  - morphology: Mapping[str, float]  (ignored)
  - budget: {"n_tokens": int, "char_len": int}

Output:
  - sequence: List[OperatorId]  # e.g. [CUT, REDUCE]
  - decision: PolicyDecision with rules_fired
```

length-Π は既に `LengthOnlyPolicy.propose()` として実装済み。

### 3.3 Proposed Additions (implementation scope)

1. **Evaluation harness**: `bite_eval` に length_pi を arm として登録
2. **Paired design**: morphology policy と同一 N_pilot 入力で実行し、差分を記録
3. **Matched-pair filter**: 同一 token count のペア抽出ロジック
4. **Metrics**: paired comparison (McNemar / sign test) + effect size

## 4. Evaluation Plan (out-of-scope now)

将来の実装 PR では以下を測定：

| Item | Method |
| --- | --- |
| Paired accuracy | morphology policy vs length-Π on matched pairs |
| Token-length bins | stratify by short/medium/long |
| Morphology sensitivity | compare sequence diffs where morphology differs |
| Constraint satisfaction | `constraints_ok_rate` per arm |

**Out-of-scope (this design only):**

- ❌ 有料 API call
- ❌ Full 384 pilot rerun
- ❌ Threshold edits
- ❌ Code changes
- ❌ `aggregates.parquet` generation

## 5. Risks / Open Questions

1. **Calibration**: 現在 `TBD_CALIBRATE` の cutpoints は synthetic。実データから決める基準は？
2. **Matched pair coverage**: token count 完全一致のペアが少ない場合、length bins での緩和は許容するか？
3. **Path B dependency**: `dependency_chain` 修正後の 48-call family slice と length-only arm の評価順序？

## 6. Acceptance Criteria (future implementation PR)

実装 PR は以下を満たす：

- [ ] `bite_eval` に `length_pi` arm を登録（config + runner）
- [ ] Matched-pair extraction logic 実装（test coverage）
- [ ] Paired comparison metrics 出力（CSV + summary JSON）
- [ ] `analysis/` に結果レポート追加（形態素効果の isolation）
- [ ] All tests pass (offline only, no paid API)
- [ ] No threshold changes to existing policies
- [ ] AGENTS.md に従い hand_over doc 更新

---

**Next**: 人間が未解決 risks を判断後、実装スライスを切る。
