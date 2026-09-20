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

## 現在の freeze

```text
phase2c-dispersion-freeze-v0.2
```

v0.1 は削除していない。上書きしていない。v0.2 が supersede する。

- 残置: `benchmarks/spec/phase2c-dispersion-freeze.json`（revision `phase2c-dispersion-freeze-v0.1`）
- 現行: `benchmarks/spec/phase2c-dispersion-freeze-v0.2.json`

変更したのは Phase 2D 判定規則の曖昧さだけ。48 pair、tokenizer、prompt、length criterion、arms、secondary axes は v0.1 のまま。

evaluation は未開封。

---

## v0.2 で固定した判定

### eligible pair

次をすべて満たす pair だけが confirmatory 対象。

- Phase 1C length criterion を満たす
- instrumentation / self-check に失敗していない
- frozen canonical identity / wrapper / tokenizer contract を満たす

length criterion を外れた pair は除外し、救済しない。

### dispersion_specific_signal

eligible pair について、先に length_pi の clustered / dispersed が同じ routing/operator behavior かを見る。

同一 token 長なのに length_pi 自体が違う判断をした pair は BITE signal にしない。instrumentation / policy consistency issue として記録する。

その上で、次のいずれかがあれば `dispersion_specific_signal = true`。

- rule_pi の operator sequence が clustered / dispersed で異なる
- rule_pi の transformed / no-op 状態が clustered / dispersed で異なる
- rule_pi_rebite の recovery 発火状態が clustered / dispersed で異なる

単なる raw payload hash の違いは signal にしない（入力順序が違うため）。

evidence recall / provenance / T_total の差は必ず記録するが、それ単独では routing signal にしない。

`length_pi != rule_pi` の件数は別 endpoint として保存するが、それだけで dispersion-specific signal とはしない。

### Phase 2D verdict

- `PHASE2D_BLOCKED`: negative control / instrumentation self-check 失敗、frozen contract 破損、eligible pair が 0、その他公平な比較が成立しない
- `PHASE2D_OFFLINE_SIGNAL`: eligible ≥ 1 かつ dispersion_specific_signal ≥ 1
- `PHASE2D_OFFLINE_NO_SIGNAL`: eligible ≥ 1 かつ dispersion_specific_signal = 0

SIGNAL が 1 pair でもラベルは SIGNAL。強い一般化はしない。必ず `n_signal / n_eligible` と scale / dependency / structure / redundancy 別分布を報告する。

---

## 目的（v0.1 から不変）

evaluation/holdout を走らせることではない。本番比較条件を開封前に固定すること。

---

## 固定した primary contrast（v0.1 から不変）

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

差が出るまで threshold を調整することは禁止。

---

## 判定（Phase 2C）

```text
FROZEN_PRE_HOLDOUT
```

現行 revision: `phase2c-dispersion-freeze-v0.2`（supersedes v0.1）

evaluation は未開封。

---

## 成果物

- `src/bite_bench/phase2c.py`
- `benchmarks/spec/phase2c-dispersion-freeze.json`（v0.1、残置）
- `benchmarks/spec/phase2c-dispersion-freeze-v0.2.json`（現行）
- `spec/phase2c-dispersion-freeze.schema.json`（v0.1）
- `spec/phase2c-dispersion-freeze-v0.2.schema.json`
- `tests/test_phase2c_dispersion_freeze.py`
- 本 handover


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
