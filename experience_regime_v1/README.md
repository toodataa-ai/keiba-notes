# Experience Regime E0/E1/E2 — Shadow Research v0.1

## 目的

キャリア経験量の違いを、現行の能力評価とは分離して観測する研究モジュールです。

- **E0**: 発走前の通算出走数 0戦
- **E1**: 発走前の通算出走数 1〜3戦
- **E2**: 発走前の通算出走数 4戦以上

現段階では **STEP1順位・印・買い目を一切変更しません**。まず現行予想の誤差をRegime別に測り、E0/E1で本当に別モデルが必要かを検証します。

## 対象レース — 11R限定ではない

2026-10-10以降、Shadow研究の母集団は **JRAの1R〜12Rすべて** とします。

正式サイトで公開する予想は従来どおりメインレース中心ですが、Shadow研究は新馬・未勝利を含む全レースからカテゴリ別に抽出します。履歴の薄い馬を研究するのに、新馬・未勝利を外すとE0/E1の観測が偏るためです。

### 抽出方式

正式予想として作るメインレースは追加コストがないためShadowへ全件含めます。それとは別に、1R〜12Rの残りから週単位で層化抽出します。

| race_category | 区分 | 週次目標 |
|---|---|---:|
| debut | 新馬 | 3レース |
| maiden | 未勝利 | 3レース |
| class_1 | 1勝クラス | 2レース |
| class_2 | 2勝クラス | 2レース |
| class_3 | 3勝クラス | 2レース |
| open_listed | OP・L | 2レース |
| graded | GIII・GII・GI | 2レース |

目標数より開催が少ないカテゴリは、存在するレースをすべて採用し、不足分を別カテゴリで水増ししません。

抽出は `experience_regime_v1/sampling.py` が `week_id + race_id + seed_namespace` の固定ハッシュで順位付けします。同じrace poolと設定なら何度実行しても同じレースが選ばれます。結果を見て都合のよいレースへ差し替えることを防ぐためです。

## 原則

1. v3.1本線は変更しない
2. E0/E1/E2は発走前に確定できる `starts_before_race` だけで機械分類する
3. Shadow対象レースではexperience情報をprediction snapshot内に保存し、Grade Aはproof commitで固定する
4. `race_no`・`race_category`・`sample_origin` も発走前に保存する
5. 結果を見た後の分類変更・抽出変更は禁止
6. 「未経験＝低能力」としない
7. E0/E1の不確実性を、根拠なく固定減点しない
8. μ/σ補正はRegime別かつカテゴリ別の誤差が十分に観測されてからChallengerとして別実装する

## prediction snapshotへの追加契約

```json
{
  "race_context": {
    "race_no": 4,
    "race_category": "debut",
    "sample_origin": "stratified_sample"
  },
  "experience": {
    "model_version": "e012-shadow-v0.1",
    "horses": {
      "1": {"starts_before_race": 0, "regime": "E0"},
      "2": {"starts_before_race": 2, "regime": "E1"},
      "3": {"starts_before_race": 8, "regime": "E2"}
    }
  }
}
```

`sample_origin` は正式予想レースなら `official_prediction`、追加研究枠なら `stratified_sample` とします。

`regime` は監査用の冗長項目です。正解は常に `starts_before_race` から再計算します。不一致は検証エラーにします。

## Shadowで測る指標

馬単位でRegime別、さらに **race_category × Regime** で以下を集計します。

- horse observations
- race coverage
- 実勝率 / 実3着内率
- 予測勝率平均 / 予測3着内率平均
- 勝率Brier / 3着内Brier
- STEP1平均順位
- ◎○▲への選出率

これにより「E1が弱い」ではなく、たとえば「未勝利のE1だけ過信」「1勝クラスのE1は安定」のように切り分けます。

## 昇格フロー

`Shadow observation → category × regime analysis → historical replay → prospective Grade A蓄積 → μ/σ仮説 → Challenger → E2E比較 → Candidate → 人手承認 → production`

自動昇格はしません。

## 次段階のμ/σ構想

Regimeごとに単純な一律加減点を入れるのではなく、最終的には

`latent ability μ + uncertainty σ`

として扱います。ただしσの大きさや縮約率は現時点では未確定です。Shadowデータからカテゴリ別にも校正し、未検証の係数を本番へ入れません。
