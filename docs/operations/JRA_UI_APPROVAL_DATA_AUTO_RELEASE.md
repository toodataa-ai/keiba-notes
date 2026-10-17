# JRAサイト：承認と自動データ更新を分離した運用（子連れイベント方式）

正式なサイト画面改修には、ステージングでの表示確認、CIおよび**ユーザーの明示承認**が必須です。承認前に `docs/index.html`、`docs/this-week.html`、CSS・サイト用JSを本番へ昇格させません。正式画面v1.00とv1.01は復元用ブランチで保管済みです。復元時に `docs/data/races.json` 等のレースデータは絶対に戻しません。

**予想・結果・払戻・回顧データ更新は承認不要**です。JRAの正式プロンプト、発走前の時刻ゲート、実オッズ独立確認、STEP1不変とSTEP2監査、Git proof、HTML/PDFの全ページ検品、公開manifestおよびHTTP実体照合を通過すれば、データのみ自動的に公開します。更新対象がレース予想ページ・レースPDFでも、それらは生成されたレースデータなので画面改修として扱いません。過去の正式予想原本・final_bets・proofは不変、公開される最新レース参照だけを切り替えます。

現在の本番Pagesソースは `main/docs` です。子連れイベントの `production` UIと `data-production` データから単一のPagesアーティファクトを合成する方式へのホスティング切り替えは**未実施**。既存のJRA自動予想を停止させないよう、現行のデータ更新Actionsは継続し、正式に別途監査するまでPagesソースを変えないでください。

最終公開履歴は `docs/data/production-releases.json` を表示用、`.github/production-releases.json` を正本として同値で管理します。本番配信済みで検証済みのUI版だけ登録し、途中のステージングコミット、失敗したリリース候補、日付が確認できないリリースの架空公開時刻は登録しません。


## 恒久的な改修ルーティング（2026-10-17制定）

正本: .github/skills/keiba-site-change-routing/SKILL.md
入口: AGENTS.md
チェックリスト: .github/skills/keiba-site-change-routing/references/release-checklist.md

本番に**すでに存在する機能のUI改修**はSTAGINGで実装・実機確認してから、ユーザーの明示的な本番承認を受け、レビュー済みのUI差分だけ本番に移植する。ステージング全体のコピー（noindex、STAGING表示、旧サンプルの混入）は禁止。

本番に**存在しない機能**（レースシミュレータ・未公開コース型など）の改修はLABで実装・検証し、無断でSTAGINGや本番へ移さない。LAB→STAGINGにもユーザーの段階移行指示が必要で、さらに本番には別途承認が必要。

正式予想・結果・買い目・PDF・proofなどのDATA更新は既存の独立監査で継続し、UIリリースに巻き込まない。現行のPagesソースはmain/docs。旧v1.01のbranch/Action手順と矛盾した場合、現行構成を確認して本スキルを優先する。ステージング自動ミラーによる未承認候補の消失を防止する。
