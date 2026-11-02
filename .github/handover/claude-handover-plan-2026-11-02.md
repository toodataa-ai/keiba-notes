# ChatGPT → Claude Code 引き継ぎ調査・移行計画（2026-11-02）

状態: **調査・計画のみ**。mainマージ、本番リリース、Scheduled tasks有効化、ChatGPTリマインド停止はいずれも未実施で、利用者承認待ち。
置き場所: `.github/handover/`（GitHub Pages公開対象の `docs/` 外。DATA/UI/LABのどれにも該当しない運用文書）。

---

## 0. 調査時点の基準SHA

| 対象 | 値 |
|---|---|
| keiba-notes main | `844367f58229a7469fb8ba0bbc8be9d8c2cac40d`（2026-11-01 23:09 UTC） |
| PR #92 head | `6e0b452f24e1d624c8da5016c2cf35713b11d59e`（base=上記main、mergeable_state=clean） |
| tokyo-family-events-ai main | `ebe42ba`（2026-10-30） |
| train-timer main | `c8c9443`（2026-10-31） |
| Claude Scheduled tasks | 登録0件（重複なし） |

---

## 1. 競馬予想研究所 toodataa-ai/keiba-notes

### 1.1 指定PR/Issueの現状

| # | 種別 | 状態 | 実証状況 | 次の判断 |
|---|---|---|---|---|
| **#92** | Draft PR（→main） | CI 6件中5件success、`shadow`ジョブはskipped（PR上では実運転しない設計）。25ファイル、正式原本・races.json・latest_prompt・地方Shadow変更0と記載 | **7テーマ実レース有効ペア 0件**。default-branch `workflow_run` 実運転、発走前全頭特徴量取得、結果突合、データ公開は未実施 | マージ可否は利用者判断。マージしても「完了」ではなく「Shadow運転開始の前提が整う」だけ。マージ前に保護5 tree SHA不変を再照合 |
| **#83** | Draft PR（base=#81ブランチ） | mergeable clean | 朝Shadow 1回実行成功（blocker保存まで）。実候補生成・両側proof・有効比較は全テーマ0件 | #92に統合済み → #92採用時に#83/#81はclose候補（自動closeしない） |
| **#81** | Draft PR（→旧main `cd05152`） | unstable | 設計・事前登録のみ。進捗20件中0のまま | 同上 |
| **#82** | Issue | open（11項目すべて未チェック） | 既知blocker: `.github/production-releases.json` と `docs/data/production-releases.json` のmain上不一致（v1.06 pending_public_validation） | #92マージ後も閉じない。チェック項目は実証時のみ更新 |
| **#77** | Draft PR（LAB） | unstable（release-channel-guardが上記不一致で失敗） | 京都2000互換QAは自動検査上完了。**利用者目視承認・Safari/実機・原SVG派生配信許諾が未確認**。承認済みコース0、PR2未着手 | LAB限定維持。PR2はPR1受入れ後のみ |

### 1.2 その他のopen項目（引き継ぎ対象として記録）

- PR: #86（STAGING 無料調教時計の手動取得）、#85（無料9項目根拠品質）、#79（東京・京都馬場Shadow事前登録）、#69/#7（Stage B馬場ラベル）、**#64（非Draft・2026-10-25から放置、v3.17時計Shadow）**、#43（地方Challenger v0.2）、#40、#27（旧v3.12系、陳腐化の可能性）
- Issue: #87（調教定期収集は未承認）、#80（馬場③実走Shadow）、#78（E0/E1/E2 9因子STEP1）、#75（全場シミュレータ）、#3（馬場Pilot→Validated）
- 横断blocker: production-releases.json 2系統の不一致（#77/#81のguard失敗原因）。過去記録を消さず、承認済みrelease履歴と突合して是正方針を利用者に提案する必要あり。

### 1.3 既存のGitHub Actions定期実行（Claudeタスクと重複させない対象）

| workflow | cron (UTC) | JST | 性質 |
|---|---|---|---|
| local-racing-shadow-publish | `7 0-14 * * *`, `7 23 * * *` | 08:07〜23:07 毎時 | 地方Shadow DATA公開（実処理） |
| local-shadow-roi-staging-preview | `17 1 * * *` | 10:17 | staging preview |
| local-shadow-cumulative-roi-preview | `27 1 * * *` | 10:27 | preview |
| experience-regime-step1-freeze-v1 | `15,45 23 * * 5,6,0` ほか | 土日月 08:15/08:45 ほか | 研究STEP1凍結 |

