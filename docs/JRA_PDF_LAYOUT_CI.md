# JRA予想PDF レイアウト固定と公開前CI

適用: 2026-10-11以降の新規JRAメイン予想PDFのみ。10/10以前の予想・PDF・成績を再生成・上書きしない。

## 正本とページ構造

- 正式プロンプト: docs/data/latest_prompt.json → v3.7
- 帳票契約: docs/data/jra_pdf_layout_policy_v1.json
- CSS: docs/assets/jra-pdf-reader-v1.css（2026-10-10承認版。日付固定フッターを汎用表記へ変更）
- 入力: docs/reports/<race-id>.html。発走前のprediction/final_bets/proofを固定してから作る。
- 出力: docs/pdfs/<race-id>.pdf。
- HTMLタグ: data-full-report="true", data-authored-report="true"。承認済みCSSをstyle要素に正確に埋め込む。
- 冒頭5ページ + 各馬1頭1ページ + 最後3ページ。A4縦、決められた色/フォント/余白。馬ごとの1/N表示と馬番・馬名は必須。
- 要約JSONを勝手に完全版にせず、①〜⑨や直接実績など取得できなかった証拠は未取得と表示。内部SHAはPDFではなくJSON側にのみ保存。

## 自動検査

.github/workflows/jra-pdf-reader-guard.yml はPR時に承認スタイル指紋・異常系テストを検証する。意図的にCSSを変える／ページを増やす／長いSHAを露出させると失敗する。

.github/workflows/render-pdfs.yml は新規JRAレポートのみWeasyPrint 68.0で生成し、GitHubコミット前に .github/scripts/validate-jra-pdf-layout.py を実行する。CSS指紋、A4、N+8ページ、馬ごとの独立1ページと並び、文字が枠を超えていないこと、文字化け、実質空白ページ、不要な長い識別子を検査。NGならPDF公開コミットを中止する。過去PDFは再生成しない。

手動検証: python -m weasyprint docs/reports/<race-id>.html /tmp/race.pdf を実行した後、python .github/scripts/validate-jra-pdf-layout.py --html docs/reports/<race-id>.html --pdf /tmp/race.pdf を実行する。

## 公開上の注意

CI合格だけではGitHub Pages上の配信を確認したことにはならない。URLのHTTPステータスとファイル実体を別途検証する。main/docsを直接配信している場合、mainに直接pushされたHTMLを後段CIで取り消すことはできないため、branch protection/rulesetで必須CIと直接push制限を設定する必要がある。

レイアウトの変更が必要な場合はreader-v2など新しい契約・比較PDFを作成し、ユーザー承認後に正式切替する。reader-v1のCSS SHAを無断で更新しない。
