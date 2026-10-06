# E0/E1/E2 Shadow Weekend Runbook — 2026-10-10〜2026-10-12

## Purpose

2026-10-10から、Experience Regime E0/E1/E2のShadow観測を **JRA 1R〜12Rすべてを母集団** として開始する。

正式サイトの予想は従来どおりv3.1のメインレース予想を表示する。Experience Regimeは観測専用であり、STEP1順位、◎○▲△×、ABC評価、STEP2、買い目を変更しない。

## Population and sampling

### 母集団
- JRA全開催場
- 各開催日の1R〜12R
- 芝・ダートを問わない
- 新馬、未勝利、条件戦、OP/L、重賞を含む

### 必ず含めるレース
正式予想として作成するメインレースは `sample_origin=official_prediction` としてShadowにも全件含める。

### 追加で層化抽出するレース
正式予想レースとは別に、残りの1R〜12Rから `experience_regime_v1/sampling.py` でカテゴリ別に抽出する。

週次目標:
- 新馬 `debut`: 3レース
- 未勝利 `maiden`: 3レース
- 1勝クラス `class_1`: 2レース
- 2勝クラス `class_2`: 2レース
- 3勝クラス `class_3`: 2レース
- OP・L `open_listed`: 2レース
- GIII・GII・GI `graded`: 2レース

対象カテゴリの開催数が目標未満なら、存在するレースをすべて採用して不足を記録する。他カテゴリで不足分を埋めない。

## Sampling procedure — before any result is known

1. 当該週のJRA全レース1R〜12Rをrace pool JSONへ列挙する。
2. 各レースに `race_category` を公式の競走条件から付与する。
3. 正式予想対象レースには `official_prediction=true` を付ける。
4. 以下を実行して週次sample planを固定する。

```bash
python experience_regime_v1/sampling.py \
  --pool <race-pool.json> \
  --output <sample-plan.json>
```

5. sample planを発走前に保存する。結果を見た後の差し替えは禁止する。

抽出順位は `week_id + race_id + seed_namespace` の固定ハッシュで決まり、同じ入力なら再実行しても同じ結果になる。

## Pre-race collection — mandatory for every selected race

各Shadow対象レースのprediction snapshotを発走前proof commitへ保存する時点で、以下を保存する。

### race_context
- venue
- race_no
- race_name
- race_category
- sample_origin: `official_prediction` / `stratified_sample`

### 全出走馬
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
- 従来どおりメインレース中心
- v3.1のSTEP1順位・印・ABC評価・STEP2・買い目を掲載
- Experience Regimeを理由に順位や印を変更しない
- 追加抽出した1R〜12Rの研究用予想は正式予想アーカイブへ掲載しない

### Shadow / research collection
- 1R〜12Rを母集団としたカテゴリ別抽出
- E0/E1/E2ラベル
- starts_before_race
- race_category × Regime別の実勝率・実3着内率
- 予測勝率・予測3着内率がある場合の平均
- Brier score
- STEP1平均順位
- ◎○▲選出率

を結果確定後に集計する。

## Why category stratification matters

Shadowの目的は単なる件数増加ではない。新馬・未勝利を含めることでE0/E1を十分に観測しつつ、条件戦・OP/L・重賞も別枠で保持する。

評価は「E1全体」だけでなく、たとえば以下まで分解する。
- 新馬 × E0
- 未勝利 × E1
- 1勝クラス × E1/E2
- OP/L × E2
- 重賞 × E1/E2

これにより、経験量の問題とレースクラス固有の問題を混同しない。

## Disclosure policy

公開サイトでは「JRA 1R〜12Rを母集団にカテゴリ別Shadow検証中」であること、目的、分類定義、抽出方式、採用条件、集計レベルの進捗を公開する。

正式予想ページには追加抽出レースの個別予想や個別馬Shadow出力を掲載しない。

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
- カテゴリ別安定性のレビュー必須
- E2にmaterial regressionがないこと

条件を満たしても自動昇格しない。次段階はRegime別・カテゴリ別の不確実性とshrinkage（μ/σ）Challengerの設計であり、本番接続は別承認とする。
