# Experience Regime E0/E1/E2 — Shadow Research v0.1

## 目的

キャリア経験量の違いを、現行の能力評価とは分離して観測する研究モジュールです。

- **E0**: 発走前の通算出走数 0戦
- **E1**: 発走前の通算出走数 1〜3戦
- **E2**: 発走前の通算出走数 4戦以上

現段階では **STEP1順位・印・買い目を一切変更しません**。まず現行予想の誤差をRegime別に測り、E0/E1で本当に別モデルが必要かを検証します。

## 原則

1. v3.1本線は変更しない
2. E0/E1/E2は発走前に確定できる `starts_before_race` だけで機械分類する
3. Grade Aではexperience情報もprediction snapshot内に保存し、proof commitで固定する
4. 結果を見た後の分類変更は禁止
5. 「未経験＝低能力」としない
6. E0/E1の不確実性を、根拠なく固定減点しない
7. μ/σ補正はRegime別誤差が十分に観測されてからChallengerとして別実装する

## prediction snapshotへの追加契約

既存JSONに以下を**任意追加**できます。既存E2E schemaは壊しません。

```json
{
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

`regime` は監査用の冗長項目です。正解は常に `starts_before_race` から再計算します。不一致は検証エラーにします。

## Shadowで測る指標

馬単位でRegime別に以下を集計します。

- horse observations
- race coverage
- 実勝率 / 実3着内率
- 予測勝率平均 / 予測3着内率平均
- 勝率Brier / 3着内Brier
- STEP1平均順位
- ◎○▲への選出率

これにより「E0だけ過信」「E1だけ過小評価」「E2は安定」などを結果論ではなく継続データで確認します。

## 昇格フロー

`Shadow observation → historical replay → prospective Grade A蓄積 → μ/σ仮説 → Challenger → E2E比較 → Candidate → 人手承認 → production`

自動昇格はしません。

## 次段階のμ/σ構想

Regimeごとに単純な一律加減点を入れるのではなく、最終的には

`latent ability μ + uncertainty σ`

として扱います。ただしσの大きさや縮約率は現時点では未確定です。Shadowデータから校正し、未検証の係数を本番へ入れません。
