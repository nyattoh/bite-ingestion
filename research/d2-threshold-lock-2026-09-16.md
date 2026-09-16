# D-2 閾値ロック v0.1 — 委任に基づく決め打ち（非実験）

- **作成日**: 2026-09-16（ユーザー時刻帯 UTC+9 / JST 相当）
- **役割**: Gate C 再開前の **数値・品質定義の v0.1 ロック**。Go 判定はこのロック後に可能になるが、**本ジョブでは Gate C を実行しない**。
- **委任根拠**: 本人委任「広く知見を集めて適切に決めて」（適当＝雑ではなく適切）。
- **拘束**: 出典なし数字禁止。arXiv:2609.15964 の報告値（含む 98.0%）は着想のみ・数値ソース不可。Pivot-to-bench 維持。ユーザー直送・購入・公開・push・有料実験・Gate C 実行なし。
- **前提**: `d2-threshold-candidates-2026-09-16.md`、`bite-02`–`04`、`PAPER_OUTLINE.md`；追加文献は §7。

**ラベル凡例**: 【根拠＝文献】／【根拠＝慣行】／【根拠＝設計】／【実測＝文書】

---

## 1. メタ

| 項目 | 内容 |
|---|---|
| 文書種別 | **v0.1 決め打ちロック**（preregistration 数値確定）。候補調査の後継 |
| 委任 | 本人委任に基づき、候補空欄を本 MD で埋める |
| 実験状態 | **未実行**。Gate C / BITE-14 pilot / 有料 API **本ジョブでは行わない** |
| Go 判定 | ロック後に**可能になる**が、本ジョブでは **実行しない** |
| 公式暫定 | **Pivot-to-bench**（BITE-01）【実測＝文書】。architecture Survive 断定禁止 |
| ドメイン | morphology-aware ingestion / BITEBench / matched-quality cost。臨床 QA attribution（2609.15964）とは主ドメイン不一致 |
| 見直し | §6 トリガでのみ再オープン |

---

## 2. Q 定義（単位）

### 2.1 主指標 \(Q\)（matched-quality 制約に使用）

| 項目 | ロック内容 |
|---|---|
| **定義** | **task accuracy**：gold \(y^\star\) との一致率（二値正誤の平均）。尺度 \([0,1]\)（報告時は百分率可だが制約式は \([0,1]\)） |
| **単位** | 無次元割合（accuracy） |
| **baseline** | 同一 task・同一 target model・同一 effort の **Raw full context** 条件の \(Q\) を \(Q_{\mathrm{baseline}}\) とする【根拠＝設計＝bite-02/04・OUTLINE §8】 |
| **rubric** | タスクに rubric がある場合は **別表で報告**するが、v0.1 の制約 \(Q(\pi)\ge Q_{\mathrm{baseline}}-\delta\) の \(Q\) には **用いない**（主 \(Q\) を単一に保つ）【根拠＝設計】 |
| **複合** | accuracy と rubric / claim-support の加重合成は **v0.1 不採用**（解釈不能・閾値汚染）【根拠＝設計】 |

### 2.2 副指標（制約外・探索的）

| 指標 | 扱い |
|---|---|
| Rubric score | 存在する場合のみ並行観測。探索的 |
| Claim-support / CSR・CCR 系（2609.15964 着想） | **副指標として並行観測可**。主 \(Q\)・\(\delta\)・Go 線に **入れない**【根拠＝設計／candidates M3–M4＝適用不可】 |
| visible / recoverable evidence recall | 制約の \(\rho\) 側（§3）。\(Q\) と混同しない |
| \(\mathrm{Prov}\) | 制約の \(\eta\) 側 |

### 2.3 「98%」を \(Q\) に直結しない理由

1. 本人仮「98%以上？」は **未確定**であり、candidates MD で非ロックと明記済み【実測＝文書＝candidates §3】。
2. arXiv:2609.15964 Abstract / Table 1 の **98.0%** は claude-opus-5 の **verbatim quote 付与率（Covered/Verbatim）** であり、完全裏付け（CCR **37.1%**）でも、task accuracy でも、matched-quality でもない【根拠＝文献＝Zhang et al. 2026】。
3. ドメイン不一致（臨床 QA attribution ≠ BITEBench ingestion）のため、当該 % の直写は **適用不可**【根拠＝設計＝candidates 総合判定】。
4. よって **98% を \(Q\)・\(\delta\)・\(\rho\)・\(\eta\)・Go いずれにも使用しない**。

