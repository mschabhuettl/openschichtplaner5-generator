'use strict';
// S-UX02A-01: permanent carryforward of the supplemental validation/load races.
// Real Chromium, original page handlers, real solver/store. Only response timing
// and one declared admission 503 are injected; no test registration is imported.
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawn}=require('node:child_process');
const {chromium}=require('playwright');
const navigate=require('./navigation.cjs');
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function bounded(promise,ms,label){
 let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error(label+' timed out')),ms);})]);}finally{clearTimeout(timer);}
}
function deferred(){let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};}
function writeEvidence(name,data){
 const out=process.env.WEB_TEST_RACES_OUTPUT_DIR;if(!out)return;
 fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,name+'.json'),JSON.stringify(data,null,2)+'\n',{flag:'wx'});
}
// Keep the loopback guard installed. Do not unrouteAll: in the pinned runtime
// that can disable interception while another owned callback is still held.
function controlledRoutes(page,base){
 const active=new Set(),releases=[],errors=[],records=[];let closing=false;
 function track(work){
  const task=Promise.resolve().then(work).catch(error=>{errors.push(error);});
  active.add(task);void task.then(()=>active.delete(task));return task;
 }
 async function install(pattern,handler){
  await page.route(pattern,route=>track(async()=>{
   try{await handler(route);}catch(error){
    // Retain the original error; an abort is only to settle the browser request.
    try{await bounded(route.abort(),2000,'Failed route abort');}catch(abortError){errors.push(abortError);}
    throw error;
   }
  }));
 }
 async function hold(pattern){
  assert(!closing,'Cannot add a gate during teardown');
  const seen=deferred(),release=deferred(),record={pattern,finished:false};let used=false;
  releases.push(release.resolve);records.push(record);
  await install(pattern,async route=>{
   if(closing||used)return route.fallback();used=true;
   record.method=route.request().method();record.url=route.request().url();record.payload=route.request().postData();
   try{
    const response=await route.fetch({timeout:10000});
    record.status=response.status();record.response=await response.text();seen.resolve();
    // Gate AFTER the real backend completed, not before the actual request.
    await bounded(release.promise,15000,'Held backend response');
    await route.fulfill({response});
   }finally{record.finished=true;}
  });
  return {wait:()=>bounded(seen.promise,12000,'Backend response arrival'),release:release.resolve,record};
 }
 return {hold,records,errors,get active(){return active.size;},
  async guard(){await install('**/*',route=>new URL(route.request().url()).origin===base?route.continue():route.abort());},
  async failAdmission(){
   let used=false;
   await install('**/api/snapshots/check',async route=>{
    if(closing||used)return route.fallback();used=true;
    records.push({injection:'admission-503',method:route.request().method(),url:route.request().url(),payload:route.request().postData(),status:503});
    await route.fulfill({status:503,contentType:'application/json',body:'{"detail":"Synthetic admission failure S-UX02A-01"}'});
   });
  },
  async drain(){
   closing=true;releases.forEach(release=>release());
   await bounded((async()=>{
    // Recheck after completions: fallback/guard callbacks can join the set.
    do{await Promise.all([...active]);await pause(0);}while(active.size);
   })(),18000,'Owned route callback drain');
   assert.equal(active.size,0,'All owned callbacks finished before browser close');
   if(errors.length)throw new AggregateError(errors,'Owned route callback errors');
  }
 };
}
async function withWorkspace(name,run){
 const root=path.resolve(__dirname,'../..'),state=fs.mkdtempSync(path.join(os.tmpdir(),'review-workspace-races-'));
 const server=spawn(process.env.WEB_TEST_PYTHON||'python',['tests/browser/server.py'],{cwd:root,env:{...process.env,TMPDIR:os.tmpdir(),WEB_TEST_STATE:state,WEB_TEST_PORT:'0'},stdio:['ignore','pipe','pipe']});
 let output='',browser,routes,spawnError,activeBeforeClose,stopping=false;const failures=[],pageErrors=[],consoleErrors=[],warnings=[],requests=[];
 const exited=new Promise(resolve=>{server.once('exit',resolve);server.once('error',error=>{spawnError=error;resolve();});});
 for(const stream of [server.stdout,server.stderr])stream.on('data',data=>output+=data);
 try{
  const base=await bounded((async()=>{while(!stopping){
   if(spawnError)throw spawnError;
   if(server.exitCode!==null||server.signalCode!==null)throw Error('Fixture exited: '+output);
   const address=output.match(/Uvicorn running on (http:\/\/127\.0\.0\.1:\d+)/)?.[1];
   if(address){try{if((await fetch(address+'/healthz',{signal:AbortSignal.timeout(1000)})).ok)return address;}catch{}}
   await pause(100);
  }throw Error('Fixture startup stopped');})(),15000,'Fixture startup');
  browser=await chromium.launch({headless:true,args:['--no-sandbox'],timeout:15000,...(process.env.WEB_TEST_CHROMIUM?{executablePath:process.env.WEB_TEST_CHROMIUM}:{})});
  const page=await browser.newPage({baseURL:base,viewport:{width:1440,height:1000}});page.setDefaultTimeout(10000);
  page.on('pageerror',error=>pageErrors.push(error.message));
  page.on('console',message=>{const row={text:message.text(),location:message.location()};if(message.type()==='error')consoleErrors.push(row);if(message.type()==='warning')warnings.push(row);});
  page.on('request',request=>{const url=new URL(request.url());if(url.pathname.startsWith('/api/'))requests.push({method:request.method(),path:url.pathname,payload:request.postData()});});
  routes=controlledRoutes(page,base);await routes.guard();
  await page.goto(base);await page.waitForFunction(()=>window.PlannerApp);
  await bounded(run(page,{base,routes,requests}),70000,'Workspace race scenario');
 }catch(error){failures.push(error);}
 finally{
  stopping=true;
  // Release AND drain before closing; retain cleanup failures alongside the
  // scenario failure rather than hiding them with ignoreErrors/unrouteAll.
  try{if(routes)await routes.drain();}catch(error){failures.push(error);}
  activeBeforeClose=routes?.active;
  try{if(browser)await bounded(browser.close(),5000,'Browser shutdown');}catch(error){failures.push(error);}
  try{
   if(server.pid&&server.exitCode===null&&server.signalCode===null){
    server.kill('SIGTERM');try{await bounded(exited,5000,'Fixture shutdown');}
    catch{server.kill('SIGKILL');await bounded(exited,5000,'Fixture forced shutdown');}
   }
  }catch(error){failures.push(error);}
  finally{fs.rmSync(state,{recursive:true,force:true});}
  const deliberate503=routes?.records.filter(record=>record.injection==='admission-503').length||0;
  const allowed=consoleErrors.filter(row=>row.location.url.endsWith('/api/snapshots/check')&&/^Failed to load resource: the server responded with a status of 503 \(Service Unavailable\)$/.test(row.text));
  try{
   assert.deepEqual(pageErrors,[],'No page exceptions');
   assert.equal(allowed.length,deliberate503,'Only the deliberately injected admission 503 may log a console error');
   assert.deepEqual(consoleErrors.filter(row=>!allowed.includes(row)),[],'No unexpected console.error');
   assert.deepEqual(routes?.errors||[],[],'No hidden route errors');
  }catch(error){failures.push(error);}
  writeEvidence(name+'-fixture',{server:output,requests,pageErrors,consoleErrors,warnings,routes:routes?.records,routeErrors:routes?.errors.map(error=>error.stack),activeBeforeClose,failures:failures.map(error=>error.stack)});
 }
 if(failures.length===1)throw failures[0];if(failures.length)throw new AggregateError(failures,'Workspace scenario/cleanup failed');
}
async function createAndSolve(page){
 await page.click('#newProject');await page.fill('#wizardName','Synthetisches Team Oktober');
 await page.fill('#wizardStart','2026-10-05');await page.fill('#wizardEnd','2026-10-09');await page.fill('#wizardTimezone','Europe/Vienna');
 await page.click('#wizardNext');await page.fill('#wizardPeople','Testperson A\nTestperson B\nTestperson C');await page.click('#wizardNext');
 for(const id of ['wizardRulesConfirmed','wizardApprovalsConfirmed','wizardContextConfirmed'])await page.check('#'+id);
 await page.click('#wizardCreate');await page.waitForFunction(()=>snapshot&&!document.getElementById('createProjectDialog').open);
 const hours=page.locator('#people tbody tr:first-child input[type=number]');await hours.fill('32');await hours.press('Tab');
 await navigate(page,'demand');const minimum=page.locator('td[data-demand-day="2026-10-05"] input.demand-value');await minimum.fill('2');await minimum.press('Tab');
 await navigate(page,'calculate');await page.fill('#limit','5');await page.click('#solve');
 await page.waitForFunction(()=>!solving&&!jobId&&document.getElementById('result').textContent.includes('Vollständig und geprüft'),null,{timeout:40000});
 assert.equal(await page.locator('#calendar .shift-badge').count(),6);
}
async function stateOf(page){return page.evaluate(()=>({
 wire:ProjectJSON.stringify(currentSnapshot()),id:snapshot.id,revision:snapshot.revision,dirty,jsonDirty,version:changeVersion,
 result:document.getElementById('result').textContent,analysisHidden:document.getElementById('planAnalysis').hidden,
 analysisText:document.getElementById('planAnalysisContent').textContent,active:document.body.dataset.activePanel,
 raw:document.getElementById('json').value,busy:projectSwitchBusy()
}));}
async function save(page){await page.click('#headerSave');await page.waitForFunction(()=>!dirty&&!projectSwitchBusy());return JSON.parse((await stateOf(page)).wire);}
async function readback(page,saved){const response=await page.request.get('/api/snapshots/'+encodeURIComponent(saved.id));assert.equal(response.status(),200);const data=await response.json();assert.deepEqual(data,saved,'Exact backend snapshot and revision preserved');return data;}
async function fixFirst(page){await page.locator('#calendar .shift-badge').first().click();await page.locator('#plan tbody tr:first-child input[type=checkbox]').check();}
async function validationWire(page){return page.evaluate(()=>ProjectJSON.stringify({snapshot,assignments}));}
async function releaseValidation(page,pending){pending.release();await page.waitForFunction(()=>document.getElementById('validate').dataset.busy!=='true');assert(pending.record.finished);}
function unchanged(after,before,keys=['wire','id','revision','dirty','jsonDirty','version','result','analysisHidden','analysisText']){for(const key of keys)assert.deepEqual(after[key],before[key],key+' preserved');}
function assertNoWrites(requests,start){assert.deepEqual(requests.slice(start).filter(row=>['PUT','PATCH','DELETE'].includes(row.method)||row.method==='POST'&&!['/api/validate','/api/snapshots/check','/api/readiness'].includes(row.path)),[],'Race must not write persisted state');}

