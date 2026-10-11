import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';

const reportsDir = path.resolve('docs/reports');
const styledSourcesDir = path.resolve('docs/styled-report-sources');
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

// Protect recovered authored HTML including CSS, colors, typography and layout.
// If a canonical recovery source changes unexpectedly, fail closed.
const canonicalStyledSourceSha256 = new Map([
  ['2026-10-04-kyoto-daishoten', '685cce49411872735c8d1d3ec65999bf8c437d5e11526caeb8ec04c43484ab98'],
  ['2026-10-04-mainichi-okan', 'd765450417b12f1b08e2c5dbac5aeef278c3235664cc17123d75e8506fa5032f']
]);

fs.mkdirSync(reportsDir, { recursive: true });
fs.mkdirSync(pdfDir, { recursive: true });

const racesData = JSON.parse(fs.readFileSync(racesPath, 'utf8'));
const races = Array.isArray(racesData.races) ? racesData.races : [];
const racesById = new Map(races.map(race => [race.id, race]));

function decodeXzBase64(sourcePath) {
  const b64 = fs.readFileSync(sourcePath, 'utf8').replace(/\s+/g, '');
  const compressed = Buffer.from(b64, 'base64');
  return execFileSync('xz', ['-dc'], {
    input: compressed,
    maxBuffer: 20 * 1024 * 1024
  }).toString('utf8');
}

function sha256(value) {
  return createHash('sha256').update(value).digest('hex');
}

function restoreCanonicalStyledReports() {
  if (!fs.existsSync(styledSourcesDir)) return;

  const sources = fs.readdirSync(styledSourcesDir)
    .filter(file => file.endsWith('.html.xz.b64'))
    .sort();

  for (const sourceFile of sources) {
    const slug = sourceFile.replace(/\.html\.xz\.b64$/, '');
    const race = racesById.get(slug);
    if (!race) throw new Error(`Styled report source has no races.json entry: ${slug}`);
    if (!race.report) throw new Error(`Styled report source race has no report path: ${slug}`);

    const html = decodeXzBase64(path.join(styledSourcesDir, sourceFile));
    const expectedSha = canonicalStyledSourceSha256.get(slug);
    if (expectedSha && sha256(html) !== expectedSha) {
      throw new Error(`${slug}: canonical styled source SHA-256 mismatch`);
    }
    if (!html.includes('data-full-report="true"') || !html.includes('data-authored-report="true"')) {
      throw new Error(`${slug}: canonical styled source is missing authored full-report markers`);
    }

    const reportPath = path.resolve('docs', race.report);
    fs.mkdirSync(path.dirname(reportPath), { recursive: true });
    fs.writeFileSync(reportPath, html);
    console.log(`Restored canonical authored report ${race.report} from styled source`);
  }
}

restoreCanonicalStyledReports();

// Preserve the visitor counter when restoring immutable authored HTML sources.
// The canonical source hash is checked before adding this non-printing script.
for (const name of fs.readdirSync(reportsDir).filter(file => file.endsWith('.html'))) {
  const reportPath = path.join(reportsDir, name);
  const authoredHtml = fs.readFileSync(reportPath, 'utf8');
  // Historical >=2026-10-11 prereace reports are immutable; never rewrite them to inject a script.
  const race = racesById.get(name.replace(/\.html$/, ''));
  if (race?.date >= '2026-10-11') continue;
  if (!authoredHtml.includes('visitor-counter.js') && authoredHtml.includes('</body>')) {
    const tag = '<script src="../assets/visitor-counter.js?v=20261006-1" defer></script>';
    fs.writeFileSync(reportPath, authoredHtml.replace('</body>', `  ${tag}\n</body>`));
    console.log(`Preserved visitor counter in ${name}`);
  }
}

function getHorseCount(html) {
  const declared = Number(html.match(/data-horse-count="(\d+)"/)?.[1] || 0);
  if (declared) return declared;
  const diagnosisMarkers = (html.match(/data-horse-diagnosis="true"/g) || []).length;
  if (diagnosisMarkers) return diagnosisMarkers;
  return (html.match(/class="horse-title"/g) || []).length;
}

