import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';

const reportsDir = path.resolve('docs/reports');
const fullReportsDir = path.resolve('docs/full-reports');
const pdfDir = path.resolve('docs/pdfs');
const racesPath = path.resolve('docs/data/races.json');
const cutoverDate = '2026-10-04';
const mandatoryMarkers = [
  '発走時馬場予測',
  '芝馬場質5分類',
  '当日バイアス3分離',
  '類似条件タイム',
  '同条件直接実績',
  'STEP1',
  '想定展開',
  '想定隊列',
  '再監査',
  '全頭診断',
  '◎弱点監査',
  'STEP2',
  '能力本線',
  '期待値追加',
  '緊急リスクフラグ',
  '推奨買い目',
  '最終結論'
];

fs.mkdirSync(reportsDir, { recursive: true });
fs.mkdirSync(pdfDir, { recursive: true });

const racesData = JSON.parse(fs.readFileSync(racesPath, 'utf8'));
const races = Array.isArray(racesData.races) ? racesData.races : [];
const racesById = new Map(races.map(race => [race.id, race]));

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function decodeArchivedText(sourcePath) {
  const b64 = fs.readFileSync(sourcePath, 'utf8').replace(/\s+/g, '');
  const compressed = Buffer.from(b64, 'base64');
  return execFileSync('xz', ['-dc'], {
    input: compressed,
    maxBuffer: 20 * 1024 * 1024
  }).toString('utf8');
}

function normalizePages(text) {
  const pages = text.split('\f');
  while (pages.length && !pages.at(-1).trim()) pages.pop();
  return pages;
}

function createArchiveHtml(race, pages) {
  const diagnosisPattern = /全頭診断[\s\S]*?horse\s+\d+\s*\/\s*\d+/;
  const horsePages = pages.filter(page => diagnosisPattern.test(page)).length;
  const pageSections = pages.map((page, index) => {
    const isHorse = diagnosisPattern.test(page);
    const horseAttr = isHorse ? ' data-horse-diagnosis="true"' : '';
    return `<section class="archive-page" data-source-page="${index + 1}"${horseAttr}><pre>${escapeHtml(page.replace(/^\n+|\n+$/g, ''))}</pre></section>`;
  }).join('\n');

  return `<!doctype html>
<html lang="ja" data-full-report="true" data-source-pages="${pages.length}" data-horse-count="${horsePages}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>${escapeHtml(race.race)} ${escapeHtml(race.prompt_version || '')} 完全版</title>
  <style>
    @page{size:A4;margin:0}
    *{box-sizing:border-box}
    html,body{margin:0;padding:0;background:#e5e7eb;color:#111827;font-family:"Meiryo UI","Meiryo","Noto Sans CJK JP",sans-serif}
    .archive-note{max-width:960px;margin:16px auto;padding:12px 16px;border-radius:12px;background:#111827;color:#fff;font-size:14px;line-height:1.6}
    .archive-note strong{display:block;font-size:16px}
    .archive-page{width:210mm;height:297mm;margin:14px auto;background:#fff;padding:8mm;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.12)}
    .archive-page pre{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font-family:"Noto Sans Mono CJK JP","Meiryo UI","Meiryo",monospace;font-size:11pt;line-height:1.32;color:#111827}
    @media(max-width:760px){.archive-note{margin:10px}.archive-page{width:100%;height:auto;min-height:0;margin:10px 0;padding:14px 10px;overflow:auto;box-shadow:none}.archive-page pre{font-size:11px;line-height:1.5;min-width:0}}
    @media print{html,body{background:#fff}.archive-note{display:none}.archive-page{margin:0;box-shadow:none;break-inside:avoid}.archive-page:not(:last-child){break-after:page}.archive-page pre{font-size:11pt;line-height:1.32}}
  </style>
</head>
<body>
  <div class="archive-note"><strong>完全版・発走前スナップショット</strong>このページは発走前に確定した完全版予想を保存したものです。結果確定後も予想本文は改変しません。</div>
  <main>${pageSections}</main>
  <script>
    window.fitArchivePages = () => {
      const maxPt = 11;
      const minPt = 9.5;
      const stepPt = 0.1;
      for (const section of document.querySelectorAll('.archive-page')) {
        const pre = section.querySelector('pre');
        if (!pre) continue;
        const style = getComputedStyle(section);
        const availableHeight = section.clientHeight
          - parseFloat(style.paddingTop || '0')
          - parseFloat(style.paddingBottom || '0');
        let pt = maxPt;
        pre.style.fontSize = pt + 'pt';
        while (pre.scrollHeight > availableHeight + 1 && pt > minPt) {
          pt = Math.max(minPt, +(pt - stepPt).toFixed(1));
          pre.style.fontSize = pt + 'pt';
        }
        section.dataset.renderFontPt = pt.toFixed(1);
      }
    };
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', window.fitArchivePages);
    } else {
      window.fitArchivePages();
    }
    window.addEventListener('load', window.fitArchivePages);
  </script>
</body>
</html>`;
}

