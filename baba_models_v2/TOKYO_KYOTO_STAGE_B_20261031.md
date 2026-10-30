# 東京・京都 Stage B（芝/ダート）検証 第1弾 — 2026-10-31

## 現在の判断

- 対象は東京芝・東京ダート・京都芝・京都ダートの4モデルのみ。
- Stage A は既存候補を維持し、Stage B は4モデルとも pilot のまま。
- 正式STEP1、final_bets、過去prediction/result/review、latest_prompt.json、本番ルータ、公開モデル台帳を変更しない。
- Stage Bの実レース精度検証は公式レース単位の「走路・発走時刻」の追加照合が済むまで未完了。

## 既存結果から回収できた根拠

2026-10-31時点の docs/data/races.json では32レース中、東京・京都のレースが18件。公式JRA結果URLと4区分馬場ラベルを持つものは16件（東京8・京都8）。そのうち結果確認時刻が記録されているものは14件。対象開催日は8日。

これらは現時点で検証済みStage Bデータ16件という意味ではない。元の記録から公式走路（芝/ダート）と発走時刻を厳密に確定できないため、自動推測せず、研究用 worklist CSV の該当列を空欄で出力する。

## 第1弾の実装

- stage_b_label_inventory_v1.py: 既存JRA回顧から公式ラベル候補を抽出。日付・JRA原本URL・結果確認時刻を整理。芝/ダートと発走時刻は捏造しない。
- stage_b_tokyo_kyoto_v1.py: 公式確認済みCSVとJRA当日朝含水率、JMA時間別気象を結び付け、静的朝予測と現行Stage B heuristicの4区分確率を比較する検証器。
- test_stage_b_tokyo_kyoto_v1.py: 4モデル、未来の降雨、重複、未確認ラベル、旧京都レジームの拒否試験。
- tokyo-kyoto-stage-b-research-v1.yml: CIでテストと公式ラベル候補一覧の生成を実行する。データは研究用アーティファクトのみ。

## 予測と検証の境界

JRA朝含水率は当日かつ観測時刻のある公式記録に限定する。東京の気象は府中、京都は長岡京（雨量）・京田辺（気温や風）の既存取得器を使う。発走1時間前以降を観測終了時刻とする時間別データは利用しない。欠測が多い場合は計算しない。

Log Loss、Brier、Top1、隣接クラス的中率、10分割ECE、雨天遷移別の精度を保存する。古いJMA値の発表・訂正時刻まで確認できていないため、時刻だけによるバックテストを「発走前に確実に取得できた実績」とは呼ばない。結果には historical_publication_availability_verified=false と formal_promotion_eligible=false を固定する。公式レース結果ラベルと検証モデル予測は予測作成時には混ぜない。

## 実行手順（研究環境）

公式証拠リスト:

    python baba_models_v2/stage_b_label_inventory_v1.py --races docs/data/races.json --output tmp/stage_b/label_worklist.csv --audit tmp/stage_b/inventory.json

各行の走路と正確な発走時刻を公式資料で照合し、同じヘッダの検証済みCSVを別途作成。既存のStage A取得工程を使い、競馬場別JRA観測CSVとJMA時間別気象CSVを列名を確認して連結後、以下を実行:

    python baba_models_v2/stage_b_tokyo_kyoto_v1.py --labels tmp/stage_b/verified_official_labels.csv --observations tmp/stage_b/jra_morning_merged.csv --weather tmp/stage_b/jma_hourly_merged.csv --output tmp/stage_b/replay.json

時刻入力はJSTのオフセットなしISO形式に統一。結果確認時刻は、ラベル証拠の照合にだけ使う。

## 次の昇格条件（各モデル）

promotion_policy.json のStage B基準: 公式ラベル80レース以上、独立開催日12日以上、2暦年以上、雨天遷移6日以上。事前登録した別の比較モデルが現行heuristicよりLog LossとBrierをともに5%以上改善すること。雨天遷移ケースのBrier悪化10%以内、時刻リーク防止・再現可能な時系列検証が必要。現段階では比較用Challengerも未登録であり、4モデルとも本番接続や昇格は行わない。
