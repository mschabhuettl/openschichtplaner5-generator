'use strict';
// UX03C-NATIVE-RAW: unchanged browser app and real synthetic backend.
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawn}=require('node:child_process');
const {chromium}=require('playwright');
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function bounded(promise,ms,label){let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error(label+' timed out')),ms);})]);}finally{clearTimeout(timer);}}
async function fixture(name,run){
 const root=path.resolve(__dirname,'../..'),state=fs.mkdtempSync(path.join(os.tmpdir(),'review-native-number-'));
 const server=spawn(process.env.WEB_TEST_PYTHON||'python',['tests/browser/server.py'],{cwd:root,env:{...process.env,TMPDIR:os.tmpdir(),WEB_TEST_STATE:state,WEB_TEST_PORT:'0'},stdio:['ignore','pipe','pipe']});
 let output='',browser,spawnError;
 const exited=new Promise(resolve=>{server.once('exit',resolve);server.once('error',error=>{spawnError=error;resolve();});});
 for(const stream of [server.stdout,server.stderr])stream.on('data',data=>output+=data);
 const observations={consoleErrors:[],pageErrors:[],cases:[]},artifacts=process.env.WEB_TEST_SCREENSHOT_DIR;
 if(artifacts)fs.mkdirSync(artifacts,{recursive:true});
 try{
  const base=await bounded((async()=>{for(;;){
   if(spawnError)throw spawnError;
   if(server.exitCode!==null||server.signalCode!==null)throw Error('Fixture exited: '+output);
   const address=output.match(/Uvicorn running on (http:\/\/127\.0\.0\.1:\d+)/)?.[1];
   if(address){try{if((await fetch(address+'/healthz',{signal:AbortSignal.timeout(1000)})).ok)return address;}catch{}}
   await pause(100);
  }})(),15000,'Fixture startup');
  browser=await chromium.launch({headless:true,args:['--no-sandbox'],timeout:15000,...(process.env.WEB_TEST_CHROMIUM?{executablePath:process.env.WEB_TEST_CHROMIUM}:{})});
  const page=await browser.newPage({baseURL:base,viewport:{width:1440,height:1000}});page.setDefaultTimeout(7000);
  page.on('pageerror',error=>observations.pageErrors.push(error.message));
  page.on('console',message=>{if(message.type()==='error')observations.consoleErrors.push(message.text());});
  await page.route('**/*',route=>new URL(route.request().url()).origin===base?route.continue():route.abort());
  await page.goto(base);await page.waitForFunction(()=>window.PlannerApp);
  await bounded(run(page,{base,observations,artifacts}),90000,'Native numeric scenario');
  assert.deepEqual(observations.pageErrors,[]);assert.deepEqual(observations.consoleErrors,[]);
 }finally{
  try{if(browser)await bounded(browser.close(),5000,'Browser shutdown');}
  finally{try{if(server.pid&&server.exitCode===null&&server.signalCode===null){server.kill('SIGTERM');try{await bounded(exited,5000,'Fixture shutdown');}catch{server.kill('SIGKILL');await bounded(exited,5000,'Fixture forced shutdown');}}}
   finally{fs.rmSync(state,{recursive:true,force:true});if(artifacts){fs.writeFileSync(path.join(artifacts,name+'.json'),JSON.stringify(observations,null,2)+'\n');fs.writeFileSync(path.join(artifacts,name+'-server.log'),output);}}}
 }
}
async function settle(page){await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));await pause(180);}
async function savedDemo(page){await page.click('#demo');await page.waitForFunction(()=>!!snapshot&&!projectSwitchBusy());await page.click('#headerSave');await page.waitForFunction(()=>!dirty&&!projectSwitchBusy());}
async function persisted(page,id){return {list:await(await page.request.get('/api/snapshots')).json(),detail:await(await page.request.get('/api/snapshots/'+id)).json()};}
async function wireState(page){return page.evaluate(()=>({wire:ProjectJSON.stringify(currentSnapshot()),dirty,jsonDirty,changeVersion}));}
async function holdResponse(page,pattern,method='POST'){
 let release,arrive,finish,failure,payload;
 const held=new Promise(r=>release=r),seen=new Promise(r=>arrive=r),done=new Promise(r=>finish=r);
 const handler=async route=>{if(route.request().method()!==method)return route.fallback();try{payload=route.request().postDataJSON();const response=await route.fetch();arrive();await bounded(held,15000,'Real response held');await route.fulfill({response});}catch(e){failure=e;try{await route.abort();}catch{}}finally{finish();}};
 await page.route(pattern,handler,{times:1});
 return {seen,payload:()=>payload,async drain(){release();await bounded(done,15000,'Owned response drain');if(failure)throw failure;}};
}
test('NATIVE-REVIEW-VALID-REVERT valid edit to original before blur clears the native draft',async()=>fixture('native-valid-revert',async(page,{observations})=>{
 await savedDemo(page);const input=page.locator('#people [data-employee-hours]').first(),original=await input.inputValue(),before=await wireState(page),id=await page.evaluate(()=>snapshot.id),backend=await persisted(page,id);
 await input.focus();await input.fill('9');await input.fill(original);await input.press('Tab');await settle(page);
 observations.after=await page.evaluate(()=>({draft:hasNativeDraft(),draftVersion,dirty,readiness:currentReadiness(),wire:ProjectJSON.stringify(currentSnapshot()),changeVersion}));
 assert.equal(observations.after.wire,before.wire);assert.equal(observations.after.changeVersion,before.changeVersion);assert.equal(observations.after.draft,false,'valid edit/revert must not leave a pending native draft');assert.equal(observations.after.dirty,false,'unchanged persisted data is not dirty');assert.notEqual(observations.after.readiness.state,'draft');assert.deepEqual(await persisted(page,id),backend);
 // A second edit/revert must not erase a previously admitted, unsaved edit.
 await input.fill('12');await input.press('Tab');const changed=await wireState(page);await input.fill('9');await input.fill('12');await input.press('Tab');await settle(page);
 assert.deepEqual(await wireState(page),changed);assert.equal(await page.evaluate(()=>hasNativeDraft()),false);assert.deepEqual(await persisted(page,id),backend);
}));
test('NATIVE-REVIEW-MIRROR-ADMISSION detail edits rebase the retained table field and Save persists visible hours',async()=>fixture('native-mirror-admission',async(page,{observations})=>{
 await savedDemo(page);const baseline=await page.evaluate(()=>currentSnapshot()),table=page.locator('#people [data-employee-hours]').first(),original=await table.inputValue();await table.evaluate(e=>window.mirrorTable=e);
 await page.locator('#people tbody tr:first-child button').click();const detail=page.locator('#details [data-employee-hours]');
 await detail.fill('12');await detail.press('Tab');await settle(page);assert.equal(await table.inputValue(),'12');assert(await table.evaluate(e=>e===window.mirrorTable));
 await table.fill(original);await table.press('Tab');await settle(page);
 assert.deepEqual(await page.evaluate(()=>currentSnapshot()),baseline,'mirror correction must restore the entire baseline, not only the visible field');assert.equal(await detail.inputValue(),original);
 const writes=[];page.on('request',r=>{if(r.method()==='PUT')writes.push(r.postDataJSON());});
 await page.click('#headerSave');await page.waitForFunction(()=>!projectSwitchBusy());assert.deepEqual(writes,[baseline]);const stored=await persisted(page,baseline.id);baseline.revision=stored.detail.revision;
 assert.deepEqual(stored.detail,baseline);assert.equal(await table.inputValue(),original);assert.equal(await page.evaluate(()=>dirty||hasNativeDraft()),false);
 await page.reload();await page.locator(`.project-card[data-project-id="${baseline.id}"]`).click();await page.waitForFunction(id=>snapshot?.id===id&&!projectSwitchBusy(),baseline.id);assert.deepEqual(await page.evaluate(()=>currentSnapshot()),baseline);observations.exactMinutes=stored.detail.employees[0].target_minutes;
}));
test('NATIVE-REVIEW-SAVE-ACK-REVERT queued revert rebases only the acknowledged canonical origin',async()=>fixture('native-ack-revert',async(page,{observations})=>{
 await savedDemo(page);const input=page.locator('#people [data-employee-hours]').first();await input.fill('12');await input.press('Tab');assert.equal(await page.evaluate(()=>dirty),true);
 const before=await page.evaluate(()=>currentSnapshot()),hold=await holdResponse(page,'**/api/snapshots','PUT');
 try{await page.click('#headerSave');await bounded(hold.seen,7000,'Save arrival');await page.waitForFunction(()=>$('people').inert);await input.evaluate(e=>{window.nativeNode=e;e.value='9';e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));});}finally{await hold.drain();}
 await page.waitForFunction(()=>!projectSwitchBusy());const stored=await persisted(page,before.id);before.revision=stored.detail.revision;assert.deepEqual(stored.detail,before);assert.equal(await page.evaluate(()=>dirty&&hasNativeDraft()),true,'acknowledgement cannot clear newer native text');
 await input.fill('12');await input.press('Tab');await settle(page);assert(await input.evaluate(e=>e===window.nativeNode));assert.deepEqual(await page.evaluate(()=>currentSnapshot()),stored.detail);assert.equal(await page.evaluate(()=>hasNativeDraft()),false);assert.equal(await page.evaluate(()=>dirty),false,'acknowledged canonical state with reverted raw draft is clean');assert.deepEqual(await persisted(page,before.id),stored);observations.cleanAfterAcknowledgedRevert=true;
 // The acknowledgement does not make a later admitted edit clean.
 await input.fill('13');await input.press('Tab');const changed=await wireState(page);await input.fill('9');await input.fill('13');await input.press('Tab');await settle(page);assert.deepEqual(await wireState(page),changed);assert.equal(changed.dirty,true);assert.deepEqual(await persisted(page,before.id),stored);
}));
test('NATIVE-MIRROR-RAW-PRESERVATION model synchronization preserves a pending mirrored exponent',async()=>fixture('native-mirror-raw',async(page,{observations})=>{
 await savedDemo(page);const baseline=await page.evaluate(()=>currentSnapshot()),backend=await persisted(page,baseline.id);await page.locator('#people tbody tr:first-child button').click();
 const table=page.locator('#people [data-employee-hours]').first(),detail=page.locator('#details [data-employee-hours]');await table.evaluate(e=>window.mirrorTable=e);
 await table.fill('');await table.pressSequentially('1e');await table.press('Tab');assert(await table.evaluate(e=>e.validity.badInput));
 await detail.fill('12');await detail.press('Tab');await settle(page);assert.equal(await page.evaluate(()=>currentSnapshot().employees[0].target_minutes),720);
 assert(await table.evaluate(e=>e===window.mirrorTable&&e.validity.badInput),'canonical mirror update must not overwrite unadmitted native text');assert.deepEqual(await persisted(page,baseline.id),backend);
 await table.focus();await table.press('Backspace');assert.equal(await table.inputValue(),'1');await table.press('Tab');const expected=structuredClone(baseline);expected.employees[0].target_minutes=60;assert.deepEqual(await page.evaluate(()=>currentSnapshot()),expected);assert.equal(await detail.inputValue(),'1');assert.equal(await page.evaluate(()=>dirty&&!hasNativeDraft()),true);
 await page.click('#headerSave');await page.waitForFunction(()=>!projectSwitchBusy());const stored=await persisted(page,baseline.id);expected.revision=stored.detail.revision;assert.deepEqual(stored.detail,expected);assert.equal(await page.evaluate(()=>dirty),false);observations.nativeBackspace='1';
}));
const numericCases=[
 {key:'Soll',selector:'#people [data-employee-hours]',section:'people',model:['employees','target_minutes'],expected:60},
 {key:'weekly',selector:'#details [data-employee-weekly-hours]',section:'details',model:['employees','contractual_weekly_minutes'],expected:60},
 {key:'cap',selector:'#details [data-employee-cap]',section:'details',model:['employees','max_period_minutes'],expected:60},
 {key:'Min',selector:'#demands input[data-table-column="minimum"]',section:'demand',model:['demands','minimum'],expected:1},
 {key:'Max',selector:'#demands input[data-table-column="maximum"]',section:'demand',model:['demands','maximum'],expected:1}
];
async function expose(page,c){
 if(c.section==='demand'){
  await page.click('.main-nav [data-navigate="setup"]');await page.click('#setupNav [data-navigate="rules"]');await page.click('[data-config-to="bedarf"]');
  if(!(await page.locator('details[data-config="bedarf"]').evaluate(e=>e.open)))await page.locator('details[data-config="bedarf"] > summary').click();
 }else{await page.click('.main-nav [data-navigate="team"]');if(c.section==='details')await page.locator('#people tbody tr:first-child button').click();}
 return page.locator(c.selector).first();
}
async function focused(page,input){await settle(page);const m=await input.evaluate(e=>{const r=e.getBoundingClientRect(),h=document.querySelector('.topbar').getBoundingClientRect(),hit=document.elementFromPoint((r.left+r.right)/2,(r.top+r.bottom)/2);return {focused:e===document.activeElement,left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:innerWidth,height:innerHeight,header:h.bottom,hit:hit===e||e.contains(hit)};});assert(m.focused&&m.hit&&m.left>=0&&m.right<=m.width&&m.top>=Math.max(0,m.header)&&m.bottom<=m.height,'settled numeric focus '+JSON.stringify(m));return m;}
for(const width of [1440,390])for(const action of ['save','solve'])for(const c of numericCases)test(`UX03C-NATIVE-RAW ${c.key} ${action} blocks hidden badInput and correction persists at ${width}`,async()=>fixture(`native-${c.key}-${action}-${width}`,async(page,{observations,artifacts})=>{
 await page.setViewportSize({width,height:1000});await savedDemo(page);
 const baseline=await page.evaluate(()=>currentSnapshot()),before=await wireState(page),backend=await persisted(page,baseline.id),writes=[];
 page.on('request',r=>{if(r.method()==='PUT'||(r.method()==='POST'&&r.url().endsWith('/api/jobs')))writes.push(r.url());});
 const input=await expose(page,c);await input.fill('');await input.pressSequentially('1e');await input.evaluate(e=>window.nativeNode=e);
 await page.click('.main-nav [data-navigate="projects"]');assert.equal((await wireState(page)).wire,before.wire);assert.equal((await wireState(page)).changeVersion,before.changeVersion);
 if(action==='save')await page.click('#headerSave');else{await page.click('.main-nav [data-navigate="plan"]');await page.click('#solve');}
 await page.waitForFunction(()=>!projectSwitchBusy());await settle(page);
 assert(await input.evaluate(e=>e===window.nativeNode&&e.validity.badInput&&e.isConnected),'same native badInput node');
 observations.focus=await focused(page,input);assert.deepEqual(writes,[]);assert.equal((await wireState(page)).wire,before.wire);assert.deepEqual(await persisted(page,baseline.id),backend);
 if(artifacts)await page.screenshot({path:path.join(artifacts,`native-${c.key}-${action}-${width}.png`)});
 await input.press('Backspace');assert.equal(await input.inputValue(),'1','native exponent text actually survives');await input.press('Tab');
 const expected=structuredClone(baseline);expected[c.model[0]][0][c.model[1]]=c.expected;
 assert.deepEqual(await page.evaluate(()=>currentSnapshot()),expected,'correction changes only the intended model field');
 await page.click('#headerSave');await page.waitForFunction(()=>!dirty&&!projectSwitchBusy());const stored=await persisted(page,baseline.id);expected.revision=stored.detail.revision;assert.deepEqual(stored.detail,expected);
 await page.reload();await page.locator(`.project-card[data-project-id="${baseline.id}"]`).click();await page.waitForFunction(id=>snapshot?.id===id&&!projectSwitchBusy(),baseline.id);
 assert.deepEqual(await page.evaluate(()=>currentSnapshot()),stored.detail);const reopened=await expose(page,c);assert.equal(await reopened.inputValue(),'1');
 observations.cases.push({field:c.key,action,width,backspace:'1',exactReopen:true,writes:writes.length});
}));
test('NATIVE-PREVIEW-ISOLATION editing a proposal threshold does not create a project draft',async()=>fixture('native-preview',async(page,{observations})=>{
 await savedDemo(page);const before=await wireState(page),id=await page.evaluate(()=>snapshot.id),backend=await persisted(page,id);
 await page.click('.main-nav [data-navigate="setup"]');await page.click('#setupNav [data-navigate="rules"]');await page.click('[data-config-to="profile"]');
 const input=page.locator('#serviceGroups input[type="number"]');await input.fill('181');await input.press('Tab');await settle(page);
 observations.after=await wireState(page);assert.deepEqual(observations.after,before,'proposal-only controls must not mark canonical project dirty');assert.equal(await page.evaluate(()=>hasNativeDraft()),false);assert.deepEqual(await persisted(page,id),backend);
}));
test('RAW-JSON-ABA edit and explicit revert invalidate an older validation response',async()=>fixture('json-aba',async(page,{observations})=>{
 await savedDemo(page);const before=await wireState(page),id=await page.evaluate(()=>snapshot.id),backend=await persisted(page,id),hold=await holdResponse(page,'**/api/validate');
 try{
  await page.click('.main-nav [data-navigate="plan"]');await page.click('#validate');await bounded(hold.seen,7000,'Validation arrival');
  await page.click('.main-nav [data-navigate="setup"]');await page.click('#setupNav [data-navigate="rules"]');await page.click('[data-config-to="daten"]');
  const input=page.locator('#json'),original=await input.inputValue();await input.fill(original+' ');await input.fill(original);page.once('dialog',d=>d.accept());await page.click('#refreshJson');
  assert.deepEqual(await wireState(page),before,'raw edit/revert leaves canonical state unchanged');
 }finally{await hold.drain();}
 await page.waitForFunction(()=>$('validate').dataset.busy!=='true');await settle(page);
 observations.notice=await page.locator('#notice').innerText();assert.match(observations.notice,/Daten während der Prüfung geändert/,'old result must not certify a different raw edit generation');assert.equal(await page.locator('#validationSummary').count(),0);assert.deepEqual(await persisted(page,id),backend);
}));
test('NATIVE-REPLACEMENT-GENERATION rejects a late project replacement after a queued native edit',async()=>fixture('native-replacement',async(page,{observations})=>{
 await savedDemo(page);const input=page.locator('#people [data-employee-hours]').first();await input.fill('12');await input.press('Tab');await input.evaluate(e=>window.nativeNode=e);
 const before=await wireState(page),id=await page.evaluate(()=>snapshot.id),backend=await persisted(page,id),hold=await holdResponse(page,'**/api/demo','GET');page.once('dialog',d=>d.accept());
 try{await page.click('.main-nav [data-navigate="projects"]');await page.click('#demo');await bounded(hold.seen,7000,'Demo arrival');await page.waitForFunction(()=>$('people').inert);await input.evaluate(e=>{e.value='9';e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));});}finally{await hold.drain();}
 await page.waitForFunction(()=>!projectSwitchBusy());await settle(page);observations.after=await wireState(page);
 assert.deepEqual(observations.after,before,'replacement must not discard a newer numeric draft when canonical dirty was already true');assert.equal(await page.evaluate(()=>window.nativeNode.isConnected),true);assert.equal(await input.inputValue(),'9');assert.match(await page.locator('#notice').innerText(),/während des Ladens geändert/);assert.deepEqual(await persisted(page,id),backend);
}));
test('NATIVE-REVIEW-RETRY-SAVE rejects a queued native draft before PUT and allows correction',async()=>fixture('native-retry-save',async(page,{observations})=>{
 await savedDemo(page);const before=await page.evaluate(()=>currentSnapshot()),input=page.locator('#people [data-employee-hours]').first(),hold=await holdResponse(page,'**/api/snapshots','PUT');
 try{await page.click('#headerSave');await bounded(hold.seen,7000,'Save arrival');await page.waitForFunction(()=>$('people').inert);await input.evaluate(e=>{window.nativeNode=e;e.value='9';e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));});}finally{await hold.drain();}
 await page.waitForFunction(()=>!projectSwitchBusy());const stored=await persisted(page,before.id),canonical=await wireState(page),writes=[];page.on('request',r=>{if(r.method()==='PUT')writes.push(r.postDataJSON());});
 await page.click('#headerSave');await page.waitForFunction(()=>!projectSwitchBusy());await settle(page);
 assert.deepEqual(writes,[],'retry must not write stale canonical values while a different raw draft is visible');assert.deepEqual(await persisted(page,before.id),stored);assert.deepEqual(await wireState(page),canonical);assert.match(await page.locator('#notice').innerText(),/Zahleneingabe.*bestätigen/);
 observations.focus=await focused(page,input);assert.equal(await input.inputValue(),'9');assert(await input.evaluate(e=>e===window.nativeNode));await input.press('Tab');
 const expected=structuredClone(stored.detail);expected.employees[0].target_minutes=540;assert.deepEqual(await page.evaluate(()=>currentSnapshot()),expected);
 await page.click('#headerSave');await page.waitForFunction(()=>!projectSwitchBusy());assert.equal(writes.length,1);assert.deepEqual(writes[0],expected);
 const final=(await persisted(page,before.id)).detail;expected.revision=final.revision;assert.deepEqual(final,expected);assert.deepEqual(await page.evaluate(()=>currentSnapshot()),expected);assert.equal(await page.evaluate(()=>dirty||hasNativeDraft()),false);observations.target=final.employees[0].target_minutes;
}));
test('UX03C-NATIVE-RAW late Save acknowledgment preserves a queued native draft',async()=>fixture('native-save-ack',async(page,{observations})=>{
 await savedDemo(page);const before=await page.evaluate(()=>currentSnapshot()),input=page.locator('#people [data-employee-hours]').first();await input.evaluate(e=>window.nativeNode=e);
 const hold=await holdResponse(page,'**/api/snapshots','PUT');
 try{
  await page.click('#headerSave');await bounded(hold.seen,7000,'Save arrival');await page.waitForFunction(()=>$('people').inert);
  // Explicit queued DOM-input seam: keyboard editing is correctly inert here.
  // Dispatch the real listener, without changing its source or canonical model.
  await input.evaluate(e=>{e.value='9';e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));});
 }finally{await hold.drain();}
 await page.waitForFunction(()=>!projectSwitchBusy());await settle(page);
 const stored=(await persisted(page,before.id)).detail;before.revision=stored.revision;assert.deepEqual(stored,before);assert.deepEqual(await page.evaluate(()=>currentSnapshot()),stored);
 observations.after=await wireState(page);observations.raw=await input.inputValue();
 assert.equal(observations.after.dirty,true,'late acknowledgement must not mark a newer unadmitted native draft saved');assert.equal(observations.raw,'9');assert(await input.evaluate(e=>e===window.nativeNode));
}));
test('UX03C-NATIVE-RAW late readiness cannot certify a newer native badInput draft',async()=>fixture('native-readiness',async(page,{observations})=>{
 await savedDemo(page);const baseline=await wireState(page),id=await page.evaluate(()=>snapshot.id),backend=await persisted(page,id);
 const hold=await holdResponse(page,'**/api/readiness');
 try{
  await page.click('.main-nav [data-navigate="plan"]');await bounded(hold.seen,7000,'Readiness arrival');
  await page.click('.main-nav [data-navigate="team"]');const input=page.locator('#people [data-employee-hours]').first();
  await input.fill('');await input.pressSequentially('1e');await input.evaluate(e=>window.nativeNode=e);await input.press('Tab');
  assert(await input.evaluate(e=>e.validity.badInput));assert.equal((await wireState(page)).wire,baseline.wire);
  await page.click('.main-nav [data-navigate="plan"]');
 }finally{await hold.drain();}
 await settle(page);observations.after=await page.evaluate(()=>({readiness:currentReadiness(),status:$('automaticReadinessStatus').dataset.state,readinessVersion,changeVersion,connected:window.nativeNode.isConnected,bad:window.nativeNode.validity.badInput}));
 assert.deepEqual(await persisted(page,id),backend);
 assert.equal(observations.after.readiness.state,'draft','native badInput is an unadmitted draft, never a current readiness result');
 assert.equal(observations.after.status,'draft');assert.equal(observations.after.readinessVersion,-1);
 assert(observations.after.connected&&observations.after.bad);
}));

