# Upcoming schedule data

`upcoming_schedule.json` はトップページの「今後の予測・回顧予定」の表示元です。

- 対象: JRA各開催日の11R（メインレース）
- 予測予定: 当日午前（最新の出馬表・馬場情報を反映）
- 回顧予定: 結果確定後〜当日夜
- 更新: `.github/workflows/update-upcoming-schedule.yml` が毎週月曜09:15 JSTにJRA公式の開催日程を再取得
- 生成: `scripts/update_upcoming_schedule.py`

JRAの事前番組は変更される場合があるため、当週木曜16時頃の出馬表を基準に最終確認します。
