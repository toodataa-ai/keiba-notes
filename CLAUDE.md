# CLAUDE.md — keiba-notes（Claude向け引き継ぎ）

このリポジトリで作業する Claude は、まずこのファイルと `AGENTS.md`、`.github/skills/keiba-site-change-routing/SKILL.md` を読むこと。
最終更新：2026-11-02（v1.08 まで本番リリース済み・文字サイズ統一の変更案を追記）

## ユーザーの方針
- 報告は**日本語**で行う（英語で報告しない）。専門用語は避け、平易に。
- Claude は **Pro プラン**。方針は「Claude の使用量をできるだけ使わずに自動化」。自動化は GitHub Actions（公開リポジトリなので無料）で完結させるのを優先する。
- 今後の改善は **Claude 中心**で進める。Claude Code（別製品）の方が向いている改修が出たら、Claude Code にそのまま貼れる指示文を作る。
- 予想（①）と回顧（②）の実行は、当面 **ChatGPT のまま**（Claude の使用量を使わないため）。

## 改善の仕組み（2026-11-02 構築）
| 段階 | 誰が | 手動/自動 |
|---|---|---|
| ① 正式予想（発走前固定） | ChatGPT（朝の通知の指示文をコピペ） | 手動 |
| ② 結果・回顧の記録 | ChatGPT（夜の通知の指示文をコピペ） | 手動 |
| ③ 改善案の計算と新旧比較 | GitHub Actions `jra-improvement-experiments-v1.yml`（結果push時＋毎日22:23 JST） | 自動 |
| ④ 判定 | 20レース到達で Issue（ラベル experiment-ready）が自動で立つ → ユーザーが A/B/C をコメント | 手動 |
| 反映 | A のときだけ Claude が正式プロンプトの新しい版を作る | 手動 |

- 改善が止まっていた原因：改善テーマは揃っていたのに比較相手（チャレンジャー）が一度も登録されず、ペアが0件のまま毎週 no_change だった。ChatGPT 側で作られていた7テーマの Draft PR（#79/#81/#83/#92）は条件が重く実レース0件だったため、凍結してクローズ済み（ブランチは残存）。
- 改善案（チャレンジャー）は「封印済みの正式 v3.13 STEP1 から決定的に計算する関数」。オッズ・結果は使わず、正式の印・買い目には一切反映しない研究用。
- 登録簿：`e2e_validation/improvement_experiments_v1.json`。コードは git blob SHA で固定。**コードを変えたら別の実験IDとして登録し直す**（同じIDで変更すると runner がエラーで止まる）。
- Git に登録された後に発走したレースだけが正式な比較ペア（prospective）。それ以前は参考の再現（replay_support_only）で、判定には数えない。
- 採点：`e2e_validation/experiment_runner_v1.py` → `docs/data/jra_experiment_status_v1.json`（条件別内訳つき）。判定 Issue の本文：`e2e_validation/experiment_ready_issue_v1.py`（採用条件との機械照合つき）。
- `e2e_validation/improvement_cycle_v1.py` は登録済み実験と残りペア数を反映する。

