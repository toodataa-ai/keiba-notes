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
