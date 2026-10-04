import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const reportsDir=path.resolve('docs/reports');
const pdfDir=path.resolve('docs/pdfs');
fs.mkdirSync(pdfDir,{recursive:true});
const files=fs.readdirSync(reportsDir).filter(f=>f.endsWith('.html')).sort();
if(!files.length){console.log('No reports found.');process.exit(0)}
const browser=await chromium.launch({headless:true});
for(const file of files){
  const page=await browser.newPage({viewport:{width:1280,height:1800}});
  const url=pathToFileURL(path.join(reportsDir,file)).href;
  await page.goto(url,{waitUntil:'networkidle'});
  await page.emulateMedia({media:'print'});
  const out=path.join(pdfDir,file.replace(/\.html$/,'.pdf'));
  await page.pdf({path:out,format:'A4',printBackground:true,preferCSSPageSize:true,margin:{top:'0mm',right:'0mm',bottom:'0mm',left:'0mm'}});
  console.log(`Rendered ${out}`);
  await page.close();
}
await browser.close();
