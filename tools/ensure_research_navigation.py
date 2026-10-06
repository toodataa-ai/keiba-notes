#!/usr/bin/env python3
from pathlib import Path
import re

DOCS = Path('docs')

HOME_STYLE = '''
<style id="simple-home-navigation-style">
.simple-home-nav{display:flex!important;justify-content:flex-start!important;align-items:center!important;gap:0!important;margin-bottom:18px!important}
.simple-home-nav .method-brand,.simple-home-nav a,.simple-home-link{display:inline-flex!important;align-items:center!important;gap:6px!important;padding:10px 14px!important;border-radius:999px!important;background:#fff!important;color:#17171a!important;border:1px solid rgba(0,0,0,.12)!important;box-shadow:0 1px 4px rgba(0,0,0,.08)!important;text-decoration:none!important;font-size:14px!important;font-weight:800!important;line-height:1.2!important}
.simple-home-bottom{display:flex;justify-content:center;margin:34px 0 8px}
.simple-home-bottom a{display:inline-flex;align-items:center;justify-content:center;min-height:48px;padding:11px 20px;border-radius:999px;background:#17171a;color:#fff!important;text-decoration:none;font-weight:800;border:1px solid #17171a}
@media(max-width:640px){.simple-home-nav .method-brand,.simple-home-nav a,.simple-home-link{width:100%;justify-content:center;min-height:48px}.simple-home-bottom a{width:100%}}
</style>'''.strip()

HOME_NAV = '<nav class="method-nav simple-home-nav" aria-label="トップページへ戻る"><a class="method-brand" href="index.html">← トップページに戻る</a></nav>'
HOME_BOTTOM = '<div class="simple-home-bottom"><a href="index.html">トップページに戻る</a></div>'

INDEX_NAV_STYLE = '''
<style id="home-research-navigation-style">
.home-nav-groups{margin-top:22px;max-width:980px}
.home-nav-group{padding:18px;border:1px solid rgba(255,255,255,.12);border-radius:14px;background:rgba(255,255,255,.035)}
.home-nav-group+.home-nav-group{margin-top:34px}
.home-nav-group.research{background:rgba(255,255,255,.02)}
.home-nav-head{margin-bottom:13px}
.home-nav-head h2{margin:0;color:#fff;font-size:20px;line-height:1.35}
.home-nav-head p{margin:6px 0 0;color:#aeb3bd;font-size:12px;line-height:1.6}
.home-nav-kicker{display:inline-block;margin-bottom:5px;color:#e06170;font-size:10px;font-weight:900;letter-spacing:.08em}
.home-main-actions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.home-main-actions a{display:flex;align-items:center;justify-content:center;min-height:46px;padding:9px 8px;border-radius:9px;background:#fff;color:#17171a;text-decoration:none;font-size:12px;font-weight:800;text-align:center;border:1px solid rgba(255,255,255,.2)}
.hero-nav.research-nav{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:0;max-width:none}
.research-nav .hero-nav-link{display:block;min-height:92px;padding:13px 14px;background:#f7f7f8}
.research-nav .hero-nav-title{display:block;color:#17171a;font-size:14px;font-weight:850;line-height:1.35}
.research-nav .hero-nav-desc{display:block;margin-top:6px;color:#666a73;font-size:11px;font-weight:600;line-height:1.5}
.research-nav .hero-nav-arrow{display:block;margin-top:8px;text-align:right}
@media(max-width:640px){
  .home-nav-group{padding:14px 12px}
  .home-nav-group+.home-nav-group{margin-top:30px}
  .home-nav-head h2{font-size:18px}
  .home-main-actions{grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}
  .home-main-actions a{padding:8px 4px;font-size:11px}
  .hero-nav.research-nav{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
  .research-nav .hero-nav-link{min-height:104px;padding:12px 10px}
  .research-nav .hero-nav-title{font-size:13px}
  .research-nav .hero-nav-desc{font-size:10px}
}
</style>'''.strip()


