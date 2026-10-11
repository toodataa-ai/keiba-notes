// Validate the actual production prestart workflow, not only library test fixtures.
// Never silently accept nonexistent commands or a publish-before-validation order.
import fs from 'node:fs';
import assert from 'node:assert/strict';
const path='.github/workflows/jra-prestart-pipeline-v311.yml';
const source=fs.readFileSync(path,'utf8');
const scriptRefs=[...new Set((source.match(/\.github\/scripts\/[\w.\/-]+\.(?:mjs|py)/g)||[]))];
assert(scriptRefs.length>=8,'expected complete prereace test and PDF pipeline');
for(const file of scriptRefs)assert(fs.existsSync(file),'prestart workflow references missing script: '+file);
const stages=[
  'Run v3.11 balanced optimisation, history and regression CI',
  'Validate path and reserve immutable snapshot names',
  'Generate and audit the complete unsealed betting snapshot',
  'Adaptively paginate every selected/rejected candidate and verify PDF before freezing',
  'Freeze snapshot in a real Git commit before race start',
  'Seal final prediction with existing Git proof',
  'Generate final PDF from immutable proof, validate every page and append public registry',
  'Commit only new prediction PDF HTML and appended race registry'
];
let previous=-1;
for(const stage of stages){
 const at=source.indexOf(stage);
 assert(at>previous,'missing/misordered v3.11 prepublish stage: '+stage);
 previous=at;
}
const pre=source.slice(source.indexOf(stages[3]),source.indexOf(stages[4]));
const final=source.slice(source.indexOf(stages[6]),source.indexOf(stages[7]));
const publishing=source.slice(source.indexOf(stages[7]));
assert(pre.includes('validate-jra-pdf-content-v311.py'),'must validate authored PDF before proof commit');
assert(pre.includes('1:1'),'adaptive pagination must attempt at least one row per PDF page');
assert(pre.includes('VALIDATED') && pre.includes('exit 1'),'do not accept failed prereace PDF');
assert(final.indexOf('validate-jra-pdf-content-v311.py')>=0 &&
       final.indexOf('validate-jra-pdf-content-v311.py') <
       final.indexOf('jra-publish-live-v311.py'),
       'sealed prediction PDF must pass rendered-content audit before registry staging');
assert(publishing.includes('actual!=expected') && publishing.includes('git push'),
  'publication must refuse unintended or incomplete file changes');
assert(source.includes('cannot overwrite') && source.includes('Prior official report/PDF exists'),
  'must guard immutable prior publications');
console.log('PASS: all '+scriptRefs.length+' prereace scripts exist; ordered snapshot, full PDF inspection, proof and atomic official publish');
