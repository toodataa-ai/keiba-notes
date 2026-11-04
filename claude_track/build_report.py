"""Claude の予想の詳細ページを作る。出力: docs/claude-reports/<race_id>.html
中身は、保存済みの予想（STEP1・STEP2）と、あれば回顧・結果。保存済みの予想は書き換えない。
結果・反省は、見たくない人のために折りたたむ。"""
from __future__ import annotations
import json
from html import escape as _esc
from pathlib import Path
from claude_track import score_claude as sc

ROOT = Path(__file__).resolve().parents[1]
CSS = ("main{padding:24px 0}.sheet{background:#fff;border:1px solid #e5e5ea;border-radius:14px;padding:16px;margin:0 0 14px}"
       ".sheet h2{margin:0 0 10px;font-size:18px}.eyebrow.dark{color:#71717a;font-size:12px;font-weight:700;margin:0 0 4px}"
       ".tbl{width:100%;border-collapse:collapse;font-size:14px}.tbl th,.tbl td{border-bottom:1px solid #eee;padding:7px 6px;text-align:left;vertical-align:top}"
       ".tbl td.n{text-align:right;white-space:nowrap}.mk{font-weight:700;font-size:16px}.top li{margin:0 0 8px}.muted{color:#71717a;font-size:13px}"
       ".wrapx{overflow-x:auto}details.sp{background:#fff;border:1px solid #e5e5ea;border-radius:14px;padding:12px 16px;margin:0 0 14px}details.sp summary{font-weight:700;cursor:pointer}")


def e(v):
    return _esc(str(v if v is not None else ""))


def pct(x):
    return "—" if x is None else f"{x*100:.1f}%"


def yen(n):
    return "—" if n is None else f"{int(n):,}円"


def render(p: dict, s2: dict | None, review: dict | None, res: dict | None, scored: dict | None) -> str:
    horses = sorted(p.get("horses", []), key=lambda h: (sc.MARKS.index(h["mark"]) if h.get("mark") in sc.MARKS else 99, -(h.get("win_prob") or 0)))
    marked = [h for h in horses if h.get("mark")]
    h = [f'<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
         f'<title>{e(p.get("race_name",""))} Claudeの予想</title><link rel="stylesheet" href="../assets/style.css"><style>{CSS}</style></head><body>'
         f'<header class="hero"><div class="wrap"><p class="eyebrow">{e(p.get("date",""))} · {e(p.get("venue",""))}</p><h1>{e(p.get("race_name",""))} Claudeの予想</h1>'
         f'<p class="lead">予想の版 {e(p.get("prompt_version") or "—")}　発走前の保存 {e(p.get("generated_at") or "—")}　オッズは見ずに評価</p></div></header><main class="wrap">']
    h.append('<section class="sheet"><p class="eyebrow dark">STEP1</p><h2>本紙印</h2><ul class="top" style="padding-left:18px">'
             + "".join(f'<li><span class="mk">{e(x["mark"])}</span> {e(x["no"])} {e(x.get("name",""))}　<span class="muted">能力{e(x.get("ability","—"))}・勝率{pct(x.get("win_prob"))}</span><br>{e(x.get("reason",""))}</li>' for x in marked)
             + '</ul></section>')
    gf = p.get("going_forecast")
    if gf:
        pr = gf.get("probs", {})
        h.append('<section class="sheet"><p class="eyebrow dark">TRACK</p><h2>馬場の予測</h2><p><b>' + " / ".join(f"{e(k)} {pct(v)}" for k, v in pr.items()) + f'</b></p><p class="muted">最も可能性が高い：{e(gf.get("most_likely",""))}（朝の公式発表・含水率・気象庁の実測から計算した目安です）</p></section>')
    h.append('<section class="sheet"><p class="eyebrow dark">ALL</p><h2>全頭の評価</h2><div class="wrapx"><table class="tbl"><tr><th>馬番</th><th>馬名</th><th>印</th><th>能力</th><th>勝率</th><th>3着内</th><th>根拠</th></tr>'
             + "".join(f'<tr><td class="n">{e(x["no"])}</td><td>{e(x.get("name",""))}</td><td>{e(x.get("mark") or "")}</td><td>{e(x.get("ability",""))}</td><td class="n">{pct(x.get("win_prob"))}</td><td class="n">{pct(x.get("top3_prob"))}</td><td>{e(x.get("reason",""))}</td></tr>' for x in sorted(p.get("horses", []), key=lambda z: z["no"]))
             + '</table></div></section>')
    if s2:
        bets = s2.get("bets", [])
        body = ("".join(f'<tr><td>{e(b["type"])}</td><td>{e("→".join(map(str,b["selection"])) if b["type"] in ("馬単","三連単") else "-".join(map(str,b["selection"])))}</td><td class="n">{yen(b.get("stake_yen"))}</td><td class="n">{e(b.get("market_odds","—"))}</td><td>{e(b.get("reason",""))}</td></tr>' for b in bets)
                if bets else "")
        h.append('<section class="sheet"><p class="eyebrow dark">STEP2</p><h2>買い目（仮想）</h2>'
                 + (f'<div class="wrapx"><table class="tbl"><tr><th>券種</th><th>組番</th><th>金額</th><th>オッズ</th><th>理由</th></tr>{body}</table></div><p class="muted">合計 {yen(s2.get("total_stake_yen"))}　オッズ取得 {e(s2.get("odds_observed_at") or "—")}　実際には購入しません</p>'
                    if bets else f'<p>見送り：{e(s2.get("skip_reason") or "")}</p>') + '</section>')
    if res and scored:
        h.append('<details class="sp"><summary>結果を見る</summary><p>3着内：' + e("・".join(map(str, res["finish_order"][:3]))) + f'　購入{yen(scored.get("stake_yen"))} → 払戻{yen(scored.get("payout_yen"))}</p></details>')
    if review:
        h.append('<details class="sp"><summary>Claudeの反省会を見る</summary>' + f'<p>{e(review.get("summary",""))}</p>'
                 + (f'<p>◎の結果：{e(review["honmei_result"])}</p>' if review.get("honmei_result") else "")
                 + (f'<p>失敗の分類：{e("、".join(review["failure_types"]))}</p>' if review.get("failure_types") else "")
                 + ("<p>学んだこと：</p><ul>" + "".join(f"<li>{e(x)}</li>" for x in review.get("lessons", [])) + "</ul>" if review.get("lessons") else "") + '</details>')
    h.append('<p class="actions"><a class="btn secondary" href="../results.html#claude">← 過去の成績へ戻る</a></p></main></body></html>\n')
    return "".join(h)


def main(pred_dir: Path | None = None, out_dir: Path | None = None, results_dir: Path | None = None):
    pred_dir = pred_dir or ROOT / "claude_track/predictions"
    out_dir = out_dir or ROOT / "docs/claude-reports"
    results_dir = results_dir or ROOT / "e2e_validation/results"
    scored = {x["race_id"]: x for x in sc.run(pred_dir, results_dir)["races"]}
    n = 0
    for rid, slot in sc.load_race_files(pred_dir).items():
        p = slot["step1"]
        if not p:
            continue
        rf = sc.resolve_result(rid, results_dir)
        res = json.loads(rf.read_text(encoding="utf-8")) if rf else None
        rv = ROOT / "claude_track/reviews" / f"{rid}.json"
        review = json.loads(rv.read_text(encoding="utf-8")) if rv.is_file() else None
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{rid}.html").write_text(render(p, slot["step2"], review, res, scored.get(rid)), encoding="utf-8")
        n += 1
    print(f"wrote {n} reports")


if __name__ == "__main__":
    main()