### 改善パイプライン（研究→登録→比較→判定の運用・2026-11-02）
- 基準：`e2e_validation/improvement_pipeline_policy_v1.json`（数字はここだけ。画面は結果を表示するだけ）。判定：`e2e_validation/improvement_pipeline_v1.py` → `docs/data/jra_improvement_pipeline_v1.json`。自動処理：`.github/workflows/jra-improvement-pipeline-v1.yml`（毎日22:40 JST＋関連データのpush時）。通知のみで、登録・採用は自動ではしない。
- 管理単位：展開／馬場（公式馬場補正＋10競馬場）／若駒（0戦・1〜3戦・4戦以上・血統）／購入セット。各単位の段階は 研究→登録→比較→判定。
- 登録条件：馬場の競馬場＝芝・ダートの両方が「候補」以上（すでに本番で使っている中山・阪神は対象外）／若駒の戦歴区分＝勝率を確かめられる馬30頭分／血統＝0戦・1〜3戦が条件に届き、かつ血統情報が9割以上／その他＝回顧で3レース・2開催以上。
- 条件に届くと Issue（ラベル registration-ready、題名に単位ID）が1単位1回だけ立つ。ユーザーが A/B/C で答える。**A のとき Claude が比較用プログラムを書いて登録する**（`e2e_validation/challengers/` に追加、`improvement_experiments_v1.json` に別実験IDで登録。単位ごとの登録は登録簿の `unit_ids`（例 `["field_experience:e0"]`）で紐づける。`unit_ids` が無い登録は、その仮説全体の単位だけに紐づく）。
- 馬場モデルの記録（`baba_models_v2/model_registry.json` → `build_dashboard_data.py` → `docs/data/baba_model_registry.json`）は**自動では更新されない**。バックテスト（`.github/workflows/baba-stage-a-all-tracks-v1.yml`、手動起動）を実行し、`baba_models_v2/apply_stage_a_results.py` で記録に反映する。2026-11-02 に札幌・函館・福島・新潟・中京・小倉のStage A（翌朝の含水率）が「候補」になり、東京・京都と合わせて8競馬場がStage A候補。**次はStage B（発走時の馬場の確率予測）**：公式の馬場状態ラベル付きレースデータの収集と校正が必要（昇格基準：ラベル付き80レース・12開催日・2年・雨天遷移6日）。Stage Bが候補になって初めて、競馬場ごとの改善案登録の条件に届く。札幌2018年の書式と画像のみPDF（中京2021年第6回）への対応済み（後者は読み飛ばして記録）。
- **Stage B の正解データ（2026-11-02 取得済み）**：`baba_models_v2/jra_going_labels.py`（JRA公式の結果ページを POST でたどる。robots.txt は全面許可、2.5秒おき）→ `baba_models_v2/going_labels/jra_going_<年>.csv`（2018〜2026-11-01、30,537レース、取得失敗0日。列：日付・競馬場・回・日目・レース番号・発走時刻・芝/ダート・馬場状態・天候・距離・コース詳細（内/外など）・レース名）。手動起動：`baba-going-labels-v1.yml`（`years` に JSON 配列）。ChatGPT が出した CSV は出典URLが存在しないドメインだったため破棄（値は公式と一致したが使わない）。
- **含水率・クッション値・使用コース（A〜D）**：`baba_models_v2/observations/<競馬場>_observations.csv`（`baba-observations-publish-v1.yml`、全10競馬場、2018〜）。**クッション値は2025年以降のPDFにしかない**（2024年以前は含水率のみ）。A〜DはPDFでは2025年以降だが、JRA「馬場概要」ページから2021年〜は全日取得済み（下の Stage B 実験の項）。**2018〜2020年のA〜Dは取得元なし**（JRA-VAN の有料データなど。年ごとに並びが変わるので推測では埋めない）。函館2018は観測データなし、中京2021第6回は画像PDFで読み飛ばし。
- 目標（ユーザー 2026-11-02）：当日朝に、①前日の馬場（公式の馬場状態・含水率）②前日の天気（降水・気温・湿度）③当日の予報（天気・気温・湿度）に加え、**当日朝の公式含水率**も入力にして、レース時間帯の馬場状態を予測。競馬場・コース（A〜D・内回り/外回り）・芝ダートごとに差が出るかをデータで確かめる。過去の予報は無いので、学習時は当日の実測で代用（見かけの精度が上がる点に注意）。データが少ない組み合わせは全体共通モデル＋差の調整で扱う。
- **Stage B 実験（2026-11-03）**：`baba_models_v2/jra_course_overview.py`（芝のA〜D＝JRA馬場概要ページ、**2021年〜のみ公開**、取得率100%、`going_labels/turf_course_by_day.csv`）、`jma_weather_racedays.py`（レース日と前3日の気象庁時間別。`weather/jma_hourly_<競馬場>.csv`。湿度は気象台のみ全期間OK＝`jma_weather.HUMIDITY_STATION`。中山=船橋＋千葉、阪神=西宮＋大阪を追加）、`stage_b_dataset.py`（1レース1行、`stage_b/stage_b_dataset.csv.gz`）、`stage_b_experiment.py`（2023〜2026を未来として評価、`stage_b/experiment_v1.json`）。結果（ログ損失、芝/ダート）：競馬場・季節のみ0.715/1.033 → +前日の馬場0.700/0.836 → +当日朝の含水率0.592/0.530 → +前日〜当日早朝の実測気象（予報なしで使える）0.458/0.447 → +当日の実測気象（完全な予報の代用＝上限）0.303/0.281 → +コース（内外・A〜D・距離）0.308/0.282（効果なし）。**過去の予報は保存されていない**ため、予報込みの精度は上限と下限のあいだ。次：①今日から気象庁の予報を毎日保存して実際の予報精度を測る ②「当日朝に発表される馬場状態を一日そのまま使う」現行の考え方を基準に比較 ③昇格基準の指標（Brier・隣接正解率・校正・雨天遷移日）と漏れ監査 ④競馬場ごとの結果を `model_registry.json` に反映。
- **Stage B 基準との比較（2026-11-03）**：`baba_models_v2/stage_b_baseline.py` → `stage_b/baseline_v1.json`。基準＝「その日・その芝/ダの最初のレースの馬場がそのまま一日続く」（最初のレース自体は採点から除外。実際の朝の公式発表は未保存のため、これで代用＝基準に少し有利）。結果（ログ損失 芝/ダ、2023〜26）：基準 0.295/0.284、F2 0.603/0.538、F3a 0.476/0.460、F3（上限）0.309/0.282。**全レースでは基準に勝てない**（途中で変わらない日が約86%で、基準はほぼ満点のため）。**途中で馬場が変わった日（芝802・ダ830レース）**：基準 1.635/1.467、F3a 1.526/1.277、F3 0.870/0.798 → 変化日では F3a がやや上、完全予報なら大きく上。課題：現モデルは「当日朝の公式発表の馬場状態」を入力にしていない（基準と同じ情報を使っていない）。次は朝の公式馬場状態＋含水率＋気象で『変化するか・どちらに変わるか』を予測する形に作り直す。朝の公式発表の過去分は未保存なので、今日から保存を始める必要がある。
- **Stage B v2（朝の馬場状態を入力に追加・2026-11-03）**：`baba_models_v2/stage_b_model_v2.py` → `stage_b/model_v2.json`。朝の馬場＝その日最初のレースの馬場で代用（朝の公式発表は未保存）。ログ損失 芝/ダ（全レース）：基準0.295/0.284、G2予報なし0.297/0.242、G3完全予報（上限）0.165/0.154。馬場が途中で変わった日：基準1.635/1.467、G2 1.531/1.090、G3 0.751/0.642。結論：ダートは予報なしでも基準に勝つ。芝は予報なしだと基準と同等で、**予報の精度が決め手**。コース（内外・A〜D）は引き続き効果なし。次：気象庁の予報と朝の公式馬場状態を毎日自動保存→予報込みで再評価。
- **予報の毎日保存（2026-11-03 開始）**：`baba_models_v2/forecast_archive.py` ＋ `.github/workflows/baba-forecast-archive-v1.yml`（毎日 18:10 と 06:10 JST）→ `baba_models_v2/forecast_archive/<年>/<月>/<日時>.json.gz`。気象庁の予報（10競馬場の担当官署の生データ）と、JRAの馬場状態・含水率・クッション値ページ（生HTML）をそのまま保存。記録のみで予想には使わない。数週間たまったら、①予報の当たり具合 ②朝の公式馬場状態を使った公平な基準比較 をやる（保存HTMLの解析は未実装）。
- **馬場の状態を3つで表す（2026-11-03・Stage A/B の表記をやめる）**：`baba_models_v2/stage_b_status.py` → `stage_b/status_v1.json`（競馬場×芝ダートごとに 使える見込み／予報待ち／まだ足りない。基準＝予報なしでログ損失・Brier とも5%以上改善、雨で変わる日のBrierが10%超悪化しない、80レース・12開催日・2年・雨天遷移6日以上）→ `apply_going_status.py` が `model_registry.json` に `going_status` を追加（旧 stage_a/stage_b は残す）→ `build_dashboard_data.py`。`improvement_pipeline_v1.py` の馬場の登録条件は、芝・ダートとも「使える見込み」に変更（`going_status` が無ければ旧条件）。detail.going / going_text を追加（旧 text は互換のため据え置き）。現状：使える見込み10／予報待ち7／まだ足りない3。**両方が使える見込み**は福島（登録待ち）と阪神（本番で使用中）。予報がたまったら `stage_b_status.py` を実予報で作り直す。再計算：`python3 stage_b_status.py && python3 apply_going_status.py && python3 build_dashboard_data.py`（baba_models_v2 内）→ `python3 e2e_validation/improvement_pipeline_v1.py`。
- **朝の公式馬場状態の取得元（2026-11-03 判明）**：JRA `https://www.jra.go.jp/keiba/baba/index.html`（1番目の開催場）／`index2.html`／`index3.html`。開催場ごとに 芝・ダートの馬場状態、発表時刻（金曜正午〜当日朝）、天候、含水率、使用コースが載る（開催場の並びは週で変わる）。`baba_models_v2/jra_going_now.py`（`parse_going_page`、テスト付き）で読み取れる。**予報の毎日保存は11/3まで『基礎知識』の説明ページを誤って保存していた**ため上記に修正（土日月 8:40 JST の保存も追加）。11/3 以前の保存分に朝の公式発表は含まれない。福島の毎朝の馬場予測の実装は、この取得元が使えるため着手可能（未着手）。
- **福島の馬場予測・毎朝の自動実行（2026-11-03、記録のみ）**：`baba_models_v2/going_predict_live.py`（予報なしモデルG2。朝の公式馬場状態・含水率＝`jra_going_now.py`、前日の結果、気象庁の実測D-3〜Dから各レースの 良/稍重/重/不良 の確率を出す）＋ `.github/workflows/baba-going-live-v1.yml`（土日月 8:45 JST、福島と阪神（2026-11-03 阪神もユーザー採用A）。手動起動で date/track 指定可）→ `baba_models_v2/live/<日付>_<競馬場>.json`。**正式予想・ChatGPTには未接続**（本番に出す前にユーザー再確認）。過去日のリプレイテスト・実ページでの試運転（東京 2026-11-01）は成功。レース時刻は直近2年の同競馬場の中央値で代用。朝の発表と最初のレースの馬場がずれる場合がある点に注意。
- **馬場予測は比較を挟まず採用（ユーザー決定 2026-11-03）**：芝・ダートとも「使える見込み」になった競馬場は state=`ready_to_adopt`（Issue「[採用できます]」、ラベル registration-ready）。A＝採用（Claude が毎朝の馬場予測を自動生成して正式予想へつなぐ。本番に出す前に再確認）／B＝予報がたまるまで待つ／C＝採用しない。20レース比較（登録→比較→判定）は馬場予測には使わない。採用の実装（毎朝の予測の自動生成）は未着手。公式馬場補正（EXP-002）は勝つ確率の微調整で、別物。Issue 重複の不具合（全角かっこの照合ミス）を修正済み。
- **中山・阪神は2026-11-03にユーザー判断で過去の判定を破棄**（status=backtesting、routing.production=false、`reset_note` 付き）。正式プロンプト v3.13 に馬場予測モデルを使う記述は無かった。他の競馬場と同じ基準で評価：阪神＝芝・ダートとも使える見込み（ユーザーが2026-11-03 に A＝採用と回答。朝の予測の記録は福島と同じ仕組みで自動実行。正式予想への接続は未定・再確認が必要）、中山＝芝が予報待ち。福島はユーザーが A（採用）と回答済み＝実装は未着手（朝の公式馬場状態の取得元が未確定）。

