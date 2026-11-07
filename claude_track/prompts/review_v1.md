# Claude の回顧の手順書 claude-review-v1.0（土日月の夜に実行）

報告は日本語・平易に。リポジトリは toodataa-ai/keiba-notes（main）。

## 前提
- 結果は `claude_track/results/<race_id>.json`（公式の着順・払戻。Claude 用の自動処理 `claude-results-v1.yml` が、レース後（土日月の 17:17・17:47 JST）に Sportnavi の結果ページから保存する）。無いときは `e2e_validation/results/<ChatGPT側のレース名>.json`（ChatGPT の回顧が書く共有の結果ファイル）を使ってよい。どちらも無いレースは、無いと報告して終わり（結果を推測しない）。
- **最初にやること：GitHub の定時が遅れる保険（2026-11-04 追加）**。GitHub Actions の定時実行は数時間遅れることがある（2026-11-03 に実測）。この手順書を動かしている Claude の定時は遅れないので、**Claude 自身が先に起動する**。GitHub の定時（結果 17:17/17:47）は「保険」。
  1. 結果の取得を起動：`gh api -X POST repos/toodataa-ai/keiba-notes/actions/workflows/claude-results-v1.yml/dispatches -f ref=main`（結果が保存されると、採点・公開も自動で続く）。
  2. 1〜2分おきに `git pull` して、結果ファイルが出るまで最大15分待つ。それでも無いレース（発走30分未満・払戻未確定など）は、無いと報告する。
  3. 結果の保存を確認したら、順番に起動して各回の完了を待つ（失敗しても次へ進み、record_run の note に書く）：`claude-track-publish-v1.yml`（採点・公開）→ `jra-improvement-experiments-v1.yml`（改善案の採点）→ `jra-improvement-pipeline-v1.yml`（基準の確認）。起動の形式は上と同じ（`gh api -X POST repos/toodataa-ai/keiba-notes/actions/workflows/<名前>/dispatches -f ref=main`）。GitHub の定時は保険。
  3b. **馬場傾向の計算も起動する**（翌日の予想が使う、その日の馬場の傾向。2026-11-08 追加）：`gh api -X POST repos/toodataa-ai/keiba-notes/actions/workflows/baba-bias-v1.yml/dispatches -f ref=main`（日付は省略。出馬表があり、まだ計算していない直近3日を自動で処理する。全12レースの結果が出ている競馬場だけ保存される）。完了は待たなくてよい。失敗しても止まらず、record_run の note に書く。
  4. 起動のコマンドが失敗しても（権限なし・gh が使えないなど）、止まらずに従来どおり進める。失敗したことは、最後の実行記録の `--note` に書く。
- `git pull` で最新を取る。
- Claude の予想は `claude_track/predictions/<race_id>/`。**保存済みの予想は書き換えない。**
- ChatGPT の予想・回顧は、**Claude 自身の回顧を保存したあと**に、比較のためにだけ読んでよい。

## やること（レースごと）
1. 自分の予想と結果を比べる：◎○▲の着順、想定ペースと実際の展開、馬場の想定と確定馬場、好材料を印に反映できていたか、買い目の収支（印の正確さと買い目の採算は分けて評価）、再発する課題か単発か。
2. 失敗の分類（能力／適性／展開／馬場予測／購入戦略／リスク集中／データ不足）から当てはまるものを選ぶ。当たったことを理由に、評価が正しかったとは言わない。
3. `claude_track/reviews/<race_id>.json` に保存（追加のみ）：
```json
{"schema_version":1,"predictor":"claude","race_id":"…","reviewed_at":"<JST>","summary":"…（3文以内）",
 "honmei_result":"…","failure_types":["適性"],"lessons":["…"],"repeatable":true}
```
4. commit して main へ push。

## 週の比較（週末分がそろったら1回だけ）
`claude_track/reviews/weekly-<週の月曜の日付>.md` に、同じレースについて ChatGPT と Claude の違いを書く：◎の着順、3着内に入れた印の数、買い目の収支、できたこと／できなかったことの対比、次に試す改善案（承認が必要なので提案だけ）。成績は合算しない。push したら、改善案があれば GitHub に Issue（ラベル `claude-review`、題名「[Claudeの回顧] 週の比較 <日付>」）を1件立て、ユーザーが A（反映）／B（保留）／C（採用しない）で答えられるようにする。反映は A のときだけ。

## 実行記録（最後に必ず）
終わったら（開催なし・失敗・見送りの場合も）、自分の実行記録を残して push する。サイトの「自動運用の状況」に出る。
`python3 -m claude_track.record_run --task T3 --status <ok|fail|skipped> --note "<短い日本語の説明（例：3レース保存、開催なし、結果未取得で回顧0件）>" --started-at "<最初に実行を始めた時刻 ISO>"`
その後 `git add docs/data/automation/claude_task_runs_v1.json` → commit → `git pull --rebase origin main` → push（失敗したら少し待って再試行）。記録を残せないほど早く失敗した場合は、記録なしでよい（記録がないこと自体が、サイトに「記録なし」と出る）。
