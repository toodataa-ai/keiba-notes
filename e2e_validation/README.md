# E2E予想検証基盤 v1

## 目的

競馬予想プロンプトの改良が、部分指標ではなく **予想全体** の精度・再現性・馬券成績を本当に改善したかを、同じルールで比較するための基盤です。

対象フロー:

`予想時点情報 → STEP1評価/印 → 馬場・展開 → STEP2/買い目 → 結果 → 採点 → 版比較`

## 最重要原則: 結果リークを分離する

### Grade A: prospective_strict

正式な比較に使うゴールドスタンダードです。

- 予想ファイルを発走前にGitへコミットする
- case.jsonには、その予想が存在した **pre-race commit SHA** を記録する
- 採点時はHEADの予想ファイルではなく `git show <proof_commit>:<prediction_path>` を読む
- proof commitの時刻、予想生成時刻、情報cutoffが発走前cutoffを超えていないことを検証する
- 結果ファイルはレース後に別途追加する

これにより、レース後に予想内容を書き換えてもGrade Aとして採点されません。

### Grade B: historical_replay

過去レースを時点情報だけで再構成した検証です。構造検証には使えますが、LLMが学習済み知識として結果を知っている可能性を完全には排除できないため、**正式なプロンプト昇格判定には単独で使いません**。

### synthetic

CI・計算ロジックの動作確認専用です。実成績には一切含めません。

## ディレクトリ

- `config.json` — 比較ポリシー
- `manifests/` — プロンプト版と依存ファイルの固定マニフェスト
- `cases/` — 実レースのE2Eケース
- `fixtures/` — synthetic test
- `evaluate.py` — リーク監査・採点・版比較
- `test_evaluate.py` — 単体テスト
- `docs/e2e.html` — GitHub Pages可視化
- `docs/data/e2e_status.json` — 集計結果

## 予想スナップショットの考え方

予想ファイルには最低限、以下を残します。

- race_id / prompt_version
- generated_at / information_cutoff_at
- ◎○▲
- STEP1順位（取得できる場合）
- 馬場確率、展開確率（取得できる場合）
- 各馬の勝率・3着内率（将来のCalibration対応。現時点では任意）
- 買い目と賭け金
- 使用したソースの公開時刻

確率がない版も採点できますが、Brier score / log lossは `coverage=false` として扱います。これにより、現在の「確率校正不足」自体も可視化できます。

## 指標

必須:

- ◎勝率
- ◎3着内率
- ◎○▲による実Top3捕捉率
- 勝ち馬が◎○▲に入った率
- 馬券投資額・払戻・ROI（settlementがあるケース）

取得時のみ:

- 勝率Brier score
- 勝率log loss
- 3着内率Brier score
- 馬場状態log loss
- 展開log loss
- 勝ち馬の順位 / MRR

## 版比較

`config.json` の baseline / candidate を、**同じGrade Aレースの共通集合だけ**で比較します。

初期段階では自動昇格しません。`minimum_strict_shared_cases` 未満なら `insufficient_data` と表示し、サンプルが貯まってから昇格基準を判断します。

ROIは分散が大きいため、単独でプロンプトの優劣を決めません。命中・確率校正・条件別安定性と併記します。

## 運用

1. レース前に現行版（将来は現行版＋候補版）で予想スナップショットを保存
2. そのコミットSHAをproofとして保持
3. レース後にresult.jsonを追加
4. GitHub ActionsがE2E採点
5. `docs/e2e.html` で結果を確認
6. 十分なGrade Aケースが貯まった段階で、週次改善の根拠へ利用

## 注意

E2E検証基盤は「未来を完全に予測できる」ことを保証するものではありません。目的は、**変更前後を同一条件で測り、改善したつもりの改悪を止めること**です。