// Retained independent negative lifecycle controls.
test('NEIGHBOR-FAILED-SAVE no acknowledged origin on injected HTTP rejection',async()=>fixture('failed-save',async(page,{observations})=>{
 await savedDemo(page);const input=page.locator('#people [data-employee-hours]').first(),id=await page.evaluate(()=>snapshot.id),backend=await persisted(page,id);
 await input.fill('12');await input.press('Tab');const before=await wireState(page);
 let release,arrive,finish;const gate=new Promise(r=>release=r),seen=new Promise(r=>arrive=r),done=new Promise(r=>finish=r);
 await page.route('**/api/snapshots',async route=>{if(route.request().method()!=='PUT')return route.fallback();arrive();await gate;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'synthetic reviewer rejection; no backend write'})});finish();},{times:1});
 try{await page.click('#headerSave');await bounded(seen,7000,'rejected Save arrival');await page.waitForFunction(()=>$('people').inert);await input.evaluate(e=>{e.value='9';e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));});}finally{release();await bounded(done,7000,'rejected response drain');}
 await page.waitForFunction(()=>!projectSwitchBusy());assert.deepEqual(await persisted(page,id),backend);assert.equal(await page.evaluate(()=>nativeDraftOrigin.dirty),true);
 await input.fill('12');await input.press('Tab');await settle(page);assert.deepEqual(await wireState(page),before);assert.equal(await page.evaluate(()=>hasNativeDraft()),false);assert.deepEqual(await persisted(page,id),backend);
 observations.expectedConsoleErrors=observations.consoleErrors.filter(x=>x.includes('503'));observations.consoleErrors=observations.consoleErrors.filter(x=>!x.includes('503'));observations.dirtyAfterRejectedSave=true;
}));
test('NEIGHBOR-MULTI-MIRROR successive current canonical rebases preserve raw node',async()=>fixture('multi-mirror',async(page,{observations})=>{
 await savedDemo(page);const id=await page.evaluate(()=>snapshot.id),backend=await persisted(page,id);await page.locator('#people tbody tr:first-child button').click();const table=page.locator('#people [data-employee-hours]').first(),detail=page.locator('#details [data-employee-hours]');await table.evaluate(e=>window.retained=e);
 await table.fill('');await table.pressSequentially('1e');await table.press('Tab');
 for(const v of ['12','14','16']){await detail.fill(v);await detail.press('Tab');assert.equal(await page.evaluate(()=>currentSnapshot().employees[0].target_minutes),Number(v)*60);assert(await table.evaluate(e=>e===window.retained&&e.validity.badInput));}
 await table.fill('16');await table.press('Tab');await settle(page);assert.equal(await page.evaluate(()=>hasNativeDraft()),false);assert.equal(await page.evaluate(()=>dirty),true);assert.deepEqual(await persisted(page,id),backend);
 for(const v of ['18','16','19']){await detail.fill(v);await detail.press('Tab');await table.fill('16');await table.press('Tab');assert.equal(await page.evaluate(()=>currentSnapshot().employees[0].target_minutes),960);assert.equal(await detail.inputValue(),'16');}
 await page.click('#headerSave');await page.waitForFunction(()=>!projectSwitchBusy());const stored=await persisted(page,id);assert.equal(stored.detail.employees[0].target_minutes,960);assert.deepEqual(await page.evaluate(()=>currentSnapshot()),stored.detail);assert.equal(await page.evaluate(()=>dirty||hasNativeDraft()),false);observations.persistedMinutes=960;
}));
test('NEIGHBOR-ACK-TWO-DRAFTS last revert alone restores acknowledged clean origin',async()=>fixture('two-drafts',async(page,{observations})=>{
 await savedDemo(page);await page.locator('#people tbody tr:first-child button').click();const table=page.locator('#people [data-employee-hours]').first(),cap=page.locator('#details [data-employee-cap]'),capOriginal=await cap.inputValue();await table.fill('12');await table.press('Tab');const id=await page.evaluate(()=>snapshot.id),hold=await holdResponse(page,'**/api/snapshots','PUT');
 try{await page.click('#headerSave');await bounded(hold.seen,7000,'Save arrival');await page.waitForFunction(()=>$('people').inert);for(const input of [table,cap])await input.evaluate(e=>{e.value='9';e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));});}finally{await hold.drain();}
 await page.waitForFunction(()=>!projectSwitchBusy());const stored=await persisted(page,id);await table.fill('12');await table.press('Tab');assert.equal(await page.evaluate(()=>dirty&&hasNativeDraft()),true);await cap.fill(capOriginal);await cap.press('Tab');await settle(page);assert.equal(await page.evaluate(()=>dirty||hasNativeDraft()),false);assert.deepEqual(await page.evaluate(()=>currentSnapshot()),stored.detail);assert.deepEqual(await persisted(page,id),stored);observations.finalClean=true;
}));
