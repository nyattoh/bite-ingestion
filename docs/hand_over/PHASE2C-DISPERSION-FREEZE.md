# PHASE2C-DISPERSION-FREEZE 引き継ぎ

- 担当: Grok
- ベース: `origin/main` = `dce759efbb94ae941a86c3358b1b717da3224c14`（Phase 2A merge 後）
- 前提: Phase 2B `PHASE2B_LENGTH_CONTROL_PARTIAL`（PR #21、calibration のみ）
- ブランチ: `feat/phase2c-dispersion-freeze`
- 実行日: 2026-09-19
- 有料 API: **未使用**
- evaluation surface の token 計測 / profiler / routing / operator: **未実行**
- Phase 1C length criterion: **未変更**
- Phase 2A 設計: **未変更**

---

## 目的

evaluation/holdout を走らせることではない。本番比較条件を開封前に固定すること。

採点条件を書いて封をする作業。

---

## 固定した primary contrast

axis: **dispersion**（clustered vs dispersed）

各 evaluation canonical case について、structure × redundancy の 4 組合せを保持した pair を事前登録した。

- 12 evaluation cases × 4 pair = **48** confirmatory pairs
- 同一: canonical facts / question / answer / required evidence / scale / dependency / structure / redundancy / prompt wrapper / tokenizer contract
- 異なるもの: dispersion のみ

structure / redundancy は削除していない。primary confirmatory には混ぜない。secondary / length-confounded stress axes として残す。evaluation を見て新しい matching 方法は作らない。

---

## Length criterion（Phase 1C のまま）

- abs token delta ≤ 3
- symmetric relative delta ≤ 4%
- padding なし

Phase 2B calibration の事実: dispersion 48/48 で abs_delta = 0。

evaluation 側の delta は未確認。Phase 2D で基準を外れた pair は除外し、閾値を広げて救済しない。

---

## Phase 2D に事前登録したもの（未実行）

arms: `raw_full` / `length_pi` / `rule_pi` / `rule_pi_rebite`

primary question:

同じ facts・同じ token 長・同じ surface 形式でも、required evidence の dispersion だけが変わったとき、length_pi と rule_pi の routing/operator behavior は異なるか？

paid model accuracy は primary endpoint にしない。BITE wins も endpoint にしない。

offline endpoints: length_pi != rule_pi の pair 数、clustered/dispersed で rule_pi sequence が変わる pair 数、operator が payload を変えた pair 数、visible/recoverable recall、provenance、re-bite 発火数、T_total、raw_full との payload 差。

判定:

- `PHASE2D_OFFLINE_SIGNAL`
- `PHASE2D_OFFLINE_NO_SIGNAL`
- `PHASE2D_BLOCKED`

差が出るまで threshold を調整することは禁止。

---

## 判定（Phase 2C）

```text
FROZEN_PRE_HOLDOUT
```

evaluation は未開封。

---

## 成果物

- `src/bite_bench/phase2c.py`
- `benchmarks/spec/phase2c-dispersion-freeze.json`
- `spec/phase2c-dispersion-freeze.schema.json`
- `tests/test_phase2c_dispersion_freeze.py`
- 本 handover
