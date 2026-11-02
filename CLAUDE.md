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

### 登録中の改善案（どちらも 2026-11-02 13:00 JST 以降のレースから計上、各20ペアで判定）
- **EXP-001 展開・位置取り補正** `e2e_validation/challengers/pace_v1.py`（近4走の1角通過順位→脚質、先行馬の数→ペースS/M/H、勝率に倍率）。参考：過去18レースで log loss 2.317→2.301（14/18で改善）、ダート・新潟で悪化警告。
- **EXP-002 馬場状態補正** `e2e_validation/challengers/going_v1.py`（発走前の公式馬場と同じ芝/ダでの良・道悪の近走成績）。参考：過去18レースで log loss ほぼ同じ。内外のトラックバイアスは発走前データが無く対象外。
- 次の候補：「購入セット・印との整合性」（ticket_portfolio）、「若駒・経験不足」（field_experience）。どちらも未登録。

## サイト変更の仕組み（2026-11-02 作り直し）
- STAGING ＝「本番＋承認待ちの変更案」。変更案は**本番と同じ書き方**で `.github/staging-candidates/<docs配下と同じパス>` に置き、`.github/staging-candidates.json` に登録 → `python3 .github/scripts/staging-baseline-v2.py` でステージングを生成。docs/staging/ の HTML を直接編集しない（自動で作り直される）。
- 変更案のページはバッジ「STAGING 変更案・承認待ち」。ステージング内のリンクはステージングに留まる（improvement-cycle.html も対象ページに追加済み）。
- ユーザーの明示承認（「本番リリースOK」など）を得たら、`.github/workflows/jra-ui-promote-v1.yml` を `candidate_id` と承認の原文 `approval_quote` で実行（この環境では下の「作業上の注意」の REST 起動を使う）。本番へバイト一致コピー → ステージング再同期 → リリース台帳に自動採番で記録 → 保護データ不変・ガード・公開HTTP一致を確認。
- ガード：`.github/scripts/jra-release-guard-v1.py`（全リリース共通の不変条件＋過去リリースの固定値）。

### 承認待ちの変更案
- `ui-site-cleanup-v1`（全12ページ）：①文字サイズ統一（`assets/type-scale-v1.css`、タイトル最大24px・スマホ22px・節17px・補足12px以上）②トップの閲覧数を控えめな1行に＋**自分のブラウザの閲覧は数えない**（`?owner=1` を開いたブラウザだけ除外、`?owner=0` で解除。`assets/visitor-counter.js`）③トップを「予想のしくみと改善（2枚）／改善案を育てる研究／別の研究」に再編（改善の歩み＝roadmap はカードにせず、フッターの小さなリンクのみ。ユーザー指示）④旧比較検証（e2e.html）を「旧方式の比較記録（参考）」に格下げ（トップから外し、改善状況ページの折りたたみからリンク）⑤roadmap.html を「改善の歩み（履歴）」に改名⑥馬場・若駒の研究ページに「つながる改善テーマ」注記⑦methodology.html を重複を省いて再構成（番号の誤り・A/B/C の意味・古い版表記を修正）⑧サイト名を「AIによる競馬予想研究所」に統一。**ユーザーの「本番リリースOK」待ち**。
- 本番リリース済み：v1.06 改善状況ページのシンプル版／v1.07 トップと今週のAI予想を平易な日本語に（公開予定の1行つき）／v1.08 改善状況ページの試算注記。
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

## スケジュールタスク（Claude、通知文の表示のみ）
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
