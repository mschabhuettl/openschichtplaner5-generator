'use strict';
// Genuine same-source preset/manual parity, API and newly built DBF fixtures.
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {execFileSync}=require('node:child_process');
const {fixture,teams,state,settle}=require('./import-fixture.cjs');
async function importResult(page,endpoint){
 const request=page.waitForRequest(r=>r.method()==='POST'&&r.url().endsWith(endpoint));
 const response=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith(endpoint));
 const check=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/api/snapshots/check'));
 const beforeMs=Date.now();await page.click('#import');const rr=await response,remoteText=await rr.text(),afterMs=Date.now(),cr=await check;
 assert.equal(rr.status(),200,remoteText);assert.equal(cr.status(),200);
 await page.waitForFunction(()=>!!snapshot&&!projectSwitchBusy());
 return {beforeMs,afterMs,requestText:(await request).postData(),remoteText,checkRequestText:cr.request().postData(),checkResponseText:await cr.text(),canonicalText:await page.evaluate(()=>ProjectJSON.stringify(currentSnapshot())),dirty:await page.evaluate(()=>dirty)};
}
async function backend(page){const result={};for(const key of ['/api/snapshots','/api/snapshots?archived=true','/api/jobs']){const response=await page.request.get(key);assert.equal(response.status(),200);result[key]=await response.json();}return result;}
for(const sourceType of ['api','directory'])test('UX03C-A02 '+sourceType+' month versus manual complete raw-wire parity',async()=>{
 const source=sourceType==='directory'?fs.mkdtempSync(path.join(os.tmpdir(),'import-parity-dbf-')):null;
 const hashes=()=>Object.fromEntries(fs.readdirSync(source).sort().map(n=>[n,require('node:crypto').createHash('sha256').update(fs.readFileSync(path.join(source,n))).digest('hex')]));
 let sourceBefore;
 try{
  const sourceFixture=source?JSON.parse(execFileSync(process.env.WEB_TEST_PYTHON||'python',[path.join(__dirname,'import-dbf-fixture.py'),source],{encoding:'utf8',env:{...process.env,TMPDIR:os.tmpdir()}})):null;
  if(source)sourceBefore=hashes();
  await fixture('import-parity-'+sourceType,async(page,{base,observations,artifacts})=>{
  observations.sourceFixture=sourceFixture;
 const endpoint=sourceType==='api'?'/api/remote-import':'/api/import';
 const requests=[];function observe(p){p.on('request',r=>{if(['POST','PUT','PATCH','DELETE'].includes(r.method()))requests.push({method:r.method(),path:new URL(r.url()).pathname});});}observe(page);
 async function select(p){if(sourceType==='api')return teams(p);await p.click('#openImport');await p.selectOption('#sourceType','directory');await p.fill('#directory',source);await p.click('#inspect');await p.waitForSelector('[data-team-id="2"]');await p.check('[data-team-id="2"]');}
 observations.backendBefore=await backend(page);for(const list of Object.values(observations.backendBefore))assert.deepEqual(list,[]);
 await select(page);const before=await state(page);await page.click('#quickStart > summary');await page.fill('#quickMonth','2026-02');await page.click('#quickPrepare');await settle(page);
 assert.deepEqual(await state(page),before);assert.equal(requests.length,0,'preset sends no import or write');assert.deepEqual(await backend(page),observations.backendBefore);
 await page.screenshot({path:path.join(artifacts,sourceType+'-preset-before-import.png'),fullPage:true});
 observations.preset=await importResult(page,endpoint);await settle(page);await page.screenshot({path:path.join(artifacts,sourceType+'-preset-imported.png'),fullPage:true});
 const manualPage=await page.context().browser().newPage({baseURL:base,viewport:{width:1440,height:1000},timezoneId:'Europe/Vienna',locale:'de-AT'});manualPage.setDefaultTimeout(7000);observe(manualPage);manualPage.on('pageerror',e=>observations.pageErrors.push(e.message));manualPage.on('console',m=>{if(m.type()==='error')observations.consoleErrors.push(m.text());});
 await manualPage.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());await manualPage.goto(base);await manualPage.waitForFunction(()=>window.PlannerApp);await select(manualPage);
 await manualPage.fill('#start','2026-02-01');await manualPage.fill('#end','2026-02-28');await manualPage.selectOption('#demandSource','history');if(!await manualPage.locator('#importOptions').evaluate(e=>e.open))await manualPage.click('#importOptions > summary');
 for(const [id,value] of Object.entries({timezone:'Europe/Vienna',historyStart:'2023-02-01',historyEnd:'2026-01-31',demandHistoryStart:'2025-02-01',demandHistoryEnd:'2025-02-28',historyMinDays:'3'}))await manualPage.fill('#'+id,value);
 await manualPage.check('#autoKind');await manualPage.uncheck('#autoHistory');await manualPage.uncheck('#reuseSetup');await manualPage.selectOption('#historyPlan','ist');await manualPage.selectOption('#referencePlan','ist');await manualPage.selectOption('#existingPlanMode','reference');
 await manualPage.screenshot({path:path.join(artifacts,sourceType+'-manual-before-import.png'),fullPage:true});
 observations.manual=await importResult(manualPage,endpoint);await settle(manualPage);await manualPage.screenshot({path:path.join(artifacts,sourceType+'-manual-imported.png'),fullPage:true});
 assert.equal(observations.preset.requestText,observations.manual.requestText,'byte-exact complete import requests');
 observations.backendAfter=await backend(page);assert.deepEqual(observations.backendAfter,observations.backendBefore);
 observations.requests=requests;assert.equal(requests.filter(r=>r.path===endpoint).length,2);assert.equal(requests.filter(r=>r.path==='/api/snapshots/check').length,2);assert(requests.every(r=>r.method==='POST'&&[endpoint,'/api/snapshots/check','/api/readiness'].includes(r.path)),'no implicit write endpoint');
 observations.unpersistedIds=[];for(const result of [observations.preset,observations.manual]){const id=JSON.parse(result.canonicalText).id;const response=await page.request.get('/api/snapshots/'+encodeURIComponent(id));observations.unpersistedIds.push({id,status:response.status()});assert.equal(response.status(),404);}
 assert.deepEqual(observations.consoleErrors,[]);
 observations.sourceType=sourceType;const wires=path.join(artifacts,'raw-wires-'+sourceType+'.json');fs.writeFileSync(wires,JSON.stringify(observations,null,2)+'\n');
 observations.oracle=JSON.parse(execFileSync(process.env.WEB_TEST_PYTHON||'python',[path.join(__dirname,'import-parity-oracle.py'),wires],{encoding:'utf8',env:{...process.env,TMPDIR:require('node:os').tmpdir()}}));
 assert.equal(observations.oracle.status,'PASS');await manualPage.close();

 if(source){const after=hashes();observations.sourceReadback={before:sourceBefore,after,unchanged:JSON.stringify(sourceBefore)===JSON.stringify(after)};assert.deepEqual(after,sourceBefore,'DBF import never modifies source');}
 },{sourceRoot:source});
 }finally{
  try{if(sourceBefore)assert.deepEqual(hashes(),sourceBefore,'DBF source unchanged even on failure');}
  finally{if(source)fs.rmSync(source,{recursive:true,force:true});}
 }
});