---

## 3. ロック表（v0.1）

制約式（再掲・BITE-02/04）:

\[
\min_{\pi}\; T_{total}(\pi)
\quad\mathrm{s.t.}\quad
Q(\pi)\ge Q_{\mathrm{baseline}}-\delta,\;
\mathrm{Recall}^{\mathrm{vis}}_{evidence}(\pi)\ge\rho_{\mathrm{visible}},\;
\mathrm{Recall}^{\mathrm{rec}}_{evidence}(\pi)\ge\rho_{\mathrm{recoverable}},\;
\mathrm{Prov}(\pi)\ge\eta
\]

| 記号 | ロック値 | 根拠タグ | 短い理由 |
|---|---|---|---|
| \(\delta\) | **0.05**（絶対差；accuracy 尺度上 5 percentage points） | 【根拠＝慣行／文献】 | 非劣性マージンは文脈依存で万能則はないが、絶対差 **5–10 pp** 帯が実務で多用（死亡率 NI レビュー中央値絶対 9%；腫瘍学 response 平均約 12.7%）。EMA は臨床・統計の事前正当化を要求。LLM eval では 3 pp 検出に約 1000 問が目安（Miller 2024）→ v0.1 で「matched」を主張しつつ精密 power 捏造を避けるため、**やや緩いが慣行内の 5 pp** を採用。0.01 は過密・過大 \(N\)、0.10+ は matched 主張が弱い |
| \(\rho_{\mathrm{visible}}\) | **0.50** | 【根拠＝設計】 | BITE-03/04：初回落下を許す設計。visible=1.0 強制は Recover の存在意義を消す。gold \(\mathrm{Ev}^\star\) の半数未満 visible は degenerate（ほぼ空 \(E\)）に近いため下限 0.50 |
| \(\rho_{\mathrm{recoverable}}\) | **0.90** | 【根拠＝設計】 | Recover 後（\(E\cup\) \(R\) 経由取得可能）で gold \(\mathrm{Ev}^\star\) の大部分を覆うことを要求。H4（回復可能性）と整合。1.00 は計測ノイズ・境界ケースで常時 `constraint_fail` になりやすい |
| \(\eta\) | **0.95** | 【根拠＝設計】 | \(\mathrm{Prov}=\) packet 必須 provenance フィールド完備率（§3.1）。BITE-03 必須キー（`source_uri`/`version`/`span`/`unit_id` 等）と整合。0.95 でほぼ完備を要求しつつ単一欠損の即失格を避ける |
| \(J\) | **3** | 【根拠＝慣行／設計】 | Bounded Recover。IterCOMP は反復上限 **5**、平均反復は hop 数に応じ約 2–3 帯。無制限 agent 禁止（BITE-02/03）。3 は「数回の定型回復」と近傍慣行の間 |
| \(B_r\)（\(B_r\)） | **\(\min(4096,\ \lfloor 0.5\cdot T_{\mathrm{in}}(\mathrm{raw})\rfloor)\)** 追加 token（Recover 全 call 累計の in+out） | 【根拠＝設計】 | 計算可能な上限。raw 入力の半分か 4096 の小さい方。タスク規模に比例しつつ絶対キャップで暴走防止。ledger に累計を記録 |
| \(N_{\mathrm{pilot}}\) | **合成 family あたり 24** instance（Gate C / BITE-14 想定） | 【根拠＝慣行／設計】 | Julious (2005) pilot 目安 **12/群**（分散推定・実現可能性；検出力主張ではない）。family 内のばらつき見積りのため 12 を超え **24**。精密 power は行わない |
| \(N_{\mathrm{full}}\) | **合成 family あたり 100** instance | 【根拠＝慣行／設計】 | Pilot 後の拡大。OLMES/HELM 系は大規模ベンチで上限サンプリング慣行あり；Miller の「3 pp・α=0.05・power 80% → 約 1000」は**モデル差検出**の例示であり、本ロックの \(\delta=0.05\)・family 分割・pilot 二段と目的が異なるため **捏造の精密 power はしない**。8 synthetic family ×100 ≈ 800 を full 目標の目安とする |
| \(N_{\mathrm{real}}\) | **ライセンスクリア後に別登録**（本 v0.1 では合成優先） | 【根拠＝設計＝bite-04 TB-4】 | real workload は TB；本ロックは合成で Gate C 可能化 |
| \(\alpha\) | **0.05**（確認的；両側） | 【根拠＝慣行】 | 実験科学・LLM eval 報告の標準有意水準 |
| 多重比較補正 | **確認的集合に Holm**；それ以外は探索的宣言・未補正または FDR を明示分離 | 【根拠＝慣行／文献】 | 確認的を少数に絞り探索と分離する事前登録慣行（Simmons et al.; Holm は Bonferroni より検出力高い FWER 制御） |
| 確認的主仮説集合 | **C1** H2: 制約充足下で \(T_{total}\) が Raw および事前指定「最良単一戦略」baseline（adaptive chunking **または** universal REDUCE の一方を解析前に1つ固定）より改善；**C2** H1: transparent \(\mathbf{m}\) が length-only に対し sequence 予測の増分；**C3** H6: overhead 込み純節約の符号が正。各 family 集約規則は解析プロトコルで固定 | 【根拠＝設計＝bite-04 §7 Go】 | Go の核3+1のうち統計検定に載せるものを3本に圧縮。H3/H4/H5 および claim-support は探索的 |
| Oracle 予算 | **合法 sequence 全列挙**（正規形部分列・各 op 高々1・非空 → 最大 **15**）。task instance あたり最大 **15** 回の \(T_{total}\) 評価 | 【根拠＝設計】 | \(\mathcal{O}\) が4元で空間が小さいため列挙が計算可能上限。追加ランダム探索は不要 |
| タイブレーク | (1) 制約充足；(2) より小さい \(T_{total}\)；(3) より短い \(\|\pi\|\)（op 数）；(4) sequence の辞書式順序（CUT≺UNTANGLE≺REDUCE≺INTEGRATE） | 【根拠＝設計】 | BITE-03「同点は事前タイブレーク」。決定的・再現可能 |
| Cache 計上 | **主報告 \(T_{total}\)**＝条件間で同一の provider **billed / 実課金トークン**方針。加えて **logical presented tokens** を別欄。キャッシュ割引の有無を全条件で一致させ、混在禁止（BITE-02 DC-3/DC-5） | 【根拠＝設計】 | 二重計上回避と baseline 公平性。provider 差は実験前に1方針へ固定 |