def save_if_changed(path: Path, original: str, text: str) -> None:
    if text != original:
        path.write_text(text, encoding='utf-8')
        print(f'updated {path}')
    else:
        print(f'no changes {path}')


def add_home_style(text: str) -> str:
    if 'simple-home-navigation-style' not in text:
        text = text.replace('</head>', f'{HOME_STYLE}\n</head>', 1)
    return text


def remove_english_kickers(text: str) -> str:
    return re.sub(r'\s*<p class="kicker">.*?</p>', '', text, flags=re.S)


def replace_bottom_links(text: str) -> str:
    pattern = r'<section class="links-panel[^"]*"[^>]*>.*?</section>'
    if re.search(pattern, text, flags=re.S):
        return re.sub(pattern, HOME_BOTTOM, text, count=1, flags=re.S)
    if 'simple-home-bottom' not in text:
        return text.replace('</main>', f'{HOME_BOTTOM}\n</main>', 1)
    return text


def simplify_method_page(filename: str, replacements=None) -> None:
    path = DOCS / filename
    text = path.read_text(encoding='utf-8')
    original = text
    text = add_home_style(text)
    text = re.sub(r'<nav class="method-nav"[^>]*>.*?</nav>', HOME_NAV, text, count=1, flags=re.S)
    text = re.sub(r'<nav class="method-nav simple-home-nav"[^>]*>.*?</nav>', HOME_NAV, text, count=1, flags=re.S)
    text = remove_english_kickers(text)
    text = replace_bottom_links(text)
    text = re.sub(r'\s*<a href="#links">.*?</a>', '', text, flags=re.S)
    if replacements:
        for old, new in replacements:
            text = text.replace(old, new)
    save_if_changed(path, original, text)


def simplify_index() -> None:
    path = DOCS / 'index.html'
    text = path.read_text(encoding='utf-8')
    original = text

    text = re.sub(r'\s*<div class="lab-signature".*?</div>', '', text, count=1, flags=re.S)
    text = re.sub(r'<span class="brand-lab-en">.*?</span>', '', text, count=1, flags=re.S)
    if 'home-research-navigation-style' not in text:
        text = text.replace('</head>', f'{INDEX_NAV_STYLE}\n</head>', 1)

    nav = '''<div class="home-nav-groups">
        <section class="home-nav-group main" aria-labelledby="mainPredictionTitle">
          <div class="home-nav-head">
            <span class="home-nav-kicker">このサイトの中心</span>
            <h2 id="mainPredictionTitle">JRAメインレース予想</h2>
            <p>各開催日のメインレースをAIで予想し、結果と回顧まで同じページで公開します。</p>
          </div>
          <div class="home-main-actions">
            <a href="#upcomingDisclosure">今後の予定</a>
            <a href="#performanceDisclosure">成績</a>
            <a href="#archiveDisclosure">予想履歴</a>
          </div>
        </section>

        <section class="home-nav-group research" aria-labelledby="researchTitle">
          <div class="home-nav-head">
            <span class="home-nav-kicker">精度向上のための研究</span>
            <h2 id="researchTitle">予想を強くするために検証していること</h2>
            <p>以下はすべて、JRAメインレース予想の精度向上につなげるための研究・検証です。</p>
          </div>
          <nav class="hero-nav research-nav" aria-label="研究・検証ページ">
            <a class="hero-nav-link" href="methodology.html"><span class="hero-nav-title">予想ロジックと改善の考え方</span><span class="hero-nav-desc">予想をどう組み立て、どう検証するか</span><span class="hero-nav-arrow">→</span></a>
            <a class="hero-nav-link" href="roadmap.html"><span class="hero-nav-title">改善ロードマップ</span><span class="hero-nav-desc">何を改善し、どの条件で採用するか</span><span class="hero-nav-arrow">→</span></a>
            <a class="hero-nav-link" href="baba-models.html"><span class="hero-nav-title">馬場予測の研究</span><span class="hero-nav-desc">10競馬場×芝・ダートを個別に検証</span><span class="hero-nav-arrow">→</span></a>
            <a class="hero-nav-link" href="e2e.html"><span class="hero-nav-title">JRA予想の比較検証</span><span class="hero-nav-desc">予想を先に固定し、結果と比較して改良効果を測る</span><span class="hero-nav-arrow">→</span></a>
            <a class="hero-nav-link" href="experience-regime.html"><span class="hero-nav-title">経験の少ない馬の研究</span><span class="hero-nav-desc">新馬やキャリアの浅い馬の予想難度を検証</span><span class="hero-nav-arrow">→</span></a>
            <a class="hero-nav-link" href="local-racing-shadow.html"><span class="hero-nav-title">地方競馬での予想研究</span><span class="hero-nav-desc">地方競馬でも予想と結果を蓄積して傾向を研究</span><span class="hero-nav-arrow">→</span></a>
          </nav>
        </section>
      </div>'''
    if re.search(r'<div class="home-nav-groups">.*?</div>\s*<div class="hero-prompt-status">', text, flags=re.S):
        text = re.sub(r'<div class="home-nav-groups">.*?</div>\s*(?=<div class="hero-prompt-status">)', nav + '\n      ', text, count=1, flags=re.S)
    else:
        text = re.sub(r'<nav class="hero-nav"[^>]*>.*?</nav>', nav, text, count=1, flags=re.S)

    text = re.sub(r'<span class="eyebrow dark">(?:UPCOMING|PERFORMANCE|PROMPT|ARCHIVE)</span>', '', text)
    text = re.sub(r'<p class="eyebrow dark">(?:UPCOMING|PERIOD|ARCHIVE)</p>', '', text)
    text = text.replace('地方競馬はDaily Shadow研究として分離', '地方競馬は予想研究として分離')
    text = text.replace('地方競馬はシャドー研究として分離', '地方競馬は予想研究として分離')

    save_if_changed(path, original, text)


