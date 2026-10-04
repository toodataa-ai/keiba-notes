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
  const reportPath = path.join(reportsDir, file);
  const out = path.join(pdfDir, file.replace(/\.html$/, '.pdf'));

  // The authored originals were rendered with WeasyPrint 68. Render the authored
  // HTML directly so its CSS colors, type sizes, tables and fixed A4 layout survive.
  execFileSync('python3', ['-m', 'weasyprint', reportPath, out], {
    stdio: 'inherit',
    maxBuffer: 20 * 1024 * 1024
  });

  const slug = file.replace(/\.html$/, '');
  const race = racesById.get(slug);
  const renderedPages = pdfPageCount(out);
  if (race?.full_report_pages && renderedPages !== race.full_report_pages) {
    throw new Error(`${slug}: rendered PDF pages ${renderedPages} != expected ${race.full_report_pages}`);
  }
  console.log(`Rendered ${out} with WeasyPrint 68 (${renderedPages} pages)`);
}