test('S-UX02A-01 late validation cannot bless a newer plan edit',async()=>withWorkspace('validation-edit',async(page,{routes,requests})=>{
 await createAndSolve(page);const persisted=await save(page),before=await stateOf(page),expected=await validationWire(page),start=requests.length;
 const pending=await routes.hold('**/api/validate');await page.click('#validate');await pending.wait();
 assert.equal(pending.record.status,200);assert.equal(pending.record.payload,expected,'Exact original validation wire');
 await fixFirst(page);const later=await stateOf(page);assert(later.dirty);assert(later.version>before.version);assert.match(later.result,/nicht aktuell/);assert(later.analysisHidden);assert.equal(later.analysisText,'');
 await releaseValidation(page,pending);const after=await stateOf(page);unchanged(after,later);
 assert.deepEqual(JSON.parse(pending.record.payload).assignments,persisted.assignments);
 const backend=await readback(page,persisted);assertNoWrites(requests,start);
 writeEvidence('validation-edit',{before,later,after,sent:pending.record,backend});
}));

test('S-UX02A-01 late validation cannot bless another opened project',async()=>withWorkspace('validation-switch',async(page,{routes,requests})=>{
 await createAndSolve(page);const persisted=await save(page);
 const demoResponse=await page.request.get('/api/demo');assert(demoResponse.ok());const demo=await demoResponse.json();demo.id='race-empty-project';demo.revision='0';demo.assignments=[];
 const response=await page.request.put('/api/snapshots',{data:demo});assert(response.ok());const empty=await response.json();await readback(page,empty);
 await page.reload();await page.locator(`.project-card[data-project-id="${persisted.id}"]`).press('Enter');await page.waitForFunction(id=>snapshot?.id===id&&!projectSwitchBusy(),persisted.id);
 const before=await stateOf(page),expected=await validationWire(page),start=requests.length;
 const pending=await routes.hold('**/api/validate');await page.click('#validate');await pending.wait();assert.equal(pending.record.payload,expected);assert.equal(pending.record.status,200);
 await navigate(page,'projects');await page.locator(`.project-card[data-project-id="${empty.id}"]`).press('Enter');await page.waitForFunction(id=>snapshot?.id===id&&!projectSwitchBusy(),empty.id);
 const switched=await stateOf(page);assert.equal(switched.active,'team');assert.equal(switched.dirty,false);assert.equal(switched.jsonDirty,false);assert(switched.analysisHidden);assert.match(switched.result,/noch nicht geprüft/);assert(switched.version>before.version);
 assert.deepEqual(JSON.parse(switched.wire),empty);
 await releaseValidation(page,pending);const after=await stateOf(page);unchanged(after,switched);assert.equal(after.active,'team');
 assert.equal(JSON.parse(pending.record.payload).snapshot.id,persisted.id);
 const backend=[await readback(page,persisted),await readback(page,empty)];assertNoWrites(requests,start);
 writeEvidence('validation-switch',{before,switched,after,sent:pending.record,backend});
}));

