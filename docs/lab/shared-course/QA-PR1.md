# PR1 QA — 共通基盤・京都2000互換移植

比較基準は **c653c23fc7d80745dce08e32b890cb92a846e2eb** に固定。引継ぎHEADは f176feab634055ddd1833827e47a54fd8eb7784b。PR #77はDraft、未マージ・未配信。本レポートはレビュー用であり、利用承認ではない。

## 実装結果

JSON Schema/厳格バリデータ、C1有向グラフのposition/rails/tangent/section/grade/runoff、共通Runtime、エンジン設定注入、京都の既存C1/物理geometry/画素マスク互換、2〜18頭/seed/倍率等のUIを実装。京都以外のロックは解除していない。原SVG・旧C1データ・正式データは変更なし。コース別HTML/エンジンの複製なし。

## QAマトリクスと実測

詳細値と各画面のSHA256は [QA-RESULTS-PR1.json](QA-RESULTS-PR1.json)。スクリーンショットはローカル `/tmp/keiba-pr1-matrix/`、`/tmp/keiba-pr1-realtime/`、`/tmp/keiba-pr1-goal/`、`/tmp/keiba-pr1-existing-browser/` とPRのCI artifactに保存する。画像素材の新規公開・ページ配信はしない。

| 検査 | ケース | 結果 |
| --- | --- | --- |
| 既存compare-shared-course-v1 | 架空18/実17 × 90/legacy × seed 2026,1,75 | 12最終物理状態完全一致・同seed再現 |
| Runtime経由の固定SHA比較 | 上記12条件＋繰り返し | 全馬の最終物理状態完全一致 |
| 京都raw C1座標 | 0〜2000mの整数距離 × lane 0〜14 | 30,015点完全一致（既存APIとRuntime両方） |
| 同一Chromium内の固定SHA比較 | 上記12条件＋少頭数3seed | 15条件完全一致 |
| 必須1270m A/B | 390/1024px × 架空18/実17 | 全物理状態・投影・馬番描画位置・zoom一致 |
| 全区間ブラウザ再生 | 390/1024 × 6/18/実17頭 × 3seed × 1/2/4倍 | 54全馬完走、全最終状態が同じChromiumの固定SHA基準と完全一致 |
| 実時間requestAnimationFrame | 390/1024 × 6/18/実17頭 × seed2026 × 1/2/4倍 | 18全馬完走、倍率間と固定SHA基準に完全一致 |
| 枠外進入・全馬ゴール板通過 | 390/1024 × 2/6/18頭 × 1/2/4倍 | 18条件、全馬進入・板通過・完走、走行中逆行0 |
| 既存ability90ブラウザ検査（変更なし） | 390/1024 × 架空18/実17 × 1/2/4倍 | 12条件成功、停止フレーム0、最大フレーム間隔約16.8ms、カメラlegacy切替で物理不変 |
| 選択UI | 人数変更・seed変更・実17固定・未検証disabled | 確認、横overflowなし |
| schema/graph | 不正定義31種類、支線・合流・直線・芝→ダート・2周回・runoff | 不正定義拒否、架空走路の6頭が単一エンジンで完走・再現 |
| 既存Node回帰 | test_race_clean_course_v1 / ability90 | 成功。条件の削除や物理許容値の緩和なし |

54+18条件はスタート、1270m、直線入口1672m、ゴール前80m、ゴール板、全馬完走後の6地点を同じ連続再生で記録。描画は物理固定80msと独立。全頭数・枠色、18番lane範囲、実況/全体図の同じ座標使用、SVG等方変換、画像縦横比、結果行数、1〜3着表示を数値検査。2頭時は存在する1〜2着を検査。

### 一致と差分・残る見え方