def simplify_e2e() -> None:
    path = DOCS / 'e2e.html'
    text = path.read_text(encoding='utf-8')
    original = text
    text = add_home_style(text)

    home_nav = '<nav class="nav simple-home-nav" aria-label="トップページへ戻る"><a class="simple-home-link" href="index.html">← トップページに戻る</a></nav>'
    if re.search(r'<nav class="nav"[^>]*>.*?</nav>', text, flags=re.S):
        text = re.sub(r'<nav class="nav"[^>]*>.*?</nav>', home_nav, text, count=1, flags=re.S)
    elif re.search(r'<nav class="nav simple-home-nav"[^>]*>.*?</nav>', text, flags=re.S):
        text = re.sub(r'<nav class="nav simple-home-nav"[^>]*>.*?</nav>', home_nav, text, count=1, flags=re.S)
    else:
        text = text.replace('<header><div class="inner">', '<header><div class="inner">' + home_nav, 1)

    replacements = [
        ('<title>JRA E2E Shadow | 競馬予想精度向上AI</title>', '<title>JRA予想の比較検証 | 競馬予想精度向上AI</title>'),
        ('<title>JRA E2E シャドー検証 | 競馬予想精度向上AI</title>', '<title>JRA予想の比較検証 | 競馬予想精度向上AI</title>'),
        ('<h1>JRA E2E Shadow</h1>', '<h1>JRA予想の比較検証</h1>'),
        ('<h1>JRA E2E シャドー検証</h1>', '<h1>JRA予想の比較検証</h1>'),
        ('Git proofを残したまま', '発走前コミット証明を残したまま'),
        ('<strong>正式な性能比較は Grade A / prospective_strict のみ。</strong> Historical replay は補助検証であり、同じ一覧でも明確に区別して表示します。', '<strong>正式な性能比較は Grade A の発走前固定実戦だけ。</strong> 過去再現検証は補助資料として明確に区別します。'),
        ('End-to-End Prediction Validation', '発走前固定型のE2E検証'),
        ('発走前Git proofあり', '発走前コミット証明あり'),
        ('Baseline / Candidate 比較', '基準版 / 候補版 比較'),
        ('Baseline: <strong>', '基準版: <strong>'),
        (' / Candidate: <strong>', ' / 候補版: <strong>'),
        ('<th>Version</th>', '<th>版</th>'),
        ('<th>◎○▲ Top3捕捉</th>', '<th>◎○▲の3着内捕捉</th>'),
        ('<th>Win Brier</th>', '<th>勝率Brier</th>'),
        ('<th>ROI</th>', '<th>回収率</th>'),
        ('<h2>発走前 Shadow → proof → 結果</h2>', '<h2>発走前予測 → 証明 → 結果</h2>'),
        ('地方競馬Daily Shadowと同じ考え方で', '地方競馬での予想研究と同じ考え方で'),
        ('地方競馬シャドー研究と同じ考え方で', '地方競馬での予想研究と同じ考え方で'),
        ('発走前snapshotとproof commit', '発走前スナップショットとコミット証明'),
        ('<option value="historical">Grade B historical replay</option>', '<option value="historical">Grade B 過去再現</option>'),
        ('発走前snapshotのみ', '発走前スナップショットのみ'),
        ('Shadowデータを読み込み中です。', '検証データを読み込み中です。'),
        ('シャドーデータを読み込み中です。', '検証データを読み込み中です。'),
        ('<b>発走前固定</b>information cutoffより前にsnapshotを保存。', '<b>発走前固定</b>情報締切時刻より前にスナップショットを保存。'),
        ('<b>Git proof</b>Grade Aは発走前commit SHAで存在証明。', '<b>コミット証明</b>Grade Aは発走前commit SHAで存在を証明。'),
        ('prediction原本へ着順・払戻を追記しない。', '予測原本へ着順・払戻を追記しない。'),
    ]
    for old, new in replacements:
        text = text.replace(old, new)

    if 'simple-home-bottom' not in text:
        text = text.replace('</main>', f'{HOME_BOTTOM}\n</main>', 1)

    save_if_changed(path, original, text)