→ Claudeのリマインドは「指示文の通知」のみなので処理の二重実行にはならないが、**通知を受けて手動実行する作業がActionsの自動処理と同じ対象を扱わないか**を各指示文で明記する（例: 地方Shadow朝予想はActionsの08:07公開と競合しないか）。

### 1.4 引き継げる運用資産

- `AGENTS.md`、`.github/skills/keiba-site-change-routing/`（LAB/STAGING/PRODUCTION/DATA振り分け）
- `.github/lab/feature-registry.json`（機能状態台帳）
- `docs/operations/*`（JRA承認・発走前上書き禁止・完了addendum等）
- 正本プロンプト: `docs/data/latest_prompt.json` が指す版（ファイル名から最新版を推測しない）
- `shadow_lab/README.md`（#92/#83ブランチ上）

---

## 2. 東京23区子連れイベント toodataa-ai/tokyo-family-events-ai

- **注意: このセッションでは読み取り専用（anonymous clone）**。PR/Issue操作・pushには `add_repo(access: push)` の追加承認が必要。
- 環境: main=開発/staging、production=本番アプリ、data-staging/data-production=動的データ、release/*・data-release/*=不変スナップショット（AGENTS.md）。
- 正本プロンプト: `site/data/latest_prompt.json` → v1.15。
- 休日判定: `tools/rolling_horizon.py`（内閣府公式祝日CSV、取得失敗はBLOCKER、休日明け以外は `status=skipped`）。read-onlyの `holiday-after-plan.yml`（workflow_dispatchのみ）。
- **スケジュール実行のworkflowは0件**（重複リスクはChatGPTタスクとClaudeタスクの間のみ）。
- open: PR #37（Canva フォントサイズ、非Draft）、Issue #65/#62/#52（ソースパリティ監査残）、**#41（2026-10-26 休日明け更新が必須参照元5件未完了で公開停止）**、#18（杉並区309候補 BLOCKER）。
- 閲覧カウンター・管理画面: `site/admin.html`、`site/usage-*`、`analytics/`、metrics Worker系workflow（deploy-metrics-history-worker、diagnose-metrics-worker-403）。直近commitは「keiba metrics namespaceをWorkerに分離」→ 2リポジトリ共通カウンターの境界を引き継ぎ時に確認要。
- Instagram/Canva: `site/canva.html`、`docs/CANVA_DRAFT_INTEGRATION.md`、`docs/canva_*`、`audit-canva-*`/`test-canva-golden-layout` workflow。

## 3. その他の継続開発

| 項目 | 確認結果 | 扱い |
|---|---|---|
| トレインタイマー音声・BGM | `toodataa-ai/train-timer`（public）に `voice-balance-preview.html`、`assets/music/README.md`、`docs/BGMER_SETUP.md`。open PR/Issue 0 | 引き継ぎ候補。現行の未完了課題はGitHub上に記録なし → 利用者からChatGPT側の残課題を受領要 |
| Canva Instagramテンプレート | tokyo-family-events-ai内のCanva契約・テンプレート（上記）。Canva本体のデザイン資産はGitHub外 | Canva側テンプレートの所在は**調査対象（不明）**。推測で特定しない |
| その他リポジトリ | tokyo-weekend-events、keio-bus-map、sky-lift、toiletmap、keiba-forecast-ai(2, private) が存在 | 今回の依頼範囲外。継続対象か利用者に確認 |

---

## 4. 定期リマインド移行計画（Asia/Tokyo）

### 4.1 前提と不足

- **ChatGPTに登録中の4タスクのプロンプト全文は未受領 → 現時点で作成不可（不足）**。受領した全文を正本とし、一字一句そのまま格納する。推測で補完・要約・統合しない。
- 競馬の朝/夜は「複数の独立したコピペ用指示文」を出す仕様 → 原文の各ブロックを個別に保持し、出力でも個別のコードブロックとして並べる。
- 各タスクは**通知のみ**。発火時に予想・回顧・データ更新・push・PR・Actions起動を行わない旨を各プロンプト冒頭のガード文として付与（原文の前に置き、原文自体は変更しない）。

### 4.2 タスク案

| # | 名称 | cron（案） | 方式 | 発火時の動作 |
|---|---|---|---|---|
| T1 | 地方競馬Shadow 朝予想・前日回顧 | `CRON_TZ=Asia/Tokyo 0 8 * * *` | 新規セッション/回 | 原文の指示文群をそのまま出力し通知 |
| T2 | JRA正式予想・E0/E1/E2研究収集 | `CRON_TZ=Asia/Tokyo 0 8 * * 6,0,1` | 同上 | 同上 |
| T3 | JRA正式回顧・研究回顧 | `CRON_TZ=Asia/Tokyo 0 19 * * 6,0,1` | 同上 | 同上 |
| T4 | 東京23区イベント更新 | `CRON_TZ=Asia/Tokyo 0 8 * * 1-5` | 同上 | 下記休日判定で該当日のみ指示文を通知、非該当日は通知しない |

- 時刻は依頼どおり08:00/19:00。サーバ混雑で毎時0分は数分遅延し得る。許容できなければ07:4x等へずらす案もある（利用者判断）。
- 通知: push通知を有効化（emailは依頼時のみ）。
- 新規セッション方式を推奨（前回の会話状態に引きずられない、原文をそのまま出す用途に適する）。
- T2/T3の月曜は、JRA月曜開催がない週も通知される（ChatGPT現行と同じ想定。原文で確認）。

### 4.3 T4 休日判定

- 平日毎朝08:00に起動し、`tools/rolling_horizon.py --as-of <JST当日>`（read-only、内閣府祝日CSV）で `eligible` の日だけ指示文を出す。`skipped` は無通知、CSV取得失敗は「休日判定不能BLOCKER」として通知（黙って省略しない）。
- 2026-11 実測: 11/2(月) eligible、11/4(水・文化の日翌日) eligible、11/9(月) eligible、11/24(火・11/21〜23 土日+勤労感謝の日の3連休明け) eligible。
- **要確認**: 現スクリプトは単独の平日祝日の翌日（例 11/4 水）も eligible。依頼の「連続休日明け最初の平日」「月曜08:00」と一致するか、ChatGPT原文の判定規則で確定する。
  - 案A: rolling_horizon.py の判定に従う（リポジトリ正本と一致）
  - 案B: 「土日を含む連続休日」の明けのみ（通常は月曜、月曜祝日なら火曜）
- 判定はタスクの通知可否だけに使い、データ探索・公開は行わない。

### 4.4 テスト〜切替手順（重複防止）

1. 利用者から4タスクの原文全文を受領 → `.github/handover/reminders/T1..T4.txt` に原文保存（SHA256記録）。
2. Claudeタスクを **無効状態で作成**（または run_once のテスト用で作成）し、`fire_trigger` で手動発火 → 出力が原文とバイト一致（ガード文を除く）、ブロック数一致、通知到達を確認。T4は eligible/skipped/BLOCKER の3パターンを `--as-of` 指定で確認。
3. 利用者が出力と通知を確認し**移行承認**。
4. Claudeタスクを有効化 → 次回発火で並走1回確認 → 利用者がChatGPT側を停止。並走期間は「同じ指示文が2通届く」だけで処理は二重実行されないが、利用者側で片方だけ実行する。
5. 台帳: `.github/handover/scheduled-tasks-ledger.json`（タスクID・cron・有効状態・ChatGPT側停止日）で、ChatGPT／Claude／Actions の三者を一覧管理。

---

## 5. 共通開発ルール（CLAUDE.mdへ保存する内容）

`.github/handover/CLAUDE.md.proposed` に案を作成。承認後、keiba-notesルートへ `CLAUDE.md` として配置（AGENTS.mdを参照させる薄い形）。tokyo-family-events-ai側も同様の案を push権限付与後に作成。

## 6. 利用者に判断を求める事項

1. ChatGPT 4タスクのプロンプト全文の提供（必須）
2. T4休日判定の規則（案A/案B）
3. PR #92 のマージ可否（マージ後もShadow実績は0から）
4. production-releases.json 不一致の是正方針
5. tokyo-family-events-ai / train-timer への push権限付与（add_repo access: push）
6. CLAUDE.md案の配置承認
7. 時刻ジッター（08:00厳守 or 数分前倒し）
