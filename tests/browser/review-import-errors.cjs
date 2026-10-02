'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {fixture,state:baseState,persisted,settle,visibleFeedback,bounded,teams}=require('./import-fixture.cjs');
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
for(const width of [1440,390])test('A03 changed+invalid native/raw preservation numeric and source error '+width,async()=>fixture('preservation-'+width,async(page,ctx)=>{
 const o=ctx.observations;o.covered=[];await page.setViewportSize({width,height:1000});const {stored}=await seed(page,ctx);
 await page.click('.main-nav [data-navigate="team"]');const input=page.locator('#people [data-employee-hours]').first();await input.fill('');await input.pressSequentially('1e');assert(await input.evaluate(e=>e.validity.badInput));await input.evaluate(e=>window.retainedNative=e);
 await page.click('.main-nav [data-navigate="projects"]');await teams(page);
 await page.evaluate(()=>{$('json').value=' { "synthetic unfinished": ';$('json').dispatchEvent(new Event('input',{bubbles:true}));});o.rawSeam='Explicit queued textarea input in hidden raw editor; not claimed as keyboard navigation';
 const before=await state(page),backend=await persisted(page,ctx.base,stored.id),requests=[];assert(before.dirty&&before.jsonDirty);page.on('request',r=>{if(['POST','PUT'].includes(r.method())&&!r.url().endsWith('/api/readiness'))requests.push(new URL(r.url()).pathname);});
 await page.locator('#file').setInputFiles({name:'numeric-invalid.json',mimeType:'application/json',buffer:Buffer.from('{"metadata":{"unsafe":1e309}}')});
 await page.waitForFunction(()=>!projectSwitchBusy()&&$('fileFeedback').classList.contains('error'));await settle(page);await visibleFeedback(page,'fileFeedback',o,ctx.artifacts,'preserved-numeric');assert.match(await page.locator('#fileFeedback').textContent(),/JSON-Zahlen/);
 assert.deepEqual(await state(page),before);assert.deepEqual(await persisted(page,ctx.base,stored.id),backend);assert.deepEqual(requests,[]);o.covered.push('A03:numeric + native invalid1e + invalid edited raw + dirty exact invariants');
 await page.locator('#file').setInputFiles({name:'syntax-invalid.json',mimeType:'application/json',buffer:Buffer.from('{invalid')});
 await page.waitForFunction(()=>!projectSwitchBusy()&&$('fileFeedback').textContent.includes('Syntax'));await settle(page);await visibleFeedback(page,'fileFeedback',o,ctx.artifacts,'preserved-syntax');assert.deepEqual(await state(page),before);assert.deepEqual(await persisted(page,ctx.base,stored.id),backend);assert.deepEqual(requests,[]);o.covered.push('A04:syntax error with native+raw drafts preserved');
 const valid=await(await page.request.get('/api/demo')).text();
 await page.route('**/api/snapshots/check',r=>r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Synthetischer Datei-HTTP-Fehler 503'})}),{times:1});
 await page.locator('#file').setInputFiles({name:'synthetic-http.json',mimeType:'application/json',buffer:Buffer.from(valid)});
 await page.waitForFunction(()=>!projectSwitchBusy()&&$('fileFeedback').textContent.includes('Datei-HTTP'));await settle(page);await visibleFeedback(page,'fileFeedback',o,ctx.artifacts,'preserved-file-http');assert.deepEqual(await state(page),before);assert.deepEqual(await persisted(page,ctx.base,stored.id),backend);assert.deepEqual(requests,['/api/snapshots/check']);o.covered.push('A04:file HTTP failure with native+raw drafts preserved');
 await page.route('**/api/remote-import',r=>r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Synthetischer Import-HTTP-Fehler 503'})}),{times:1});
 let accepted=0;page.once('dialog',async d=>{accepted++;await d.accept();});await page.click('#import');await page.waitForFunction(()=>!projectSwitchBusy()&&$('importFeedback').textContent.includes('Import-HTTP'));assert.equal(accepted,1);await settle(page);await visibleFeedback(page,'importFeedback',o,ctx.artifacts,'preserved-import-http');assert.deepEqual(await state(page),before);assert.deepEqual(await persisted(page,ctx.base,stored.id),backend);assert.deepEqual(requests,['/api/snapshots/check','/api/remote-import']);o.covered.push('A04:import HTTP failure with native+raw drafts preserved');
 await page.route('**/api/remote-source',r=>r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Synthetischer Erhaltungsfehler 503'})}),{times:1});await page.click('#inspect');await page.waitForFunction(()=>!$('inspect').dataset.busy&&$('sourceFeedback').classList.contains('error'));await settle(page);await visibleFeedback(page,'sourceFeedback',o,ctx.artifacts,'preserved-source');
 assert.deepEqual(await state(page),before);assert.deepEqual(await persisted(page,ctx.base,stored.id),backend);o.covered.push('A03:source503 + native invalid1e + invalid edited raw exact invariants');
 await page.click('#inspect');await page.waitForFunction(()=>$('sourceFeedback').textContent.includes('3 Teams gefunden'));assert.deepEqual(await state(page),before);assert.deepEqual(await persisted(page,ctx.base,stored.id),backend);o.covered.push('A03:source retry with invalid drafts preserved');
 o.preservation={before,after:await state(page),backendBefore:backend,backendAfter:await persisted(page,ctx.base,stored.id),requests};
 await page.click('.main-nav [data-navigate="team"]');assert(await input.evaluate(e=>e===window.retainedNative&&e.isConnected&&e.validity.badInput));await input.focus();await input.press('Backspace');assert.equal(await input.inputValue(),'1');o.nativeRecovery='1e -> Backspace -> 1 on same retained node';
 assert.equal(o.consoleErrors.filter(e=>!e.includes('503')).length,0);
}));