def simplify_baba_models() -> None:
    path = DOCS / 'baba-models.html'
    text = path.read_text(encoding='utf-8')
    original = text
    text = add_home_style(text)

    text = text.replace('<title>馬場予測モデル | KEIBA AI NEXT</title>', '<title>馬場予測モデル | 競馬予想精度向上AI</title>')
    text = re.sub(
        r'<div class="top"><div><div class="small">.*?</div><h1>(.*?)</h1></div><a href="[^"]*">.*?</a></div>',
        r'<div class="top"><div><h1>\1</h1></div><a class="simple-home-link" href="index.html">← トップページに戻る</a></div>',
        text,
        count=1,
        flags=re.S
    )
    text = text.replace('Pilotをどう進化させるか', '試験運用をどう進化させるか')
    text = text.replace('<strong>Pilot → Backtesting → Candidate → Validated</strong>', '<strong>試験運用 → 検証中 → 候補 → 検証済み</strong>')
    text = text.replace('Candidate生成までは自動化し、本番予想への接続は承認後だけ行います。', '候補生成までは自動化し、本番予想への接続は承認後だけ行います。')
    text = text.replace('Candidateになっても自動で本番ルータへ接続しません。既存Validatedモデルも勝手に置換しません。', '候補になっても自動で本番ルータへ接続しません。既存の検証済みモデルも勝手に置換しません。')
    text = text.replace('<span class="status validated">Validated</span><span class="status candidate">Candidate</span><span class="status backtesting">Backtesting</span><span class="status pilot">Pilot</span><span class="status degraded">Degraded</span>', '<span class="status validated">検証済み</span><span class="status candidate">候補</span><span class="status backtesting">検証中</span><span class="status pilot">試験運用</span><span class="status degraded">要改善</span>')
    text = text.replace("const labels={validated:'Validated',candidate:'Candidate',backtesting:'Backtesting',pilot:'Pilot',degraded:'Degraded',retired:'Retired'};", "const labels={validated:'検証済み',candidate:'候補',backtesting:'検証中',pilot:'試験運用',degraded:'要改善',retired:'終了'};")
    text = text.replace('Stage A Candidate（本番未接続）', 'Stage A 候補（本番未接続）')
    text = text.replace('Stage A Candidate', 'Stage A 候補')
    text = text.replace('Candidate → Validated、本番モデル置換は承認必須。', '候補 → 検証済み、本番モデル置換は承認必須。')
    text = text.replace('Data policy:', 'データ方針：')
    if 'simple-home-bottom' not in text:
        text = text.replace('</main>', f'{HOME_BOTTOM}\n</main>', 1)

    save_if_changed(path, original, text)


