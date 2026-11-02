---
name: keiba-site-change-routing
description: Route future keiba-notes site modifications into STAGING for existing production features and LAB for unpublished features. Enforce explicit UI release approval, protect prediction/PDF/proof data, and audit GitHub Pages publication.
---

# 競馬AIサイトの環境振り分け・昇格スキル

## 毎回まず確認すること
対象: toodataa-ai/keiba-notes。最初に AGENTS.md、本スキル、references/release-checklist.md を読み、GitHubの現在のmain/docs・本番URL・LAB台帳を確認してから作業する。旧v1.01専用の説明を現行構成だと思い込まない。

2026-10-17現在:
- PRODUCTION: GitHub Pages の main/docs（正式に公開されたユーザー向け機能）。
- STAGING: docs/staging/。本番と同じ通常画面11件を staging-baseline-v2.py で生成し、ステージング表示とリンクの違いだけを付ける。新しい画面改修は本番には書かずここで審査する。
- LAB: docs/lab/。本番未公開のシミュレータ・コース設計・購入UI研究・開発中機能を実装する。
- DATA: docs/data、docs/reports、docs/pdfs、e2e_validation、地方競馬Shadowなど。正式な予想原本・PDF・買い目・proofの正本。UI改修で変更禁止。

LABとSTAGINGはGitHub Pagesで閲覧可能だが、そのこと自体は「本番に機能が存在する」の根拠ではない。本番画面とその正式導線・実装を確認すること。

## STAGING変更案の仕組み（2026-11-02から）
本番に既にある画面の変更は、次の手順だけで行う。docs/staging/ のHTMLを直接編集しない（自動で作り直される）。
1. 変更後の画面を**本番と同じ書き方**で `.github/staging-candidates/<docs配下と同じパス>` に置く（例：`.github/staging-candidates/improvement-cycle.html`、新しいCSSは `.github/staging-candidates/assets/xxx.css`）。
2. `.github/staging-candidates.json` に候補（id・title・pages・assets・summary、status=awaiting_user_approval）を登録する。
3. `python3 .github/scripts/staging-baseline-v2.py` を実行してコミット。STAGINGの該当ページは変更案で表示され（バッジ「変更案・承認待ち」）、ステージング内のリンクはステージング内に留まる。候補のCSS等は docs/staging/candidate-assets/ から配信される。
4. ユーザーにステージングURLで確認してもらい、「本番リリースOK」等の明示承認を得る。
5. 承認後、`.github/workflows/jra-ui-promote-v1.yml` を candidate_id と承認の原文（approval_quote）で実行する。変更案を本番へバイト一致でコピーし、候補を台帳から外し、STAGINGを本番に再同期し、リリース台帳（v番号を自動採番）に記録、保護データ不変・ガード検査・公開HTTPバイト一致まで確認する。
承認前に docs/ の本番画面を直接変更しない。ガードは `.github/scripts/jra-release-guard-v1.py`（全リリース共通の不変条件＋過去リリースの固定値）。

## 絶対的な振り分けルール

### A. 本番に存在する機能を改修
例: 公開済みトップ、今週のAI予想、過去成績、E0/E1/E2研究、正式公開画面の表示・操作。
1. 現在の本番ソース、参照JS/CSS、実際に配信中のページを確認。
2. STAGINGにだけ、現在の本番を基準とした最小UI差分を実装する。共有の本番資産に先に変更を加えない。ステージング専用JS/CSSを使う。
3. 本番最新の予想・買い目を参照し、古い固定プレビューで最新データを代替しない。
4. モバイル/PC・リンク・JavaScript・レイアウト・デグレ・データ非削除・GitHub Pages HTTP一致を検証する。
5. ユーザーの「本番リリース」の明示承認を待つ。承認前に本番UIへ反映しない。
6. 承認された見た目・動作を保って、許可されたUI差分のみ本番へ移植する。ステージング全体はコピーしない。STAGING表示、noindex、base href、ステージング用リンク、古いプレビュー差替えJSは本番に入れない。
7. 本番リリース後に最新の本番基準をステージングへ同期。ただし他の未承認候補を事前に退避・保護してから行う。

「そのまま本番」は、承認されたUI結果が変わらない意味であり、環境専用HTMLをバイト単位で直接コピーする意味ではない。

### B. 本番に存在しない機能を開発・修正
例: シミュレータ（docs/lab/race-simulator.html）、京都芝2000m走行線、全10場コース型、新規実験機能。
1. LABだけに実装し、LABのJS/CSS/コースJSON・参照関係を維持する。
2. LAB実URL・実ブラウザ・テスト・依存素材・研究データを検証する。シミュレータは正式予想・STEP1/STEP2・final_betsに接続しない。
3. LABの変更は feature-registry.json に事実として記録する。コミットやCI成功だけで自動承認にしない。
4. LABからSTAGINGへ進めるにはユーザーの段階移行指示と完成確認が必要。STAGING検証後も、PRODUCTIONへの昇格には別途明示承認が必要。
5. 関連HTML/JS/CSS/JSON一式を検品し、旧URL・研究PDF・他機能を削除しない。

### C. 公式予想などデータのみを更新
JRA/NAR公式発走前情報・オッズ・結果・回顧・正式HTML/PDF・Git proofは従来の正本DATA手順を継続する。正規の証拠、時刻、immutable prediction/final_bets、CI、PDF全ページ、公開HTTP一致などを満たす場合、UIの本番承認を必要としない。UIリリースと混同せず、過去正式原本を上書きしない。

### D. 両方を含む依頼
例: 今週の予想画面修正＋シミュレータ改修はSTAGINGとLABに分割する。それぞれ成果物・QA・承認・コミットを分け、意図しない本番混入を禁止する。

## 自動ミラーと旧リリース手順の落とし穴
.github/workflows/jra-staging-week-mirror-publish.yml は現行本番の画面変更後、docs/stagingの通常画面を本番テンプレートから再生成する。未承認候補がある場合、この自動処理で差分が消える恐れがある。必ず他の候補のGit SHA・保存先・承認状態を先に確認し、LABまたは別のGit証跡に保護する。通常は python3 .github/scripts/staging-baseline-v2.py --check で検査し、書き込みの自動同期は保護を確認した場合だけ。

.github/workflows/jra-site-ui-release-v1.yml は旧v1.01と旧branch構成向けで、安全ゲートがある。勝手に解除しない。現行は main/docs への、承認されたUI差分限定のリリースと正規の検証が必要。安全な経路が実行できないときはBLOCKERとして報告し、無断の代替経路へ切り替えない。

## 本番リリースの強制ゲート
- 作業前後のmain commit、stage候補SHA、対象ファイルと明示承認を記録する。
- git diffで変更ファイルをUI許可リストと照合。docs/staging全体や旧branchのコピー禁止。
- UIリリースコミットの前後で docs/data、docs/reports、docs/pdfs、e2e_validation、local_racing_shadow_v1 のGit tree SHAを比較して差分なしを保証。
- 最新予想・印・買い目・PDF・proof・回顧・公開manifestは不変。DATA更新が並行した場合は再取得して競合を解消し、古い内容で上書きしない。
- スマホ/PC実ブラウザ、画面のデグレ、GitHub Actions、GitHub Pagesの実際のHTML/JS/CSS HTTPバイト一致を確認する。
- 公開成功後のみリリース済みと報告し、台帳の承認状態を更新する。失敗・未検証なら残課題と原因を明示する。

詳しい作業順序と例は references/release-checklist.md に記載。
