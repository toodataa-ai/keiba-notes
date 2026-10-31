const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');process.chdir(root);
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const registry=read('docs/lab/shared-course/SOURCE-REGISTER.json');
for(const asset of registry.assets){assert.equal(crypto.createHash('sha256').update(fs.readFileSync(asset.path)).digest('hex'),asset.sha256);assert.equal(asset.writtenPermissionVerified,false);}
const catalog=read('docs/lab/race-course-catalog-v1.json');
const inventory={source:'race-course-catalog-v1.json',sourceCheckedOn:catalog.source_checked_on,coverageDenominatorCertified:false,
 reason:'Existing catalog collapses rail variants to representative A; historical settings and special starts require official-source audit in a later approved phase.',
 approvedCourseCount:0,labCompatibilityCourseIds:['kyoto_turf_inner_2000'],otherCoursesUnlocked:false,
 venues:catalog.venues.map(v=>({code:v.code,name:v.name,officialUrl:v.official_url,routeTypes:v.routes.length,candidateDistances:v.routes.reduce((n,r)=>n+r.distances_m.length,0),approved:0}))};
inventory.candidateTotal=inventory.venues.reduce((n,v)=>n+v.candidateDistances,0);
const bytes=JSON.stringify(inventory,null,2)+'\n',target='docs/lab/shared-course/INVENTORY.json';
if(process.argv.includes('--check'))assert.equal(fs.readFileSync(target,'utf8'),bytes);else fs.writeFileSync(target,bytes);
// A per-commit allowlist prevents accidental DATA, STAGING or production edits.
const base=process.env.COURSE_CHANGE_BASE||'f176feab634055ddd1833827e47a54fd8eb7784b';
const files=cp.execFileSync('git',['diff','--name-only',base],{encoding:'utf8'}).trim().split('\n').filter(Boolean).concat(cp.execFileSync('git',['ls-files','--others','--exclude-standard'],{encoding:'utf8'}).trim().split('\n').filter(Boolean));
const allowed=p=>p.startsWith('docs/lab/')||p.startsWith('tools/')||p==='.github/workflows/lab-shared-course-v1.yml'||p==='.github/lab/feature-registry.json';
assert(files.every(allowed),files.filter(p=>!allowed(p)).join(','));
for(const asset of registry.assets){assert.equal(cp.execFileSync('git',['show',base+':'+asset.path]).compare(fs.readFileSync(asset.path)),0);}
console.log('PASS_LAB_ONLY_ASSET_INTEGRITY_AND_CANDIDATE_INVENTORY',JSON.stringify({candidateTotal:inventory.candidateTotal,venues:inventory.venues.length,approved:0,files:files.length}));