- 画面差分は選択UIの追加。京都の物理・SVG・raw C1・1270m投影は維持。画像寸法、アンカー、マスク、カメラ、余走設定をJSONから注入する。
- 18頭の密集・部分重なりは旧版から残る。54/18マトリクスの6地点で重大重なり指標は最大17組。座標を動かして重なりを隠す処理は追加していない。個々のtouching/severe値はJSONに残す。目視受入れ対象であり「重なりゼロ」とはしない。
- 余走カメラが引く間のスクリーン上の変位と、馬の走行方向を区別。ゴールまでの逆行0、物理距離は単調、従来のゴール後減速・引き画を維持。
- NodeとChromiumのMath実装差で架空18頭の1頭のdisplayDに2.27e-13m差を観測。各環境内の旧/新比較は厳密一致。跨環境の差を許容値で丸めて合格にはしていない。
- 最初の追加テストで余走上限38mの設計ミスを検出し、旧式の上限＋表示coastを覆う125mへ修正。物理終了閾値32mは不変。
- 初回マトリクス末尾のoptionに対するPlaywright isDisabled判定を、DOMのdisabled属性＋`:disabled`検査へ訂正。完走測定を保存し、UI検査だけ再実施。先行失敗の履歴は生JSONのpriorHarnessErrorsに残す。

## 再実行

```sh
node tools/build-shared-course-v1.cjs --check
node tools/audit-shared-course-v1.cjs --check
node tools/test-shared-course-v1.cjs
node tools/test-shared-course-runtime-v1.cjs
node tools/compare-shared-course-v1.cjs BASE_CHECKOUT
node tools/qa-shared-course-parity-v1.cjs BASE_CHECKOUT /tmp/compatibility.json
node tools/qa-shared-course-browser-baseline-v1.cjs BASE_CHECKOUT /tmp/compatibility.json
node tools/browser-shared-course-v1.cjs BASE_CHECKOUT
COURSE_QA_OUT=/tmp/course-controlled node tools/qa-shared-course-browser-v1.cjs
COURSE_QA_OUT=/tmp/course-realtime node tools/qa-shared-course-browser-v1.cjs --realtime
node tools/qa-shared-course-goal-v1.cjs
node tools/summarize-shared-course-qa-v1.cjs /tmp/compatibility.json /tmp/course-controlled /tmp/course-realtime
```

BASE_CHECKOUTは必ず指定SHA。CIもこのSHAをcheckoutする。既存Node回帰、既存能力90ブラウザ検査も維持する。CIは検査・artifact保存のみ、push/merge/deploy権限を持たない。

## CI・blocker・完了判定

新CIの最新実行状況・commit SHAはPR本文に記録。初回の追加監査は、Actionsの合成mergeに含まれるmain並行更新と比較用checkoutをPR差分と誤認して失敗。比較対象を合成mergeの第1親に固定し、`.course-base/` の検査用checkoutだけを未追跡一覧から除外した。正式データの許可範囲は広げていない。既存release-channel-guardは **作業前から** 2つの公開履歴JSONが不一致。公開側だけに `pending_public_validation` のv1.06項目がある。基準/引継ぎHEAD/mainのblob/SHA256と意味差は [CI-EXISTING-GUARD.json](CI-EXISTING-GUARD.json)。両原本は編集せず、CIを無効化しない。

実装とローカル自動QAは完了し、レビュー可能。**PR1の最終受入れは未完了**：ユーザーによる全体の目視承認、権利台帳の未確認事項、既存CI blockerの扱いに関するレビューが残る。Safari/実機は未確認、Chromiumでの検査を全ブラウザ保証とはしない。人の目視検査を自動検査で代替した扱いにしない。

新しい公開LAB URLはない。既存の https://toodataa-ai.github.io/keiba-notes/lab/race-clean-course-v1.html は従来配信版で、このPRの確認先ではない。ローカルのPRブランチとCI artifactで確認する。

PR2へ進む条件はPR1の検証結果・残る目視/権利/CI事項の確認と、ユーザーの明示的な次段階承認。今回PR2や新しい実コース定義には着手していない。マージ・Pages公開・本番リリース・STAGING昇格は実施しない。
