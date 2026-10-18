# LAB v6: 元画像そのまま＋馬番の丸が走る
- WHY: v1〜v5では全体図に原画像、実況に独自レンダリングの芝帯を使ったため、実況が歪んだ。
- FIX: 実況ステージの元画像は全体図と**同じURL**。620×430pxの絵の見かけを保持したまま、CSS translate + isotropic scale で注目馬周辺を切り出す。画像は自前のコース線で上書きしない。
- QUALITY: 元画像のピクセルをブラウザの ImageSmoothingQuality=high の描画で4倍の2480×1720キャンバスに補間。サーバーに画像をコピー/再配布しない。画素数は増やせても元にない実細部は増えない。ブラウザがアップスケール不可の場合は同一画像のDOM imgにフォールバック。
- HORSE: 枠色付きの**馬番丸自身**を動的キャンバスで直接描く。馬シルエット、矢印、実位置ドット/ガイド線はなし。衝突回避は文字マーカー表示位置のみ（エンジンの物理位置・レーン・脚質・速度・時計・結果は不変）。
- RISK: 外部画像配信停止時には背景が欠ける。画像自体の拡大時に元解像度由来の細部限界がある。独立にトレースされた走行位置の画像上較正は継続して確認が必要。
- ACCEPT: 8 checkpoints x mobile 390px + desktop 1024px, independent marker spacing, same src in both, 4x browser resample loaded, no drawn course, Pages HTTP bytes match, official DATA untouched.
- ENV: Only LAB. Formal races, predictions, odds, final_bets, review and PDF untouched. No STAGING/PRODUCTION promotion or feature approval without explicit user decision.

## v6.1: 番号の芝帯内表示
- 実ブラウザ画像で一部の衝突回避番号が茶色い領域へ飛び出していたため、表示上の候補を走行距離±136mの近傍と芝内外ラチ間0.12〜0.90の領域のみに制限。
- 注目馬の表示位置は実走行座標のまま。他の番号もカメラ上でコース帯内の空き位置を優先する。色や帯は描かない。
- 衝突と芝帯内の両方をブラウザQAゲートへ加える（見えない馬は従来同様「全頭隊列」から追跡可能）。
