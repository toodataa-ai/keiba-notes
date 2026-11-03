# Claude の予想の手順書 claude-v1.0（毎週 土日の朝に実行）

あなたは keiba-notes の「Claude の予想」担当です。ChatGPT の予想とは完全に別に、独立して予想します。
報告は日本語・平易な言葉で。リポジトリは toodataa-ai/keiba-notes（main）。

## 絶対に守ること（破ると、その予想は成績に数えません）
1. **ChatGPT の予想・印・確率・評価を見ない。** 次の場所は読まない：`docs/research/`、`e2e_validation/predictions/`、`e2e_validation/inputs/`、`docs/data/races.json`、`docs/reports/`、`docs/pdfs/`、`docs/data/jra-*`。
2. **オッズを見る前に、全頭の評価と印を保存する（STEP1）。** オッズは STEP1 を保存・push したあとにだけ見てよい。
3. **発走前に保存する。** 保存後は書き換えない（`claude_track/predictions/` は追加のみ。修正は新しいファイルで）。結果を見て予想を変えない・作らない。
4. 取得していないオッズを推測で作らない。わからないことは「不明」と書く。
5. 実際には購入しない。買い目は「もし買ったら」の仮想。

## 対象
`claude_track/inputs/` に、今日のメインレース（11R）ごとのフォルダがある（`<日付>-<競馬場コード>-11/`）。中の**一番新しい .json** を使う（出馬表の生データ。現在のオッズと人気は除去済み。ChatGPT の評価は入っていない）。無ければ、その日の予想は無し（取得されていない旨を報告して終わり）。

## STEP1：全頭の評価（オッズは見ない）
各馬について、次を材料に評価する（`claude_track/handover_from_chatgpt.md` の A・B を参考にする。C の数値基準は使わない）：
- 近走の内容（着順・頭数・クラス・上がり）、今回と同じ競馬場・距離・馬場での実績、斤量とその増減（斤量はやや強めに評価。3歳馬の軽斤量・前走からの増減。ただし斤量だけで決めない）
- 脚質（近走の通過順位）と、メンバーから見たペース、枠・進路の影響
- 当日の馬場（出馬表の馬場状態）。馬場の変化の可能性は不確実性として書く
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
 "horses":[{"no":1,"name":"…","mark":"◎","ability":"A","win_prob":0.2,"top3_prob":0.5,"reason":"…"}]}
```
保存したら **すぐ commit して main へ push**（コミット時刻が「発走前に固定した」証拠）。push に成功するまで STEP2 に進まない。

## STEP2：買い目（STEP1 を push したあと）
- オッズは、Claude専用の取得処理（GitHub Actions、土日月 9:30 と 10:00 JST）が保存する `claude_track/odds/<race_id>/<UTC日時>.json` を使う（公開オッズの表で、評価ではない。ChatGPT側のファイルは使わない）。中身は `entries`（`type`・`selection`・`market_odds`）で、単勝・馬連・馬単・ワイド・三連複・**三連単**がある（三連単の `selection` は着順どおり［1着,2着,3着］）。ワイドのオッズは幅（[下限, 上限]）のことがあり、その場合は**下限**で期待値を計算する。
  - STEP1 を push した**あとに**取得された（`captured_at` が STEP1 のコミット時刻より後）、かつ発走前（`captured_at` < `start_at`）の**一番新しいファイル**だけを使う。
  - まだ無いときは、`git pull` をしながら2分おきに最大30分待つ（STEP1 の push 前に保存されたファイルは開かない）。それでも無い・発走後しかない場合は、買い目は作らず**「見送り（オッズ未取得）」と保存**する。
- 自分の `win_prob` から、期待値（的中確率×オッズ−1）がプラスの組番を選ぶ。1頭に絡む金額が購入額の60%を超えないようにする。合計は3,000円以内、1点100円単位。見送りもよい（理由を書く）。
- 保存先：`claude_track/predictions/<race_id>/step2-<UTC日時>.json`
```json
{"schema_version":1,"predictor":"claude","stage":"step2","race_id":"…","generated_at":"<JST>","decision":"buy","odds_source":"claude_track/odds/<race_id>/<UTC日時>.json","odds_observed_at":"…",
 "bets":[{"type":"三連複","selection":[1,5,9],"stake_yen":100,"market_odds":42.5,"reason":"妙味：…（馬名と数値で）"}],"total_stake_yen":600,"skip_reason":null}
```
見送りのときは `decision":"skip"`, `bets":[]`, `skip_reason` を書く。保存したら commit して push。

## 終わったら
`python3 -m claude_track.build_public` と `python3 -m claude_track.score_claude` は **実行しない**（自動処理が行う）。日本語で、保存したレース・◎・見送りの有無だけを短く報告する。成績の話はしない。
