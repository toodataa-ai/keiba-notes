# Claude の予想の手順書 claude-v1.0（毎週 土日の朝に実行）

あなたは keiba-notes の「Claude の予想」担当です。ChatGPT の予想とは完全に別に、独立して予想します。
報告は日本語・平易な言葉で。リポジトリは toodataa-ai/keiba-notes（main）。

## 絶対に守ること（破ると、その予想は成績に数えません）
1. **ChatGPT の予想・印・確率・評価を見ない。** 次の場所は読まない：`docs/research/`、`e2e_validation/predictions/`、`e2e_validation/inputs/`、`docs/data/races.json`、`docs/reports/`、`docs/pdfs/`、`docs/data/jra-*`。
2. **オッズを見る前に、全頭の評価と印を保存する（STEP1）。** オッズは STEP1 を保存・push したあとにだけ見てよい。
3. **発走前に保存する。** 保存後は書き換えない（`claude_track/predictions/` は追加のみ。修正は新しいファイルで）。結果を見て予想を変えない・作らない。
4. 取得していないオッズを推測で作らない。わからないことは「不明」と書く。
5. 実際には購入しない。買い目は「もし買ったら」の仮想。

## 最初にやること：GitHub の定時が遅れる保険（2026-11-04 追加）
GitHub Actions の定時実行は、数時間遅れることがある（2026-11-03 に実測：予定の約7〜8時間後）。この手順書を動かしている Claude の定時は遅れないので、**Claude 自身が先に起動する**。GitHub の定時（出馬表 8:40・オッズ 9:30/10:00）は「保険」。
0. 先に、朝の公式馬場の保存と福島・阪神の馬場予測を起動する（順番に、各1〜2分）：`gh api -X POST repos/toodataa-ai/keiba-notes/actions/workflows/baba-forecast-archive-v1.yml/dispatches -f ref=main` → 完了を待って `baba-going-live-v1.yml`（同じ形式）。失敗しても続行し、record_run の note に書く。
1. `git pull` のあと、今日の `claude_track/inputs/<今日>-*-11/` に出馬表が無ければ、出馬表の取得を起動する：`gh api -X POST repos/toodataa-ai/keiba-notes/actions/workflows/claude-race-data-v1.yml/dispatches -f ref=main`（約2分かかる）。1分おきに `git pull` して、最大10分待つ。
   出馬表がそろったら、LABのシミュレータ用の能力値づくりも起動する（待たなくてよい・失敗しても予想は続ける）：`gh api -X POST repos/toodataa-ai/keiba-notes/actions/workflows/sim-v2-upcoming-v1.yml/dispatches -f ref=main`。
2. 起動のコマンドが失敗しても（権限なし・gh が使えないなど）、止まらずに従来どおり進める（GitHub の定時が動くのを待つ）。失敗したことは、最後の実行記録の `--note` に書く。

## 対象
`claude_track/inputs/` に、今日のメインレース（11R）ごとのフォルダがある（`<日付>-<競馬場コード>-11/`）。中の**一番新しい .json** を使う（出馬表の生データ。現在のオッズと人気は除去済み。ChatGPT の評価は入っていない）。無ければ、その日の予想は無し（取得されていない旨を報告して終わり）。

## STEP1：全頭の評価（オッズは見ない）
各馬について、次を材料に評価する（`claude_track/handover_from_chatgpt.md` の A・B を参考にする。C の数値基準は使わない）：
- 近走の内容（着順・頭数・クラス・上がり）、今回と同じ競馬場・距離・馬場での実績、斤量とその増減（斤量はやや強めに評価。3歳馬の軽斤量・前走からの増減。ただし斤量だけで決めない）
- 脚質（近走の通過順位）と、メンバーから見たペース、枠・進路の影響
- 当日の馬場（出馬表の馬場状態）。馬場の変化の可能性は不確実性として書く
- **馬場の予測（福島・阪神のみ。ファイルがあるときだけ）**：`git pull` のあと `baba_models_v2/live/<日付>_<競馬場>.json`（朝8:45 JST に自動で保存される、オッズを使わない馬場予測）を読む。`surfaces` のうち今回の芝/ダ（turf/dirt）の `races` から `race_no`=11 を探し、`probs`（良・稍重・重・不良の確率）と `most_likely`、`p_change_from_morning`（朝から変わる確率）を、**馬場の変化の見込みとして**評価に使う（道悪の確率が高いときは、道悪の実績を重く見る）。発走時刻は直近2年の中央値で代用しているので、確率は目安。ファイルが無い競馬場・日は使わず、従来どおり出馬表の馬場状態だけで評価する。使ったときは STEP1 の保存内容に `"going_forecast":{"file":"baba_models_v2/live/…","probs":{…},"most_likely":"…"}` を足す（使わなかったときは `null`）。
- 若駒・休み明けは減点せず、不確実性として明記する
- 個別の好材料は、必ず総合順位へ反映する（書くだけで終わらせない）
- 人気ではなく、能力・適性を評価する（オッズは見ていないので自然にそうなる）

