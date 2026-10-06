# 地方競馬 Daily Shadow v0.1

## 目的

地方競馬の高頻度な開催を、JRA本番予想とは分離した研究用Shadow母集団として利用する。

対象はまず以下の6場。

- 大井
- 川崎
- 船橋
- 浦和
- 園田
- 名古屋

地方競馬の結果を、そのままJRA本番の重み・印・プロンプトへ流し込んではならない。
目的は「地方で効いた補正をJRAへ移植する」ことではなく、複数場・複数条件で再現する抽象的な予測特徴や誤差構造を高速に発見し、JRA側で改めてE2E検証できる候補を作ることである。

## 基本サイクル

1. 当日の対象6場の開催有無と全レースを公式情報で確認する。
2. 発走前に各レースのcompact Shadow predictionを固定する。
3. cutoff後はpredictionを変更しない。
4. 公式結果確定後にresultを結合する。
5. venue / distance / class / going / pace / running style / gate / jockey / weight / rotation / ability rank / reliability 等で誤差を分解する。
6. 毎日aggregateを更新する。
7. 週次で、複数場・複数日で再現した論点だけをtransfer candidateとして整理する。
8. transfer candidateはJRA productionへ直接入れず、JRA側のChallenger / E2Eで検証する。
9. JRA本番採用は明示承認が必要。

## データ契約

### pre-race prediction

最低限、以下を保存する。

- race_id
- date
- venue
- race_no
- race_name
- surface / distance
- class / age condition
- scheduled_start_at
- generated_at
- information_cutoff_at
- runners
- STEP1相当の能力順位
- pace仮説
- going
- 主要な位置取り / 枠 / 騎手 / 斤量 / ローテ情報
- sources（name / url / published_at or observed_at）
- model_version = local-daily-shadow-v0.1

結果、着順、払戻、レース後記事をpredictionへ書いてはならない。

### post-race result

公式確定後に別ファイルとして保存する。

- race_id
- official_result_at
- finish_order
- official_going
- available official splits / positions
- prediction_path
- error summaries

## 研究単位

地方6場を一つの均質な母集団として扱わない。

最低でも以下で分ける。

- 競馬場
- 距離帯
- クラス
- 年齢条件
- 頭数
- 馬場
- ペース
- 脚質
- 枠
- 騎手
- 斤量
- ローテ

特に南関4場、園田、名古屋はコース形状・砂質・番組構成・騎手構成が異なるため、venue-specific effectは原則ローカルに留める。

## JRAへ持ち込めるもの

直接の数値補正ではなく、次のような「抽象化された方法論」をtransfer candidateにできる。

- 逃げ・先行馬密度とテン性能から展開崩壊リスクを推定する方法
- 枠×脚質×頭数から位置取り不利を定量化する方法
- 同日レースから時計速度 / 位置 / 進路バイアスを分離する方法
- 騎手の条件別寄与を馬質から分離する方法
- 斤量変化をクラス・年齢・距離と分離して見る方法
- ローテ短縮 / 延長による再現性変化を測る方法

## 禁止事項

- 地方の勝率やROIが良かったという理由だけでJRAの重みを変更する。
- 大井1800m等のvenue-specific係数を中山ダ1800m等へ直接コピーする。
- 結果を見た後でpredictionを修正する。
- 一日だけの特殊馬場や荒れ結果を一般化する。
- 地方Shadow成績をJRA正式成績へ合算する。

## 昇格思想

Daily Shadow → repeated finding → transferable candidate → JRA historical/replay or Grade A E2E → human approval → production

地方競馬は学習速度を上げる研究場であり、JRA本番モデルの教師データそのものではない。