simplify_index()

simplify_method_page('methodology.html', [
    ('<span class="live-label">CURRENT PROMPT</span>', '<span class="live-label">現行プロンプト</span>'),
    ('<span class="live-label">GRADE A E2E CASES</span>', '<span class="live-label">Grade A 検証件数</span>'),
    ('<span class="live-label">E2E EXPERIMENT</span>', '<span class="live-label">E2E 比較状態</span>'),
])

simplify_method_page('roadmap.html', [
    ('<small>CURRENT PROMPT</small>', '<small>現行プロンプト</small>'),
    ('<small>TRACK MODELS</small>', '<small>馬場モデル</small>'),
    ('<small>STAGE A CANDIDATES</small>', '<small>Stage A 候補</small>'),
    ('<small>GRADE A E2E</small>', '<small>Grade A E2E</small>'),
    ('通常のJRA開催週では、予想・回顧・週次改善を別タスクとして分離しています。', '通常のJRA開催週では、発走前予想と、回顧・週次改善を2系統に分離しています。'),
])

simplify_method_page('experience-regime.html', [
    ('<title>Experience Regime E0/E1/E2 | 競馬予想精度向上AI</title>', '<title>経験の少ない馬の予想研究 | 競馬予想精度向上AI</title>'),
    ('<small>MODE</small><strong>SHADOW</strong>', '<small>運用</small><strong>研究中</strong>'),
    ('<small>SCOPE</small>', '<small>対象</small>'),
    ('<small>COVERAGE</small>', '<small>カバー率</small>'),
    ('<small>OBSERVATIONS</small>', '<small>観測数</small>'),
    ('Experience Regime E0/E1/E2 — Shadow observation only.', 'E0/E1/E2 経験量研究 — 観測専用。'),
])

simplify_method_page('local-racing-shadow.html', [
    ('<title>地方競馬 シャドー研究 | 競馬予想精度向上AI</title>', '<title>地方競馬での予想研究 | 競馬予想精度向上AI</title>'),
    ('<small>MODE</small><strong>DAILY SHADOW</strong>', '<small>運用</small><strong>研究中</strong>'),
    ('<small>VENUES</small>', '<small>対象場</small>'),
    ('<small>OBSERVED</small>', '<small>観測レース</small>'),
    ('<small>TRANSFER</small>', '<small>転用候補</small>'),
    ('<small>RACES OBSERVED</small>', '<small>観測レース</small>'),
    ('<small>RESULTS JOINED</small>', '<small>結果照合済み</small>'),
    ('<small>TRANSFER CANDIDATES</small>', '<small>転用候補</small>'),
    ('地方競馬 Daily Shadow', '地方競馬での予想研究'),
    ('地方競馬 シャドー研究', '地方競馬での予想研究'),
    ('DAILY SHADOW', '予想研究'),
])

simplify_e2e()
simplify_baba_models()
