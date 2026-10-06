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
    if replacements:
        for old, new in replacements:
            text = text.replace(old, new)
    save_if_changed(path, original, text)


def simplify_index() -> None:
    path = DOCS / 'index.html'
    text = path.read_text(encoding='utf-8')
    original = text

    # 英語の装飾ラベルを外し、トップページを入口に集約する。
    text = re.sub(r'\s*<div class="lab-signature".*?</div>', '', text, count=1, flags=re.S)
    text = re.sub(r'<span class="brand-lab-en">.*?</span>', '', text, count=1, flags=re.S)
    text = re.sub(
        r'\.hero-nav\{display:grid;grid-template-columns:[^;]+;',
        '.hero-nav{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));',
        text,
        count=1
    )

    nav = '''<nav class="hero-nav" aria-label="主要ページ">
        <a class="hero-nav-link" href="methodology.html"><span class="hero-nav-label"><span>予想ロジックと検証思想</span></span><span class="hero-nav-arrow">→</span></a>
        <a class="hero-nav-link" href="roadmap.html"><span class="hero-nav-label"><span>今後のブラッシュアップ思想</span></span><span class="hero-nav-arrow">→</span></a>
        <a class="hero-nav-link" href="e2e.html"><span class="hero-nav-label"><span>JRA シャドー検証</span></span><span class="hero-nav-arrow">→</span></a>
        <a class="hero-nav-link" href="experience-regime.html"><span class="hero-nav-label"><span>E0/E1/E2 経験量研究</span></span><span class="hero-nav-arrow">→</span></a>
        <a class="hero-nav-link" href="local-racing-shadow.html"><span class="hero-nav-label"><span>地方競馬 シャドー研究</span></span><span class="hero-nav-arrow">→</span></a>
        <a class="hero-nav-link" href="baba-models.html"><span class="hero-nav-label"><span>馬場予測モデル</span></span><span class="hero-nav-arrow">→</span></a>
      </nav>'''
    text = re.sub(r'<nav class="hero-nav"[^>]*>.*?</nav>', nav, text, count=1, flags=re.S)

    # アコーディオン見出しは日本語だけを残す。
    text = re.sub(r'<span class="eyebrow dark">(?:UPCOMING|PERFORMANCE|PROMPT|ARCHIVE)</span>', '', text)
    text = re.sub(r'<p class="eyebrow dark">(?:UPCOMING|PERIOD|ARCHIVE)</p>', '', text)
    text = text.replace('地方競馬はDaily Shadow研究として分離', '地方競馬はシャドー研究として分離')

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

    text = text.replace('<title>JRA E2E Shadow | 競馬予想精度向上AI</title>', '<title>JRA E2E シャドー検証 | 競馬予想精度向上AI</title>')
    text = text.replace('End-to-End Prediction Validation', '発走前固定型のE2E検証')
    text = text.replace('Baseline / Candidate 比較', '基準版 / 候補版 比較')
    text = text.replace('Baseline: <strong>', '基準版: <strong>')
    text = text.replace(' / Candidate: <strong>', ' / 候補版: <strong>')
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
    ('<small>MODE</small><strong>SHADOW</strong>', '<small>運用</small><strong>研究中</strong>'),
    ('<small>SCOPE</small>', '<small>対象</small>'),
    ('<small>COVERAGE</small>', '<small>カバー率</small>'),
    ('<small>OBSERVATIONS</small>', '<small>観測数</small>'),
])

simplify_method_page('local-racing-shadow.html', [
    ('<small>MODE</small><strong>DAILY SHADOW</strong>', '<small>運用</small><strong>研究中</strong>'),
    ('<small>VENUES</small>', '<small>対象場</small>'),
    ('<small>OBSERVED</small>', '<small>観測レース</small>'),
    ('<small>TRANSFER</small>', '<small>転用候補</small>'),
    ('<small>RACES OBSERVED</small>', '<small>観測レース</small>'),
    ('<small>RESULTS JOINED</small>', '<small>結果照合済み</small>'),
    ('<small>TRANSFER CANDIDATES</small>', '<small>転用候補</small>'),
])

simplify_e2e()
simplify_baba_models()
