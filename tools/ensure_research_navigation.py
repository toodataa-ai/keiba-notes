#!/usr/bin/env python3
from pathlib import Path

p = Path('docs/index.html')
text = p.read_text(encoding='utf-8')
original = text

text = text.replace(
    '.hero-nav{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));',
    '.hero-nav{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));'
)

needle = '<a class="hero-nav-link" href="experience-regime.html"><span class="hero-nav-label"><span class="hero-nav-new">SHADOW</span><span>E0/E1/E2 経験量研究</span></span><span class="hero-nav-arrow">→</span></a>'
local = '<a class="hero-nav-link" href="local-racing-shadow.html"><span class="hero-nav-label"><span class="hero-nav-new">DAILY</span><span>地方競馬 Daily Shadow</span></span><span class="hero-nav-arrow">→</span></a>'
if local not in text:
    if needle not in text:
        raise SystemExit('experience-regime navigation anchor not found')
    text = text.replace(needle, needle + '\n        ' + local, 1)

old_footer = '<footer class="wrap footer"><p>対象はJRAメインレースのみ。土日だけでなく、祝日月曜などJRA開催がある日は同じ運用で集計します。</p></footer>'
new_footer = '<footer class="wrap footer"><p>正式成績の対象はJRAメインレース。地方競馬はDaily Shadow研究として分離し、JRA正式成績・本番予想へ直接混在させません。</p></footer>'
if old_footer in text:
    text = text.replace(old_footer, new_footer, 1)

if text != original:
    p.write_text(text, encoding='utf-8')
    print('updated docs/index.html')
else:
    print('no changes')
