# JRA全10場 馬場予測 v2 additive layer

## 目的
既存の中山・阪神モデルおよび競馬予想プロンプトを変更せず、JRA全10場の芝/ダートを段階的にカバーする追加レイヤー。

## 非破壊方針
- 既存ファイルを削除・上書きしない。
- `latest_prompt.json`、`prompt_history.json`、`races.json`、HTML/PDF生成処理には触れない。
- 既存の検証済み/パイロットモデルを自動的に置換しない。
- 本ディレクトリは opt-in。明示的に `baba_models_v2.predict` を利用した場合だけ動く。
- 他場モデルの係数を「検証済みモデル」として流用しない。
- Candidate生成までは自動化してよいが、Candidate→Validatedと本番ルータ変更は承認必須。

## 対応
札幌、函館、福島、新潟、東京、中山、中京、京都、阪神、小倉 × turf/dirt = 20モデル。

## モデルライフサイクル
`pilot → backtesting → candidate → validated → degraded / retired`

状態の正本は `model_registry.json`。サイト公開用の `docs/data/baba_model_registry.json` は `build_dashboard_data.py` で正本から生成する。

### Stage A
前日・前々日情報から次のJRA公式朝含水率を予測する。LOYOまたは時系列ホールドアウトで MAE / RMSE / ±1pt 等を検証する。

### Stage B
当日朝のJRA公式含水率をアンカーに、降雨・乾燥時間・気温・風・日照等から各レース時点のJRA公式「良/稍重/重/不良」を確率予測する。

発走時含水率そのものに公式正解ラベルがない場合、それを架空の教師ラベルとして扱わない。Stage Bの昇格判定は公式馬場状態ラベルを用い、Log Loss / Brier Score / Calibration 等で現行heuristicと比較する。

## 昇格ガード
`promotion_policy.json` に初期昇格基準を定義する。

- サンプル数と複数年データを必須化
- baseline改善を必須化
- dry/wet・雨天遷移ケースを別監査
- leakage監査必須
- backtest再現性必須
- Candidateは本番へ自動接続しない

`promotion.py` はこれらを機械判定し、条件不足を理由付きで返す。

## 既存モデルの扱い
中山・阪神は既存専用モデルを維持する。ただし新ダッシュボードでは、Stage AとStage Bを分けて表示する。

たとえば中山芝v1.1はStage AがLOYO検証済みだが、Stage Bは依然として operational heuristic であり、モデル全体を一括して「すべて検証済み」とは表示しない。

## 東京・京都
東京・京都 v0.1 は最初の `backtesting` 対象。東京は2018年以降の履歴、京都は2023年再開後を現行レジームとして優先する。旧京都を無条件に混合しない。

## ファイル
- `config.json`: 競馬場別のJRA含水率目安・現行Pilot設定
- `predict.py`: 非破壊Stage B Pilot
- `model_registry.json`: 20モデルの状態・実績・昇格不足条件
- `promotion_policy.json`: Candidate昇格基準
- `promotion.py`: 自動昇格判定
- `validate_registry.py`: レジストリ/本番接続ガード
- `build_dashboard_data.py`: サイト表示データ生成
- `test_smoke.py`: 非回帰・昇格ガードのSmoke test

## CI
`.github/workflows/validate-baba-models.yml` で以下を確認する。
1. 20モデルが重複なく登録されている
2. Candidateが無承認で本番接続されていない
3. Pilot予測が既存モデルを置換していない
4. 昇格判定ガードが機能する
5. サイト用registryが正本と同期している
