# PHASE3D-SENSOR-V1-DESIGN-FREEZE 引き継ぎ

- 担当: Grok
- 前提: Phase 3C `PHASE3C_SENSOR_SCOPED`（PR #26）
- ブランチ: `feat/phase3d-sensor-v1-design-freeze`
- 実行日: 2026-09-19
- 有料 API: **未使用**
- Phase 2 evaluation: **未使用**
- `dependency_dispersion_v0` / deterministic_v0 / RulePolicy / HIGH / LOW: **未変更・未接続**
- v1 実装: **未着手**

v0 の既知制限を消さない。実装前に v1 の範囲と edge 規則を固定する。routing にはまだ載せない。

---

## 判定

```text
PHASE3D_V1_DESIGN_FROZEN
```

設計上の自己矛盾はなかった。BITE wins / Go ではない。

---

## 残す v0 制限

- 対応は key=value / one-line JSON に限定されていた
- pretty JSON / CSV / YAML / prose は unsupported
- blank / wrap で物理行距離が歪む
- identifier 再出現を reference と誤認する
- 5000 行で約 41 秒（value atom × 全行）
- raw / normalized の routing 採用は未決定

---

## 1. Performance

v0 の「value atom ごとに全行スキャン」をアルゴリズムから除く。

v1: 文書を一度走査して identifier occurrence index を作り、value-side identifier は index lookup する。

成功条件は wall-time ではなく **全行再走査の除去**。SLO は置かない。実装後に 100 / 500 / 1000 / 5000 / 10000 行を測る。

---

## 2. Edge 規則（heuristic）

比較した candidate:

| id | 共有 env が edge か | kv one-hop | v1 |
|---|---|---|---|
| value_to_any_occurrence（v0） | なる | 取れる | primary にしない |
| value_to_value_cooccurrence | なる | 取れない | primary にしない |
| value_to_foreign_key_side | ならない | 取れる | primary の一部 |
| value_to_record_identifier | ならない | 取れる | primary の一部 |

**primary:** `value_to_key_or_record_id`

unit i の value-side identifier が、別 unit j の key-side、または閉じた record-id フィールド（`id` / `k`）の値として出たときだけ edge。同一 copy は edge にしない。

env / service / owner / label の共有値だけでは edge にしない。stopword を fixture 見て増やして救わない。

gold / answer / Phase 2 key prefix は使わない。heuristic であり、target に key-side / record-id が無い value-to-value ポインタは取りこぼす。

---

## 3. 距離単位

v1 の距離軸は **logical unit index**。物理行は diagnostic only。

- key=value: 空行は unit にしない。`=` のある非空行が 1 unit
- JSON: 文書を parse し、array of objects なら object が 1 unit。pretty と compact が同じ構造なら同じ unit 列

blank / pretty-print で dependency distance を変えない。identifier 途中 wrap は malformed であり invariance 対象外。prose は必須にしない。

---

## 4. Format scope（結果を見て広げない）

- 必須: key=value、JSON（one-line / pretty を同一 logical structure）
- optional: CSV、YAML
- out-of-scope: prose

---

## 5. 量

保持: n_edges、absolute logical-unit edge distance、normalized、component span、chain span。

この Phase では INTEGRATE 閾値を置かない。raw / normalized の routing 採用も v1 validation 前には決めない。v1 の mean は v0 の行距離と無変換では比較しない。

---

## Fixture（実測前）

Phase 2 は使わない。必須: true dep near/medium/far、同じ依存で文書長だけ変える、pretty vs compact、blank/wrap invariance、shared env/service/owner/label、無関係な同一 identifier、true edge + pollution、one-hop / two-hop / branch、no-reference、malformed。

期待関係は manifest に固定済み（near < medium < far、scale の raw 一定、共有ラベルは n_edges=0、pollution は true near と一致、など）。

---

## やっていないこと

- v1 sensor の実装
- v0 の黙った改変
- RulePolicy 接続
- holdout 再採点
- 性能閾値
- format の後付け拡大

---

## 成果物

- `benchmarks/spec/phase3d-sensor-v1-design-freeze.json`
- `src/bite_eval/phase3d_v1_freeze.py`
- `tests/test_phase3d_sensor_v1_design_freeze.py`

---

## 次

freeze どおりに `dependency_dispersion_v1` を **別モジュール** で実装する。v0 は残す。この PR ではやらない。