test('S-UX02A-01 second-stage admission 503 retains the incumbent draft',async()=>withWorkspace('admission-503',async(page,{routes,requests})=>{
 await createAndSolve(page);const persisted=await save(page);await fixFirst(page);const local=await stateOf(page);
 await navigate(page,'projects');page.on('dialog',dialog=>dialog.accept());const start=requests.length;
 await routes.failAdmission();await page.locator(`.project-card[data-project-id="${persisted.id}"]`).click();
 await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('Synthetic admission failure S-UX02A-01')&&!projectSwitchBusy());
 const rejected=await stateOf(page);unchanged(rejected,local);assert(rejected.dirty);assert.equal(rejected.busy,false);
 const injection=routes.records.find(record=>record.injection==='admission-503');assert.equal(injection.payload,JSON.stringify(persisted),'Exact admission wire from real saved-project GET');assert.deepEqual(JSON.parse(injection.payload),persisted);assert.equal(injection.method,'POST');
 assert(requests.slice(start).some(row=>row.method==='GET'&&row.path==='/api/snapshots/'+persisted.id),'Real first-stage saved-project GET ran');
 assert.equal(await page.locator('#headerSave').isDisabled(),false);assert.equal(await page.locator(`.project-card[data-project-id="${persisted.id}"]`).isDisabled(),false);
 const backend=await readback(page,persisted);assertNoWrites(requests,start);writeEvidence('admission-503',{local,rejected,injection,backend});
}));

