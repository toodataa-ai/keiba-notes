# 京都芝2000m内回り・うまぽっと画像上走行線 QA v0.45

## 範囲と安全性
- 環境: LABのみ。正式本番・ステージングは変更しない。
- コード: `docs/lab/race-umapot-overlay-v1.js` の表示座標補正と診断用の9地点ガイド。
- デモ: https://toodataa-ai.github.io/keiba-notes/lab/race-simulator.html?demo=shuka-one
- 診断（紫の走行線・9地点ラベル）: https://toodataa-ai.github.io/keiba-notes/lab/race-simulator.html?demo=shuka-one&guide=1
- 原画像: https://umapot.com/data/powerpoint/kyoto_couse/kyoto_couse_1.jpg （うまぽっとの原画像を外部リンクで表示。画像そのものは複製していない）
- **最重要**: レース計算エンジン、脚質、ペース、時計、正式予想、STEP1/STEP2、買い目、PDF、proofは変更しない。

## 画像座標の登録
ソース画像は620×430px。距離・座標 (m, x, y):

| 距離 | x | y |
|---:|---:|---:|
| 0 | 350 | 317 |
| 100 | 294 | 316 |
| 308.7 | 178 | 301 |
| 530 | 165 | 204 |
| 900 | 286 | 147 |
| 1270 | 463 | 136 |
| 1435 | 510 | 197 |
| 1671.6 | 490 | 317 |
| 2000 | 294 | 317 |

登録値は実画像の内回りの芝帯中央を別途手動で参照した**画面ピクセル近似**。GPS・測量値ではない。距離に沿うアンカー補正はC1連続の区分Hermite曲線を使い、アンカーをまたぐ表示位置の速度の段差を抑える。東京芝2000m/京都芝1400m外回りには補正を適用しない。

## 監査
- 自動QA: `tools/test_race_sim_lab_kyoto_inner_v045.cjs`。
- CI: `.github/workflows/validate-lab-kyoto-inner-v045.yml`。
- 実行: https://github.com/toodataa-ai/keiba-notes/actions/runs/39016076212 （成功）。
- 9地点: 登録値との差が0.02px以内。
- 5mごとの独立した内芝帯ガイドとの差: 最大5.17px、許容10px以内。
- 5mごとの最大マーカー移動距離: 3.03px。
- 元の東京/京都外回りのチェックポイント値と同じ。
- Chromium 390px/1024pxで実画像620×430読み込み、ページJavaScriptエラーなし、1頭の再生開始と描画が成功。
- Actions runの artifact `kyoto-inner-2000-image-alignment-v045` に原画像＋ガイドのスクリーンショットを保存（保持14日）。

## 未完了・目視承認
**現時点ではユーザーの画面目視承認は得ていない。** 自動検査の合格を正式な「走行可能コース承認」に読み替えてはいけない。原画像に重ねた9地点の位置、とくに最初のコーナー・内外分岐・第4コーナー・直線をユーザーが確認する。承認後に東京芝1600mなどへの汎用化を進める。別のレースの実馬データに接続する前に、対象コースの受入れを独立に行う。

## 再開時の手順
1. `AGENTS.md` と `.github/skills/keiba-site-change-routing/SKILL.md` を先に読む。
2. 開発先は本番未公開機能のためLAB。 `docs/staging` の旧実験ソースは互換アーカイブとして保持。
3. `docs/lab/race-umapot-overlay-v1.js` 内の距離アンカー・画像補正だけを変更。
4. 既存2コースの座標不変、5m刻み、元画像と実ブラウザをすべて再検証。
5. GitHub Pages公開ファイルとGit blobの一致を検査し、ユーザーの目視を待つ。