### 3.1 \(\mathrm{Prov}\) / \(\eta\) の操作定義

【根拠＝設計＝BITE-03 packet】

- 対象: 各 \(E\) item の `provenance`（`source_uri`, `version`, `span`）および各 \(R\) entry の `locator`＋`unit_id`。
- \(\mathrm{Prov}(\pi)=\)（必須フィールドが欠落していない item/entry 数）／（item+entry 総数）。
- self-reported coverage は \(\mathrm{Prov}\) に含めない。

### 3.2 Recall 分表の操作定義

【根拠＝設計＝BITE-02/03】

- \(\mathrm{Recall}^{\mathrm{vis}}=\) gold \(\mathrm{Ev}^\star\) unit のうち visible \(E\) に含まれる割合。
- \(\mathrm{Recall}^{\mathrm{rec}}=\) gold \(\mathrm{Ev}^\star\) unit のうち、\(E\) にあるか、\(R\) 上で `recoverable=true` かつ locator 有効なものに含まれる割合（**実際に Recover を走らせた後**の最終被覆でも可；報告時に「potential vs realized」を注記）。
- 単一スコアへの潰し禁止。

---

## 4. 代替案と棄却理由

| パラメータ | 棄却した代替 | 棄却理由 |
|---|---|---|
| \(Q\) | 98% 閾値そのものを \(Q\) にする | 単位が citation coverage；ドメイン不一致；本人仮未確定【根拠＝文献／設計】 |
| \(Q\) | CCR/CSR を主 \(Q\) | matched-quality・cost 制約の主軸は task 正答。検証可能性は副指標【根拠＝設計＝candidates】 |
| \(Q\) | accuracy+rubric 複合 | 重み恣意・δ解釈不能【根拠＝設計】 |
| \(\delta=0.01\) | 過密 NI | Miller 例示でも 3 pp に大規模 \(N\)；pilot 二段と非整合。精密 power 捏造を誘発【根拠＝慣行】 |
| \(\delta=0.10\) または相対 10% of \(Q_{\mathrm{baseline}}\) | 緩すぎ／baseline 依存で解釈がぶれる | 「matched-quality」主張が弱い；相対%は低 baseline で絶対に過大許容【根拠＝設計】 |
| \(\delta\) を 2609.15964 の % から逆算 | 論文に matched-quality なし | 【適用不可＝candidates M9–M10】 |
| \(\rho_{\mathrm{visible}}=1.0\) | 初回全証拠必須 | Recover/H4 を無効化；設計契約と矛盾【根拠＝設計】 |
| \(\rho_{\mathrm{visible}}=0.90\) かつ recover 緩い | 初回高要求 | 「落とせる設計」に反する；圧縮系の意義が薄い【根拠＝設計】 |
| \(\rho_{\mathrm{recoverable}}=1.0\) | 完全被覆強制 | 境界・注釈ノイズで常時 fail；0.90 で十分厳しい【根拠＝設計】 |
| \(\eta=1.0\) | 完全 Prov | 同上；0.95 で実務的 |
| \(\eta=\) VCR 直写（例 98.9%） | 単位不一致 | VCR≠packet 完備【根拠＝文献／candidates M2】 |
| \(J=1\) | 回復ほぼ無し | H4・adversarial_omission を評価不能【根拠＝設計】 |
| \(J=5\) または無制限 | IterCOMP 上限に合わせる／agent 化 | 無制限禁止；平均 2–3 帯なら 3 で足りる設計判断【根拠＝慣行／設計】 |
| \(B_r\) 無制限 or タスク非依存の巨大固定のみ | 暴走・不公平 | 計算可能・規模比例の min(cap, 0.5 raw) を採用【根拠＝設計】 |
| \(N_{\mathrm{pilot}}=12\) のみ | Julious 最小 | family 内 texture ばらつき見積りに薄い → 24【根拠＝慣行＋設計】 |
| \(N_{\mathrm{full}}=1000\)/family | Miller 3 pp 例の直写 | 目的・δ・family 構造が異なる；コストと捏造 power のリスク【根拠＝設計】 |
| \(\alpha=0.01\) | より厳格 | 確認的少数＋Holm で Type I は制御；初回ベンチで過保守【根拠＝慣行】 |
| 全指標に Bonferroni | 過剰保守 | 確認的を絞った上で Holm【根拠＝慣行】 |
| Oracle をランダム探索のみ | 空間が小さいのに近似 | 15 列挙が厳密かつ計算可能【根拠＝設計】 |
| Cache を logical のみ | 実コストと乖離 | billed を主、logical を併記【根拠＝設計＝DC-3】 |

