'use strict';
// UX-02B: actual Chromium layout/resources against an isolated synthetic store.
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawn}=require('node:child_process');
const {chromium}=require('playwright');
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function bounded(promise,ms,label){
 let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error(label+' timed out')),ms);})]);}finally{clearTimeout(timer);}
}
async function fixture(name,run){
 const root=path.resolve(__dirname,'../..'),state=fs.mkdtempSync(path.join(os.tmpdir(),'review-navigation-'));
 const server=spawn(process.env.WEB_TEST_PYTHON||'python',['tests/browser/server.py'],{cwd:root,env:{...process.env,TMPDIR:os.tmpdir(),WEB_TEST_STATE:state,WEB_TEST_PORT:'0'},stdio:['ignore','pipe','pipe']});
 let output='',browser,spawnError;
 const exited=new Promise(resolve=>{server.once('exit',resolve);server.once('error',error=>{spawnError=error;resolve();});});
 for(const stream of [server.stdout,server.stderr])stream.on('data',data=>output=(output+data).slice(-16000));
 const observations={consoleErrors:[],pageErrors:[]};
 const artifacts=process.env.WEB_TEST_SCREENSHOT_DIR;
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
  const page=await browser.newPage({baseURL:base,viewport:{width:1440,height:1000}});page.setDefaultTimeout(10000);
  page.on('pageerror',error=>observations.pageErrors.push(error.message));
  page.on('console',message=>{if(message.type()==='error')observations.consoleErrors.push(message.text());});
  await page.route('**/*',route=>new URL(route.request().url()).origin===base?route.continue():route.abort());
  const response=await page.goto(base);await page.waitForFunction(()=>window.PlannerApp);
  observations.csp=response.headers()['content-security-policy'];
  await bounded(run(page,{base,observations,artifacts}),60000,'Navigation scenario');
  assert.deepEqual(observations.pageErrors,[],'no JavaScript exceptions');
 }finally{
  try{if(browser)await bounded(browser.close(),5000,'Browser shutdown');}
  finally{
   try{if(server.pid&&server.exitCode===null&&server.signalCode===null){server.kill('SIGTERM');try{await bounded(exited,5000,'Fixture shutdown');}catch{server.kill('SIGKILL');await bounded(exited,5000,'Fixture forced shutdown');}}}
   finally{
    fs.rmSync(state,{recursive:true,force:true});
    if(artifacts)fs.writeFileSync(path.join(artifacts,name+'.json'),JSON.stringify(observations,null,2)+'\n');
   }
  }
 }
}
async function importLayout(page){
 return page.evaluate(()=>{
  const width=innerWidth,rect=e=>{const r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width};};
  // Deliberate local table/navigation scrolling is not document overflow.
  const visible=e=>e.getClientRects().length&&!e.closest('[hidden]')&&![...document.querySelectorAll('details:not([open])')].some(d=>d!==e&&d.contains(e)&&!d.querySelector(':scope > summary')?.contains(e));
  return {width,height:innerHeight,scrollY,scrollX,documentWidth:document.documentElement.scrollWidth,
   outside:[...document.querySelectorAll('#mainContent *,.topbar *')].filter(visible).map(e=>({tag:e.tagName,id:e.id,className:e.className,...rect(e)})).filter(r=>r.right>width||r.left<0),
   controls:[...document.querySelectorAll('#importDetails input:not([type=file]),#importDetails select,#importDetails button')].filter(visible).map(e=>({id:e.id,...rect(e)}))};
 });
}
test('UX-02B four real main destinations preserve the project through local setup navigation',async()=>fixture('four-areas',async(page,{observations,artifacts})=>{
 const nav=page.locator('.main-nav [data-navigate]');
 assert.deepEqual(await nav.evaluateAll(nodes=>nodes.map(e=>e.dataset.navigate)),['projects','plan','team','setup'],'four actual main controls, not hidden legacy aliases');
 assert.equal(await nav.evaluateAll(nodes=>nodes.filter(e=>e.hidden||e.getClientRects().length===0).length),0,'main controls themselves are visible; status badges may be hidden');
 assert.equal(await nav.locator('span:first-of-type').allTextContents().then(texts=>texts.join('|')),'Projekte|Plan|Team|Einrichtung');
 for(const name of ['plan','team','setup'])assert(await page.locator(`.main-nav [data-navigate="${name}"]`).isDisabled(),'unavailable without a project');
 await page.click('#newProject');await page.fill('#wizardName','Synthetische Navigation');
 await page.fill('#wizardStart','2026-10-05');await page.fill('#wizardEnd','2026-10-09');await page.fill('#wizardTimezone','Europe/Vienna');
 await page.click('#wizardNext');await page.fill('#wizardPeople','Testperson A\nTestperson B\nTestperson C');await page.click('#wizardNext');
 await page.click('#wizardNext'); // Separate rule review after shifts.
 for(const id of ['wizardRulesConfirmed','wizardApprovalsConfirmed','wizardContextConfirmed'])await page.check('#'+id);
 await page.click('#wizardCreate');await page.waitForFunction(()=>!document.getElementById('createProjectDialog').open&&PlannerApp.getState().snapshot);
 const before=await page.evaluate(()=>({wire:ProjectJSON.stringify(currentSnapshot()),dirty,changeVersion}));
 await page.locator('.main-nav [data-navigate="setup"]').press('Enter');
 assert(await page.locator('[data-panel="demand"]').isVisible());
 await page.locator('#setupNav [data-navigate="rules"]').press('Enter');
 await page.locator('#rulesNav [data-config-to="ziele"]').press('Enter');
 assert(await page.locator('#weights').isVisible());
 await page.locator('.main-nav [data-navigate="team"]').press('Enter');
 await page.locator('.main-nav [data-navigate="setup"]').press('Enter');
 assert(await page.locator('#weights').isVisible(),'local configuration choice survives other main areas');
 assert.equal(await page.locator('.main-nav [aria-current="page"]').getAttribute('data-navigate'),'setup');
 assert.match(await page.title(),/^Einrichtung/);
 assert.deepEqual(await page.evaluate(()=>({wire:ProjectJSON.stringify(currentSnapshot()),dirty,changeVersion})),before,'navigation never saves, edits or confirms input');
 observations.viewports=[];
 for(const width of [320,390,768,1440,2560]){
  await page.setViewportSize({width,height:1000});await page.evaluate(()=>{document.activeElement?.blur();window.scrollTo(0,0);return new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));});
  const measured=await nav.evaluateAll(nodes=>({width:innerWidth,documentWidth:document.documentElement.scrollWidth,navWidth:nodes[0].parentElement.clientWidth,navScroll:nodes[0].parentElement.scrollWidth,buttons:nodes.map(e=>{const r=e.getBoundingClientRect();return {label:e.textContent,left:r.left,right:r.right,top:r.top,bottom:r.bottom,height:r.height};})}));
  observations.viewports.push(measured);if(artifacts)await page.screenshot({path:path.join(artifacts,'navigation-'+width+'.png')});
  assert.equal(measured.documentWidth,width);assert.equal(measured.navScroll,measured.navWidth,'no horizontal main-navigation scrolling');
  for(const b of measured.buttons)assert(b.left>=0&&b.right<=width&&b.top>=0&&b.bottom<=1000&&b.height>=44,'visible main touch target '+JSON.stringify(b));
 }
 assert.deepEqual(observations.consoleErrors,[]);
}));
test('UX-02B Plan owns input checking, options and the real calculation without another route',async()=>fixture('combined-plan',async(page,{base,observations,artifacts})=>{
 await page.click('#newProject');await page.fill('#wizardName','Synthetischer gemeinsamer Plan');
 await page.fill('#wizardStart','2026-10-05');await page.fill('#wizardEnd','2026-10-09');await page.fill('#wizardTimezone','Europe/Vienna');
 await page.click('#wizardNext');await page.fill('#wizardPeople','Testperson A\nTestperson B\nTestperson C');await page.click('#wizardNext');
 await page.click('#wizardNext'); // Separate rule review after shifts.
 for(const id of ['wizardRulesConfirmed','wizardApprovalsConfirmed','wizardContextConfirmed'])await page.check('#'+id);
 await page.click('#wizardCreate');await page.waitForFunction(()=>!document.getElementById('createProjectDialog').open&&PlannerApp.getState().snapshot);
 const initial=await page.evaluate(()=>currentSnapshot());
 let checks=0;const writes=[];page.on('request',r=>{if(new URL(r.url()).pathname==='/api/readiness')checks++;if(['POST','PUT'].includes(r.method())&&!r.url().endsWith('/api/readiness'))writes.push({path:new URL(r.url()).pathname,body:r.postDataJSON()});});
 await page.route('**/api/readiness',route=>route.fulfill({status:503,contentType:'application/json',body:'{"detail":"Synthetische Vorprüfung nicht verfügbar"}'}),{times:1});
 await page.locator('.main-nav [data-navigate="plan"]').press('Enter');
 await page.waitForFunction(()=>document.getElementById('automaticReadinessStatus').dataset.state==='error');
 assert(await page.locator('#solve').isVisible(),'starting is available even when preflight failed');
 assert.equal(await page.locator('#planTitle').evaluate(e=>e===document.activeElement),true);
 assert.equal(await page.locator('[data-panel="calculate"]').count(),0,'no second calculation route');
 await page.locator('#openCalculationOptions').press('Enter');
 assert(await page.locator('#limit').isVisible());assert(await page.locator('#partial').isVisible());
 await page.fill('#limit','1');await page.check('#partial');
 await page.locator('.main-nav [data-navigate="team"]').press('Enter');
 await page.locator('.main-nav [data-navigate="plan"]').press('Enter');
 assert.equal(checks,1,'same input version is not redundantly checked');
 assert.equal(await page.locator('#limit').inputValue(),'1');assert(await page.locator('#partial').isChecked());
 await page.locator('#inputReview > summary').press('Enter');
 await page.locator('#retryReadiness').press('Enter');
 await page.waitForFunction(()=>document.getElementById('automaticReadinessStatus').dataset.state==='ready');
 assert.equal(checks,2);assert.equal(writes.length,0,'navigation/preflight never saves or starts a job');
 assert.deepEqual(await page.evaluate(()=>currentSnapshot()),initial);
 await page.locator('#inputReview > summary').press('Enter');
 await page.locator('#calculationOptions > summary').press('Enter');
 await page.locator('#solve').press('Enter');
 await page.waitForFunction(()=>!PlannerApp.getState().solving&&!PlannerApp.getState().jobId&&document.getElementById('result').textContent.includes('Vollständig'),null,{timeout:40000});
 assert.equal(await page.evaluate(()=>document.body.dataset.activePanel),'plan');
 assert.equal(await page.locator('#calendar .shift-badge').count(),5);
 const enqueue=writes.find(r=>r.path==='/api/jobs');assert(enqueue,'real job enqueued');
 observations.writes=writes;observations.checks=checks;
 assert.equal(enqueue.body.time_limit,1);assert.equal(enqueue.body.partial,true);
 const final=await page.evaluate(()=>currentSnapshot());assert.equal(final.id,initial.id);
 const persisted=await(await page.request.get(base+'/api/snapshots/'+initial.id)).json();
 assert.equal(persisted.id,initial.id);assert.deepEqual(persisted.employees,initial.employees);
 assert.equal(await page.locator('#calculationOptions').evaluate(e=>e.open),false,'calculation never forces optional editors open');
 if(artifacts)await page.screenshot({path:path.join(artifacts,'combined-plan.png')});
 assert.equal(observations.consoleErrors.length,1,'only the intentionally injected HTTP 503');assert.match(observations.consoleErrors[0],/503/);
}));
async function focusGeometry(page,selector){
 // Measure the final target, not isVisible() or a pre-scroll focus event.
 await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
 await pause(150);
 return page.locator(selector).evaluate(e=>{
  const r=e.getBoundingClientRect(),header=document.querySelector('.topbar').getBoundingClientRect();
  const x=(r.left+r.right)/2,y=(r.top+r.bottom)/2,hit=document.elementFromPoint(x,y);
  return {focused:document.activeElement===e,left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:innerWidth,height:innerHeight,headerBottom:header.bottom,scrollX,scrollY,uncovered:hit===e||e.contains(hit)};
 });
}
function assertFocusedVisible(r){
 assert(r.focused&&r.left>=0&&r.right<=r.width&&r.top>=Math.max(0,r.headerBottom)&&r.bottom<=r.height&&r.uncovered,'settled focus target must be inside the viewport and not occluded: '+JSON.stringify(r));
}
test('NAV-PARTIAL-01 diagnostic demand action reveals the local editor without changing data',async()=>fixture('demand-reveal',async(page,{observations,artifacts})=>{
 await page.evaluate(async()=>{load(await api('/api/demo'));navigate('rules');selectConfig('dienste');navigate('plan');renderValidation({valid:false,complete:false,diagnostics:[{code:'coverage',message:'Synthetischer offener Bedarf',demand_id:snapshot.demands[0].id}]});document.getElementById('validationDetails').open=true;});
 const before=await page.evaluate(()=>ProjectJSON.stringify(currentSnapshot()));
 await page.getByRole('button',{name:'Bedarf öffnen',exact:true}).click();
 observations.target=await page.evaluate(()=>({area:document.body.dataset.activePanel,config:configPanel,query:pageState('demands',40).query,focus:document.activeElement?.dataset.collectionSearch}));
 assert(await page.locator('#demands').isVisible(),'diagnostic reveals actual demand editor');
 assert.equal(observations.target.config,'bedarf');assert.equal(observations.target.focus,'demands');
 observations.geometry=await focusGeometry(page,'#demands input[type="search"]');
 if(artifacts)await page.screenshot({path:path.join(artifacts,'demand-reveal.png')});
 assertFocusedVisible(observations.geometry);
 assert.equal(await page.evaluate(()=>ProjectJSON.stringify(currentSnapshot())),before);
 assert.deepEqual(observations.consoleErrors,[]);
}));
for(const width of [1440,390])for(const entry of ['diagnostic','reference-id','reference-date','unresolved','calendar']){
 test(`NAV-PARTIAL-01 ${entry} demand correction keeps visible focus at ${width}px`,async()=>fixture(`focus-${entry}-${width}`,async(page,{base,observations,artifacts})=>{
  await page.setViewportSize({width,height:width===390?800:1000});
  const expected=await page.evaluate(async entry=>{
   const data=await api('/api/demo'),d=data.demands[0],date=data.shifts.find(s=>s.id===d.shift_id).segments[0].start.slice(0,10);
   data.metadata.reference_schedule=[{demand_id:d.id,date,employee_id:101,shift_id:201}];
   data.unresolved=[`Bestehender Dienst sp5:employee:101 ${date}: Zuordnung prüfen.`];
   data.assignments=[];load(data);navigate('rules');selectConfig('dienste');
   if(entry==='diagnostic'){
    navigate('plan');renderValidation({valid:false,complete:false,diagnostics:[{code:'coverage',message:'Synthetischer offener Bedarf',demand_id:d.id}]});document.getElementById('validationDetails').open=true;
   }else if(entry==='unresolved')selectConfig('offen');
   else if(entry==='calendar')navigate('plan');
   return {query:['reference-date','unresolved'].includes(entry)?date:d.id};
  },entry);
  const before=await page.evaluate(()=>({wire:ProjectJSON.stringify(currentSnapshot()),dirty,changeVersion}));
  const writes=[];page.on('request',r=>{if(['PUT','POST','DELETE'].includes(r.method())&&!r.url().endsWith('/api/readiness'))writes.push({url:r.url(),method:r.method()});});
  if(entry==='diagnostic')await page.getByRole('button',{name:'Bedarf öffnen',exact:true}).press('Enter');
  else if(entry.startsWith('reference-')){
   await page.locator('#referenceImport details > summary').press('Enter');
   await page.locator('#referenceImport').getByRole('button',{name:entry==='reference-id'?'Zugeordneten Bedarf prüfen':'Bedarfe am Datum prüfen',exact:true}).press('Enter');
  }else if(entry==='unresolved')await page.locator('#unresolved').getByRole('button',{name:'Bedarfe am Datum prüfen',exact:true}).press('Enter');
  else {await page.selectOption('#planView','positions');await page.locator('#calendar .vacancy-badge').first().press('Enter');}
  observations.geometry=await focusGeometry(page,'#demands input[type="search"]');
  if(artifacts)await page.screenshot({path:path.join(artifacts,`focus-${entry}-${width}.png`)});
  assertFocusedVisible(observations.geometry);
  assert.equal(await page.locator('#demands input[type="search"]').inputValue(),expected.query);
  assert.equal(await page.evaluate(()=>configPanel),'bedarf');
  assert.deepEqual(await page.evaluate(()=>({wire:ProjectJSON.stringify(currentSnapshot()),dirty,changeVersion})),before);
  assert.deepEqual(writes,[]);assert.deepEqual(await(await page.request.get(base+'/api/snapshots')).json(),[]);assert.deepEqual(await(await page.request.get(base+'/api/jobs')).json(),[]);
  assert.deepEqual(observations.consoleErrors,[]);
 }));
}
test('NAV-PARTIAL-02 invalid hidden time limit is revealed and focused without enqueue',async()=>fixture('invalid-limit',async(page,{observations})=>{
 await page.evaluate(async()=>{load(await api('/api/demo'));navigate('plan');});
 const before=await page.evaluate(()=>ProjectJSON.stringify(currentSnapshot()));
 const writes=[];page.on('request',r=>{if(r.method()==='PUT'||new URL(r.url()).pathname==='/api/jobs')writes.push(r.url());});
 await page.click('#openCalculationOptions');await page.fill('#limit','0');await page.click('#calculationOptions > summary');await page.click('#solve');
 await page.waitForFunction(()=>!solving&&!projectSwitchBusy()&&document.getElementById('notice').textContent.includes('Zeitlimit'));
 assert(await page.locator('#limit').isVisible(),'invalid limit must not remain hidden');
 await page.waitForFunction(()=>document.activeElement===document.getElementById('limit'));
 assert.equal(await page.locator('#limit').inputValue(),'0');assert.deepEqual(writes,[]);
 assert.equal(await page.evaluate(()=>ProjectJSON.stringify(currentSnapshot())),before);
 observations.focus=await page.evaluate(()=>document.activeElement.id);
}));
test('NAV-PARTIAL-03 invalid hidden profile field survives and receives focus after save unlock',async()=>fixture('invalid-profile',async(page,{observations})=>{
 await page.evaluate(async()=>{load(await api('/api/demo'));navigate('rules');selectConfig('profile');});
 await page.locator('#profiles details').first().locator('summary').click();
 const field=page.locator('[data-profile-field="min_rest_minutes"]').first();await field.fill('-1');await field.press('Tab');
 await page.evaluate(()=>{window.invalidProfileNode=document.querySelector('[data-profile-field="min_rest_minutes"]');});
 const before=await page.evaluate(()=>ProjectJSON.stringify(currentSnapshot()));
 const writes=[];page.on('request',r=>{if(r.method()==='PUT')writes.push(r.url());});
 await page.locator('#rulesNav [data-config-to="dienste"]').click();await page.click('#headerSave');
 await page.waitForFunction(()=>!projectSwitchBusy()&&document.getElementById('notice').textContent.includes('Ungültige'));
 assert(await field.isVisible(),'saving reveals the actual invalid profile field');
 await page.waitForFunction(()=>document.activeElement===window.invalidProfileNode);
 assert.equal(await field.inputValue(),'-1');assert.equal(await page.evaluate(()=>invalidProfileNode.isConnected),true,'no redraw discards the invalid node');
 assert.deepEqual(writes,[]);assert.equal(await page.evaluate(()=>ProjectJSON.stringify(currentSnapshot())),before);
 observations.state=await page.evaluate(()=>({configPanel,dirty,focused:document.activeElement===invalidProfileNode}));
}));
test('UX-B07 import fits a 320px document without clipping its controls',async()=>fixture('import-320',async(page,{observations,artifacts})=>{
 // Match the baseline: Projects contains an actual completed calculation.
 await page.click('#newProject');await page.fill('#wizardName','Synthetisches Team Oktober');
 await page.fill('#wizardStart','2026-10-05');await page.fill('#wizardEnd','2026-10-09');await page.fill('#wizardTimezone','Europe/Vienna');
 await page.click('#wizardNext');await page.fill('#wizardPeople','Testperson A\nTestperson B\nTestperson C');await page.click('#wizardNext');
 await page.click('#wizardNext'); // Separate rule review after shifts.
 for(const id of ['wizardRulesConfirmed','wizardApprovalsConfirmed','wizardContextConfirmed'])await page.check('#'+id);
 await page.click('#wizardCreate');await page.waitForFunction(()=>!document.getElementById('createProjectDialog').open&&PlannerApp.getState().snapshot);
 await require('./navigation.cjs')(page,'calculate');await page.fill('#limit','1');await page.click('#solve');
 await page.waitForFunction(()=>!PlannerApp.getState().solving&&!PlannerApp.getState().jobId&&document.getElementById('result').textContent.includes('Vollständig'),null,{timeout:40000});
 await page.click('#saveDraft');await page.waitForFunction(()=>!PlannerApp.getState().dirty&&!projectSwitchBusy());
 const saved=await page.evaluate(()=>ProjectJSON.stringify(currentSnapshot()));
 await page.click('.main-nav [data-navigate="projects"]');
 await page.waitForSelector('.job-row');
 await page.click('#openImport');await page.selectOption('#sourceType','api');await page.click('#inspect');
 await page.waitForSelector('#teamTree input[type=checkbox]');
 await page.setViewportSize({width:320,height:1000});
 await page.locator('#openImport').focus();await page.keyboard.press('Enter');
 observations.layout=await importLayout(page);
 if(artifacts)await page.screenshot({path:path.join(artifacts,'import-320.png')});
 assert.equal(observations.layout.documentWidth,320,JSON.stringify(observations.layout));
 for(const control of observations.layout.controls)assert(control.left>=0&&control.right<=320,control.id+' must fit without document scrolling');
 assert.equal(await page.locator('#sourceType').evaluate(e=>e===document.activeElement),true,'keyboard import keeps focus on source');
 observations.viewportChecks=[];
 for(const width of [320,390,768,1440]){
  await page.setViewportSize({width,height:1000});
  await page.locator('.job-row').scrollIntoViewIfNeeded();
  const layout=await importLayout(page);
  const row=await page.locator('.job-row').evaluate(e=>{
   const bounds=e.getBoundingClientRect();
   return {left:bounds.left,right:bounds.right,top:bounds.top,bottom:bounds.bottom,
    children:[...e.children].map(child=>{const r=child.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom};}),
    text:e.textContent,scrollY,scrollX};
  });
  observations.viewportChecks.push({layout,row});
  if(artifacts)await page.screenshot({path:path.join(artifacts,'job-row-'+width+'.png')});
  assert.equal(layout.documentWidth,width,'populated import width '+width);
  for(const child of row.children)assert(child.left>=row.left&&child.right<=row.right&&child.top>=row.top&&child.bottom<=row.bottom,'job information contained, not clipped: '+JSON.stringify({width,row}));
  assert.match(row.text,/Synthetisches Team Oktober/);assert.match(row.text,/Beendet · Ergebnis prüfen/);
 }
 assert.equal(await page.evaluate(()=>ProjectJSON.stringify(currentSnapshot())),saved,'navigation and inspect preserve the exact saved project');
 assert.equal(await page.evaluate(()=>dirty),false);
}));
test('UX-B08 local favicon decodes under the unchanged restrictive CSP',async()=>fixture('favicon',async(page,{base,observations})=>{
 // A settled initial load and reload must not emit CSP/resource console errors.
 await page.reload({waitUntil:'networkidle'});
 assert.equal(observations.csp,"default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'");
 assert.deepEqual(observations.consoleErrors,[],'no favicon CSP errors or other console errors');
 const href=await page.locator('link[rel="icon"]').getAttribute('href');
 assert.equal(new URL(href,base).origin,base,'favicon is same-origin, not a data URL');
 const response=await page.request.get(href);assert(response.ok(),'icon served by actual application');
 assert.match(response.headers()['content-type'],/^image\/svg\+xml/);
 observations.resource={href,status:response.status(),contentType:response.headers()['content-type']};
 // Native headless browser chrome is not a tab-icon visual oracle. Instead
 // actually decode the declared icon as an image under the document's CSP.
 observations.decoded=await page.evaluate(async href=>{const image=new Image();image.src=href;await image.decode();return {width:image.naturalWidth,height:image.naturalHeight};},href);
 assert(observations.decoded.width>0&&observations.decoded.height>0);
 assert.deepEqual(observations.consoleErrors,[]);
}));
