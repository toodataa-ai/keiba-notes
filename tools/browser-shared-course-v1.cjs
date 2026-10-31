const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),base=path.resolve(process.argv[2]);
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try{
 for(const width of [390,1024])for(const trial of ['synthetic','shuka2026']){
 const results=[];
 for(const dir of [base,root]){
  const page=await browser.newPage({viewport:{width,height:900}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>{
   const url=new URL(route.request().url());
   if(url.hostname!=='lab.test')return route.abort();
   const name=path.join(dir,decodeURIComponent(url.pathname));
   if(!name.startsWith(dir+'/'))return route.abort();
   if(!fs.existsSync(name))return route.fulfill({status:404,body:''});
   const ext=path.extname(name),type={'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml'}[ext]||'text/plain';
   return route.fulfill({contentType:type,body:fs.readFileSync(name)});
  });
  await page.goto('http://lab.test/docs/lab/race-clean-course-v1.html?trial='+trial+'&checkpoint=1270');
  await page.waitForFunction(()=>window.CleanLab?.inspect().sharedGeometryEnabled,{timeout:30000});
  await page.waitForTimeout(300);
  const result=await page.evaluate(()=>({state:CleanLab.getState(),inspect:CleanLab.inspect(),overflow:document.documentElement.scrollWidth>innerWidth}));
  assert.deepEqual(errors,[]);assert(!result.overflow);assert(!result.inspect.turfError);assert(!result.inspect.sharedGeometryError);
  results.push(result);
  await page.screenshot({path:'/tmp/kyoto-'+(dir===root?'after':'before')+'-'+width+'-'+trial+'.png',fullPage:true});
  await page.close();
 }
 assert.deepEqual(results[1].state,results[0].state);
 assert.deepEqual(results[1].inspect.positions,results[0].inspect.positions);
 console.log('PASS browser geometry/state/overflow',width,trial);
 }
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