---

## 5. ロック宣言

**以下を v0.1 としてロックする。**

- **日付**: 2026-09-16（UTC+9）
- **委任根拠**: 本人委任「広く知見を集めて適切に決めて」に基づく決め打ち。雑な丸めではなく、非劣性マージン慣行・LLM eval 統計慣行・BITE-02/03/04 契約・近傍システム（IterCOMP 反復上限）を照合した選定。
- **ロック対象**: §2 の \(Q\) 定義；§3 表の \(\delta,\rho_{\mathrm{visible}},\rho_{\mathrm{recoverable}},\eta,J,B_r,N_{\mathrm{pilot}},N_{\mathrm{full}},\alpha,\) 多重比較方針、確認的仮説集合、oracle 予算、タイブレーク、cache 計上方針。
- **明示的にロックしない**: 2609.15964 の報告 %（98.0% 等）；real-data \(N\)；有料 API 予算額（TB-6）；名称案 B の人間最終承認（TB-1）。
- **Pivot-to-bench**: 維持。本ロックは評価契約の数値であり、architecture Survive の証明ではない。
- **Gate C**: 本ロックにより Go 判定の**前提**は満たし得るが、**本ジョブでは Gate C / 実験 / 購入 / 公開 / push / ユーザー直送を実行しない**。

---

## 6. 見直しトリガ（再オープン条件）

次のいずれかを満たす場合のみ v0.1 を reopen し、差分を日付付きで記録する:

