"""Readable STEP1 presentation only. Original v3.13 grades and evidence stay immutable."""
import html
import re

FACTOR_LABELS = ('① 斤量','② 展開','③ 馬場・トラックバイアス',
                 '④ ローテーション','⑤ コース適性','⑥ 血統',
                 '⑦ 調教','⑧ 騎手','⑨ 基礎能力')
STATUS = {'unavailable':'未取得','not_available':'未取得','missing':'未取得',
          'unknown':'確認できず','verified':'確認済み','available':'取得済み'}
HORSE_STYLE = '''<style>
/* v3.15 per-horse human-readable print layout, one A4 page per horse */
.horse-page h1{font-size:16pt;margin:4px 0 6px}
.horse-page h2{font-size:10pt;margin:10px 0 5px;border-left:3px solid #74869d;padding-left:7px}
.horse-facts{display:flex;gap:15px;flex-wrap:wrap;border-bottom:1px solid #d6dde6;padding:4px 0 7px;font-size:9pt}
.horse-score{display:inline-flex;align-items:center;gap:7px;white-space:nowrap}
.horse-page .grade{display:inline-block;font-weight:750;border:1px solid #c7cdd6;border-radius:4px;padding:1px 8px;color:#314052;background:#f3f5f7}
.horse-page .g-Aplus{background:#f6e6b1;border-color:#ddb76e;color:#72500f}
.horse-page .g-A{background:#e7edf8;border-color:#a7bddd;color:#254c83}
.horse-page .g-Bplus{background:#e2f0ea;border-color:#9bbfae;color:#285b45}
.horse-page .g-B{background:#eef1f5;border-color:#b9c2cc;color:#45505d}
.horse-page .g-Bminus{background:#f9eee0;border-color:#dfc4a8;color:#80562b}
.horse-page .g-C{background:#f5e7e7;border-color:#d9b3b3;color:#8b4747}
.horse-page table.factor-grid{table-layout:fixed;border-collapse:separate;border-spacing:5px 4px;font-size:9pt}
.horse-page .factor-grid td{border:1px solid #dbe1e9;border-radius:4px;padding:5px 7px;vertical-align:middle;background:#fafbfc}
.horse-page .factor-label{display:block;color:#47566c;font-size:8pt;margin-bottom:3px}
.horse-page .assessment{font-size:9pt;line-height:1.48;margin:4px 0 7px;white-space:normal;overflow-wrap:anywhere}
.horse-page table.run-table{font-size:8.3pt;table-layout:fixed}
.horse-page .run-table th,.horse-page .run-table td{padding:5px 4px;overflow-wrap:normal}
.horse-page .run-table th:nth-child(1){width:20%}
.horse-page .run-table th:nth-child(2){width:17%}
.horse-page .run-table th:nth-child(3){width:24%}
.horse-page .run-table th:nth-child(4){width:17%}
.horse-page .run-table th:nth-child(5){width:22%}
.horse-page .supplement{font-size:8.5pt;color:#4c5c70;line-height:1.5;margin:7px 0}
.horse-page .technical-ref{font-size:8pt;color:#59687b;margin-top:8px}
.horse-page .technical-ref a{color:#3c5b7e;text-decoration:none}
</style>'''

def esc(v):
    return html.escape(str(v),quote=True)

def chip(grade):
    grade = str(grade) if grade is not None else '未評価'
    klass = {'A+':'g-Aplus','A':'g-A','B+':'g-Bplus','B':'g-B',
             'B-':'g-Bminus','C':'g-C'}.get(grade,'')
    return f'<span class="grade {klass}">{esc(grade)}</span>'

