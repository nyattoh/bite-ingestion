# PHASE3F-ROUTING-CALIBRATION-FREEZE 引き継ぎ

- 担当: Grok
- 前提: Phase 3E `PHASE3E_V1_VALIDATED`（PR #28）
- ブランチ: `feat/phase3f-routing-calibration-freeze`（3E HEAD から）
- 実行日: 2026-09-19
- 有料 API: **未使用**
- Phase 2 evaluation: **未使用**
- v1 / v0 / RulePolicy / HIGH / LOW: **未変更・未接続**
- calibration 測定: **未実施**
- evaluation の routing/profiler 値: **未開封**
- threshold 値: **未決定**

データを見る前に、v1 を routing に使う場合の選び方だけを固定する。

---

## 判定

```text
PHASE3F_ROUTING_CALIBRATION_PROTOCOL_FROZEN
```

BITE wins / Go ではない。

---

## 新規 generation `p3f`

Phase 2 とは別。required format は validated 済みの key=value と JSON のみ。CSV / YAML / prose は入れない。

canonical facts / question / answer / required evidence は surface から分離。sensor 入力は `payload` / `text` だけ。gold leakage 禁止。

near / medium / far は同一 logical unit の並べ替え。padding なし（token 長は同じ multiset で揃う）。

- scale: small 8 / medium 24 / large 48 distractors
- shape: one-hop / two-hop / branch
- replica: 0,1 calibration / 2,3 evaluation
- medium の挟み: 3 unit（scale をまたいでも absolute 4）
- far: 両端（relative 固定、absolute は規模で伸びる）

---

## Split

evaluation は 3F で routing/profiler 値を出さない。Phase 3G は calibration だけ測る。

---

## Adversarial（sensor は変えない）

suffix exposure の誤 edge を 3G で測るための新規 case:

- key suffix が value と一致
- shared prefix
- shared suffix
- identifier substring だが dependency ではない
- unrelated な同一 value
- true dependency + misleading suffix

intended_edges は scorer 専用。

---

## Candidate（追加しない）

- A: `mean_edge_distance`
- B: `mean_edge_distance_norm`
- C: 事前固定の raw∧norm 2 変量ルール

選択は n_signal 最大ではない。優先順位:

1. adversarial false-positive rate を最小化
2. near < medium < far の ordering coverage
3. scale 安定性（medium の raw 一定、far の norm 一定）
4. kv / JSON の bin 一致
5. 単一 bin が calibration の 95% 以上なら失格
6. tie は A → B → C

---

## Threshold 探索（値は 3F で決めない）

3G の calibration だけで、登録済み grid を探す。evaluation を見て変えない。

目的関数は adversarial FP 最小のうえ ordering coverage。INTEGRATE 率は目的にしない。

---

## Operator 対応（候補のみ）

dispersion が高いから自動 INTEGRATE にはしない。bin は low / mid / high。

- M1: low は他 feature と合わせて INTEGRATE に寄与しうる。high はこの feature 単独では INTEGRATE しない
- M2: high が寄与しうる。low は追加 operator なし

採用は 3G。既存 RulePolicy は 3F で変更しない。

---

## 成果物

- `src/bite_bench/phase3f.py`
- `benchmarks/spec/phase3f-routing-calibration-freeze.json`
- `benchmarks/spec/phase3f-split-manifest.json`
- `tests/test_phase3f_routing_calibration_freeze.py`

---

## 次

Phase 3G で calibration split だけを測り、この規則で candidate と threshold をロックする。evaluation はまだ開けない。
