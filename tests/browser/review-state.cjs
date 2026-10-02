'use strict';
// Real Chromium + real backend; only request/response scheduling is controlled.
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawn}=require('node:child_process');
const {chromium}=require('playwright');
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function bounded(promise,ms,label){
 let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error(label+' timed out')),ms);})]);}
 finally{clearTimeout(timer);}
}
async function withPage(run){
 const state=fs.mkdtempSync(path.join(os.tmpdir(),'review-state-'));
 // Let the child's listener allocate its own port atomically; no shared default
 // and no close/rebind race when two fixture processes start concurrently.
 const server=spawn(process.env.WEB_TEST_PYTHON||'python',['tests/browser/server.py'],{cwd:path.resolve(__dirname,'../..'),env:{...process.env,WEB_TEST_STATE:state,WEB_TEST_PORT:'0'},stdio:['ignore','pipe','pipe']});
 let output='',browser,spawnError;const releases=[];
 const exited=new Promise(resolve=>{server.once('exit',resolve);server.once('error',error=>{spawnError=error;resolve();});});
 for(const stream of [server.stdout,server.stderr])stream.on('data',data=>output=(output+data).slice(-16000));
 try{
  const base=await bounded((async()=>{
   for(;;){
    if(spawnError)throw spawnError;
    if(server.exitCode!==null||server.signalCode!==null)throw Error('Fixture exited: '+output);
    const address=output.match(/Uvicorn running on (http:\/\/127\.0\.0\.1:\d+)/)?.[1];
    if(address){try{if((await fetch(address+'/healthz',{signal:AbortSignal.timeout(1000)})).ok)return address;}catch{}}
    await pause(100);
   }
  })(),15000,'Fixture startup');
  browser=await chromium.launch({headless:true,args:['--no-sandbox'],timeout:15000,...(process.env.WEB_TEST_CHROMIUM?{executablePath:process.env.WEB_TEST_CHROMIUM}:{})});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(15000);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  // Exact historical scripts can be replayed without modifying the worktree.
  if(process.env.REVIEW_APP_SOURCE)await page.route('**/static/app.js',route=>route.fulfill({path:process.env.REVIEW_APP_SOURCE,contentType:'application/javascript'}));
  if(process.env.REVIEW_WORKSPACE_SOURCE)await page.route('**/static/workspace.js',route=>route.fulfill({path:process.env.REVIEW_WORKSPACE_SOURCE,contentType:'application/javascript'}));
  await page.goto(base);await page.waitForFunction(()=>window.PlannerApp);
  const gate=(ms=15000)=>{
   let release,notify;const seen=new Promise(r=>notify=r),wait=new Promise(r=>release=r);releases.push(release);
   // Start a deadline only when the gate is awaited: an unused side must not
   // reject out of band and bypass the fixture's cleanup.
   return {get seen(){return bounded(seen,ms,'Gate arrival');},get wait(){return bounded(wait,ms,'Gate release');},release,notify};
  };
  await bounded(run(page,gate,{base,state,pid:server.pid}),30000,'Browser scenario');assert.deepEqual(errors,[]);
 }finally{
  releases.forEach(release=>release());
  try{if(browser)await bounded(browser.close(),5000,'Browser shutdown');}
  finally{
   try{
    if(server.pid&&server.exitCode===null&&server.signalCode===null){
     server.kill('SIGTERM');
     try{await bounded(exited,5000,'Fixture shutdown');}
     catch{server.kill('SIGKILL');await bounded(exited,5000,'Fixture forced shutdown');}
    }
   }finally{fs.rmSync(state,{recursive:true,force:true});}
  }
 }
}
test('HARNESS fixture uses a kernel-allocated port, not the shared default',async()=>withPage(async page=>{
 assert.notEqual(new URL(page.url()).port,'8765');
}));
for(const side of ['seen','wait'])test(`HARNESS gate ${side} has a bounded wait`,async()=>withPage(async(page,gate)=>{
 const delayed=gate(30),result=await Promise.race([delayed[side].then(()=> 'unexpected completion',error=>error.message),pause(150).then(()=> 'unbounded wait')]);
 assert.match(result,/Gate .* timed out/);
}));
test('HARNESS concurrent fixtures have distinct listeners and stores',async()=>{
 const fixtures=[];let release;const bothReady=new Promise(resolve=>release=resolve);
 await Promise.all([0,1].map(i=>withPage(async(page,gate,fixture)=>{
  fixtures.push(fixture);if(fixtures.length===2)release();await bounded(bothReady,10000,'Concurrent startup');
  const storedName=await page.evaluate(async i=>{
   const s=await api('/api/demo');s.id='concurrent-fixture';s.employees[0].name='Fixture '+i;
   await api('/api/snapshots','PUT',s);return (await api('/api/snapshots/'+s.id)).employees[0].name;
  },i);
  assert.equal(storedName,'Fixture '+i);
 })));
 assert.equal(new Set(fixtures.map(f=>f.base)).size,2);assert.equal(new Set(fixtures.map(f=>f.state)).size,2);
 for(const fixture of fixtures)assert.equal(fs.existsSync(fixture.state),false);
});
test('HARNESS a gate timeout closes browser, reaps server and removes state',async()=>{
 let fixture;
 await assert.rejects(withPage(async(page,gate,info)=>{fixture=info;await gate(30).seen;}),/Gate arrival timed out/);
 assert(fixture);assert.equal(fs.existsSync(fixture.state),false);assert.throws(()=>process.kill(fixture.pid,0),{code:'ESRCH'});
});
test('HARNESS honors WEB_TEST_CHROMIUM and cleans up failed launches',async()=>{
 const previous=process.env.WEB_TEST_CHROMIUM;process.env.WEB_TEST_CHROMIUM=path.join(os.tmpdir(),'missing-review-browser');
 try{await assert.rejects(withPage(async()=>{}),/executable.*(exist|missing)|ENOENT/i);}
 finally{if(previous===undefined)delete process.env.WEB_TEST_CHROMIUM;else process.env.WEB_TEST_CHROMIUM=previous;}
});
test('UI-001 real save locks decisions and never acknowledges later edits',async()=>withPage(async(page,gate)=>{
 await page.evaluate(async()=>load(await api('/api/demo')));
 await require('./navigation.cjs')(page,'calculate');
 const cap=page.locator('#openDecisions').getByRole('button',{name:'Grenze bei 150 % des Solls setzen',exact:true});await cap.waitFor({state:'visible'});
 let captured;const delayed=gate();
 await page.route('**/api/snapshots',async route=>{if(route.request().method()!=='PUT')return route.continue();captured=route.request().postDataJSON();delayed.notify();await delayed.wait;await route.continue();});
 await page.click('#headerSave');await delayed.seen;
 assert(await cap.evaluate(b=>b.disabled||!!b.closest('[inert]')),'decision is locked during PUT');
 await cap.evaluate(b=>b.onclick()); // Prove central handler guard, not just CSS.
 assert(await page.evaluate(()=>snapshot.employees.every(e=>e.max_period_minutes==null)));
 // A future editor which misses the lock still cannot be falsely acknowledged.
 await page.evaluate(()=>{snapshot.employees[0].max_period_minutes=900;invalidateResult();});
 delayed.release();await page.waitForFunction(()=>document.querySelector('#save').dataset.busy!=='true');
 const after=await page.evaluate(async()=>({dirty,status:document.querySelector('#saveStatus').textContent,live:snapshot.employees[0].max_period_minutes,stored:(await api('/api/snapshots/'+encodeURIComponent(snapshot.id))).employees[0].max_period_minutes}));
 assert.equal(captured.employees[0].max_period_minutes,null);assert.equal(after.live,900);assert.equal(after.stored,null);assert.equal(after.dirty,true);assert.match(after.status,/Ungespeicherte/);
 await page.unroute('**/api/snapshots');await page.click('#headerSave');await page.waitForFunction(()=>!dirty&&document.querySelector('#save').dataset.busy!=='true');
 const stored=await page.evaluate(async()=>(await api('/api/snapshots/'+encodeURIComponent(snapshot.id))).employees[0].max_period_minutes);assert.equal(stored,900);
}));
for(const first of ['file','save'])test(`UI-001 real overlapping CSV read/save: ${first} first`,{timeout:45000},async()=>withPage(async(page,gate)=>{
 await page.evaluate(async()=>load(await api('/api/demo'),true));
 const csv=await page.evaluate(()=>TeamTransfer.toCsv(currentSnapshot()));
 await page.evaluate(()=>{
  const text=File.prototype.text;
  window.fileReadGate=new Promise(resolve=>window.releaseFileRead=resolve);
  File.prototype.text=async function(...args){if(this.name==='overlap-team.csv'){window.fileReadStarted=true;await window.fileReadGate;}return text.apply(this,args);};
 });
 await page.locator('#teamImport').setInputFiles({name:'overlap-team.csv',mimeType:'text/csv',buffer:Buffer.from(csv)});
 await page.waitForFunction(()=>window.fileReadStarted);
 const put=gate();let sent;
 await page.route('**/api/snapshots',async route=>{if(route.request().method()!=='PUT')return route.continue();sent=route.request().postDataJSON();put.notify();await put.wait;await route.continue();});
 await page.click('#headerSave');await put.seen;
 if(first==='file'){await page.evaluate(()=>window.releaseFileRead());await page.waitForFunction(()=>document.querySelector('#teamImport').dataset.busy!=='true');}
 else{put.release();await page.waitForFunction(()=>document.querySelector('#save').dataset.busy!=='true');}
 assert(await page.locator('#teamImport').isDisabled(),'the outstanding operation retains its lock');
 if(first==='file'){put.release();await page.waitForFunction(()=>document.querySelector('#save').dataset.busy!=='true');}
 else{await page.evaluate(()=>window.releaseFileRead());await page.waitForFunction(()=>document.querySelector('#teamImport').dataset.busy!=='true');}
 const result=await page.evaluate(async()=>({busy:projectSwitchBusy(),dirty,revision:snapshot.revision,stored:await api('/api/snapshots/'+encodeURIComponent(snapshot.id))}));
 assert.equal(result.busy,false);assert.equal(result.dirty,false);assert.equal(result.stored.revision,result.revision);assert.deepEqual(result.stored.employees,sent.employees);
 assert.equal(await page.locator('#teamImport').isDisabled(),false,'CSV chooser is usable after both completions');
 assert.equal(await page.locator('#save').isDisabled(),false);
 // A real second selection is accepted; the prior busy state is not sticky.
 await page.locator('#teamImport').setInputFiles({name:'after-overlap.csv',mimeType:'text/csv',buffer:Buffer.from(csv)});
 await page.waitForFunction(()=>document.querySelector('#teamImport').dataset.busy!=='true'&&teamTransferReport!==null);
}));
test('UI-003 real specific workplace keeps wildcard mentoring validation',async()=>withPage(async page=>{
 const before=await page.evaluate(async()=>{
  const s=await api('/api/demo');s.employees[0].approvals=[{function_id:'f0',workplace_id:'*',valid_from:s.context_start,valid_until:s.context_end,supervised:true}];
  s.employees.forEach(e=>e.mentor_capacity=0);load(await api('/api/snapshots/check','POST',s),true);
  return {approvals:structuredClone(snapshot.employees[0].approvals),report:await api('/api/validate','POST',{snapshot:currentSnapshot(),assignments})};
 });
 assert(before.report.diagnostics.some(d=>d.code==='mentoring'),'positive control: wildcard requires a mentor');
 await page.locator('.matrix-cell[data-employee-id="e000"][data-function-id="f0"][data-workplace-id="w0"]').click();
 const after=await page.evaluate(async()=>({approvals:snapshot.employees[0].approvals,report:await api('/api/validate','POST',{snapshot:currentSnapshot(),assignments})}));
 assert(after.report.diagnostics.some(d=>d.code==='mentoring'),'specific grant must not remove the real mentoring violation');
 assert.equal(after.report.valid,false);assert.deepEqual(after.approvals[0],before.approvals[0]);
 assert.equal(after.approvals.find(a=>a.function_id==='f0'&&a.workplace_id==='w0')?.supervised,true);
 // Independent-work is an explicit edit, never an effect of expansion.
 const independent=await page.evaluate(async()=>{const s=currentSnapshot();s.employees=structuredClone(s.employees);s.employees[0].approvals.find(a=>a.workplace_id==='w0').supervised=false;return api('/api/validate','POST',{snapshot:s,assignments});});
 assert.equal(independent.diagnostics.some(d=>d.code==='mentoring'),false,'negative control exercises the actual validator predicate');
}));
for(const route of ['matrix','history'])test(`UI-003 real ungrouped ${route} retains family mentoring validation`,async()=>withPage(async page=>{
 const before=await page.evaluate(async()=>{
  const s=await api('/api/demo');s.metadata.service_matrix_version=1;
  s.positions[0].name='Review duty 06-14';s.positions[1].name='Review duty 14-22';
  s.employees[0].approvals=[{function_id:'f0',workplace_id:'*',valid_from:s.context_start,valid_until:s.context_end,supervised:true}];s.employees.forEach(e=>e.mentor_capacity=0);
  s.metadata.history_matrix=[{employee_id:'e000',suggested_approvals:[{function_id:'f1',workplace_id:'*'}]}];
  const demand=s.demands.find(d=>s.positions.find(p=>p.id===d.position_id)?.function_id==='f1');
  s.assignments=[{employee_id:'e000',demand_id:demand.id,fixed:false,segments:[]}];
  load(await api('/api/snapshots/check','POST',s),true);
  return {approvals:structuredClone(snapshot.employees[0].approvals),report:await api('/api/validate','POST',{snapshot:currentSnapshot(),assignments})};
 });
 assert(before.report.diagnostics.some(d=>d.code==='approval'),'new member initially has no approval');
 await page.uncheck('#groupFamilies');
 if(route==='matrix')await page.locator('.matrix-cell[data-employee-id="e000"][data-function-id="f1"]').click();else await page.click('#confirmHistory');
 const after=await page.evaluate(async()=>({grouped:familienModus,approvals:snapshot.employees[0].approvals,report:await api('/api/validate','POST',{snapshot:currentSnapshot(),assignments})}));
 assert.equal(after.grouped,false);assert.equal(after.report.diagnostics.some(d=>d.code==='approval'),false,'the intended grant was made');
 assert(after.report.diagnostics.some(d=>d.code==='mentoring'),'ungrouping cannot authorize work without a mentor');assert.equal(after.report.valid,false);
 assert.deepEqual(after.approvals[0],before.approvals[0]);assert.equal(after.approvals.length,2);assert.equal(after.approvals[1].supervised,true);
 const independent=await page.evaluate(async()=>{const s=currentSnapshot();s.employees=structuredClone(s.employees);s.employees[0].approvals.find(a=>a.function_id==='f1').supervised=false;return api('/api/validate','POST',{snapshot:s,assignments});});
 assert.equal(independent.diagnostics.some(d=>d.code==='mentoring'),false,'explicit independent grant is the negative control');
}));
// Minimal complete plan: changing only the new grant's supervision must be
// enough to switch the real validator and CSV export between reject and accept.
async function familyScopeProject(page,{workplace='w1',siblingWorkplace='*'}={}){
 const response=await page.request.get(new URL('/api/demo',page.url()).href);assert(response.ok());const s=await response.json();
 s.id='review-family-scope';s.revision='0';s.metadata.service_matrix_version=1;
 s.employees=s.employees.slice(0,1);s.employees[0].mentor_capacity=0;s.wishes=[];s.restrictions=[];
 s.positions=s.positions.slice(0,2);s.positions[0].name='Review duty 06-14';s.positions[1].name='Review duty 14-22';
 const demand=s.demands.find(d=>d.position_id===s.positions[1].id);s.demands=[demand];s.shifts=s.shifts.filter(shift=>shift.id===demand.shift_id);
 s.assignments=[{employee_id:s.employees[0].id,demand_id:demand.id,fixed:false,segments:[]}];
 s.employees[0].approvals=[{function_id:'f0',workplace_id:siblingWorkplace,valid_from:s.context_start,valid_until:s.context_end,supervised:true}];
 s.metadata.history_matrix=[{employee_id:s.employees[0].id,observed_assignment_count:3,suggested_approvals:[{function_id:'f1',workplace_id:workplace,evidence_count:3}]}];
 return s;
}
async function importFamilyProject(page,s,grouped){
 const checking=page.waitForResponse(r=>r.url().endsWith('/api/snapshots/check')&&r.request().method()==='POST');
 await page.locator('#file').setInputFiles({name:'family-scope.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(s))});
 const checked=await checking;assert.equal(checked.status(),200,'the actual file-import schema accepts the fixture');
 await page.waitForFunction(()=>snapshot?.metadata.history_matrix?.length===1&&!projectSwitchBusy());
 await page.locator('.main-nav [data-navigate="team"]').click();await page.locator('#groupFamilies').setChecked(grouped);
 assert.equal(await page.evaluate(()=>familienModus),grouped);
 return checked.json();
}
async function validateAndExport(page,s){
 const data={snapshot:s,assignments:s.assignments};
 const validation=await page.request.post(new URL('/api/validate',page.url()).href,{data});assert.equal(validation.status(),200);
 const csv=await page.request.post(new URL('/api/export/csv',page.url()).href,{data});
 return {report:await validation.json(),csv:{status:csv.status(),body:await csv.text()}};
}
async function saveFamilyProject(page){
 const saving=page.waitForResponse(r=>r.url().endsWith('/api/snapshots')&&r.request().method()==='PUT');await page.click('#headerSave');
 const response=await saving;assert.equal(response.status(),200);const sent=response.request().postDataJSON();
 await page.waitForFunction(()=>!dirty&&!projectSwitchBusy());
 const live=await page.evaluate(()=>currentSnapshot());
 const storedResponse=await page.request.get(new URL('/api/snapshots/'+encodeURIComponent(live.id),page.url()).href);assert.equal(storedResponse.status(),200);
 const stored=await storedResponse.json();assert.equal(stored.revision,live.revision);assert.equal(stored.revision,'1');
 assert.deepEqual(stored.employees,sent.employees);assert.deepEqual(stored.assignments,sent.assignments);assert.deepEqual(stored,live);
 return stored;
}
for(const grouped of [true,false])test(`UI-R2-003 real concrete history persists family supervision: grouped=${grouped}`,async()=>withPage(async page=>{
 const input=await familyScopeProject(page),checked=await importFamilyProject(page,input,grouped);
 const before=await validateAndExport(page,checked);assert(before.report.diagnostics.some(d=>d.code==='approval'));assert.equal(before.csv.status,422);
 await page.click('#confirmHistory');const stored=await saveFamilyProject(page),after=await validateAndExport(page,stored);
 const independent=structuredClone(stored);independent.employees[0].approvals.find(a=>a.function_id==='f1').supervised=false;
 const negative=await validateAndExport(page,independent);
 assert.equal(negative.report.valid,true);assert.equal(negative.report.complete,true);assert.equal(negative.csv.status,200,'explicit independent-work control must export this complete plan');
 // Retain outcomes even on RED: persistence, validator and export have already run.
 console.log(JSON.stringify({case:'concrete-history',grouped,input:checked,stored,before,after,negative}));
 assert.equal(stored.employees[0].approvals.find(a=>a.function_id==='f1')?.supervised,true,'persisted concrete grant inherits its supervised service family');
 assert.deepEqual(stored.employees[0].approvals[0],checked.employees[0].approvals[0]);
 const expected=grouped?[['f0','w1'],['f1','w1']]:[['f1','w1']];
 assert.deepEqual(stored.employees[0].approvals.slice(1).map(a=>[a.function_id,a.workplace_id]),expected,'grouping expands functions, never the proposal workplace');
 assert.equal(after.report.valid,false);assert.equal(after.report.complete,false);assert.deepEqual(after.report.diagnostics.map(d=>d.code),['mentoring']);assert.equal(after.csv.status,422);
 await page.locator('.main-nav [data-navigate="plan"]').click();
 const validating=page.waitForResponse(r=>r.url().endsWith('/api/validate')&&r.request().method()==='POST');await page.click('#validate');assert.equal((await validating).status(),200);
 await page.locator('#validationSummary').waitFor();assert.match(await page.locator('#validationSummary').textContent(),/Regelverletzungen müssen korrigiert/);
 const exporting=page.waitForResponse(r=>r.url().endsWith('/api/export/csv')&&r.request().method()==='POST');await page.locator('[data-export="csv"]').click();assert.equal((await exporting).status(),422);
}));

async function applyFamilyGrant(page,route,grouped){
 if(route==='history')await page.click('#confirmHistory');
 else if(route==='matrix')await page.locator(grouped?'.matrix-cell[data-family="Review duty"]':'.matrix-cell[data-function-id="f1"]').click();
 else{
  await page.locator('#history').evaluate(box=>{for(let p=box.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;});
  await page.locator('#history details summary').click();
  await page.locator('#history').getByRole('button',{name:'Für Planungszeitraum ausdrücklich freigeben',exact:true}).click();
 }
}
function assertScopeValidation(result,supervised){
 assert.equal(result.report.valid,!supervised);assert.equal(result.report.complete,!supervised);
 assert.deepEqual(result.report.diagnostics.map(d=>d.code),supervised?['mentoring']:[]);
 assert.equal(result.csv.status,supervised?422:200);
}
for(const route of ['history','single-history','matrix'])for(const grouped of [true,false])for(const workplace of route==='history'?['*','w1']:['*'])for(const siblingWorkplace of ['*','w1','w2'])test(`UI-R2-003 real scope cross-product ${route} grouped=${grouped} grant=${workplace} sibling=${siblingWorkplace}`,async()=>withPage(async page=>{
 const input=await familyScopeProject(page,{workplace,siblingWorkplace}),checked=await importFamilyProject(page,input,grouped);
 const before=await validateAndExport(page,checked);assert.deepEqual(before.report.diagnostics.map(d=>d.code),['approval']);assert.equal(before.csv.status,422);
 await applyFamilyGrant(page,route,grouped);const stored=await saveFamilyProject(page);
 const expectedSupervision=workplace==='*'||siblingWorkplace==='*'||workplace===siblingWorkplace;
 const functions=grouped&&route!=='single-history'?['f0','f1']:['f1'];
 const expectedNew=functions.filter(id=>!checked.employees[0].approvals.some(a=>a.function_id===id&&a.workplace_id===workplace))
  .map(function_id=>({function_id,workplace_id:workplace,valid_from:stored.period_start,valid_until:stored.period_end,supervised:expectedSupervision}));
 assert.deepEqual(stored.employees[0].approvals,[...checked.employees[0].approvals,...expectedNew]);
 const actual=await validateAndExport(page,stored);assertScopeValidation(actual,expectedSupervision);
 const opposite=structuredClone(stored);opposite.employees[0].approvals.find(a=>a.function_id==='f1').supervised=!expectedSupervision;
 assertScopeValidation(await validateAndExport(page,opposite),!expectedSupervision);
 console.log(JSON.stringify({case:'scope-cross-product',route,grouped,workplace,siblingWorkplace,approvals:stored.employees[0].approvals,report:actual.report,exportStatus:actual.csv.status}));
}));
for(const grouped of [true,false])for(const workplace of ['*','w1'])for(const control of ['past','future','unrelated-family','existing-independent'])test(`UI-R2-003 real history control ${control} grouped=${grouped} grant=${workplace}`,async()=>withPage(async page=>{
 const input=await familyScopeProject(page,{workplace}),sibling=input.employees[0].approvals[0];
 if(control==='past')sibling.valid_until='2026-01-04';
 if(control==='future')sibling.valid_from='2026-01-19';
 if(control==='unrelated-family')input.positions[0].name='Unrelated activity';
 if(control==='existing-independent')input.employees[0].approvals.push({function_id:'f1',workplace_id:workplace,valid_from:input.period_start,valid_until:input.period_end,supervised:false});
 const checked=await importFamilyProject(page,input,grouped);
 if(await page.locator('#confirmHistory').isVisible())await page.click('#confirmHistory');
 const stored=await saveFamilyProject(page),approvals=stored.employees[0].approvals;
 assert.deepEqual(approvals.slice(0,checked.employees[0].approvals.length),checked.employees[0].approvals,'unrelated, old and explicitly independent approvals stay unchanged');
 assert.equal(approvals.find(a=>a.function_id==='f1').supervised,false);
 assert(approvals.slice(checked.employees[0].approvals.length).every(a=>a.workplace_id===workplace));
 assertScopeValidation(await validateAndExport(page,stored),false);
 const opposite=structuredClone(stored);opposite.employees[0].approvals.find(a=>a.function_id==='f1').supervised=true;
 assertScopeValidation(await validateAndExport(page,opposite),true);
}));
for(const grouped of [true,false])for(const workplace of ['*','w1'])test(`UI-R2-003 real manual independent grant stays explicit grouped=${grouped} scope=${workplace}`,async()=>withPage(async page=>{
 const input=await familyScopeProject(page,{workplace});await importFamilyProject(page,input,grouped);
 await page.locator('#matrix tbody th').getByRole('button',{name:input.employees[0].name,exact:true}).click();
 await page.locator('#details').getByRole('button',{name:'Freigabe hinzufügen',exact:true}).click();
 await page.locator('#details').getByLabel(/^Dienst \/ Arbeitsplatz/).last().selectOption(workplace==='*'?'f1':'p1');
 const supervised=page.locator('#details').getByLabel('Betreuung erforderlich',{exact:true}).last();
 assert.equal(await supervised.isChecked(),false,'manual editor explicitly exposes independent-work choice');await supervised.check();
 await page.locator('#details').getByRole('button',{name:'Details schließen',exact:true}).click();
 const stored=await saveFamilyProject(page);assertScopeValidation(await validateAndExport(page,stored),true);
 // Remove supervision through the actual editor, not a synthetic validator stub.
 await page.locator('#matrix tbody th').getByRole('button',{name:input.employees[0].name,exact:true}).click();
 await page.locator('#details').getByLabel('Betreuung erforderlich',{exact:true}).last().uncheck();
 await page.locator('#details').getByRole('button',{name:'Details schließen',exact:true}).click();
 const saving=page.waitForResponse(r=>r.url().endsWith('/api/snapshots')&&r.request().method()==='PUT');await page.click('#headerSave');assert.equal((await saving).status(),200);await page.waitForFunction(()=>!dirty&&!projectSwitchBusy());
 const readback=await page.request.get(new URL('/api/snapshots/'+encodeURIComponent(stored.id),page.url()).href);assert.equal(readback.status(),200);const independent=await readback.json();assert.equal(independent.revision,'2');
 assert.deepEqual(independent.employees[0].approvals,[stored.employees[0].approvals[0],{...stored.employees[0].approvals[1],supervised:false}]);assertScopeValidation(await validateAndExport(page,independent),false);
}));

for(const grouped of [true,false])test(`UI-R2-003 real matrix removal keeps unrelated scopes and outside-period slices grouped=${grouped}`,async()=>withPage(async page=>{
 const input=await familyScopeProject(page),base=input.employees[0].approvals[0];
 input.positions.push({...input.positions[0],id:'other',function_id:'other',name:'Unrelated activity'});
 input.employees[0].approvals.push({...base,workplace_id:'w2'},{...base,function_id:'f1'},{...base,function_id:'f1',workplace_id:'w1'},{...base,function_id:'other'});
 const checked=await importFamilyProject(page,input,grouped);
 const beforeToggle=await page.evaluate(()=>({snapshot:currentSnapshot(),dirty,assignments}));
 await page.locator('#groupFamilies').setChecked(!grouped);await page.locator('#groupFamilies').setChecked(grouped);
 assert.deepEqual(await page.evaluate(()=>({snapshot:currentSnapshot(),dirty,assignments})),beforeToggle,'display changes do not edit authorizations');
 await applyFamilyGrant(page,'matrix',grouped);const stored=await saveFamilyProject(page);
 const expected=checked.employees[0].approvals.flatMap(a=>a.function_id==='f1'||(grouped&&a.function_id==='f0')
  ?[{...a,valid_until:'2026-01-04'},{...a,valid_from:'2026-01-19'}]:[a]);
 assert.deepEqual(stored.employees[0].approvals,expected);
 const invalid=await validateAndExport(page,stored);assert.equal(invalid.report.valid,false);assert.deepEqual(invalid.report.diagnostics.map(d=>d.code),['approval']);assert.equal(invalid.csv.status,422);
}));

for(const sample of ['empty','partial'])test(`SEC-04 real readiness and validation disclose ${sample} bounded diagnostics`,async()=>withPage(async page=>{
 await page.evaluate(async sample=>{
  const s=await api('/api/demo'),oversized='x'.repeat(49153);
  s.unresolved=sample==='empty'?[oversized,oversized]:['Small first issue',oversized,'Small later issue'];
  load(await api('/api/snapshots/check','POST',s),true);
 },sample);
 const readyResponse=page.waitForResponse(r=>r.url().endsWith('/api/readiness')&&r.request().method()==='POST');
 await require('./navigation.cjs')(page,'calculate');const readiness=await (await readyResponse).json();
 assert.equal(readiness.ready,false);assert(readiness.diagnostics_omitted>0);assert.equal(readiness.diagnostics_total,readiness.diagnostics.length+readiness.diagnostics_omitted);
 if(sample==='empty')assert.equal(readiness.diagnostics.length,0);else assert(readiness.diagnostics.length>0);
 await page.waitForFunction(()=>document.querySelector('#automaticReadinessStatus').dataset.state!=='pending');
 assert.equal(await page.locator('#automaticReadinessStatus').getAttribute('data-state'),'issues','bounded diagnostics are a valid response');
 assert.equal(await page.evaluate(()=>currentReadiness().count),readiness.diagnostics_total);
 assert.match(await page.locator('#automaticReadinessDetails').textContent(),new RegExp(`${readiness.diagnostics.length}.*angezeigt.*${readiness.diagnostics_omitted}.*ausgelassen`));
 await page.evaluate(()=>{navigate('rules');selectConfig('profile');renderSetupReview();});
 await page.locator('#setupReview').getByRole('button',{name:'Planungsbereitschaft prüfen',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#setupReview').textContent.includes('Vor der Berechnung noch bearbeiten:'));
 assert.equal(await page.evaluate(()=>currentReadiness().count),readiness.diagnostics_total);
 assert.match(await page.locator('#setupReview').textContent(),/ausgelassen/);
 await page.locator('.main-nav [data-navigate="plan"]').click();
 const validationResponse=page.waitForResponse(r=>r.url().endsWith('/api/validate')&&r.request().method()==='POST');
 await page.click('#validate');const validation=await (await validationResponse).json();await page.locator('#validationSummary').waitFor();
 assert.equal(validation.valid,false);assert.equal(validation.complete,false);assert(validation.diagnostics_omitted>0);
 const text=await page.locator('#validationSummary').textContent();assert.match(text,/Regelverletzungen müssen korrigiert/);
 assert.doesNotMatch(text,/keine Regelverletzungen oder unbesetzten Stellen/);assert.match(text,new RegExp(`${validation.diagnostics.length}.*angezeigt.*${validation.diagnostics_omitted}.*ausgelassen`));
}));
test('UI-004 real replacement response cannot cross into another project',async()=>withPage(async(page,gate)=>{
 await page.evaluate(async()=>{load(await api('/api/demo'));navigate('plan');renderPlan();document.querySelector('#replacementPanel').open=true;});
 const delayed=gate();let report;
 await page.route('**/api/replacement',async route=>{const response=await route.fetch();assert(response.ok());report=await response.json();delayed.notify();await delayed.wait;await route.fulfill({response});});
 await page.evaluate(()=>{window.reviewSearch=document.querySelector('#findReplacement').onclick();});await delayed.seen;
 assert(report.duties.length>0,'real backend returned concrete replacement duties');
 await page.evaluate(async()=>{const next=await api('/api/demo');next.id=projectId();next.employees.forEach(e=>e.name='New project '+e.name);load(next,true);navigate('plan');renderPlan();document.querySelector('#replacementPanel').open=true;});
 delayed.release();await page.evaluate(()=>window.reviewSearch);
 assert.equal(await page.locator('#replacementResult').textContent(),'','old response must not use the new project’s names');
 await page.unroute('**/api/replacement');await page.click('#findReplacement');await page.locator('#replacementResult table').waitFor();
 assert.match(await page.locator('#replacementResult').textContent(),/Dienste werden frei/);
 const input=page.locator('#replacementForm input[type="date"]').first();await input.fill('2026-01-06');await input.blur();
 assert.equal(await page.locator('#replacementResult').textContent(),'');assert.equal(await page.evaluate(()=>dirty),false,'query edits do not dirty the project');
}));