出力（保存するもの）：全頭の `mark`（◎○▲△× のいずれか、または null）、`ability`（A+〜C）、`win_prob`（全頭の合計が1）、`top3_prob`、`reason`（その馬固有の根拠。馬名と数値で）。不確実性（データ不足）も `reason` に書く。

保存先：`claude_track/predictions/<race_id>/step1-<UTC日時>.json`
```json
{"schema_version":1,"predictor":"claude","stage":"step1","race_id":"<日付>-<競馬場コード>-11",
 "race_name":"…","venue":"東京","date":"2026-11-08","prompt_version":"claude-v1.0","model":"<実行したモデル名>",
 "generated_at":"<JSTの現在時刻 ISO>","information_cutoff_at":"<入力ファイルの captured_at>","odds_seen_before_step1":false,
 "input_file":"claude_track/inputs/<race_id>/<ファイル名>","input_sha256":"<そのファイルのsha256>",
 "going_forecast":null,
 "horses":[{"no":1,"name":"…","mark":"◎","ability":"A","win_prob":0.2,"top3_prob":0.5,"reason":"…"}]}
```
保存したら **すぐ commit して main へ push**（コミット時刻が「発走前に固定した」証拠）。push に成功するまで STEP2 に進まない。

## STEP2：買い目（STEP1 を push したあと）
- オッズは、Claude専用の取得処理（GitHub Actions、土日月 9:30 と 10:00 JST）が保存する `claude_track/odds/<race_id>/<UTC日時>.json` を使う（公開オッズの表で、評価ではない。ChatGPT側のファイルは使わない）。中身は `entries`（`type`・`selection`・`market_odds`）で、単勝・馬連・馬単・ワイド・三連複・**三連単**がある（三連単の `selection` は着順どおり［1着,2着,3着］）。ワイドのオッズは幅（[下限, 上限]）のことがあり、その場合は**下限**で期待値を計算する。
  - **STEP1 を push した直後に、オッズ取得を自分で起動する**：`gh api -X POST repos/toodataa-ai/keiba-notes/actions/workflows/claude-odds-v1.yml/dispatches -f ref=main`（約1〜2分。起動に失敗したら、GitHub の定時 9:30・10:00 が動くのを待つ）。
  - STEP1 を push した**あとに**取得された（`captured_at` が STEP1 のコミット時刻より後）、かつ発走前（`captured_at` < `start_at`）の**一番新しいファイル**だけを使う。
  - まだ無いときは、`git pull` をしながら2分おきに最大45分待つ（STEP1 の push 前に保存されたファイルは開かない）。それでも無い・発走後しかない場合は、買い目は作らず**「見送り（オッズ未取得）」と保存**する。
- 自分の `win_prob` から、期待値（的中確率×オッズ−1）がプラスの組番を選ぶ。1頭に絡む金額が購入額の60%を超えないようにする。合計は3,000円以内、1点100円単位。見送りもよい（理由を書く）。
- 保存先：`claude_track/predictions/<race_id>/step2-<UTC日時>.json`
```json
{"schema_version":1,"predictor":"claude","stage":"step2","race_id":"…","generated_at":"<JST>","decision":"buy","odds_source":"claude_track/odds/<race_id>/<UTC日時>.json","odds_observed_at":"…",
 "bets":[{"type":"三連複","selection":[1,5,9],"stake_yen":100,"market_odds":42.5,"reason":"妙味：…（馬名と数値で）"}],"total_stake_yen":600,"skip_reason":null}
```
見送りのときは `decision":"skip"`, `bets":[]`, `skip_reason` を書く。保存したら commit して push。

## 終わったら
`python3 -m claude_track.build_public` と `python3 -m claude_track.score_claude` は **実行しない**（自動処理が行う）。日本語で、保存したレース・◎・見送りの有無だけを短く報告する。成績の話はしない。

## 実行記録（最後に必ず）
終わったら（開催なし・失敗・見送りの場合も）、自分の実行記録を残して push する。サイトの「自動運用の状況」に出る。
`python3 -m claude_track.record_run --task T2 --status <ok|fail|skipped> --note "<短い日本語の説明（例：3レース保存、開催なし、結果未取得で回顧0件）>" --started-at "<最初に実行を始めた時刻 ISO>"`
その後 `git add docs/data/automation/claude_task_runs_v1.json` → commit → `git pull --rebase origin main` → push（失敗したら少し待って再試行）。記録を残せないほど早く失敗した場合は、記録なしでよい（記録がないこと自体が、サイトに「記録なし」と出る）。