test('S-UX02A-01 delayed admission retains late raw text via original oninput',async()=>withWorkspace('admission-late-input',async(page,{routes,requests})=>{
 await createAndSolve(page);const persisted=await save(page);await fixFirst(page);await navigate(page,'projects');
 page.on('dialog',dialog=>dialog.accept());const card=page.locator(`.project-card[data-project-id="${persisted.id}"]`),start=requests.length;
 const pending=await routes.hold('**/api/snapshots/check');await card.click();await pending.wait();assert.equal(pending.record.status,200);assert.equal(pending.record.payload,JSON.stringify(persisted),'Exact delayed admission wire');assert.deepEqual(JSON.parse(pending.record.payload),persisted);assert.deepEqual(JSON.parse(pending.record.response),persisted,'Real admission response equals persisted snapshot');
 // Request arrival precedes the workspace animation-frame lock publication.
 await page.waitForFunction(id=>document.getElementById('headerSave').disabled&&document.getElementById('newProject').disabled&&document.querySelector(`.project-card[data-project-id="${id}"]`).disabled,persisted.id);
 const before=await stateOf(page);assert(before.busy);const text='{"synthetic_late_text":true}';
 await page.evaluate(text=>{const editor=document.getElementById('json');if(typeof editor.oninput!=='function')throw Error('Original oninput missing');editor.value=text;editor.oninput();},text);
 const during=await stateOf(page);unchanged(during,before);assert.equal(during.raw,text,'Actual original handler leaves unadmitted late text intact');
 pending.release();await page.waitForFunction(()=>!projectSwitchBusy()&&document.getElementById('notice').textContent.includes('während des Ladens geändert'));
 const retained=await stateOf(page);unchanged(retained,before);assert.equal(retained.dirty,true);assert.equal(retained.raw,text);assert(pending.record.finished);
 assert.equal(await page.locator('#headerSave').isDisabled(),false);assert.equal(await page.locator('#newProject').isDisabled(),false);assert.equal(await card.isDisabled(),false);
 const backend=await readback(page,persisted);assertNoWrites(requests,start);writeEvidence('admission-late-input',{before,during,retained,sent:pending.record,backend,originalOninput:true});
}));

// Harness controls: two real responses overlap; finally must release both even
// when the scenario assertion fails. These are not claimed as product REDs.
for(const fail of [false,true])test(`S-UX02A-01 owned route drain on ${fail?'assertion failure':'success'}`,async()=>{
 const marker=new Error('Synthetic scenario assertion for teardown');let controller,held;
 const execution=withWorkspace('route-drain-'+(fail?'failure':'success'),async(page,{routes})=>{
  controller=routes;held=await Promise.all([routes.hold('**/api/demo?drain=one'),routes.hold('**/api/demo?drain=two')]);
  await page.evaluate(()=>{window.raceDrainRequests=Promise.all(['one','two'].map(id=>fetch('/api/demo?drain='+id).then(r=>r.json())));});
  await Promise.all(held.map(gate=>gate.wait()));assert.equal(held.filter(gate=>!gate.record.finished).length,2);assert(routes.active>=2);
  if(fail)throw marker;
 });
 if(fail)await assert.rejects(execution,error=>error===marker);else await execution;
 assert.equal(controller.active,0);assert.deepEqual(controller.errors,[]);assert(held.every(gate=>gate.record.finished));
});
