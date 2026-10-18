# 京都芝2000m内回り LAB v13 Safari再生停止 修正監査

## 実際の原因
2026-10-18のiPhoneで『動かない』と報告。GitHub Actions `39122726041` で実際の公開URLをLinux WebKit（iPhoneユーザーエージェント）で再現。
- `liveCourseImage`: `naturalWidth=620`, `naturalHeight=430`
- `realCourseImage`: `naturalWidth=368`, `naturalHeight=255`（SafariのレスポンシブSVGサイズ認識）
- SVGのHTTPレスポンスは正常200、JavaScriptエラー0。内部`engine.state.leader`だけは602m→777mへ進むが`turfReady=false`・画面`0m`のまま。
- v12は両画像の`naturalWidth===620`を必須としていたため`verifyVectorSource()`が描画の初期化を飛ばし、`paint()`が早期returnしてしまっていた。

## 修正
- 元SVGの読み込み成功・naturalWidth>0・naturalHeight>0・元図620:430の縦横比許容誤差と同一資産URLで判定し、Safari表示幅の違いに依存しない。
- `RaceCleanTurf.create`も元SVGの画像幅の完全一致を要求せず、`drawImage(image,0,0,W*RASTER,H*RASTER)`で原図viewBoxを620:430へ合わせて安全ピクセルを再現。
- 画像が読み込めなければ見かけだけ成功報告しない。Playwright WebKitで地元と公開サイト両方へ実際に『スタート』クリック、数秒後に距離進捗・turfReady・vectorReady・画像寸法・JSエラーを厳格に監査。
- 既存のうまぽっとSVG・京都1400物理・内ラチ優先・馬番同一サイズ・JRA予想・買い目・ステージング・本番に差分なし。

## 承認
v13のWebKit公開URL E2EおよびChromium従来QAがともに成功した後のみ実機確認リンクを案内。ユーザーの画面承認前に本番へ昇格しない。
