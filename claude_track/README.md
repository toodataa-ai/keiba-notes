# claude_track — Claude の予想・回顧・成績（ChatGPT とは完全に別）

ChatGPT の予想（`e2e_validation/`）には一切触れない。ここは Claude 専用の保存場所と採点。

## ルール（比較を公平にするため）
1. 対象は、ChatGPT が予想するレースと**同じレースだけ**。
2. Claude は ChatGPT の予想を**見ずに**、オッズを見る前に全頭を独立評価し、発走前に保存（コミット）する。コミット時刻が証拠。
3. 保存後は書き換えない（修正は新しいファイルとして追加し、最初のファイルを正とする）。
4. レース結果は共有の `e2e_validation/results/<race_id>.json` を使う（結果は 1 回だけ取得し、2 人を同じ方法で採点）。
5. Claude の買い目は「もし買ったら」の仮想。実際の購入には使わない前提で成績を測る。

## 置き場所
- `predictions/<race_id>/<prompt_version>-<UTC日時>.json` — 発走前の予想（下のスキーマ）
- `reviews/<race_id>.json` — レース後の回顧（Claude 自身の振り返り）
- `status_v1.json` — 採点の集計（`score_claude.py` が作る。サイトは `docs/data/predictors/claude_status_v1.json` を読む）

## 予想ファイルのスキーマ（schema_version 1）
```json
{
  "schema_version": 1,
  "predictor": "claude",
  "race_id": "2026-11-08-xxx",
  "prompt_version": "claude-v1.0",
  "model": "（実行したモデル名）",
  "generated_at": "2026-11-08T08:10:00+09:00",
  "information_cutoff_at": "2026-11-08T08:00:00+09:00",
  "odds_seen_before_step1": false,
  "horses": [
    {"no": 5, "name": "馬名", "mark": "◎", "ability": "A", "win_prob": 0.22, "top3_prob": 0.55, "reason": "この馬固有の根拠"}
  ],
  "bets": [{"type": "三連複", "selection": [1, 5, 9], "stake_yen": 100}],
  "total_stake_yen": 600
}
```
- `mark` は ◎○▲△× のいずれか、または null。`win_prob` は全頭で合計 1 になるよう正規化して採点する。
- `bets` の `type` は 単勝・複勝・枠連・ワイド・馬連・馬単・三連複・三連単。

## 採点（`score_claude.py`）
- 印：◎の勝率・複勝率、◎○▲の3着内に入った頭数
- 確率：勝ち馬の log loss と Brier（`win_prob` がある予想だけ）
- 買い目：的中・払戻・回収率（公式払戻 `official_payouts_yen_per_100` で採点）
- 証拠の区分：`prospective`（発走前に保存）／`not_prospective`（発走後に保存された。成績に数えない）
