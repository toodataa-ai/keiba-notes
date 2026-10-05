# Upcoming schedule data

`upcoming_schedule.json` はトップページの「今後の予測・回顧予定」の表示元です。

- 対象: JRA各開催日の11R（メインレース）
- 予測予定: 当日午前（最新の出馬表・馬場情報を反映）
- 回顧予定: 結果確定後〜当日夜
- 情報源: JRA公式の開催日程・競馬番組
- 各レースに確認元のJRA公式URLを保存
- `.github/workflows/update-upcoming-schedule.yml` はJSONの構造・URL・日付順などを検証するだけで、JRAへの自動スクレイピングは行いません。

GitHub Actions環境からJRA公式ページへの取得は403となるため、壊れた自動更新は採用しません。JRA公式で確認した予定をJSONへ反映し、CIでは表示データの整合性だけを監査します。

JRAの事前番組は変更される場合があるため、当週木曜16時頃の出馬表を基準に最終確認します。
