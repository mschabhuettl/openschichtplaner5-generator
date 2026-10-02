'use strict';
// Synthetic real-browser import regressions; helpers have no test-registration side effects.
const {test}=require('node:test'),assert=require('node:assert/strict'),path=require('node:path');
const {fixture,state,persisted,settle,visibleFeedback,bounded,teams,pause}=require('./import-fixture.cjs');
test('UX03C-A02 month presets require an explicit import and preserve request semantics',async()=>fixture('import-month',async(page,{observations})=>{
 await teams(page);await page.click('#quickStart > summary');await page.fill('#quickMonth','2026-02');
 const requests=[];page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/api/remote-import'))requests.push(r.postDataJSON());});
 await page.click('#quickPrepare');await page.waitForFunction(()=>!projectSwitchBusy());await settle(page);
 observations.presetRequests=requests.slice();
 assert.equal(requests.length,0,'UX03C-A02: month preset must not send an import');
 assert.equal(await page.evaluate(()=>snapshot),null);
 assert.deepEqual(await page.evaluate(()=>[$('start').value,$('end').value,$('historyStart').value,$('historyEnd').value,$('demandHistoryStart').value,$('demandHistoryEnd').value,$('demandSource').value,$('autoKind').checked,$('autoHistory').checked,$('reuseSetup').checked]),['2026-02-01','2026-02-28','2023-02-01','2026-01-31','2025-02-01','2025-02-28','history',true,false,false]);
 const response=page.waitForResponse(r=>r.url().endsWith('/api/remote-import')&&r.request().method()==='POST');await page.click('#import');const imported=await response;assert.equal(imported.status(),200);
 await page.waitForFunction(()=>!!snapshot&&!projectSwitchBusy());
 assert.equal(requests.length,1);assert.deepEqual(requests[0],{period_start:'2026-02-01',period_end:'2026-02-28',team_ids:['2'],timezone:'Europe/Vienna',history_plan:'ist',reference_plan:'ist',auto_history:false,history_min_days:3,existing_plan_mode:'reference',demand_source:'history',demand_history_start:'2025-02-01',demand_history_end:'2025-02-28',history_start:'2023-02-01',history_end:'2026-01-31'});
 observations.request=requests[0];observations.result=await imported.json();
 assert(await page.evaluate(()=>snapshot.profiles.every(p=>!p.confirmed)));
 assert.deepEqual(observations.consoleErrors,[]);
}));
test('UX03C-A01 separate file entry and one source-team-period import within control budget',async()=>fixture('import-layout',async(page,{base,observations,artifacts})=>{
 const demo=await(await page.request.get(base+'/api/demo')).json();let response=await page.request.put(base+'/api/snapshots',{data:demo});assert(response.ok());
 const stored=await response.json();response=await page.request.post(base+'/api/jobs',{data:{snapshot_id:stored.id,snapshot_revision:stored.revision,time_limit:1,partial:true}});assert(response.ok());const job=await response.json();
 await bounded((async()=>{for(;;){const j=await(await page.request.get(base+'/api/jobs/'+job.id)).json();if(!['queued','running'].includes(j.state))return;await pause(100);}})(),10000,'completed job fixture');
 await page.reload();await page.waitForSelector('.project-card');await page.waitForSelector('.job-row');
 assert.equal(await page.locator('#file').evaluate(e=>!!e.closest('#importDetails')),false,'UX03C-A01: file entry must not require the SP5 form');
 for(const width of [1440,390,320]){
  await page.setViewportSize({width,height:1000});await page.locator('#openImport').press('Enter');await settle(page);assert(await page.locator('#sourceType').evaluate(e=>e===document.activeElement));
  await page.selectOption('#sourceType','api');await page.click('#inspect');await page.waitForSelector('[data-team-id="2"]');await page.check('[data-team-id="2"]');await settle(page);
  const m=await page.locator('#importDetails').evaluate(d=>{const visible=e=>{if(e.closest('[hidden]')||!e.getClientRects().length||getComputedStyle(e).visibility==='hidden')return false;for(let p=e.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS'&&!p.open&&!p.querySelector(':scope > summary')?.contains(e))return false;const r=e.getBoundingClientRect();return r.width>1&&r.height>1;};return {width:innerWidth,documentWidth:document.documentElement.scrollWidth,controls:[...d.querySelectorAll('button,input,select,textarea,summary,a[href]')].filter(visible).map(e=>({id:e.id,label:e.getAttribute('aria-label')||e.labels?.[0]?.innerText||e.textContent.trim()})),primary:[...d.querySelectorAll('button.primary')].filter(visible).map(e=>e.id),sourceBeforeMonth:!!(d.querySelector('#sourceType').compareDocumentPosition(d.querySelector('#quickMonth'))&Node.DOCUMENT_POSITION_FOLLOWING)};});
  observations.measurements.push(m);if(artifacts)await page.screenshot({path:path.join(artifacts,'import-layout-'+width+'.png')});
  assert.equal(m.sourceBeforeMonth,true);assert.deepEqual(m.primary,['import']);assert(m.controls.length<=12,'import control budget '+m.controls.length);assert(m.documentWidth<=width);
  const summary=await page.locator('#importSummary').textContent();for(const text of ['Europe/Vienna','Istplan','neu planen'])assert(summary.includes(text),'chosen setting visible without opening options: '+text);
 }
}));
for(const width of [1440,390])test(`UX03C-A03 local file syntax and source errors remain visible at ${width}`,async()=>fixture('import-feedback-'+width,async(page,{observations,artifacts})=>{
 await page.setViewportSize({width,height:1000});
 const before=await state(page),requests=[];page.on('request',r=>{if(r.method()==='POST')requests.push(r.url());});
 const chooser=page.waitForEvent('filechooser');await page.locator('#file').press('Enter');const selected=await chooser;await selected.setFiles({name:'synthetic-invalid.json',mimeType:'application/json',buffer:Buffer.from('{invalid')});
 await page.waitForFunction(()=>!projectSwitchBusy()&&document.getElementById('notice').classList.contains('error'));await settle(page);
 assert.deepEqual(await state(page),before);assert.equal(requests.length,0);assert.match(await page.locator('#notice').textContent(),/Syntax/,'UX03C-A03: distinguish JSON syntax from numeric admission');
 await visibleFeedback(page,'fileFeedback',observations,artifacts,'file-error');
 await page.click('#openImport');await page.selectOption('#sourceType','api');
 await page.route('**/api/remote-source',r=>r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Synthetischer Team-Ladefehler'})}),{times:1});
 await page.click('#inspect');await page.waitForFunction(()=>!document.getElementById('inspect').dataset.busy&&document.getElementById('notice').textContent.includes('Synthetischer'));await settle(page);
 await visibleFeedback(page,'sourceFeedback',observations,artifacts,'source-error');assert.deepEqual(await state(page),before);
 await page.click('#inspect');await page.waitForSelector('[data-team-id="2"]');assert.doesNotMatch(await page.locator('#sourceFeedback').textContent(),/Synthetischer|läuft/);
 const valid=await(await page.request.get('/api/demo')).json();valid.id='synthetic-file-retry-'+width;
 const checking=page.waitForResponse(r=>r.url().endsWith('/api/snapshots/check')&&r.request().method()==='POST');
 const retryChooser=page.waitForEvent('filechooser');await page.locator('#file').press('Enter');await(await retryChooser).setFiles({name:'synthetic-valid.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(valid))});
 const checked=await checking;assert.equal(checked.status(),200);await page.waitForFunction(id=>snapshot?.id===id&&!projectSwitchBusy(),valid.id);
 assert.deepEqual(await page.evaluate(()=>currentSnapshot()),await checked.json());assert.match(await page.locator('#fileFeedback').textContent(),/Projektdatei geöffnet/);assert.equal(await page.locator('#fileFeedback').evaluate(e=>e.classList.contains('error')),false);
 assert.deepEqual(await(await page.request.get('/api/snapshots')).json(),[],'opening a file is not an implicit save');
 observations.fileRetry={openedId:valid.id,admissionStatus:checked.status(),noPersistence:true};
 assert.equal(observations.consoleErrors.filter(e=>!e.includes('503')).length,0);
}));
test('UX03C-IR01 following-period summary matches the actual import request',async()=>fixture('import-following-summary',async(page,{base,observations})=>{
 await page.click('#demo');await page.waitForFunction(()=>!!snapshot&&!projectSwitchBusy());
 const loaded=await page.evaluate(()=>({timezone:snapshot.timezone,summary:$('importSummary').textContent}));assert(loaded.summary.includes(loaded.timezone),'UX03C-IR01 loading a project also refreshes the import summary');
 await page.click('#headerSave');await page.waitForFunction(()=>!dirty&&!projectSwitchBusy());
 const id=await page.evaluate(()=>snapshot.id);await page.click('.main-nav [data-navigate="projects"]');await teams(page);
 await page.click('#importOptions > summary');await page.fill('#timezone','Pacific/Auckland');
 const before=await state(page),backend=await persisted(page,base,id),requests=[];
 page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/api/remote-import'))requests.push(r.postDataJSON());});
 await page.click('#prepareNextPeriod');await page.waitForFunction(()=>!document.getElementById('prepareNextPeriod').dataset.busy);await settle(page);
 const form=await page.evaluate(()=>({start:$('start').value,end:$('end').value,timezone:$('timezone').value,historyStart:$('historyStart').value,historyEnd:$('historyEnd').value}));
 const summary=await page.locator('#importSummary').textContent();observations.summary={form,summary};
 assert.equal(requests.length,0);assert.deepEqual(await state(page),before);assert.deepEqual(await persisted(page,base,id),backend);
 for(const value of [form.timezone,form.historyStart,form.historyEnd])assert(summary.includes(value),'UX03C-IR01 summary must reflect preset '+value);
 assert(!summary.includes('Pacific/Auckland'));
 const response=page.waitForResponse(r=>r.url().endsWith('/api/remote-import')&&r.request().method()==='POST');await page.click('#import');assert.equal((await response).status(),200);await page.waitForFunction(()=>!projectSwitchBusy());
 assert.equal(requests.length,1);assert.equal(requests[0].period_start,form.start);assert.equal(requests[0].period_end,form.end);assert.equal(requests[0].timezone,form.timezone);assert.equal(requests[0].history_start,form.historyStart);assert.equal(requests[0].history_end,form.historyEnd);
 observations.request=requests[0];assert.deepEqual(observations.consoleErrors,[]);
}));
test('UX03C-IR02 source changes invalidate feedback and ignore late outcomes',async()=>fixture('import-source-binding',async(page,{observations})=>{
 await teams(page);assert.match(await page.locator('#sourceFeedback').textContent(),/3 Teams gefunden/);
 const before=await state(page);await page.selectOption('#sourceType','directory');await settle(page);
 assert.equal(await page.locator('[data-team-id]').count(),0);
 assert.doesNotMatch(await page.locator('#sourceFeedback').textContent(),/3 Teams gefunden/,'UX03C-IR02 success belongs to its source');
 assert.match(await page.locator('#sourceFeedback').textContent(),/erneut laden/);
 await page.route('**/api/source?*',r=>r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Synthetic old directory error'})}),{times:1});
 await page.click('#inspect');await page.waitForFunction(()=>!$('inspect').dataset.busy);assert.match(await page.locator('#sourceFeedback').textContent(),/Synthetic old/);
 await page.fill('#directory','synthetic-retry-directory');await settle(page);
 assert.doesNotMatch(await page.locator('#sourceFeedback').textContent(),/Synthetic old/);assert.equal(await page.locator('#sourceFeedback').evaluate(e=>e.classList.contains('error')),false);
 for(const status of [200,503]){
  await page.selectOption('#sourceType','api');
  let release,arrived;const held=new Promise(r=>release=r),seen=new Promise(r=>arrived=r);
  const handler=async route=>{arrived();await held;await route.fulfill({status,contentType:'application/json',body:JSON.stringify(status===200?{groups:[{id:'obsolete',name:'Obsolete team'}]}:{detail:'Synthetic stale failure'})});};
  await page.route('**/api/remote-source',handler);
  try{
   await page.click('#inspect');await bounded(seen,5000,'source held');await settle(page);assert.match(await page.locator('#sourceFeedback').textContent(),/geladen/,'explicit local loading');
   // Change away and back: equality of the current path alone is not sufficient.
   await page.selectOption('#sourceType','directory');await page.selectOption('#sourceType','api');release();
   await page.waitForFunction(()=>!$('inspect').dataset.busy);await settle(page);
   assert.equal(await page.locator('[data-team-id]').count(),0);assert.match(await page.locator('#sourceFeedback').textContent(),/erneut laden/);assert.doesNotMatch(await page.locator('#sourceFeedback').textContent(),/obsolete|stale|gefunden|geladen/i);
   assert.equal(await page.locator('#sourceFeedback').evaluate(e=>e.classList.contains('error')),false);
  }finally{release();await page.unroute('**/api/remote-source',handler);}
 }
 await page.route('**/api/remote-source',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({groups:[]})}),{times:1});
 await page.click('#inspect');await page.waitForFunction(()=>!$('inspect').dataset.busy);assert.match(await page.locator('#sourceFeedback').textContent(),/Keine Teams/);
 await page.click('#inspect');await page.waitForSelector('[data-team-id="2"]');assert.match(await page.locator('#sourceFeedback').textContent(),/3 Teams gefunden/);
 assert.deepEqual(await state(page),before);observations.sourceBinding={successInvalidated:true,errorInvalidated:true,lateSuccessIgnored:true,lateFailureIgnored:true,emptyAndRetry:true};
 assert.equal(observations.consoleErrors.filter(e=>!e.includes('503')).length,0);
}));
test('UX03C-IR03 summary distinguishes comparison and historical plan with active approval threshold',async()=>fixture('import-history-summary',async(page,{observations})=>{
 await teams(page);await page.click('#importOptions > summary');await page.selectOption('#historyPlan','soll');await page.selectOption('#referencePlan','ist');await page.check('#autoHistory');await page.fill('#historyMinDays','9');await page.click('#importOptions > summary');
 const summary=await page.locator('#importSummary').textContent();observations.summary=summary;
 assert.match(summary,/Vergleichsplan: Istplan/);assert.match(summary,/Historische Planbasis: Sollplan/,'UX03C-IR03 explicit separate history plan');assert.match(summary,/automatisch.*mindestens 9 Tage/);
 const request=page.waitForRequest(r=>r.url().endsWith('/api/remote-import')&&r.method()==='POST');await page.click('#import');const payload=(await request).postDataJSON();await page.waitForFunction(()=>!!snapshot&&!projectSwitchBusy());
 assert.equal(payload.history_plan,'soll');assert.equal(payload.reference_plan,'ist');assert.equal(payload.auto_history,true);assert.equal(payload.history_min_days,9);observations.request=payload;
 await page.click('.main-nav [data-navigate="projects"]');await page.click('#importOptions > summary');await page.uncheck('#autoHistory');await page.click('#importOptions > summary');assert.match(await page.locator('#importSummary').textContent(),/Historische Freigaben: nicht automatisch/);assert.doesNotMatch(await page.locator('#importSummary').textContent(),/mindestens 9 Tage/);
 assert.deepEqual(observations.consoleErrors,[]);
}));
for(const owner of ['import','file','save'])test(`UX03C-A04 ${owner} rejects competing import-file-save handlers until completion`,async()=>fixture('import-lock-'+owner,async(page,{base,observations})=>{
 await page.click('#demo');await page.waitForFunction(()=>!!snapshot&&!projectSwitchBusy());await page.click('#headerSave');await page.waitForFunction(()=>!dirty&&!projectSwitchBusy());
 const id=await page.evaluate(()=>snapshot.id),candidate=await page.evaluate(()=>currentSnapshot());candidate.id='synthetic-replacement-'+owner;candidate.revision='0';
 await page.click('.main-nav [data-navigate="projects"]');await teams(page);
 const before=await state(page),backend=await persisted(page,base,id),requests=[];page.on('request',r=>{if(['POST','PUT'].includes(r.method())&&!r.url().endsWith('/api/readiness'))requests.push({url:new URL(r.url()).pathname,method:r.method()});});
 const pattern=owner==='import'?'**/api/remote-import':owner==='file'?'**/api/snapshots/check':'**/api/snapshots';
 let release,arrived,finished,failure;const held=new Promise(r=>release=r),seen=new Promise(r=>arrived=r),done=new Promise(r=>finished=r);
 const handler=async route=>{if(route.request().method()!==(owner==='save'?'PUT':'POST'))return route.fallback();try{arrived();await bounded(held,10000,'owned request delay');await route.continue();}catch(error){failure=error;try{await route.abort();}catch{}}finally{finished();}};
 await page.route(pattern,handler,{times:1});
 try{
  if(owner==='file')await page.locator('#file').setInputFiles({name:'synthetic-replacement.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(candidate))});else await page.click(owner==='save'?'#headerSave':'#import');
  await bounded(seen,5000,'owned request arrival');await page.waitForFunction(()=>$('file').disabled&&$('import').disabled&&$('save').disabled&&$('headerSave').disabled);await settle(page);
  const sent=requests.slice();assert.equal(sent.length,1);
  for(const competing of ['import','file','save'].filter(x=>x!==owner)){
   if(competing==='file')await page.locator('#file').setInputFiles({name:'synthetic-blocked.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(candidate))});
   else await page.evaluate(id=>$(id).onclick(),competing);
  }
  assert.deepEqual(requests,sent,'original handlers cannot start a second operation');assert.deepEqual(await state(page),before);assert.deepEqual(await persisted(page,base,id),backend);
 }finally{release();await bounded(done,10000,'owned callback drain');if(failure)throw failure;}
 await page.waitForFunction(()=>!projectSwitchBusy());await settle(page);
 for(const control of ['file','import','save'])assert.equal(await page.locator('#'+control).isDisabled(),false,'lock released '+control);
 const after=await state(page),stored=await persisted(page,base,id);
 if(owner==='save'){assert.equal(after.dirty,false);assert.deepEqual(await page.evaluate(()=>currentSnapshot()),stored.detail);assert.equal(requests.filter(r=>r.method==='PUT').length,1);}
 else {assert.deepEqual(stored,backend);assert.equal(requests.filter(r=>r.method==='PUT').length,0);assert.equal(await page.evaluate(()=>snapshot.id===null),false);if(owner==='file')assert.equal(await page.evaluate(()=>snapshot.id),candidate.id);}
 observations.lock={owner,requests,before,after,stored};assert.deepEqual(observations.consoleErrors,[]);
}));
for(const width of [1440,390])test(`UX03C-A04 presets and source navigation retain raw and native invalid input at ${width}`,async()=>fixture('import-raw-'+width,async(page,{base,observations})=>{
 await page.setViewportSize({width,height:1000});await page.click('#demo');await page.waitForFunction(()=>!!snapshot&&!projectSwitchBusy());await page.click('#headerSave');await page.waitForFunction(()=>!dirty&&!projectSwitchBusy());
 const id=await page.evaluate(()=>snapshot.id),backend=await persisted(page,base,id),originalWire=await page.evaluate(()=>ProjectJSON.stringify(currentSnapshot()));
 const input=page.locator('#people [data-employee-hours]').first();await input.fill('');await input.pressSequentially('1e');assert(await input.evaluate(e=>e.validity.badInput));await input.evaluate(e=>window.importRawNode=e);
 await page.click('.main-nav [data-navigate="projects"]');
 observations.afterBlur=await page.evaluate(()=>({wire:ProjectJSON.stringify(currentSnapshot()),dirty,changeVersion,rawValue:window.importRawNode.value,badInput:window.importRawNode.validity.badInput,connected:window.importRawNode.isConnected}));
 assert.equal(observations.afterBlur.wire,originalWire,'native invalid input must not replace canonical Soll with null');
 await teams(page);await page.click('#importOptions > summary');await page.fill('#historyMinDays','-1');await page.click('#importOptions > summary');
 // A real unadmitted JSON edit must survive local navigation and presets too.
 await page.evaluate(()=>{document.getElementById('json').value=' { "synthetic unfinished": ';document.getElementById('json').dispatchEvent(new Event('input',{bubbles:true}));});
 const before=await state(page);assert(before.jsonDirty);
 await page.click('#quickStart > summary');await page.fill('#quickMonth','2026-02');await page.click('#quickPrepare');await settle(page);
 assert.deepEqual(await state(page),before);assert.deepEqual(await persisted(page,base,id),backend);assert.equal(await page.locator('#historyMinDays').inputValue(),'-1');
 await page.click('.main-nav [data-navigate="team"]');assert(await input.evaluate(e=>e===window.importRawNode&&e.validity.badInput));await input.focus();await input.press('Backspace');assert.equal(await input.inputValue(),'1','actual native 1e text survived, not merely badInput');
 observations.raw={nativeRecovered:'1',json:before.raw,backendUnchanged:true};assert.deepEqual(observations.consoleErrors,[]);
}));
test('UX03C-D03 declined dirty import preserves wire and backend without a running hint',async()=>fixture('import-cancel',async(page,{base,observations})=>{
 await page.click('#openImport');await page.click('#demo');await page.waitForFunction(()=>!!PlannerApp.getState().snapshot&&!projectSwitchBusy());
 await page.click('#headerSave');await page.waitForFunction(()=>!PlannerApp.getState().dirty&&!projectSwitchBusy());
 const id=await page.evaluate(()=>PlannerApp.getState().snapshot.id);
 await page.fill('#projectName','Synthetischer ungespeicherter Name');await page.locator('#projectName').press('Enter');
 await page.click('.main-nav [data-navigate="projects"]');await teams(page);await page.click('#quickStart > summary');await page.fill('#quickMonth','2026-02');
 const before=await state(page),backend=await persisted(page,base,id),requests=[],dialogs=[];
 assert(before.dirty);page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/api/remote-import'))requests.push(r.postData());});
 page.on('dialog',async d=>{dialogs.push(d.message());await d.dismiss();});
 await page.click('#quickPrepare');await settle(page);assert.equal(dialogs.length,0,'preset is not a replacement');assert.equal(requests.length,0);
 await page.click('#import');await page.waitForFunction(()=>!projectSwitchBusy());await settle(page);
 assert.equal(dialogs.length,1,'real dirty replacement confirmation');assert.equal(requests.length,0);
 assert.deepEqual(await state(page),before);assert.deepEqual(await persisted(page,base,id),backend);
 const hint=await page.locator('#quickHint').textContent();observations.cancel={hint,requests,dialogs,wireAndBackendUnchanged:true};
 assert.doesNotMatch(hint,/Import läuft/,'UX03C-D03: cancelled import must not show a running status');
 assert.deepEqual(observations.consoleErrors,[]);
}));
