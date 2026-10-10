# JRA v3.10 発走前実行パイプライン（入力契約・運用）

2026-10-11追加。**既存の予想ロジック、v3.10買い目最適化エンジン、過去データ、地方競馬Shadow、PDF表示仕様は無変更。**

## 現在の実装範囲

- .github/scripts/jra-prestart-pipeline-v310.mjs: 外部で観測・監査済みのSTEP1、馬番と枠番、中央勝率、低・高シナリオと候補方式・実オッズを読み取る
- 同スクリプト: 全馬の3着以内順序付き着順分布を低・中・高の3つの相互排他的な確率分布として生成する。中央シナリオの勝率周辺分布はSTEP1を固定して維持する
- .github/scripts/jra-strategy-engine-v39.mjs: 従来の8券種・全主要方式を展開する。市場価格と選択番号を正規化した個別馬券単位で結合する
- .github/scripts/jra-portfolio-optimizer-v310.mjs: 既存の0/1整数ナップサックで、100円単位、1レース6,000円以内の期待純利益最大化を厳密実施する
- .github/workflows/jra-prestart-pipeline-v310.yml: 実レース入力が準備された場合にのみ手動実行し、GitHub上で「未封印スナップショット」を先にコミットしたうえで、発走時刻より前の証跡コミットSHAを用いて「正式JSON」を後から封印する。欠損・発走後・オッズ価格の衝突・旧パス上書きはBLOCKER
- .github/scripts/test-jra-prestart-pipeline-v310.mjs: 合成入力による正規・欠損・遅延・改変ケースの回帰テスト

**重要**: 本パイプラインはJRA、二次オッズサイト、追い切りなどの外部情報を自動取得しない。ChatGPTなどの情報収集工程で**実際に検証されたソースと証跡**を入力JSONに準備する必要がある。テストの合成オッズを実際のレースに転用することは禁止。市場オッズも勝率モデルも検証なしには生成しない。

また、**フルレポートHTML / 承認済み1頭1ページPDFの自動生成・公開は未実装**。正式JSONを生成できてもpublication_statusは「awaiting_independently_authored_full_html_and_validated_pdf」を維持し、PDF・Pagesまで完了とは報告しない。既存のPDFレンダラと検品CIを利用する場合は別途フル原稿を準備する。

## 入力ファイルの配置と実行

1. レースごとに、次項のJSON契約に沿って発走前の情報を監査・記録し、GitHubの **e2e_validation/inputs/YYYY-MM-DD-レースslug.json** に新規保存する（過去の予想は編集しない）。
2. GitHubの **Actions → JRA v3.10 prestart prediction pipeline → Run workflow** で input_path にその保存パスを入力する。毎回別ファイルのレースIDで動かす。
3. テスト→予想生成→証跡コミット→正式JSON封印→v3.10既存検査の順に進む。発走済み時刻なら途中で必ず失敗する。
4. 結果は e2e_validation/predictions/YYYY-MM-DD-レースslug/v3.10-runN-attemptN.json に格納。proof_commitはスナップショットを含むGit SHAとして照合する。
5. PDFおよびサイト掲載は別工程。正式JSONコミット＝公開済PDFという扱いは禁止。

## 入力JSONの必須フィールド

| フィールド | 要求 |
|---|---|
| prompt_version / race_id | v3.10 / \`YYYY-MM-DD-英数字slug\` |
| race_context | venue, race_no, start_at（タイムゾーン付きISO8601）, official_source_url, sale_field_size（9以上）, place_paid_positions=3, offered_types（通常8券種のみ） |
| frame_map | 全出走馬の馬番→公式枠番の対応。枠連に利用 |
| step1 | fixed_at, primary_source, no_odds_used_to_change_marks=true, runners（全頭） |
| step1.runners[] | horse_number, horse_name, mark, factor_grades（①～⑨、9つのA+/A/B+/B/B-/C）, evidence, source_url, win_probability（全頭合計1）。根拠不明・オッズ逆算・単なる印からの自動勝率配賦は禁止 |
| scenario_factors | lowとhighそれぞれのassumption（根拠文）と、全頭馬番をキーとするby_horse相対重み（正数）。シナリオ毎に規格化し全着順確率を計算 |
| strategy_plan_fixed_at | オッズ参照前に選んだ各方式の固定時刻 |
| strategies[] | type, strategy_kind, strategy_id, definition（既存expandStrategy準拠）, ability_reason, risk_reason, decision_reason。少なくとも通常8券種それぞれ1方式 |
| mode_exclusions[] | 採用計画のない各モードについてtype, mode, reason, evidence。**全方式を「評価済候補」または「除外理由あり」で網羅** |
| market_quotes[] | race_id, type, selection, market_selection_id（正規化ticketKeyと完全一致）, market_odds, observed_at, source_url, source_capture_path（e2e_validation/quote-evidence/配下に保存された証跡ファイル）, source_capture_sha256（実ファイルSHA-256、64桁）, quote_verified=true。複勝・ワイドの幅は[下限,上限]で記録 |
| input_source | 情報取得・確認の記録、監査担当など |

時刻はすべてTZ付きで扱う。STEP1固定→方式の候補計画固定→オッズ観測→最終freeze→発走の順を厳守する。オッズ観測時刻は最終固定時刻より前でなければならない。**URLと保存した証跡ファイルのSHA-256が一致しても価格の真実性までは証明できない**。元ページ内容と個別馬券、時刻の一致を入力工程で確認する必要がある（この点は今後の自動取得機構の課題）。

完全な実レース価格が揃っていなくても、**確認済み個別馬券だけを評価対象にする**。確認済み価格がゼロなら「妙味なし」ではなくBLOCKERとして停止。八券種・全方式の調査状況と価格不足を公開原本に残す。

## 安全性／互換性

- 既存prompt最新版指示はdocs/data/latest_prompt.json=v3.10を維持し、既存のmanifestのSHAを変更しない。これは**運用パイプラインの追加**であり新しい予想ロジックのバージョン変更ではない。
- パイプラインはdocs/data/races.json、既存HTML/PDF、過去prediction、地方競馬Shadowを変更しない。
- 同レースでもrun_id毎に新規のスナップショットと正式予想を生成。上書きは禁止。
- GitHub Actionsの成功は**構造化JSONの検証**を意味するだけで、馬の実力判断そのものや配当の実現性を保証しない。
- データソースの利用条件や法律、発走後の時刻制約を守る。自動的に実馬券の購入は行わない。
