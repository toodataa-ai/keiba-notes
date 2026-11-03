# Claude の回顧の手順書 claude-review-v1.0（土日月の夜に実行）

報告は日本語・平易に。リポジトリは toodataa-ai/keiba-notes（main）。

## 前提
- 結果は `claude_track/results/<race_id>.json`（公式の着順・払戻。Claude 用の自動処理 `claude-results-v1.yml` が、レース後（土日月の 17:17・17:47 JST）に Sportnavi の結果ページから保存する）。無いときは `e2e_validation/results/<ChatGPT側のレース名>.json`（ChatGPT の回顧が書く共有の結果ファイル）を使ってよい。どちらも無いレースは、無いと報告して終わり（結果を推測しない）。
- 最初に `git pull` で最新を取る。結果ファイルが無く、レースが終わって30分以上たっているときは、GitHub Actions の `claude-results-v1.yml` を手動起動（REST: `gh api -X POST repos/toodataa-ai/keiba-notes/actions/workflows/claude-results-v1.yml/dispatches -f ref=main`）して、1〜2分後にもう一度 pull する。
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
