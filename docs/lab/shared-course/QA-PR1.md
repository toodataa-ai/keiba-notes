# 京都2000互換移植: PR1途中比較

Base: c653c23fc7d80745dce08e32b890cb92a846e2eb。LABのみ・未承認。

| 比較 | 結果 |
| --- | --- |
| 架空18 / 実17 × 90 / legacy × seed 2026,1,75 | 12ケース、全馬完走後の全物理状態が完全一致 |
| 同じ条件の繰り返し | 完全一致 |
| 0..2000m × lane 0..14 | 30,015点完全一致 |
| 他コースの90表示opt-in | 表示のみ共通化、prestart six物理値は不変 |
| Chromium 390/1024px × 架空18/実17 | 1270m地点の物理状態・投影位置一致、JSエラーなし、横overflowなし |
| 走路グラフ | 支線、芝→ダート、直線、反復周回、不正経路・未対応コース拒否を確認 |

背景SVG・物理エンジン・京都の座標スプラインは未変更。コース選択欄の追加が表示差分。京都以外を利用可能とは表示しない。

1/2/4倍の実時間、ゴール前80m切替、ゴール板通過、全馬の結果表示、目視検品はこのPRで未完了。ブラウザテストのスクリーンショットはローカル /tmp/kyoto-{before,after}-{390,1024}-{synthetic,shuka2026}.png に保存。画面全体の画素同一や本番公開済みとは主張しない。

## 確認方法

- node tools/test-shared-course-v1.cjs
- node tools/compare-shared-course-v1.cjs BASE_CHECKOUT
- CHROMIUM_PATH=/usr/bin/chromium node tools/browser-shared-course-v1.cjs BASE_CHECKOUT

公開LABの現行URL: https://toodataa-ai.github.io/keiba-notes/lab/race-clean-course-v1.html

Draftブランチの変更はこのURLには未配信。PRマージやPagesデプロイは実施していないため、新版の公開LAB確認URLは未発行。ローカルまたはPRブランチのプレビューで確認する。