def render_horse(x,fixed_at,source_proof):
    n = x.get('horse_number')
    horse = x.get('horse_name')
    if n is None or not horse:
        raise ValueError('JRA_V315_READABILITY_BLOCKER: missing sealed STEP1 horse identity')
    grades = x.get('factor_grades')
    if not isinstance(grades,list) or len(grades)!=9:
        raise ValueError(f'JRA_V315_READABILITY_BLOCKER: {n} incomplete ①〜⑨ grades')
    overall = x.get('overall_grade')
    if not overall:
        raise ValueError(f'JRA_V315_READABILITY_BLOCKER: {n} missing overall grade')
    factors = []
    for start in range(0,9,3):
        cells = []
        for j in range(start,start+3):
            cells.append('<td><span class="factor-label">'+FACTOR_LABELS[j]+'</span>'+chip(grades[j])+'</td>')
        factors.append('<tr>'+''.join(cells)+'</tr>')
    prior = x.get('past_performances') or []
    if not isinstance(prior,list):
        raise ValueError(f'JRA_V315_READABILITY_BLOCKER: {n} invalid prior-races field')
    rows = []
    for p in prior:
        if not isinstance(p,dict):
            raise ValueError(f'JRA_V315_READABILITY_BLOCKER: {n} malformed prior race')
        match = '同場・同距離' if p.get('same_condition') is True else ''
        rows.append('<tr>'
                    f'<td>{esc(p.get("date","—"))}</td>'
                    f'<td>{esc(p.get("course","—"))}</td>'
                    f'<td>{esc(p.get("surface",""))}{esc(p.get("distance_m","—"))}m</td>'
                    f'<td>{esc(p.get("finish","—"))}着</td>'
                    f'<td>{esc(p.get("time","—"))} {esc(match)}</td></tr>')
    if not rows:
        rows = ['<tr><td colspan="5">公式過去走データなし。発走前原本を参照。</td></tr>']
    weight = x.get('weight_kg')
    w = f'{esc(weight)}kg' if weight is not None else '未確認'
    rider = x.get('jockey') or '未確認'
    ev = x.get('evidence') or '個別の評価根拠は固定済み原本を参照してください。'
    prob = x.get('win_probability')
    chance = f'{float(prob)*100:.1f}%' if isinstance(prob,(int,float)) else '未算定'
    workout = STATUS.get(x.get('workout_data_status'),x.get('workout_data_status') or '未記録')
    jockey_stats = STATUS.get(x.get('jockey_course_stats_status'),x.get('jockey_course_stats_status') or '未記録')
    url = x.get('source_url') or ''
    official = f'・<a href="{esc(url)}">JRA公式根拠を開く</a>' if re.match(r'^https://www\.jra\.go\.jp/',url) else ''
    return f'''<section class="page horse-page">
<div class="kicker">STEP1 発走前評価（能力・適性評価 v3.13／原本は変更なし）</div>
<h1>{esc(n)}番　{esc(horse)}　{esc(x.get('mark') or '')}</h1>
<div class="horse-facts"><span class="horse-score">総合評価 {chip(overall)}</span>
<span>斤量 <strong>{w}</strong></span><span>馬プロフィール・騎手 <strong>{esc(rider)}</strong></span></div>
<h2>①〜⑨ 評価内訳</h2><table class="factor-grid"><tbody>{''.join(factors)}</tbody></table>
<h2>能力・適性の判断根拠</h2><p class="assessment">{esc(ev)}</p>
<h2>公式近走成績</h2>
<table class="run-table"><thead><tr><th>日付</th><th>競馬場</th><th>距離</th><th>着順</th><th>時計・同条件</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<p class="supplement">調教データ：{esc(workout)} ／ 騎手のコース別データ：{esc(jockey_stats)}<br>
モデル単勝確率：{esc(chance)}（未校正の推定値。市場オッズをSTEP1に反映していません）</p>
<p class="technical-ref">STEP1固定：{esc(fixed_at)} ／ 原本証跡：{esc(source_proof)}{official}<br>
詳細な公式原文・原票は固定済み発走前JSONに保存。ここでは原本の評価や馬券を変更していません。</p>
</section>'''
