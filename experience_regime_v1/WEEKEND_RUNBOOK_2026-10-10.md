# E0/E1/E2 Shadow Weekend Runbook — 2026-10-10〜2026-10-12

## Purpose
2026-10-10から、JRA各開催日の11R（メインレース）でExperience Regime E0/E1/E2のShadow観測を開始する。

正式サイトの予想は従来どおりv3.1を表示する。Experience Regimeは観測専用であり、STEP1順位、◎○▲△×、ABC評価、STEP2、買い目を変更しない。

## Target races

### 2026-10-10（土）
- 東京11R サウジアラビアロイヤルカップ（GIII）
- 京都11R 御陵ステークス

### 2026-10-11（日）
- 東京11R アイルランドトロフィー（GII）
- 京都11R 太秦ステークス

### 2026-10-12（月・祝）
- 東京11R オクトーバーステークス（L）
- 京都11R スワンステークス（GII）

## Pre-race collection — mandatory
各レースのprediction snapshotを発走前proof commitへ保存する時点で、全出走馬について以下を保存する。

- horse_number
- starts_before_race
- regime: E0 / E1 / E2
- model_version: e012-shadow-v0.1

分類は機械的に以下のみで決める。
- E0 = 0戦
- E1 = 1〜3戦
- E2 = 4戦以上

年齢、人気、血統、調教、評判等でRegimeを変更しない。

## Separation from official prediction

### Official / public prediction
- v3.1のSTEP1順位・印・ABC評価・STEP2・買い目を掲載
- Experience Regimeを理由に順位や印を変更しない
- 個別馬のShadow診断や将来のChallenger値は正式予想ページへ掲載しない

### Shadow / research collection
- E0/E1/E2ラベル
- starts_before_race
- Regime別の実勝率・実3着内率
- 予測勝率・予測3着内率がある場合の平均
- Brier score
- STEP1平均順位
- ◎○▲選出率

を結果確定後に集計する。

## Disclosure policy

公開サイトでは「Experience RegimeをShadow検証中」であること、目的、分類定義、採用条件、集計レベルの進捗だけを公開する。

正式予想ページには個別馬のShadow出力を掲載しない。

ユーザーとのChatGPT上の運用では、`docs/data/experience_regime_status.json` と当該週のprediction snapshotを確認して、Regime別件数、coverage、誤差、進捗を必要に応じて報告できる。

注意: keiba-notesリポジトリ自体は公開リポジトリである。Gitへコミットした生データはGitHubを直接閲覧すれば参照可能であり、「正式サイト非表示」は「完全非公開」と同義ではない。将来、E0/E1/E2が順位を変えるChallenger予想へ進む場合は、Challenger出力の保管場所を別途設計する。

## Promotion guardrail

Shadow期間では固定ボーナス／ペナルティを作らない。

最低条件:
- Grade A experience付き20レース以上
- E0 30頭以上
- E1 60頭以上
- E2 100頭以上
- historical replay併用
- prospective Grade A必須
- E2にmaterial regressionがないこと

条件を満たしても自動昇格しない。次段階はRegime別の不確実性・shrinkage（μ/σ）Challengerの設計であり、本番接続は別承認とする。