- `ui-claude-view-v1`（this-week.html・results.html、新資産 `assets/claude-view-v1.js`）：「ChatGPTの予想／Claudeの予想」の切り替えを追加。Claude 側は `docs/data/predictors/claude_status_v1.json`（`python3 -m claude_track.build_public` で作る）を表示、合算しない。**v1.11 として本番リリース済み（2026-11-03）**（Claude 予想の保存・採点は `claude_track/`、上書き防止検査 `claude-track-guard-v1.yml`）。

### 登録中の改善案（どちらも 2026-11-02 13:00 JST 以降のレースから計上、各20ペアで判定）
- **EXP-001 展開・位置取り補正** `e2e_validation/challengers/pace_v1.py`（近4走の1角通過順位→脚質、先行馬の数→ペースS/M/H、勝率に倍率）。参考：過去18レースで log loss 2.317→2.301（14/18で改善）、ダート・新潟で悪化警告。
- **EXP-002 馬場状態補正** `e2e_validation/challengers/going_v1.py`（発走前の公式馬場と同じ芝/ダでの良・道悪の近走成績）。参考：過去18レースで log loss ほぼ同じ。内外のトラックバイアスは発走前データが無く対象外。
- **EXP-003 購入セットの分散（2026-11-03 登録、ユーザーが Issue #121 に A）** `e2e_validation/challengers/ticket_div_v1.py`（`kind: "portfolio"`。正式の購入セット＋正式STEP1の勝率＋**発走前に保存済みのオッズ表 `e2e_validation/quote-evidence/<race>/<種別>.json`** から、1頭に絡む金額が購入額の60%以内の買い目を作り直す。単勝・馬連・馬単・ワイド・三連複だけ。評価は `e2e_validation/portfolio_eval_v1.py`（同じ公式払戻で両方を採点。`experiment_runner_v1.py` が kind で振り分け）。回収率で比較、最大の差の1レースを除いても上回ること等を条件に20ペアで判定。参考（過去12レース、判定には数えない）：回収率 今の買い目59%／改善案3%＝改善案は不利。登録は研究のみで購入はしない。減らすだけの案（ticket_conc_v1）は軸が全買い目に入っているため偏りが減らず不採用にした。
- 次の候補：「若駒・経験不足」（field_experience）。未登録。

