# PHASE4E-FULL-KEY-REFERENCE 引き継ぎ

- 担当: Grok
- 前提: `PHASE4D_MEASUREMENT_SEMANTICS_AUDITED`
- ブランチ: `feat/phase4e-full-key-reference-v2`
- E0 protocol freeze: `9349087ab4fd5bb095a4904646243665c4464b52`
- E0 freeze blob: `911a22ff9d210de05ae799fce5c90f09c65c1029`
- Phase 4D HEAD: `8a585d2f0552541478bca5c691e4c051f5d626f3`
- 実行日: 2026-09-20
- 有料 API: **未使用**
- p3f: **未開封**
- Phase 4C: **PHASE4C_REAL_HOLDOUT_MEASURED** のまま
- Phase 4D: retrospective audit のまま
- v1 / v3 / policy v4 / planner / operators: **未変更**
- baseline / REALSTRUCT-2: **未作成**

---

## 判定

```text
PHASE4E_FULL_KEY_REFERENCE_VALIDATED
```

development validation of full-key reference identity v2。新しい holdout / confirmatory / generalization / BITE superiority ではない。

```text
Phase3S remains FAILED
Phase3Q remains FAILED
Phase4C remains MEASURED
Phase4D remains AUDITED
```

---

## Primary（fresh 20 × 4 = 80）

- exact edge / false component-prefix-suffix = 0 / 4-format 不変 / distance 1/3/4/9 exact / gate exact
- v3/v4 bridge（simple identifiers, `.` `-` なし）exact。T_high=4 carry-forward
- v4 chain_span は reachability replacement。monkeypatch なし。DFS 爆発なし
- policy v5 は v4 sensor のみ差し替え。planner は projected_actionability_plan_v1

---

## REALSTRUCT-1 retrospective（primary 合格後。判定条件ではない）

holdout / confirmatory / generalization ではない。

- hadoop-log4j / ratis-log4j: atom-aware recall 1.0 / precision 1.0（4D の v3 では 0.0 だったずれの記述）
- koel / laravel / tegra: recall/precision 1.0
- bitbake: recall 0.624、precision 1.0
- conservation safety は 12/12

---

## 成果物

- `benchmarks/spec/phase4e-full-key-reference-freeze.json`
- `src/bite_ingestion/profilers/reference_identity_v2.py`
- `src/bite_ingestion/profilers/dependency_dispersion_v4.py`
- `src/bite_ingestion/policies/conditional_texture_policy_v5.py`
- `artifacts/phase4e/exact-edge.json`
- `artifacts/phase4e/threshold-bridge.json`
- `artifacts/phase4e/format-invariance.json`
- `artifacts/phase4e/runtime-diagnostic.json`
- `artifacts/phase4e/realstruct1-retrospective.json`
- `artifacts/phase4e/full-key-reference.json`

---

## 次

sensor を REALSTRUCT-1 のスコアで再調整しない。p3f は開けない。main へ merge しない。baseline / REALSTRUCT-2 / XFER-3 は作らない。
