# 実レースE2Eケース

実レースは `cases/<race-id>/case.json` を1件ずつ追加します。

## Grade A（prospective_strict）の例

```json
{
  "schema_version": 1,
  "race_id": "2026-10-10-example",
  "date": "2026-10-10",
  "venue": "東京",
  "surface": "turf",
  "race": "Example Stakes",
  "grade": "prospective_strict",
  "cutoff_at": "2026-10-10T15:40:00+09:00",
  "predictions": [
    {
      "version": "v3.1",
      "path": "e2e_validation/predictions/2026-10-10-example/v3.1.json",
      "proof_commit": "PRE_RACE_COMMIT_SHA"
    }
  ],
  "result_path": "e2e_validation/results/2026-10-10-example.json"
}
```

`proof_commit` は、予想ファイルが発走前にGit上に存在したコミットです。採点器はHEADではなく、このコミットから予想を読みます。

結果はレース後に `result_path` へ追加します。予想ファイルへ結果情報を追記しないでください。

## Experience Regime Shadow（2026-10-10〜）

Shadow研究では正式予想の11Rだけでなく、JRA 1R〜12Rを母集団にカテゴリ別抽出したレースもGrade Aケースとして追加できます。

Shadow対象predictionには以下を発走前に保存します。

- `race_context.race_no`
- `race_context.race_category`
- `race_context.sample_origin`
- 全出走馬の `experience.horses[].starts_before_race`
- 全出走馬の `experience.horses[].regime`

`sample_origin` は正式予想レースなら `official_prediction`、層化抽出した追加研究レースなら `stratified_sample` とします。

追加研究レースは正式サイトの予想アーカイブへ表示する必要はありません。E2E/Shadow検証用のprospective caseとして保存します。
