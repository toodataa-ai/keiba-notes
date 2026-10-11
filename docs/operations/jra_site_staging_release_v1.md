# JRA サイト: ステージング・本番・版復元の運用 v1

## 対象
- **正式サイト**: https://toodataa-ai.github.io/keiba-notes/index.html
- **ステージング**: https://toodataa-ai.github.io/keiba-notes/staging/index.html
- **ステージング購入指示**: https://toodataa-ai.github.io/keiba-notes/staging/purchase-preview.html
- **公開履歴**: https://toodataa-ai.github.io/keiba-notes/release-history.html （公開版にリンクするのは承認後）
- 現行正式版UIは v1.00、試験UIは v1.01。**予測モデルは正式 v3.13**、実行入口は v3.14。ステージングの3＋穴1候補は `v3.15-candidate-shadow` であり、**正式な購入推奨ではない**。

## 分離
- ステージングブランチ `staging/jra-ui-v101-three-plus-ana` のプッシュにより `.github/workflows/jra-site-staging-v101.yml` を実行する。
- 現行v3.13の発走前原本と保存済みの研究データから研究候補を再生成、A4 PDFを全ページ検証、変更を **`docs/staging/` のみに限定して** 本番Pagesと同一オリジンの独立プレビューへ公開する。
- `docs/index.html`、`docs/this-week.html`、`docs/data/races.json`、正式予想PDF、prediction、snapshot、proof_commit、final_bets、地方競馬Shadowの本番ファイルには触れない。
- メインレースの**通常データ更新は継続して本番に反映**し、ページ表示改修だけステージングで承認待ちとする。

## ユーザーがステージングで確認する事項
1. 12R臨時参考予想のカード・リンクがトップと「今週の予想」から消えている。
2. 通常の購入方式が最大3行（BOX・流し・フォーメーション等を正確に展開）、穴狙いは第4行または見送りとなり、0～6,000円以内。
3. 画面とPDFに券種・JRAでの指定方法・指定馬番・点数・単価・合計が表示され、購入セットの不一致や重複がない。フルモデルの根拠、期待利益・的中率・損失リスクの比較も別途明示されている。
4. スマートフォンの表示、A4全文、文字切れ・余白・配色、他のナビゲーションを検品する。
5. ステージングActions成功だけでなく、公開したHTML/PDF/JSONとのHTTPバイト照合を完了する。

## v1.01本番「画面のみ」リリース
上の検品結果が問題なければ、ユーザーの**明示的承認を受けたあと**、`docs/site-release-requests/<unique-id>.json` を1ファイルのみGitHubに新規追加する。
```json
{
  "kind": "jra_site_ui_explicit_approval_v1",
  "mode": "release",
  "target_version": "v1.01",
  "expected_staging_sha": "<承認時点の staging/jra-ui-v101-three-plus-ana ブランチHEAD 40桁SHA>",
  "approval_note": "User explicitly approved staging v1.01 UI release after visual review."
}
```
`.github/workflows/jra-site-ui-release-v1.yml` が main の承認ファイル1件だけをトリガーに、source SHA一致確認→現行サイトをタグ`jra-site-v1.00`で凍結→許可済み画面2ファイルと版履歴だけをコミット→タグ`jra-site-v1.01`固定→公開HTTP全バイト照合を実施する。指示がなければ本番改修は行わない。

**重要**: v1.01は画面のみのリリースであり、古いv3.13の正式予想や実際の購入セットを再編・上書きしない。今後の正式レースで3+穴1選択を採用するには、新予測モデルのバージョンとSHAマニフェスト、全8券種fresh odds、STEP1不変、モデル校正と安全性確認、実レース新規発走前E2E、PDF全ページ検証、公開原本のGit証跡が合格した別の正式化が必要。ステージング画面では研究案と表示する。

## 旧版復元
明示的な「v1.00に戻して」などの依頼があった場合、同じパスに以下の新規承認ファイルを作る。
```json
{
  "kind": "jra_site_ui_explicit_approval_v1",
  "mode": "rollback",
  "target_version": "v1.00",
  "approval_note": "User explicitly approved restoring the previous UI release v1.00."
}
```
workflowが保存済みタグ `jra-site-v1.00` から画面2ファイルの**正確な過去内容**を復元する。最新版の予想・結果・正式PDF・回顧・成績・アクセスデータは絶対にロールバックしない。リリース／復元の操作履歴は `docs/data/jra-site-ui-history.json` に追記される。過去UIのコピーを手作業で推測して貼り直さない。

## 検証の正本
- ステージング配備: `.github/workflows/jra-site-staging-v101.yml`、原本と独立したステージングのみのgit diff、HTTPバイト一致。
- 承認後の本番配備: `.github/workflows/jra-site-ui-release-v1.yml`、`.github/scripts/jra-site-ui-release-v1.py`。
- 往復・原本保護のオフラインCI: `.github/workflows/validate-jra-site-ui-release-v1.yml`。
- 正式購入セットは SHA sealed final_bets を正本とし、研究用の購入操作一覧を正式購入内容として扱ってはならない。