function validateFullReport(race) {
  if (race.scope !== 'jra-main' || !race.report || !race.pdf || race.date < cutoverDate) return;
  const reportPath = path.resolve('docs', race.report);
  if (!fs.existsSync(reportPath)) throw new Error(`${race.id}: authored report missing: ${race.report}`);

  const html = fs.readFileSync(reportPath, 'utf8');
  if (!html.includes('data-full-report="true"')) {
    throw new Error(`${race.id}: official PDF source is not marked as a complete report`);
  }
  if (!html.includes('data-authored-report="true"')) {
    throw new Error(`${race.id}: official PDF source must be the authored HTML, not extracted/reconstructed text`);
  }
  if (html.includes('data-reconstructed-from-text="true"')) {
    throw new Error(`${race.id}: reconstructed text HTML can never be an official PDF source`);
  }

  // From 2026-10-11, a stricter user-accepted reader-v1 layout contract
  // replaces the legacy marker-only layout check. The rendered PDF itself is
  // validated below, before the publish commit is allowed.
  if (race.date >= '2026-10-11') {
    if (!html.includes('<section class="horse">')) {
      throw new Error(`${race.id}: missing individual reader-v1 horse sheets`);
    }
    return;
  }

  const missing = mandatoryMarkers.filter(marker => !html.includes(marker));
  if (missing.length) {
    throw new Error(`${race.id}: complete report is missing sections: ${missing.join(', ')}`);
  }

  const horseCount = getHorseCount(html);
  if (!race.field_size) throw new Error(`${race.id}: field_size is required for complete-report validation`);
  if (horseCount !== race.field_size) {
    throw new Error(`${race.id}: horse diagnosis count ${horseCount} != field size ${race.field_size}`);
  }
  console.log(`Validated authored complete report ${race.id}: ${horseCount}/${race.field_size} horses`);
}

for (const race of races) validateFullReport(race);

const rendererVersion = execFileSync('python3', ['-m', 'weasyprint', '--version'], { encoding: 'utf8' }).trim();
if (!rendererVersion.includes('68.0')) {
  throw new Error(`Official PDF renderer must be WeasyPrint 68.0; found: ${rendererVersion}`);
}
console.log(`Using canonical renderer: ${rendererVersion}`);

function pdfPageCount(pdfPath) {
  const info = execFileSync('pdfinfo', [pdfPath], { encoding: 'utf8' });
  const match = info.match(/^Pages:\s+(\d+)/m);
  if (!match) throw new Error(`Could not determine PDF page count: ${pdfPath}`);
  return Number(match[1]);
}

const files = fs.readdirSync(reportsDir).filter(file => file.endsWith('.html')).sort();
if (!files.length) {
  console.log('No reports found.');
  process.exit(0);
}

for (const file of files) {
  const slug = file.replace(/\.html$/, '');
  const race = racesById.get(slug);
  if (!race?.pdf) {
    console.log(`Skipping unmanaged report ${file}; existing PDF is left unchanged`);
    continue;
  }
  // Old authored PDF originals remain immutable; never regenerate them as a
  // side-effect of enabling a stricter future layout gate.
  if (race.date < '2026-10-11') {
    console.log(`Protected historical report/PDF: ${slug}`);
    continue;
  }

  const reportPath = path.join(reportsDir, file);
  const out = path.resolve('docs', race.pdf);
  fs.mkdirSync(path.dirname(out), { recursive: true });

  // Future formal releases commit a fully audited PDF with the prediction.
  // A background renderer must never rewrite any published JRA v3.10/v3.11 original.
  if (fs.existsSync(out)) {
    console.log(`Preserved immutable official PDF: ${slug}`);
    continue;
  }

  // The authored originals were rendered with WeasyPrint 68. Render the authored
  // HTML directly so its CSS colors, type sizes, tables and fixed A4 layout survive.
  execFileSync('python3', ['-m', 'weasyprint', reportPath, out], {
    stdio: 'inherit',
    maxBuffer: 20 * 1024 * 1024
  });

  // Fail closed. Never publish a broken new PDF merely because PDF
  // generation returned exit code zero.
  execFileSync('python3', [
    '.github/scripts/validate-jra-pdf-layout.py',
    '--html', reportPath,
    '--pdf', out,
    '--policy', 'docs/data/jra_pdf_layout_policy_v1.json'
  ], { stdio: 'inherit' });

  const renderedPages = pdfPageCount(out);
  if (race.full_report_pages && renderedPages !== race.full_report_pages) {
    throw new Error(`${slug}: rendered PDF pages ${renderedPages} != expected ${race.full_report_pages}`);
  }
  console.log(`Rendered ${out} with WeasyPrint 68 (${renderedPages} pages)`);
}
