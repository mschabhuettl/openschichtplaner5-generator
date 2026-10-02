'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {fixture,state:baseState,persisted,settle,visibleFeedback,bounded,teams,assertTypedEqual}=require('./import-fixture.cjs');
const path=require('node:path');
async function state(page){return {...await baseState(page),...await page.evaluate(()=>({draftVersion,nativeDraftCount:nativeDrafts.size}))};}
async function seed(page,ctx){
 const demo=await(await page.request.get('/api/demo')).json();
 const put=await page.request.put('/api/snapshots',{data:demo});assert.equal(put.status(),200);const stored=await put.json();
 const made=await page.request.post('/api/jobs',{data:{snapshot_id:stored.id,snapshot_revision:stored.revision,time_limit:1,partial:true}});assert(made.ok());const job=await made.json();
 await bounded((async()=>{for(;;){const j=await(await page.request.get('/api/jobs/'+job.id)).json();if(!['queued','running'].includes(j.state)){ctx.observations.completedJob=j;return;}await new Promise(r=>setTimeout(r,100));}})(),15000,'real job completion');
 assert.equal(ctx.observations.completedJob.state,'succeeded');
 await page.reload();await page.waitForSelector('.project-card');await page.waitForSelector('.job-row');
 await page.click('.project-card');await page.waitForFunction(()=>!!snapshot&&!projectSwitchBusy()&&!dirty);
 await page.click('.main-nav [data-navigate="projects"]');await settle(page);
 ctx.observations.fixture={stored,backend:await persisted(page,ctx.base,stored.id),setup:'real API Save+completed job; pointer card open and projects navigation only before keyboard phase'};
 return {demo,stored};
}
async function active(page){return page.evaluate(()=>{const e=document.activeElement;return {tag:e.tagName,id:e.id,team:e.dataset.teamId||null,text:(e.getAttribute('aria-label')||e.labels?.[0]?.innerText||e.textContent||'').trim().slice(0,100),navigate:e.dataset.navigate||null};});}
async function key(page,o,k){const before=await active(page);await page.keyboard.press(k);o.keys.push({key:k,before,after:await active(page)});}
async function frame(page,ctx,label,selector){
 await settle(page);
 const m=await page.evaluate(({label,selector})=>{const focused=document.activeElement,e=focused.type==='file'?focused.closest('label'):focused,r=e.getBoundingClientRect(),hit=document.elementFromPoint((r.left+r.right)/2,(r.top+r.bottom)/2);return {label,selector,focusId:focused.id,focusTag:focused.tagName,focusTeam:focused.dataset.teamId||null,matches:focused.matches(selector),visualCarrier:e===focused?'target':'file label focus-within',rect:{left:r.left,right:r.right,top:r.top,bottom:r.bottom},hit:hit===e||e.contains(hit),hitTag:hit?.tagName,hitId:hit?.id,width:innerWidth,height:innerHeight,documentWidth:document.documentElement.scrollWidth,scrollY,projects:document.querySelectorAll('.project-card').length,jobs:document.querySelectorAll('.job-row').length};},{label,selector});
 ctx.observations.measurements.push(m);await page.screenshot({path:path.join(ctx.artifacts,label+'-'+m.width+'.png')});
 assert(m.matches,'actual focused target '+JSON.stringify(m));
 if(!(m.hit&&m.rect.left>=0&&m.rect.right<=m.width&&m.rect.top>=0&&m.rect.bottom<=m.height&&m.documentWidth<=m.width))ctx.observations.geometryFailures.push(m);
 assert(m.projects>0&&m.jobs>0);
 return m;
}
async function tabTo(page,ctx,selector,direction='Tab'){
 for(let i=0;i<180;i++){
  if(await page.evaluate(s=>document.activeElement.matches(s),selector))return;
  await key(page,ctx.observations,direction);
 }
 throw Error('Tab traversal did not reach '+selector+'; active='+JSON.stringify(await active(page)));
}
async function choose(page,ctx,name,text){
 await tabTo(page,ctx,'#file','Shift+Tab');await frame(page,ctx,'chooser-'+name,'#file');
 const chooser=page.waitForEvent('filechooser');await key(page,ctx.observations,'Enter');
 await(await chooser).setFiles({name:name+'.json',mimeType:'application/json',buffer:Buffer.from(text)});
 ctx.observations.chooserCallbacks.push(name);
}
for(const width of [1440,390])test('A03+A05 actual full keyboard and numeric retry '+width,async()=>fixture('keyboard-'+width,async(page,ctx)=>{
 const o=ctx.observations;o.keys=[];o.geometryFailures=[];o.chooserCallbacks=[];o.covered=[];
 await page.setViewportSize({width,height:1000});const {demo,stored}=await seed(page,ctx);
 const requests=[];page.on('request',r=>{if(['POST','PUT','DELETE'].includes(r.method())&&!r.url().endsWith('/api/readiness'))requests.push({method:r.method(),url:new URL(r.url()).pathname,body:r.postData()});});
 await page.locator('#file').focus();o.startupFocus='Exactly one programmatic keyboard-start focus on #file; all subsequent targeted movement uses actual Tab/Shift+Tab. No locator.press auto-focus, selectOption, fill or click during keyboard task.';
 const before=await state(page),backend=await persisted(page,ctx.base,stored.id);
 await choose(page,ctx,'numeric-nonfinite','{"metadata":{"unsafe":1e309}}');
 await page.waitForFunction(()=>!projectSwitchBusy()&&$('fileFeedback').classList.contains('error'));await settle(page);
 await visibleFeedback(page,'fileFeedback',o,ctx.artifacts,'numeric-error');
 const error=await page.locator('#fileFeedback').textContent();assert.match(error,/JSON-Zahlen/);assert.doesNotMatch(error,/Syntax/);
 assert.deepEqual(await state(page),before);assert.deepEqual(await persisted(page,ctx.base,stored.id),backend);assert.deepEqual(requests,[]);
 o.numeric={input:'{"metadata":{"unsafe":1e309}}',error,before,after:await state(page),backendBefore:backend,backendAfter:await persisted(page,ctx.base,stored.id),requests:requests.slice()};o.covered.push('A03:numeric rejection exact invariants');
 const valid={...demo,id:'keyboard-valid-'+width};const checked=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/api/snapshots/check'));
 await choose(page,ctx,'valid-retry',JSON.stringify(valid));const response=await checked;assert.equal(response.status(),200);
 await page.waitForFunction(id=>snapshot?.id===id&&!projectSwitchBusy(),valid.id);
 assert.deepEqual(await page.evaluate(()=>currentSnapshot()),await response.json());assert.match(await page.locator('#fileFeedback').textContent(),/Projektdatei geöffnet/);assert(!await page.locator('#fileFeedback').evaluate(e=>e.classList.contains('error')));assert.deepEqual(await persisted(page,ctx.base,stored.id),backend);
 o.fileRetry={status:response.status(),checkWire:await response.text(),canonicalWire:await page.evaluate(()=>ProjectJSON.stringify(currentSnapshot())),backendUnchanged:true};assertTypedEqual(o.fileRetry.checkWire,o.fileRetry.canonicalWire);o.covered.push('A03:real successful check retry','A05:file Enter and callback error-retry');
 await tabTo(page,ctx,'#projectName','Shift+Tab');await key(page,o,'Control+a');await page.keyboard.type('Tastatur ungespeichert '+width);o.keys.push({type:'Tastatur ungespeichert '+width,target:await active(page)});await key(page,o,'Enter');
 await tabTo(page,ctx,'.main-nav [data-navigate="projects"]','Shift+Tab');await key(page,o,'Enter');
 await tabTo(page,ctx,'#openImport');await frame(page,ctx,'open-import','#openImport');await key(page,o,'Enter');
 await frame(page,ctx,'source','#sourceType');await key(page,o,'End');await key(page,o,'Enter');assert.equal(await page.locator('#sourceType').inputValue(),'api');
 await tabTo(page,ctx,'#inspect');await frame(page,ctx,'inspect','#inspect');await key(page,o,'Enter');await page.waitForSelector('[data-team-id="2"]');
 await tabTo(page,ctx,'[data-team-id="2"]');await frame(page,ctx,'team','[data-team-id="2"]');await key(page,o,'Space');assert(await page.locator('[data-team-id="2"]').isChecked());
 await tabTo(page,ctx,'#quickStart > summary');await frame(page,ctx,'month-disclosure','#quickStart > summary');await key(page,o,'Enter');
 await tabTo(page,ctx,'#quickMonth');await frame(page,ctx,'month-input','#quickMonth');await page.keyboard.type('02');o.keys.push({type:'02',target:await active(page)});await key(page,o,'ArrowRight');await page.keyboard.type('2026');o.keys.push({type:'2026',target:await active(page)});await key(page,o,'Tab');
 o.month=await page.locator('#quickMonth').inputValue();assert.equal(o.month,'2026-02','native month keyboard entry');
 await tabTo(page,ctx,'#quickPrepare');await frame(page,ctx,'month-preset','#quickPrepare');
 const prePreset=await state(page),preRequests=requests.slice();assert(prePreset.dirty);await key(page,o,'Space');await page.waitForFunction(()=>!$('quickPrepare').dataset.busy);await settle(page);
 assert.deepEqual(await state(page),prePreset);assert.deepEqual(requests,preRequests);assert.deepEqual(await persisted(page,ctx.base,stored.id),backend);
 assert.equal(await page.locator('#start').inputValue(),'2026-02-01');assert.equal(await page.locator('#end').inputValue(),'2026-02-28');o.covered.push('A05:source-select team-Space month-keyboard explicit preset without request');
 await tabTo(page,ctx,'#import');await frame(page,ctx,'explicit-import','#import');
 const preCancel=await state(page),cancelRequests=requests.slice(),dialogs=[];page.once('dialog',async d=>{dialogs.push({type:d.type(),message:d.message(),decision:'dismiss callback (not OS dialog keyboard)'});await d.dismiss();});
 await key(page,o,'Enter');await page.waitForFunction(()=>!projectSwitchBusy());await settle(page);
 assert.equal(dialogs.length,1);assert.deepEqual(requests,cancelRequests);assert.deepEqual(await state(page),preCancel);assert.deepEqual(await persisted(page,ctx.base,stored.id),backend);
 const hints=await page.evaluate(()=>({quickHint:$('quickHint').textContent,importFeedback:$('importFeedback').textContent}));assert.doesNotMatch(hints.quickHint+' '+hints.importFeedback,/Import läuft|läuft gerade/);o.cancel={dialogs,hints,before:preCancel,after:await state(page),requestsUnchanged:true,backendUnchanged:true};o.covered.push('A05:real declined dirty replacement no request no stale running hint');
 await tabTo(page,ctx,'#import');const remote=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/api/remote-import')),admission=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/api/snapshots/check'));
 page.once('dialog',async d=>{o.acceptedDialog={type:d.type(),message:d.message()};await d.accept();});await key(page,o,'Enter');const rr=await remote,ar=await admission;assert.equal(rr.status(),200);assert.equal(ar.status(),200);await page.waitForFunction(()=>!projectSwitchBusy());
 const req=rr.request().postDataJSON();assert.deepEqual(req.team_ids,['2']);assert.equal(req.period_start,'2026-02-01');assert.equal(req.period_end,'2026-02-28');assert.deepEqual(JSON.parse(await page.evaluate(()=>ProjectJSON.stringify(currentSnapshot()))),await ar.json());assert.deepEqual(await persisted(page,ctx.base,stored.id),backend);
 o.import={request:req,remoteText:await rr.text(),checkWire:await ar.text(),canonicalWire:await page.evaluate(()=>ProjectJSON.stringify(currentSnapshot())),backendUnchanged:true};assertTypedEqual(o.import.checkWire,o.import.canonicalWire);o.requests=requests;o.covered.push('A05:explicit Enter real remote-import and check 200');
 assert.deepEqual(o.consoleErrors,[]);assert.deepEqual(o.geometryFailures,[],'settled focused controls must intersect viewport and be unoccluded');
}));
