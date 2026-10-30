# 競馬サイト専用の匿名アクセス集計（LAB）

## 現状（2026-10-30）
- LAB画面：`docs/lab/usage-analytics.html` （今日・累計PV、セッション概数、過去7/30/90/365日）
- 接続設定：`docs/lab/usage-analytics-config.json` は `enabled=false`、`endpoint=""`。数値表示・トラッキングは**未稼働**。
- Backend候補：このディレクトリの `worker.mjs` と `schema.sql`。
- 既存本番 `docs/admin.html` と `docs/assets/visitor-counter.js` は変更していない。
- イベントサイトのWorker `tokyo-family-events-metrics` / D1に接続してはいけない。競馬専用の別D1が必要。

## 計測対象と意味
- `page_home`, `page_this_week`, `page_results`, `page_schedule`, `page_methodology`, `page_research`, `page_other`：ページ閲覧（PV）。同一人物の再表示も加算。
- `session_start`：同一タブの日本時間の日付単位で、最初の対象ページを表示した際の概数。正確な人数やUUではない。
- 実測可能な日付のみ日別履歴に表示。未計測日は0件として補完しない。
- 名前・IP・UA・閲覧URL・端末ID・Cookieなどの個人識別データはサーバーDBに保存しない。
- LAB・STAGING・admin画面は計測対象外。公開前の予想・PDF・proofは変更しない。

## 接続までの作業
1. Cloudflareで競馬専用D1 `keiba-notes-metrics` を作る。イベントサイトのD1を再利用しない。
2. `wrangler.example.toml` を参考に、DBの正しい `database_id` を設定する。認証トークンやSecretsをGitに書かない。
3. `schema.sql` を**競馬専用D1に限って**適用。既存DBにはテーブル追加・上書きしない。
4. `worker.mjs` を別Worker名 `keiba-notes-metrics` で公開し、`/stats` と `/history?days=7` のJSON応答、`/collect` のOrigin検証を確認。
5. LAB側の `usage-analytics-config.json` を接続先に切り替え、数値と履歴の取得を検証。**LAB閲覧からは書き込まない**。
6. 個別に「LAB→STAGING」承認を受け、現行本番との差分・スマホ/PC・共有ページの表示を検証。
7. 別途「本番リリース」承認後のみ、正式ページに `usage-tracker.js` 相当を組み込み、`docs/data/site-usage-config.json` を新設・有効化。既存CounterAPIとの二重計測を避ける。
8. 本番公開後、実ページのPV増分とCloudflare D1の正本値を照合。

以前のCounterAPIの過去データを新しいD1へ移行・復元したとは主張しない。新方式の計測開始以降の履歴を表示する。

### 開発検証
`node --test docs/lab/analytics/worker.test.mjs` / `node --check docs/lab/usage-analytics.js`。
