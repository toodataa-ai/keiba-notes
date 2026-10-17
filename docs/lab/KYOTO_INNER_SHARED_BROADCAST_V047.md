# 京都芝2000m内回り LAB v0.47 — 実況と全体図の画像・座標統一

## 解決する問題
実況用の独立したJRA近似ベジェが、スタート直後および2コーナー出口〜3コーナー入口の実際の直線区間で緩く方向を変えていた。うまぽっと実コース画像を使う全体図では、この描画不一致は発生しない。**実況専用コースを描き直さず、全体図と同一の原画像を拡大表示する**。

## v0.47方針
- 適用：LABの京都芝2000m内回り。全体図の画像は `#kyotoCourseImage`（うまぽっと外部オリジナル620×430px）を再利用し、別ファイルとして再配布しない。
- 全体図の馬番と実況の馬番は共に `RaceUmapotOverlay.point(profile,d,lane)` の結果を使用する。
- 実況は `RaceSimBroadcastMap` が同じ画像を `drawImage(img,0,0,620,430)` し、世界座標の平行移動・等倍比率の拡大のみ。角度回転・縦横の異なる倍率は不使用。
- 全体図と実況ではカメラの拡大率・表示範囲だけが異なる。カーブ入口や直線の角度は絶対に別計算しない。
- ゴール直前も独立した直線画面に切り替えない。元画像と共通位置の描画を継続する。
- 元画像が読めない場合、従来の別形状コースを代用せず、その旨を表示する。
- 対象外：東京芝2000m・京都芝1400m外回りの実況は従来方式のまま。正式予想、発走前原本、馬場/脚質、エンジン、時計、買い目には触れない。

## 検査
- `tools/test_kyoto_broadcast_shared_map_v047.cjs`：17の距離地点、2画面サイズ、同一座標・原画像・非回転を検査。
- `tools/test_race_sim_lab_kyoto_inner_v045.cjs`：既存の9地点、5m連続性、東京/京都外回りの回帰。
- GitHub Actionsで実ブラウザ390/1024px、画像ロード・再生・描画検査。
- LAB目視確認を経て将来の汎用化へ。まだ本番公開承認ではない。

## 確認URL
- https://toodataa-ai.github.io/keiba-notes/lab/race-simulator.html?demo=shuka-one&v=47
- https://toodataa-ai.github.io/keiba-notes/lab/race-simulator.html?demo=shuka-one&guide=1&v=47
