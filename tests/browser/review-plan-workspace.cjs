'use strict';
// UX-02A: real Chromium, real synthetic store, unchanged public controls.
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawn}=require('node:child_process');
const {chromium}=require('playwright');
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function bounded(promise,ms,label){
 let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error(label+' timed out')),ms);})]);}finally{clearTimeout(timer);}
}
async function withWorkspace(run){
 const root=path.resolve(__dirname,'../..'),state=fs.mkdtempSync(path.join(os.tmpdir(),'review-workspace-'));
 const server=spawn(process.env.WEB_TEST_PYTHON||'python',['tests/browser/server.py'],{cwd:root,env:{...process.env,TMPDIR:os.tmpdir(),WEB_TEST_STATE:state,WEB_TEST_PORT:'0'},stdio:['ignore','pipe','pipe']});
 let output='',browser,spawnError;const releases=[];
 const exited=new Promise(resolve=>{server.once('exit',resolve);server.once('error',error=>{spawnError=error;resolve();});});
 for(const stream of [server.stdout,server.stderr])stream.on('data',data=>output=(output+data).slice(-16000));
 try{
  const base=await bounded((async()=>{for(;;){
   if(spawnError)throw spawnError;
   if(server.exitCode!==null||server.signalCode!==null)throw Error('Fixture exited: '+output);
   const address=output.match(/Uvicorn running on (http:\/\/127\.0\.0\.1:\d+)/)?.[1];
   if(address){try{if((await fetch(address+'/healthz',{signal:AbortSignal.timeout(1000)})).ok)return address;}catch{}}
   await pause(100);
  }})(),15000,'Fixture startup');
  browser=await chromium.launch({headless:true,args:['--no-sandbox'],timeout:15000,...(process.env.WEB_TEST_CHROMIUM?{executablePath:process.env.WEB_TEST_CHROMIUM}:{})});
  const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});page.setDefaultTimeout(10000);
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',route=>new URL(route.request().url()).origin===base?route.continue():route.abort());
  await page.goto(base);await page.waitForFunction(()=>window.PlannerApp);
  await bounded(run(page,{base,releases}),60000,'Workspace scenario');assert.deepEqual(errors,[]);
 }finally{
  releases.forEach(release=>release());
  try{if(browser)await bounded(browser.close(),5000,'Browser shutdown');}
  finally{
   try{if(server.pid&&server.exitCode===null&&server.signalCode===null){server.kill('SIGTERM');try{await bounded(exited,5000,'Fixture shutdown');}catch{server.kill('SIGKILL');await bounded(exited,5000,'Fixture forced shutdown');}}}
   finally{fs.rmSync(state,{recursive:true,force:true});}
  }
 }
}
async function createAndSolve(page){
 // Same people, period, confirmations and demand as the UX-01 baseline-e task.
 await page.click('#newProject');await page.fill('#wizardName','Synthetisches Team Oktober');
 await page.fill('#wizardStart','2026-10-05');await page.fill('#wizardEnd','2026-10-09');await page.fill('#wizardTimezone','Europe/Vienna');
 await page.click('#wizardNext');await page.fill('#wizardPeople','Testperson A\nTestperson B\nTestperson C');await page.click('#wizardNext');
 await page.click('#wizardNext'); // Separate rule review after shifts.
 for(const id of ['wizardRulesConfirmed','wizardApprovalsConfirmed','wizardContextConfirmed'])await page.check('#'+id);
 await page.click('#wizardCreate');await page.waitForFunction(()=>!document.getElementById('createProjectDialog').open&&PlannerApp.getState().snapshot);
 await page.locator('#people tbody tr:first-child input[type="number"]').fill('32');await page.locator('#people tbody tr:first-child input[type="number"]').press('Tab');
 await require('./navigation.cjs')(page,'demand');
 const demand=page.locator('td[data-demand-day="2026-10-05"] input.demand-value');await demand.fill('2');await demand.press('Tab');
 await require('./navigation.cjs')(page,'calculate');await page.fill('#limit','5');await page.click('#solve');
 await page.waitForFunction(()=>!PlannerApp.getState().solving&&!PlannerApp.getState().jobId&&document.getElementById('result').textContent.includes('Vollständig'),null,{timeout:40000});
 assert.equal(await page.locator('#calendar .shift-badge').count(),6);
 return page.evaluate(()=>currentSnapshot());
}
async function saveDraft(page){await page.click('#saveDraft');await page.waitForFunction(()=>!PlannerApp.getState().dirty&&!projectSwitchBusy());return page.evaluate(()=>currentSnapshot());}
async function capture(page,name){
 const out=process.env.WEB_TEST_SCREENSHOT_DIR;if(!out)return;
 fs.mkdirSync(out,{recursive:true});await page.screenshot({path:path.join(out,name+'.png')});
}
test('UX-02A calendar precedes optional analysis in the first viewport',async()=>withWorkspace(async page=>{
 const solved=await createAndSolve(page);
 const measurements=[];
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:1000});
  await page.evaluate(()=>{document.activeElement?.blur();window.scrollTo(0,0);return new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));});
  await pause(150);
  const measured=await page.evaluate(()=>{
   const rect=e=>{const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right};};
   const visible=e=>{
    const r=rect(e),clip={left:0,right:innerWidth,top:Math.max(0,document.querySelector('.topbar').getBoundingClientRect().bottom),bottom:innerHeight};
    for(let p=e.parentElement;p;p=p.parentElement){
     const s=getComputedStyle(p),q=p.getBoundingClientRect();
     if(/auto|scroll|hidden|clip/.test(s.overflowX)){clip.left=Math.max(clip.left,q.left+p.clientLeft);clip.right=Math.min(clip.right,q.left+p.clientLeft+p.clientWidth);}
     if(/auto|scroll|hidden|clip/.test(s.overflowY)){clip.top=Math.max(clip.top,q.top+p.clientTop);clip.bottom=Math.min(clip.bottom,q.top+p.clientTop+p.clientHeight);}
    }
    const fullyVisible=r.left>=clip.left&&r.right<=clip.right&&r.top>=clip.top&&r.bottom<=clip.bottom;
    const points=[[.1,.1],[.5,.5],[.9,.9]].map(([x,y])=>document.elementFromPoint(r.left+(r.right-r.left)*x,r.top+(r.bottom-r.top)*y));
    return {...r,clip,fullyVisible,uncovered:points.every(hit=>hit===e||e.contains(hit))};
   };
   return {width:innerWidth,height:innerHeight,scrollX,scrollY,documentWidth:document.documentElement.scrollWidth,
    calendar:rect(document.querySelector('#calendar')),row:rect(document.querySelector('#calendar tbody tr')),person:visible(document.querySelector('#calendar tbody tr th')),
    shifts:[...document.querySelectorAll('#calendar .shift-badge')].map(e=>({date:e.closest('td').dataset.date,...visible(e)})),
    localScrolls:[...document.querySelectorAll('#calendar,#calendar *')].filter(e=>e.scrollLeft||e.scrollTop).map(e=>({className:e.className,left:e.scrollLeft,top:e.scrollTop}))};
  });measurements.push(measured);await capture(page,'calendar-'+width);
 }
 console.log('UX-02A layout',JSON.stringify(measurements));
 const [desktop,mobile]=measurements;
 // Solver assignments vary by person. DOM-first is not chronologically first.
 // Require BOTH actual duties on the first planning day, not a partially clipped
 // later-day badge that happened to be assigned to the first person.
 const firstDay=desktop.shifts.filter(s=>s.date===solved.period_start);
 assert.equal(firstDay.length,2,'reference first day has two real duties');
 assert(firstDay.every(s=>s.fullyVisible&&s.uncovered),'first-day desktop duties fully visible and hit-testable without scrolling: '+JSON.stringify(desktop));
 for(const view of measurements){assert.equal(view.scrollX,0);assert.equal(view.scrollY,0);assert.deepEqual(view.localScrolls,[]);assert.equal(view.documentWidth,view.width);}
 assert(mobile.calendar.top>=0&&mobile.person.fullyVisible&&mobile.person.uncovered,'mobile calendar and first person label visible without scrolling; no mobile duty claim: '+JSON.stringify(mobile));
 assert(mobile.row.bottom<=mobile.height-32,'UX-02B adds at least 32px mobile reserve below the first complete person row: '+JSON.stringify(mobile));
 const analysis=page.locator('#planAnalysis');assert.equal(await analysis.evaluate(e=>e.open),false,'long analysis starts closed');
 await analysis.locator(':scope > summary').press('Enter');assert.equal(await analysis.evaluate(e=>e.open),true);
 assert.match(await analysis.innerText(),/Sollerfüllung/);assert.match(await analysis.innerText(),/Freigabedecke/);
 await analysis.getByText('Technische Auswertung',{exact:true}).press('Enter');assert.match(await analysis.locator('pre').innerText(),/solver_status/);
 await analysis.locator(':scope > summary').press('Enter');assert.equal(await analysis.evaluate(e=>e.open),false);
}));
test('UX-02A input checks, plan validation and saving have distinct status',async()=>withWorkspace(async page=>{
 await createAndSolve(page);
 assert.match(await page.locator('.fact:has(#metricBlockers)').innerText(),/Eingabeprüfung/,'input-check status names its subject');
 assert.match(await page.locator('#result').innerText(),/Planvalidierung: Vollständig und geprüft/);
 assert.match(await page.locator('#saveStatus').innerText(),/Ungespeicherte/,'successful validation does not mean saved');
 const saved=await saveDraft(page);
 await page.reload();await page.locator(`.project-card[data-project-id="${saved.id}"]`).click();
 await page.waitForFunction(()=>!projectSwitchBusy()&&snapshot!==null);
 assert.match(await page.locator('#result').innerText(),/Gespeicherter Entwurf.*Planvalidierung: noch nicht geprüft/);
 assert.equal(await page.locator('#planAnalysis').isVisible(),false,'old calculation metrics are not the resumed draft');
 assert.match(await page.locator('#saveStatus').innerText(),/Gespeicherter Stand/);
 await page.click('#validate');await page.waitForFunction(()=>document.getElementById('validationSummary')!==null);
 assert.match(await page.locator('#result').innerText(),/Planvalidierung: Vollständig und geprüft/);
 assert.equal(await page.evaluate(()=>dirty),false,'checking does not make an unchanged saved draft dirty');
 await page.locator('#calendar .shift-badge').first().click();await page.locator('#plan tbody tr:first-child input[type="checkbox"]').check();
 assert.match(await page.locator('#result').innerText(),/Planvalidierung: nicht aktuell/);
 assert.match(await page.locator('#saveStatus').innerText(),/Ungespeicherte/);
 await saveDraft(page);
 assert.match(await page.locator('#result').innerText(),/Planvalidierung: nicht aktuell/,'saving does not validate the changed plan');
 await page.click('#validate');await page.waitForFunction(()=>document.getElementById('validationSummary')!==null);
 assert.match(await page.locator('#result').innerText(),/Planvalidierung: Vollständig und geprüft/);
}));
test('UX-02A resume retains dirty cancellation, errors and pending-load protection',async()=>withWorkspace(async(page,{base,releases})=>{
 await createAndSolve(page);const saved=await saveDraft(page);
 await page.fill('#projectName','Lokaler synthetischer Entwurf');await page.locator('#projectName').press('Tab');
 const local=await page.evaluate(()=>currentSnapshot());
 await page.click('.main-nav [data-navigate="projects"]');
 const card=page.locator(`.project-card[data-project-id="${saved.id}"]`);
 const dismissed=page.waitForEvent('dialog').then(dialog=>dialog.dismiss());await card.click();await dismissed;
 assert.deepEqual(await page.evaluate(()=>currentSnapshot()),local);assert.equal(await page.evaluate(()=>dirty),true);
 const accept=dialog=>dialog.accept();page.on('dialog',accept);
 await page.route('**/api/snapshots/'+saved.id,route=>route.fulfill({status:503,contentType:'application/json',body:'{"detail":"Synthetischer Ladefehler"}'}),{times:1});
 await card.click();await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('Synthetischer Ladefehler')&&!projectSwitchBusy());
 assert.deepEqual(await page.evaluate(()=>currentSnapshot()),local);assert.equal(await page.evaluate(()=>dirty),true);
 let release,notify;const wait=new Promise(r=>release=r),seen=new Promise(r=>notify=r);releases.push(release);
 await page.route('**/api/snapshots/'+saved.id,async route=>{notify();await bounded(wait,10000,'Delayed project');await route.continue();},{times:1});
 await card.click();await bounded(seen,10000,'Project request');
 // Workspace publishes its lock on the next animation frame; request arrival
 // alone is not proof that the card has been repainted.
 await page.waitForFunction(id=>document.querySelector(`.project-card[data-project-id="${id}"]`).disabled,saved.id);
 assert(await card.isDisabled());assert(await page.locator('#headerSave').isDisabled());
 // Deliberate late-programmatic-edit control: exercise the replacement binding,
 // not just disabled controls. No production or external state is touched.
 await page.evaluate(()=>{snapshot.metadata.project_name='Spätere synthetische Änderung';invalidateResult();});
 const later=await page.evaluate(()=>currentSnapshot());release();
 await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('während des Ladens geändert')&&!projectSwitchBusy());
 assert.deepEqual(await page.evaluate(()=>currentSnapshot()),later);assert.equal(await page.evaluate(()=>dirty),true);
 assert.deepEqual(await(await page.request.get(base+'/api/snapshots/'+saved.id)).json(),saved);
 assert.equal(await card.isDisabled(),false);page.off('dialog',accept);
}));
test('UX-02A an empty saved project still opens team setup',async()=>withWorkspace(async(page,{base})=>{
 const response=await page.request.get(base+'/api/demo');assert(response.ok());const s=await response.json();s.assignments=[];
 const persisted=await page.request.put(base+'/api/snapshots',{data:s});assert(persisted.ok());const saved=await persisted.json();
 await page.reload();await page.locator(`.project-card[data-project-id="${saved.id}"]`).click();await page.waitForFunction(()=>snapshot!==null&&!projectSwitchBusy());
 assert.equal(await page.evaluate(()=>document.body.dataset.activePanel),'team');assert.deepEqual(await page.evaluate(()=>currentSnapshot()),saved);assert.equal(await page.evaluate(()=>dirty),false);
}));
test('UX-02A saved draft opens from its project card in one activation',async()=>withWorkspace(async(page,{base})=>{
 await createAndSolve(page);
 await page.locator('#calendar .shift-badge').first().click();await page.locator('#plan tbody tr:first-child input[type="checkbox"]').check();
 const saved=await saveDraft(page);assert(saved.assignments.some(a=>a.fixed));
 await page.reload();await page.waitForSelector(`.project-card[data-project-id="${saved.id}"]`);
 const requests=[];page.on('request',r=>requests.push(new URL(r.url()).pathname));
 const card=page.locator(`.project-card[data-project-id="${saved.id}"]`);await card.focus();await card.press('Enter');
 await page.waitForFunction(id=>PlannerApp.getState().snapshot?.id===id&&!projectSwitchBusy(),saved.id);
 await capture(page,'resume-desktop');
 assert.deepEqual(await page.evaluate(()=>currentSnapshot()),saved,'saved assignments, fixed flags, IDs and revision preserved exactly');
 assert.equal(await page.evaluate(()=>PlannerApp.getState().dirty),false);
 assert.equal(await page.evaluate(()=>document.body.dataset.activePanel),'plan','one card activation must reach the saved plan, not Team');
 assert.equal(await page.locator('#calendar .shift-badge').count(),6);
 assert.equal(await page.locator('#planTitle').evaluate(e=>document.activeElement===e),true,'keyboard activation moves focus into the opened plan');
 assert.equal(requests.some(p=>p.startsWith('/api/jobs/')),false,'never substitute the older job for the saved draft');
 assert.deepEqual(await(await page.request.get(base+'/api/snapshots/'+saved.id)).json(),saved,'opening is read-only');
}));