1. **Pilot（BITE-14）** で分散・欠損・`constraint_fail` 率が事前想定を大きく超え、\(N_{\mathrm{full}}\) または \(\delta\) の再校正が必要と文書化できるとき。
2. **計測定義の欠陥**（例: Prov フィールド欠落定義が実装不能、Recall 注釈不一致）が Gate B 実装で判明したとき。
3. **本人が明示的に再委任**したとき（数値選好の変更を含む）。
4. **外部制約**（ライセンス・倫理・商標・API 会計仕様変更）が cache / \(N_{\mathrm{real}}\) / 名称に影響するとき。
5. **確認的仮説集合の変更**が必要な設計変更（正規形拡張の採択等）が BITE-04 TB-7 で決まったとき。

再オープン時も **出典なし数字禁止**；98% の \(Q\) 転用は引き続き禁止。

---

## 7. 出典一覧

### ローカル契約・候補

1. `/workspace/path-a/bite-ingestion/d2-threshold-candidates-2026-09-16.md` — 借り候補・98% 非ロック・適用不可判定  
2. `/workspace/path-a/bite-ingestion/bite-02-2026-09-16.md` — 制約式、\(T_{total}\)、Recover、visible/recoverable  
3. `/workspace/path-a/bite-ingestion/bite-03-2026-09-16.md` — packet、\(\mathcal{Q}_{req}\)、\(J,B_r\) 未定数値の受け皿  
4. `/workspace/path-a/bite-ingestion/bite-04-2026-09-16.md` — H1–H6、Go、統計案、TB  
5. `/workspace/uploads/bite-ingestion/PAPER_OUTLINE.md` — §4.4–4.5、§6–9、§13  

### 公開文献・ガイドライン（数値選定の根拠）

6. Zhang, J., et al. (2026). *Verifiable by Construction…* arXiv:2609.15964 — **着想のみ**；98.0% は citation coverage【文献】  
7. EMA (2005/更新系). *Guideline on the Choice of the Non-Inferiority Margin* — マージンは事前・文脈依存【慣行／文献】  
8. FDA. Non-Inferiority Clinical Trials guidance — M2＝臨床的に許容可能な効果喪失【慣行／文献】  
9. Absolute NI margins 実務帯の参考: BMJ Open 2021（死亡率 NI 中央値絶対約 9%）；oncology response NI 平均約 12.7%（Cer. 2021 レビュー）【慣行】  
10. Miller, E. (2024). *Adding Error Bars to Evals*. arXiv:2411.00640 — α=0.05、3 pp MDE に約 1000 問の例示；精密 power の直写はしない【文献】  
11. Julious, S.A. (2005). *Sample size of 12 per group rule of thumb for a pilot study*. Pharmaceutical Statistics — pilot \(N\) 慣行【慣行／文献】  
12. OLMES / HELM 系の大規模 eval サンプリング上限慣行（例: 多数インスタンス時の subsample）— full \(N\) 拡大の文脈【慣行】  
13. Gu et al. IterCOMP (arXiv:2608.13588) — 反復上限 5・平均約 2–3 帯 → \(J=3\) の近傍【慣行／文献】  
14. 多重比較・事前登録: Holm FWER；確認的 vs 探索的分離（Simmons/Nelson/Simonsohn 系解説；ARD 多重比較総説）【慣行／文献】  
15. LongLLMLingua (arXiv:2310.06839) — 圧縮下の品質維持を報告する近傍だが **δ の数値ソースには使わない**（条件・指標が異なる）【借用注意】  

### 数字方針（本 MD）

- 表中のロック値はすべて **根拠タグ付き**。
- 2609.15964 の % はロック値に転記していない。
- 捏造の精密 sample-size 計算（未知分散の仮置き）は行っていない。

---

## 8. 作業ログ

| 手順 | 結果 |
|---|---|
| 必読 MD 読取 | 完了 |
| 追加文献サーチ（NI・pilot \(N\)・多重比較・LLM eval・IterCOMP） | 完了 |
| ロック MD 作成 | 本ファイル |
| Gate C / 実験 / 購入 / 公開 / push / ユーザー直送 | **なし** |
| candidates 末尾ポインタ | 追記 |

---

## 変更履歴

- 2026-09-16: D-2 v0.1 閾値ロック初版。委任に基づく決め打ち。Gate C 未実行。