if (fs.existsSync(fullReportsDir)) {
  const archivedSources = fs.readdirSync(fullReportsDir)
    .filter(file => file.endsWith('.txt.xz.b64'))
    .sort();

  for (const sourceFile of archivedSources) {
    const slug = sourceFile.replace(/\.txt\.xz\.b64$/, '');
    const race = racesById.get(slug);
    if (!race) throw new Error(`Full report source has no races.json entry: ${slug}`);
    if (!race.report) throw new Error(`Full report source race has no report path: ${slug}`);

    const text = decodeArchivedText(path.join(fullReportsDir, sourceFile));
    const pages = normalizePages(text);
    if (race.full_report_pages && pages.length !== race.full_report_pages) {
      throw new Error(`${slug}: archived page count ${pages.length} != expected ${race.full_report_pages}`);
    }

    const diagnosisPattern = /全頭診断[\s\S]*?horse\s+\d+\s*\/\s*\d+/;
    const horsePages = pages.filter(page => diagnosisPattern.test(page)).length;
    if (race.field_size && horsePages !== race.field_size) {
      throw new Error(`${slug}: horse diagnosis count ${horsePages} != field size ${race.field_size}`);
    }

    const reportPath = path.resolve('docs', race.report);
    fs.mkdirSync(path.dirname(reportPath), { recursive: true });
    fs.writeFileSync(reportPath, createArchiveHtml(race, pages));
    console.log(`Restored complete report ${race.report}: ${pages.length} source pages / ${horsePages} horses`);
  }
}

function validateFullReport(race) {
  if (race.scope !== 'jra-main' || !race.report || !race.pdf || race.date < cutoverDate) return;
  const reportPath = path.resolve('docs', race.report);
  if (!fs.existsSync(reportPath)) throw new Error(`${race.id}: report missing: ${race.report}`);
  const html = fs.readFileSync(reportPath, 'utf8');
  if (!html.includes('data-full-report="true"')) {
    throw new Error(`${race.id}: final PDF source is not marked as a complete report`);
  }
  const missing = mandatoryMarkers.filter(marker => !html.includes(marker));
  if (missing.length) {
    throw new Error(`${race.id}: complete report is missing sections: ${missing.join(', ')}`);
  }
  const horseCount = (html.match(/data-horse-diagnosis="true"/g) || []).length;
  if (!race.field_size) throw new Error(`${race.id}: field_size is required for complete-report validation`);
  if (horseCount !== race.field_size) {
    throw new Error(`${race.id}: horse diagnosis count ${horseCount} != field size ${race.field_size}`);
  }
  console.log(`Validated complete report ${race.id}: ${horseCount}/${race.field_size} horses`);
}

for (const race of races) validateFullReport(race);

const files = fs.readdirSync(reportsDir).filter(file => file.endsWith('.html')).sort();
if (!files.length) {
  console.log('No reports found.');
  process.exit(0);
}

const browser = await chromium.launch({ headless: true });
try {
  for (const file of files) {
    const page = await browser.newPage({ viewport: { width: 1280, height: 1800 } });
    const url = pathToFileURL(path.join(reportsDir, file)).href;
    await page.goto(url, { waitUntil: 'networkidle' });
    await page.emulateMedia({ media: 'print' });
    await page.evaluate(() => window.fitArchivePages?.());

    const archiveOverflow = await page.$$eval('.archive-page', sections => sections
      .map(section => {
        const pre = section.querySelector('pre');
        if (!pre) return null;
        const style = getComputedStyle(section);
        const availableHeight = section.clientHeight
          - parseFloat(style.paddingTop || '0')
          - parseFloat(style.paddingBottom || '0');
        return pre.scrollHeight > availableHeight + 1
          ? `${section.dataset.sourcePage || '?'} (${section.dataset.renderFontPt || '?'}pt)`
          : null;
      })
      .filter(Boolean));
    if (archiveOverflow.length) {
      throw new Error(`${file}: restored text overflows source pages: ${archiveOverflow.join(', ')}`);
    }

    const out = path.join(pdfDir, file.replace(/\.html$/, '.pdf'));
    const pdfBuffer = await page.pdf({
      format: 'A4',
      printBackground: true,
      preferCSSPageSize: true,
      margin: { top: '0mm', right: '0mm', bottom: '0mm', left: '0mm' }
    });
    fs.writeFileSync(out, pdfBuffer);

    const slug = file.replace(/\.html$/, '');
    const race = racesById.get(slug);
    const renderedPages = (pdfBuffer.toString('latin1').match(/\/Type\s*\/Page\b/g) || []).length;
    if (race?.full_report_pages && renderedPages !== race.full_report_pages) {
      throw new Error(`${slug}: rendered PDF pages ${renderedPages} != expected ${race.full_report_pages}`);
    }
    console.log(`Rendered ${out}${renderedPages ? ` (${renderedPages} pages)` : ''}`);
    await page.close();
  }
} finally {
  await browser.close();
}