## サイト変更の仕組み（2026-11-02 作り直し）
- STAGING ＝「本番＋承認待ちの変更案」。変更案は**本番と同じ書き方**で `.github/staging-candidates/<docs配下と同じパス>` に置き、`.github/staging-candidates.json` に登録 → `python3 .github/scripts/staging-baseline-v2.py` でステージングを生成。docs/staging/ の HTML を直接編集しない（自動で作り直される）。
- 変更案のページはバッジ「STAGING 変更案・承認待ち」。ステージング内のリンクはステージングに留まる（improvement-cycle.html も対象ページに追加済み）。
- ユーザーの明示承認（「本番リリースOK」など）を得たら、`.github/workflows/jra-ui-promote-v1.yml` を `candidate_id` と承認の原文 `approval_quote` で実行（この環境では下の「作業上の注意」の REST 起動を使う）。本番へバイト一致コピー → ステージング再同期 → リリース台帳に自動採番で記録 → 保護データ不変・ガード・公開HTTP一致を確認。
- ガード：`.github/scripts/jra-release-guard-v1.py`（全リリース共通の不変条件＋過去リリースの固定値）。

### 承認待ちの変更案（承認はチャットで受ける）
- `ui-claude-exp-v1`（improvement-cycle.html）：「Claudeの予想だけで進めている比較」を表示。**v1.14 として本番リリース済み（2026-11-03）**。
- `ui-portfolio-card-v1`（improvement-cycle.html）：購入セットの比較カードを回収率の表示にする。**v1.13 として本番リリース済み（2026-11-03）**。
（以下は以前の記録。直近：v1.11 ui-claude-view-v1、v1.12 ui-baba-progress-v1 をリリース済み）
- `ui-baba-progress-v1`（baba-models.html・improvement-cycle.html）：馬場の研究ページに「最新の進捗」章（比較表・競馬場×芝ダートの状態一覧（registry の going_status を表示）・分かったこと・データ集めの状況）を追加、詳細カードは折りたたみ。改善状況ページの馬場は「芝◯／ダ◯」の3状態表示（研究段階のとき）。**v1.12 として本番リリース済み（2026-11-03）**。
- `ui-site-cleanup-v1`（全12ページ。**v1.09 として本番リリース済み**）：①文字サイズ統一（`assets/type-scale-v1.css`、タイトル最大24px・スマホ22px・節17px・補足12px以上）②トップの閲覧数を控えめな1行に＋**自分のブラウザの閲覧は数えない**（`?owner=1` を開いたブラウザだけ除外、`?owner=0` で解除。`assets/visitor-counter.js`）③トップを「予想のしくみと改善（別枠・控えめ）／別の研究（地方競馬のみ）」。馬場・若駒の研究は改善状況ページの「改善テーマと、つながる研究」から入るに再編（改善の歩み＝roadmap はカードにせず、フッターの小さなリンクのみ。ユーザー指示）④旧比較検証（e2e.html）を「旧方式の比較記録（参考）」に格下げ（トップから外し、改善状況ページの折りたたみからリンク）⑤roadmap.html を「改善の歩み（履歴）」に改名⑥馬場・若駒の研究ページに「つながる改善テーマ」注記⑦methodology.html を重複を省いて再構成（番号の誤り・A/B/C の意味・古い版表記を修正）⑧サイト名を「AIによる競馬予想研究所」に統一。⑩改善状況ページは「改善テーマ（研究から判定まで）」に一本化（旧「いま比較中の改善案」欄は各テーマの「比較」段階に統合。1行＝1管理単位（競馬場・戦歴区分など）の横バーで 研究→登録→比較→判定 を表示）。表示は data/*.json から自動表示（馬場＝競馬場ごと、若駒＝戦歴別の残り頭数＋血統の注記）。登録の基準と通知は上の「改善パイプライン」で運用（画面は `jra_improvement_pipeline_v1.json` を表示）。⑨全ページを白ベース＋上部だけ黒い帯に統一（`assets/theme-light-v1.css`。トップは写真の帯＋白い本文に分割、改善状況ページは白ベース化）。
- 本番リリース済み：v1.10 「一番上へ」ボタン＋トップ下線の色を戻す（2026-11-03 承認）／v1.09 サイトの改修一式（ui-site-cleanup-v1）／v1.06 改善状況ページのシンプル版／v1.07 トップと今週のAI予想を平易な日本語に（公開予定の1行つき）／v1.08 改善状況ページの試算注記。
- 購入方式の現行版は **v3.15**（10/31・11/1 も v3.15。v3.16 は 10/25 の3レースだけ）。

### 今後の候補（整理案の残り）
- roadmap の「考え方」の章を methodology へ寄せて、履歴だけにする（今回は改名と重複する日々のサイクルの削除まで）。
- 予想カード内の「回顧待ち」表示（`assets/week.js` 側）の言い換え。

## モデルの使い分け（2026-11-02 ユーザー合意）
- 方針：簡単な作業は軽いモデル、判断・設計は上位モデル。外部のAI（ChatGPT・Gemini）のAPI連携は**不要**（ユーザー判断）。Claude の中だけで使い分ける。
- 目安：
  | 作業 | モデル |
  |---|---|
  | 機械的な作業（ファイル検索、表記の置き換え、Actions の成否確認、通知文の表示） | Haiku |
  | 通常の改修（画面修正、変更案づくり、PR、リリース手順） | Sonnet |
  | 設計と判断（改善案の設計、比較結果の読み解き、リリース前の最終点検、あいまいな相談） | Opus |
- 方法：会話全体は `/model` で切り替え（ユーザー操作）。まとまった独立作業は助手（サブエージェント）にモデルを指定して任せる。数行の修正は助手を使わず直接行う（助手は文脈なしで始まるため、小さい作業では割に合わない）。
- 使用量の確認：この会話の内訳は explain-usage スキル、プラン全体は claude.ai の設定の使用量画面（Claude Code では `/usage`）。スケジュールタスクの見直し（下記）の材料にする。

## Claude予想の自動実行（2026-11-03）
- 仕組み：`claude_track/`（予想の保存・採点・公開）。出馬表の取得＝`claude-race-data-v1.yml`（土日月 8:40 JST、価格なし）→ T2 が `claude_track/prompts/predict_v1.md` で印（STEP1）を保存・push → オッズを見て買い目（STEP2）を保存。T3 が `review_v1.md` で回顧・週次比較（Issue ラベル claude-review、A/B/C）。採点・公開＝`claude-track-publish-v1.yml`。上書き防止＝`claude-track-guard-v1.yml`。買い目は仮想。ChatGPT側は別管理で合算しない。
- T2（土日月 9:10 JST）と T3（土日月 18:17 JST）は Claude の予想・回顧の実行に切り替え済み（旧：ChatGPT用指示文の表示）。権限設定は auto。初回の実走は 11/7〜8。スケジュール実行がリポジトリ取得・pushできるかは初回で確認。使用量は最初の1〜2週間で実測する。T1 は停止済み（地方競馬は Actions で自動化）。

- **GitHubの定時は「保険」に格下げ（2026-11-04）**：GitHub Actions の定時実行は数時間遅れる（11/3 に実測：18:10→01:58、18:47→02:19、19:17→02:50、19:47→03:04 JST。きょう朝の 06:10/06:30/07:30 も2時間以上動かず。地方は定時では一度も動かず手動・push のみ）。Claude の定時（T2 9:10・T3 18:17）は遅れないので、**T2 は最初に出馬表取得（claude-race-data-v1）、STEP1 push 直後にオッズ取得（claude-odds-v1）を、T3 は最初に結果取得（claude-results-v1）と若駒採点（claude-wakakoma-v1）を、REST で自分で起動する**（`predict_v1.md`・`review_v1.md`）。失敗しても従来の定時を待って続行し、記録に書く。起動権限の確認：一回だけのスケジュールタスクの中から claude-results-v1 を起動して成功（actor=toodataa-ai）。**git push が定時タスクからできるかは未確認**（初回の実走 11/7〜8 で確認）。表示は変更案 `ui-operations-backup-v1`（承認待ち）。地方競馬Shadow・予報保存・採点の定時も同様に遅れうる（未対処。地方は前日分を翌日に回収できる作り）。
- **Claudeの起動役 D1/D2（2026-11-04、ユーザー決定。モデルは Haiku）**：GitHub の定時が遅れるため、毎日の処理を Claude の定時から起動する。**D1 朝 6:03 JST**（trig_01RxVqAvBXyL667UTiombdcC）＝予報保存・地方の前日回顧・地方の予想の固定の3本を REST で起動。**D2 夕方 18:03 JST**（trig_01RdYmRBYHLu5B84fuQAVrYA）＝予報保存を起動。どちらも起動だけ（リポジトリ取得・commit・push なし、記録は残さない）。開催日の朝の出馬表取得・朝の公式馬場・馬場の朝の予測は 6:00 では早すぎる（JRA の朝の発表前）ので、T2（9:10）の手順で起動する（T2 の手順書に追加済み 11/4）。開催日の夕方の 結果→若駒→採点・公開→改善案の採点→基準の確認 は順番が大事なので、D2 ではなく T3（18:17）が結果保存後に順に起動する（T3 の手順書に追加済み 11/4。初回の実走 11/7〜8 で確認）。GitHub の定時は全部保険として残す（二重に動いても安全：予想の固定は固定済みを上書きしない／回顧は保存済みを再利用／予報保存は日時別ファイル。地方の予想の固定を二重起動して成功を確認）。起動役が動いた GitHub の実行は、実行記録の表では手動と同じ扱い（薄い表示＋『手』）。**11/4 の確認**：地方の前日の回顧（11/3分）は、金沢1Rのレース名が予想保存時と結果ページで違い（「…開幕特別Ｃ１Ｃ２」≠「…Ｃ１Ｃ２」）、安全側の停止（BLOCKED_JOIN）で失敗。起動の問題ではない（未対処）。
- **父データベース（2026-11-04 開始・研究のみ）**：ユーザー提案＝「若駒は経験数だけでは足りない。過去データで 父×距離×芝ダート×月齢（絶対的な何歳何ヶ月。デビューからではない＝晩成ほどデビューが遅れるため）の傾向表を作る」。`sire_db_v1/crawl.py` ＋ `.github/workflows/sire-db-crawl-v1.yml`（6時間おき、1回3ラウンド×100分、各ラウンドでコミット、2秒間隔、使用量0）。流れ：`baba_models_v2/going_labels/jra_going_<年>.csv`（新しい順、2026→2018。2018年が取得元（馬場ラベル）の最古＝それ以前は別のレース一覧が要る）のレースコード（年2桁＋競馬場＋回＋日目＋R）→ Sportnavi 出馬表（出走馬だけ。血統リンクを除外）→ 馬のページ。**保存先は非公開リポジトリ `toodataa-ai/keiba-notes-private-data`（`data/` 以下。公開リポジトリには生データを置かない＝出どころの利用規約への配慮、ユーザー決定 2026-11-04）。書き込みはシークレット `PRIVATE_DATA_TOKEN`（ユーザーが作成した細粒度トークン、Contents 読み書き、期限が切れたら入れ直し。切れると取得が失敗するだけでデータは消えない）。公開側に出すのは集計結果だけ。**保存：`data_v2/horses_<生まれ年>.jsonl`（1頭1行：ページに載っている項目は全部＝生年月日・性・調教師/馬主/生産者/毛色などのプロフィール・賞金・通算成績の文・血統3代・全出走履歴（日付・レースコード・レース格・競馬場・芝ダ・距離・頭数・着順・馬番・騎手・斤量・人気・オッズ・馬体重と増減・タイム・着差・通過順位・上がり3F））、処理済みレース `races_done.txt`（取れなかったレースは done にしない＝再試行）。馬のページの構造：血統は `hr-horsePedigree__gen1st/genSecond/genThird`（--sire/--dam）、履歴は `日付|レース|着順…` の表、馬名は `<title>`。**次**：集まったら集計（父×距離帯×芝ダ×月齢帯の勝率・3着内率を同条件の全体平均と比較、産駒の少ない父は系統にまとめる、検証は開催日より前のデータだけで作る）→ 0戦馬への応用（オッズとの差を説明できるか）。予想には使わない。
- **父データベースの最初の集計（2026-11-06・研究のみ）**：`sire_db_v1/aggregate.py`（入力＝非公開リポジトリの `data_v2`、環境変数 `SIRE_DATA_DIR` か `--data`。出力は集計JSONだけ。`--baseline heads|odds`、`--cutoff` より前で作った傾向が以降の出走に効くかを見る）。非公開リポジトリは `add_repo` で読み取り接続できる（clone は /home/claude/keiba-notes-private-data）。取得済みは約10,600レース（全体の約35%）、馬21,488頭、出走履歴約21万行（2014年〜）。**結果**：①期待値を「頭数だけ」にすると、父×距離×月齢の傾向は強く効いて見える（上位/下位で A/E 1.3/0.8）が、これは馬の質（クラス）が混ざった見かけ。②期待値を「単勝オッズ（0.8÷オッズ）」にすると、全出走では父×距離帯・父×月齢帯とも差が消える（5分位すべて A/E 0.95〜1.02）＝オッズに織り込み済み。③**デビュー戦だけ**（オッズに情報が少ない）では、訓練期間の父×芝ダの傾向が高い群 1.07／低い群 0.79 と段階的（約1,764出走/群・勝ち79〜177件のため誤差が大きく、結論には足りない）。④母集団の A/E が月齢で偏る（取得が新しい年から＋残った馬だけが履歴に出る選別）ので、絶対値は信用せず相対比較だけ使う。次：全期間が取れたらデビュー戦の再検証（距離帯・母父も）、成熟の型（早熟/晩成）は母集団の偏りを補正してから。予想には使わない。
- **種牡馬の初勝利マップ（2026-11-06）**：公開データ `docs/data/sire_firstwin_v1.json`（父ごとの集計のみ：勝ち上がり頭数・初勝利の平均/中央/四分位の月齢と距離・芝の割合。馬名や1頭ずつの記録は出さない）を `python3 -m sire_db_v1.build_public_map --data /home/claude/keiba-notes-private-data/data_v2` で作る（**自動更新はまだ無い**。取得が進んだら手で作り直す）。新ページ `sire-map.html`（自前のSVG。名前は重ならない分だけ、遠い位置は線でつなぐ。全体／中心を拡大・芝寄り/ダート寄り・頭数で絞り込み、並べ替え一覧）とトップ「別の研究」のカード＝変更案 `ui-sire-map-v1`（承認待ち）。ページ一覧3か所に追加済み。
- **レースシミュレータv2（LAB・2026-11-06）**：`docs/lab/race-sim-v2.html`＋`docs/lab/sim-v2/engine.js`（ブラウザとnode共通。全10場の芝ダ・内外・直線を公式諸元から競技場型で近似、位置取り＝先頭からの狙いの距離、ペース＝先行馬の数、進路・詰まり（前2.1m・横0.7m）と進路探し、コーナーの外回りロス、最後の区間の末脚と疲れ、坂）。データ `sim-v2/races-public.json`（2026年9月以降の重賞と各開催日11R、馬名・能力値0〜100・着順・オッズ。**ユーザーが2026-11-06に公開を許可**。生の履歴は置かない）・`sim-v2/meta.json`（検証）。作り方：`python3 -m sim_v2.build_races --data <非公開data_v2> --out-backtest <作業用>` → `python3 -m sim_v2.strength_model --races <作業用> --out <モデル>` → `python3 -m sim_v2.export ... --select public`。能力＝1走ごとの指数（同条件の基準タイムとの差・上がり・1角位置）をレース日より前だけで重み平均＋条件付きロジット（着順・着差・人気・クラスの上下・間隔・年齢など）。**検証（2026年3〜11月の300レース、対数損失）**：能力の勝率2.193→v2で2.128（騎手・父×芝ダ・父の初出走・距離の延長短縮・芝ダ替わり・馬体重増減を追加。全2262レースでは2.167→2.125）／シミュの勝率2.399／単勝オッズ1.923／一律2.585。新馬戦はオッズとの差が大きい（0.47）。LightGBMの順位学習は試したが悪化（2.18〜）。シミュは能力の勝率より当たらず、混ぜても改善なし＝予想には能力の勝率、シミュは展開の可視化。検証スクリプト `tools/sim_v2_backtest.cjs`・`tools/sim_v2_mix.cjs`。既知の問題：取得データで新潟直線1000mなど通過順の無いレースはタイムが欠ける（crawl.py の列ずれ。未修正）。登録 `.github/lab/feature-registry.json` の `race_sim_v2_all_courses`（未承認・LABのみ）。**当日のレース（結果前）**：`sim_v2/upcoming.py`（Claude用出馬表の馬名で非公開DBと照合し、能力値と強さを計算。係数と0〜100の分位表は `sim_v2/model_v2.json`）＋`.github/workflows/sim-v2-upcoming-v1.yml`（土日月 9:05 JST＋T2 の手順書から起動。非公開データは PRIVATE_DATA_TOKEN で取得）→ `docs/lab/sim-v2/upcoming.json`（馬名・能力値・強さのみ。オッズ・結果なし）。画面では「これから・結果前」として先頭に出る。馬場は出馬表の馬場欄の読み取りが未対応で、いまは良として扱う。
- **判定の基準づくりをClaude側でも（2026-11-03）**：`improvement_pipeline_v1.py` が、ChatGPT側の条件に加えて Claude 側の証拠でも「登録待ち」にする（どちらかが届けばよい）。①展開・馬場・購入セットの screening＝Claude自身の回顧（`claude_track/reviews/*.json` の `failure_types`：展開→pace_positioning、馬場予測→track_condition、購入戦略・リスク集中→ticket_portfolio。3レース・2開催週末（祝日月曜は直前の土日に数える））②若駒の戦歴区分＝`claude_wakakoma_v1.json` の「確認可」（30頭）。表示の文言に出所（ChatGPT／Claude）が付く。
- **馬場予測をClaudeの予想の手順書から読めるように（2026-11-03、ユーザー指示で接続）**：`predict_v1.md` の STEP1 に、福島・阪神だけ `baba_models_v2/live/<日付>_<競馬場>.json`（朝8:45の自動保存）の11Rの 良/稍重/重/不良 の確率を馬場の変化の見込みとして使う手順を追加。使ったときは STEP1 に `going_forecast` を記録（使わなければ null）。ChatGPTの予想には接続していない。
- **Claudeのタスクの実行記録（2026-11-03）**：T2/T3 は GitHub Actions ではなくClaudeのセッションなので `automation_runs_v1.json` には載らない（＝表にClaudeの使用量を使うタスクが無かったのは設計の制約）。手順書（`predict_v1.md`・`review_v1.md`）の最後に `python3 -m claude_track.record_run --task T2|T3 --status ok|fail|skipped --note …` を実行して `docs/data/automation/claude_task_runs_v1.json`（直近14日）に自分で追記・push する手順を追加。途中で落ちて記録が無い日は、表に「記録なし（⚠）」と出る。表示は変更案 `ui-claude-complete-v1`（承認待ち。operations.html に T2/T3/若駒の行、improvement-cycle.html に馬場補正・購入セット・若駒の機械採点）。判定の通知Issueは `open_ready_issues.py` に馬場補正・購入セットを追加済み。
- **自動処理の実行記録（2026-11-03）**：`.github/workflows/automation-log-v1.yml`（対象9本の完了直後に `workflow_run` で起動＋毎時7分の保険）→ `.github/scripts/automation_log_v1.py` が `docs/data/automation/automation_runs_v1.json`（直近14日・実際の開始/終了時刻・成否・実行ID）を更新してコミット。**完了の2秒後に起動することを確認済み**。対象を増やすときは、スクリプトの `TRACKED` とワークフローの `workflows:`（`name:` と完全一致）の両方に足す。ClaudeのT2/T3とChatGPTの手動実行は含まない（T2/T3 は初回の実走後に、自分で記録を残す形を検討）。表示は専用ページ **`operations.html`（自動運用の状況）**＝手動/自動の一覧・1日の流れ（各行を開くと処理内容）・実行記録の表（処理×直近7日、きょうの列に実際の開始時刻、手動/push で動いた回は薄い表示＋『手』の印、数えるのは定時の自動実行だけ）。実行記録の表は v1.17 で改善状況ページに本番リリース済み → ****v1.18 `ui-operations-page-v1` として本番リリース済み（2026-11-03）**：専用ページに移し、トップの「予想のしくみと改善」にカードを追加、改善状況ページにはリンクだけ残す**。新しいページを足したときは、ページ一覧を3か所に足すこと：`.github/scripts/staging-baseline-v2.py` の PAGES、`.github/scripts/jra-release-guard-v1.py` の CANONICAL、`.github/workflows/jra-staging-week-mirror-publish.yml`（paths と git add）。
- **2026-11-03に見つけて直した不具合**：①`baba-going-live-v1.yml` がジョブ条件に `matrix` を使っていて、全pushで0ジョブの失敗（起動前に弾かれる）。ステップ条件に変更 ②`going_predict_live.py` が「直近5日にその競馬場の開催が無い（開催初日）」で落ちていた ③`claude-track-guard-v1.yml` のテストに bs4 が無く失敗 ④`jra-staging-week-mirror-publish.yml` が付属ファイル無しの変更案で `git add` が止まっていた。①②は実際に動かして成功を確認、③④は次の該当pushで確認。既知の未解決：`Verify JRA improvement cycle staging mobile and evidence` が失敗中（マイルストン検査・以前からの不具合）。
- **Claude専用のオッズ取得（2026-11-03・ChatGPT依存をやめた）**：`claude_track/fetch_odds.py` ＋ `.github/workflows/claude-odds-v1.yml`（土日月 9:30 と 10:00 JST）。出馬表の source_cname からSportnaviのレースコード（YY＋競馬場＋回＋日目＋R）を作り、単勝・馬連・馬単・ワイド・三連複の公開オッズを `claude_track/odds/<race_id>/<UTC日時>.json` に保存（上書きなし・発走後は保存しない）。STEP2（`prompts/predict_v1.md`）はこのファイルだけを使う（STEP1 push より後に取得された最新のもの。無ければ最大45分待って「見送り」）。ChatGPTの `e2e_validation/quote-evidence/` はもう使わない。本物のページでの試験（`probe_code=2605041111`、Actions）は成功＝点数が組合せ数に一致。試験入口：手動起動の `probe_code`（過去レースのコードで取得・解析のみ、保存なし）。初回の実走は 11/7〜8。
- **Claude専用の結果取得と夕方への前倒し（2026-11-03）**：`claude_track/fetch_results.py` ＋ `.github/workflows/claude-results-v1.yml`（土日月 17:17・17:47 JST）。Sportnavi の結果ページ（`https://sports.yahoo.co.jp/keiba/race/result/<レースコード>`）から着順・払戻を `claude_track/results/<race_id>.json` に保存（上書きなし・発走25分後から・払戻未確定なら保存しない）。**天皇賞(秋)で公式の着順・払戻と完全一致を確認**。保存後は `claude-track-publish-v1.yml` を REST で直接起動。`score_claude.resolve_result` は `claude_track/results/` を先に見る（ChatGPT の `e2e_validation/results/` は予備）。T3（Claude回顧）は **18:17 JST**（trig_01ATLDvH94om4CoqoGeaEu5E）。GitHub の定時（保険）は30分間隔：experiments 18:47／pipeline 19:17／claude-track-publish 19:47。実走の確認は 11/7〜8（T3 が結果を読めるか）。サイト表示は変更案 `ui-operations-times-v1`（承認待ち）。
- **若駒の機械採点（Claude完結・2026-11-03、方針：ChatGPTの処理は残し、Claudeだけでも完結できるようにして相互評価も残す）**：`claude_track/wakakoma.py` ＋ `.github/workflows/claude-wakakoma-v1.yml`（土日月 17:57 JST、使用量0）。出馬表（11Rのカードの source_cname）から1R〜12Rのコードを作り、Sportnavi の出馬表（`/keiba/race/denma/<code>`、最終単勝オッズと馬のリンク）・結果ページ・各馬のページ（`/keiba/directory/horse/<id>/` の出走履歴＝JRA・地方・海外）から、**出走前の出走数（0戦／1〜3戦／4戦以上）ごとに、オッズ由来の勝つ確率（(1/オッズ)÷合計）と実際の勝ちを比べる**。予想（LLM）は使わない。保存＝`claude_track/wakakoma/<日付>/<race_id>.json`（追加のみ）、集計＝`docs/data/predictors/claude_wakakoma_v1.json`（30頭で「確認可」）。過去の1R（2605041101）で読み取りを確認（出走前の出走数の数え方も確認）。**実走は 11/7〜8 が最初**。確かめられるのは「若駒がオッズ上、過大・過小に評価されていないか」で、ChatGPTの正式予想の勝率を直接試すものとは別。次：①馬場補正・購入セットをClaudeの予想で採点 ②判定の条件をClaudeの回顧に基づく形へ ③馬場予測をClaudeの手順書から読めるようにする（採用の再確認あり）④画面表示（STAGING）。
- **Claude単独の比較を3本に拡張（2026-11-03）**：`claude_track/experiments.py` が `claude_experiments_v1.json` に ①位置取り（既存）②**馬場補正**（`going`。ChatGPT側 EXP-002 と同じ固定ルールをClaudeのSTEP1に適用。レースの馬場は `claude-odds-v1` がオッズ取得時にSportnaviの `馬場：` から `going` として保存＝過去1Rで取得確認）③**購入セット**（`portfolio`。基準＝Claude自身のSTEP2の買い目、比較＝同じSTEP1の確率・同じオッズ表・同じ予算から EXP-003 の機械ルール（`ticket_div_v1` の関数をそのまま再利用）で作った買い目。回収率を同じ公式払戻で比べる）を計算。各20レースで判定。判定の通知Issueと画面表示は未対応（次）。実走は 11/7〜8。
- **Claude単独の改善比較（2026-11-03）**：`claude_track/experiments.py` → `docs/data/predictors/claude_experiments_v1.json`（`claude-track-publish-v1.yml` が自動生成）。①位置取り（pace_v1 と同じ固定ルール）をClaude自身のSTEP1勝率に当て、同じ公式結果で新旧のログ損失を比べる（20レースで判定、ChatGPT側とは混ぜない）。②若駒（E0/E1/E2）：出馬表の戦績（W-S-T-他）から出走数を読み、予想勝率と実際の勝ちを区分ごとに集計（30頭分で確認可）。**出馬表に戦績の括弧が載るかは未確認**（10/31の検証用カードには無かった。次の開催週のカードで `career_data_available` を見る）。判定の通知Issue（ラベル claude-experiment-ready、1件1回・`claude_track/open_ready_issues.py`、公開処理の最後で自動）は実装済み。画面表示は変更案（STAGING）で対応予定。承認はチャット。
- **若駒（ChatGPT側）の収集**：`experience-regime-prestart-current.yml` は ChatGPT が `experience_regime_v1/requests/run-current.json` をpushして起動し、開催日ごとのURL（検証済みの種）と週のレース一覧を手で用意する作り。10/31の失敗は保存後のサイト反映確認(3分)のタイムアウトで、待ちを約10分に延長済み。「勝つ確率を確かめられる30頭分」は正式予想の勝率が元（現状あと30頭分、約3〜5レース）。完全自動化には収集の作り直しが必要（未着手）。

## 地方競馬Shadowの自動実行（2026-11-03）
- コピペ不要。GitHub Actions だけで毎日自動：予想の固定＝`local-racing-shadow-prerace-generic.yml`（毎朝 7:30 JST、当日分のリクエストは自動生成）／前日の回顧＝`local-racing-shadow-postrace.yml`（毎朝 6:30 JST、前日に保存済みの予想がなければ自動でスキップ）。Claude/ChatGPT の使用量は0。手動起動・従来のリクエストファイルpushも引き続き可。
- T1（通知文の表示）は不要になったため停止済み。試運転（手動起動）は予想・回顧とも成功。

## スケジュールタスク（旧：Claude、通知文の表示のみ。T2/T3 は上記に置き換え済み）
- T1 地方競馬Shadow 毎日 7:52 JST（trig_01GCEqKctMCwULuPhm9oF5QK）
- T2 JRA正式予想・研究収集 土日月 7:47 JST（trig_012Ybee7h38cvqziLjhiUvWo）
- T3 JRA回顧 土日月 18:44 JST（trig_01ATLDvH94om4CoqoGeaEu5E）
- 3件とも毎回 Claude の使用量を消費する（見積もり：週140〜150万トークン、Opus）。2026-11-02 18:44 の T3 初回の前後で使用量を実測し、「残す／軽いモデルにする／削除して ChatGPT 側に一本化」を決める予定。ChatGPT 側の同じ通知も有効なまま。

## 未解決・次の候補
1. トップページ・「今週のAI予想」も同じ方針でわかりやすく書き直す提案（ユーザー未回答）。
2. 次の改善案（購入セット／若駒）の登録。
3. `Validate JRA v3.8〜v3.11` の4検査が 2026-10-18 から main で失敗（10/18 の予想実行で `e2e_validation/validate_manifests.py` が変わり、`.github/scripts/validate-jra-prompt-v312.mjs` の固定SHAと不一致）。今回の変更とは無関係。
4. 古い改善ページ用の比較設定（`docs/data/e2e_status.json` の comparison が v3.0/v3.1 のまま）、E2E評価で新形式予想の勝率Brierが null になる問題（新しい runner は独自に計算しているので比較には影響なし）。

## 作業上の注意
- GitHub の GraphQL はこの環境から使えない（`gh workflow run` や `gh pr` 系も失敗する）。PR作成・マージ・ワークフロー起動は REST（`gh api repos/toodataa-ai/keiba-notes/pulls ...`、起動は `gh api -X POST repos/toodataa-ai/keiba-notes/actions/workflows/<名前>.yml/dispatches -f ref=main -f 'inputs[キー]=値'`）。
- GITHUB_TOKEN でのpushは他のワークフローを起動しない。自動処理の後続はワークフロー内で直接実行する。
- このサンドボックスから github.io には接続できない（公開ページのバイト一致確認は Actions 側で行う）。
- 浅いクローンでは古いリリースのコミットが見えない。必要なら `git fetch --depth=1000 origin main`。
- Python のバージョン差で浮動小数の最後の桁が変わる。保存済み記録の照合は 1e-9 の許容で行う（runner 実装済み）。
- 予想・PDF・結果・証拠（docs/data, docs/reports, docs/pdfs, e2e_validation の封印済みファイル, local_racing_shadow_v1）は UI 作業で変更しない。
